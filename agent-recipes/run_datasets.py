#!/usr/bin/env python3
"""Run one parameterised recipe once per row of a CSV data set and check each run.

Usage: GPUI_AGENT_TOKEN=... python3 run_datasets.py RECIPE --data datasets/1701q.csv --cli path/to/gpui-agent
       --addr 127.0.0.1:PORT [--schema bir.schema.json] [--rows 1-10] [--out runs] [--screenshots] [--label NAME]
       [--derive FILE] [--data-addr 127.0.0.1:PORT] [--screenshot-flagged] [--pause-ms N]

A CSV column whose name is a recipe parameter is bound with `--set`. `expect_errors` is the number of validation
errors the run must end with and `expect_error_fields` the `;`-separated fields they must name. A run passes when
the receipt is ok, every value written by a `form.fill` step reads back from a later `form.fields` step, and the
last `form.validate` step reports exactly the expected errors. Writes OUT/<nn>-<case>/receipt.json (and PNGs with
--screenshots), OUT/results.json and OUT/results.md. Exit 1 if any run fails.

--derive FILE (for recipes that press the real window, see ui/1701q-ui.derive.json) is a JSON object: `derive` makes
parameters from the row's columns (`from` + `map` looks a column up, `from` + `money` formats it with that many
decimals and thousands separators, `format` fills {column} names), and `after` names, per `expect_error_fields` value
("" for a row with none), a second recipe run on the same window after the first; that recipe asserts the errors the
window shows, so the run passes when both receipts are ok. `data` ({"recipe", "schema"}) names a data-plane recipe run
at --data-addr between the two: the window recipe starts the return, the data plane fills the form the window shows
(its written boxes and validation errors are the ones checked), and the follow-up presses the window again;
`data_start` and `data_end`, the same shape, run first and last at --data-addr (the taxpayer's email before the return
is started, which copies it; saving and letting go of the form, so the next row can open one). `data_abort` runs
instead of the rest when a recipe of the row failed, so one failed row does not fail the next.
--screenshot-flagged keeps only the screenshots the recipes ask for instead of one per step. --pause-ms waits between runs, outside the timed recipes,
so a screen recording can be followed.

The taxpayer in the data must already exist: on a fresh scratch database run add-tax-profile.json for that TIN
first (profile.save needs a name to create one). Use a fresh database, since a draft left for the same period
by an earlier run keeps its own header values.
"""
import argparse, csv, json, os, platform, re, subprocess, sys, time


def recipe_params(path):
    text = open(path, encoding="utf-8").read()
    if path.endswith(".json"):
        return json.loads(text).get("params", [])
    return sorted(set(re.findall(r"(?<!\$)\$([A-Za-z_][A-Za-z0-9_]*)", text)))


def same(written, read):
    try:
        return abs(float(str(written).replace(",", "")) - float(str(read).replace(",", ""))) < 0.005
    except ValueError:
        return str(written) == str(read)


def derived(spec, row):
    out = {}
    for name, how in spec.items():
        if "map" in how:
            out[name] = how["map"][row[how["from"]]]
        elif "money" in how:
            out[name] = f"{float(row[how['from']]):,.{how['money']}f}"
        else:
            out[name] = how["format"].format(**row)
    return out


def check(receipt, plan, row):
    """Reasons this run fails; empty when it passes."""
    if not receipt.get("ok"):
        return [f"receipt not ok: {receipt.get('error') or receipt.get('error_code')}"]
    why = []
    planned = {s["id"]: s["op"] for s in plan["steps"]}
    results = {s["id"]: s.get("result") or {} for s in receipt["steps"]}
    written, boxes, validate = {}, None, None
    for step in receipt["steps"]:
        op = planned.get(step["id"], {})
        if op.get("name") == "form.fill":
            written.update(op["args"]["fields"])
            boxes = None
        elif op.get("name") == "form.fields":
            boxes = {b["key"]: b.get("value") for b in results[step["id"]].get("boxes", [])}
        elif op.get("name") in ("form.validate", "filing.validate"):
            validate = results[step["id"]]
    if written and boxes is None:
        why.append("no form.fields step after form.fill, so the written values were not read back")
    elif written:
        for key, value in written.items():
            if not same(value, boxes.get(key)):
                why.append(f"{key}: wrote {value!r}, form shows {boxes.get(key)!r}")
    if validate is None and row.get("expect_errors", "") != "":
        why.append("no form.validate step, so expect_errors was not checked")
    elif validate is not None and row.get("expect_errors", "") != "":
        fields = sorted(e["field"] for e in validate.get("field_errors", []))
        want = sorted(f for f in row.get("expect_error_fields", "").split(";") if f)
        if validate.get("errors") != int(row["expect_errors"]) or (want and fields != want):
            why.append(f"validation: expected {row['expect_errors']} error(s) {want}, got {validate.get('errors')} {fields}")
    return why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recipe")
    ap.add_argument("--data", required=True)
    ap.add_argument("--cli", required=True)
    ap.add_argument("--addr", required=True)
    ap.add_argument("--schema")
    ap.add_argument("--rows", default="1-10")
    ap.add_argument("--out", default="runs")
    ap.add_argument("--screenshots", action="store_true")
    ap.add_argument("--label", default=platform.system())
    ap.add_argument("--derive")
    ap.add_argument("--data-addr")
    ap.add_argument("--screenshot-flagged", action="store_true")
    ap.add_argument("--pause-ms", type=int, default=0)
    a = ap.parse_args()
    first, _, last = a.rows.partition("-")
    schema = ["--schema", a.schema] if a.schema else []
    spec = json.load(open(a.derive, encoding="utf-8")) if a.derive else {}
    rows = list(csv.DictReader(open(a.data, encoding="utf-8")))
    out_rows = []
    for n, row in enumerate(rows, 1):
        if not int(first) <= n <= int(last or first):
            continue
        if out_rows and a.pause_ms:
            time.sleep(a.pause_ms / 1000)
        values = {**row, **derived(spec.get("derive", {}), row)}
        run_dir = os.path.join(a.out, f"{n:02d}-{row.get('case', 'run')}")
        os.makedirs(run_dir, exist_ok=True)
        # (recipe, address, schema arguments, checks the row's values): the recipe on the window, then the data-plane
        # fill into the form it opened, then the follow-up on the window.
        base = os.path.dirname(a.derive or "")
        stages = [(a.recipe, a.addr, schema, True)]
        if spec.get("data"):
            data = spec["data"]
            stages[0] = (a.recipe, a.addr, schema, False)
            if spec.get("data_start"):
                begin = spec["data_start"]
                stages.insert(0, (os.path.join(base, begin["recipe"]), a.data_addr, ["--schema", os.path.join(base, begin["schema"])], False))
            stages.append((os.path.join(base, data["recipe"]), a.data_addr, ["--schema", os.path.join(base, data["schema"])], True))
        after = spec.get("after", {}).get(row.get("expect_error_fields", ""))
        if after:
            if not spec.get("data"):
                stages[0] = (a.recipe, a.addr, schema, False)
            stages.append((os.path.join(base, after), a.addr, schema, False))
        if spec.get("data_end"):
            end = spec["data_end"]
            stages.append((os.path.join(base, end["recipe"]), a.data_addr, ["--schema", os.path.join(base, end["schema"])], False))
        why, steps, recipe_ms, wall, shots, prints, stage_ms = [], 0, 0, 0, 0, [], []
        for at, (recipe, addr, with_schema, checked) in enumerate(stages):
            sets = [x for p in recipe_params(recipe) for x in ("--set", f"{p}={values[p]}")]
            name = "receipt.json" if at == 0 else f"receipt-{at + 1}.json"
            plan = subprocess.run([a.cli, "recipe", "plan", recipe] + with_schema + sets, capture_output=True, text=True)
            cmd = [a.cli, "--addr", addr, "recipe", "run", recipe] + with_schema + sets
            cmd += ["--receipt-out", os.path.join(run_dir, name)]
            if a.screenshots and addr == a.addr:
                cmd += ["--screenshot-dir", os.path.join(run_dir, "shots" if at == 0 else f"shots-{at + 1}")]
                if a.screenshot_flagged:
                    cmd += ["--screenshot-flagged"]
            start = time.perf_counter()
            ran = subprocess.run(cmd, capture_output=True, text=True)
            wall += round((time.perf_counter() - start) * 1000)
            try:
                receipt = json.loads(ran.stdout)
                why += check(receipt, json.loads(plan.stdout), row if checked else {})
            except (ValueError, KeyError) as error:
                receipt = {}
                why.append(f"{error}: {(ran.stdout or ran.stderr or plan.stderr).strip()[:300]}")
            failed = next((s for s in receipt.get("steps", []) if not s.get("ok")), None)
            if failed:
                why.append(f"{os.path.basename(recipe)} {failed['id']}: {failed.get('error')}")
            steps += len(receipt.get("steps", []))
            recipe_ms += receipt.get("elapsed_ms") or 0
            stage_ms.append(receipt.get("elapsed_ms") or 0)
            shots += len([s for s in receipt.get("screenshots", []) if s.get("ok")])
            prints.append(receipt.get("fingerprint"))
            if why and at < len(stages) - 1:
                # Let go of the form whatever happened, so one failed row does not fail the rest.
                if spec.get("data_abort"):
                    abort = spec["data_abort"]
                    subprocess.run([a.cli, "--addr", a.data_addr, "recipe", "run", os.path.join(base, abort["recipe"]),
                                    "--schema", os.path.join(base, abort["schema"])], capture_output=True, text=True)
                break
        out_rows.append({"run": n, "case": row.get("case", ""), "ok": not why, "steps": steps, "recipe_ms": recipe_ms,
                         "stage_ms": stage_ms, "wall_ms": wall, "screenshots": shots, "fingerprint": prints[0], "why": why})
    lines = [f"| {a.label} run | data set | pass | steps | recipe ms | per recipe ms | wall ms | screenshots | notes |", "|---|---|---|---|---|---|---|---|---|"]
    for r in out_rows:
        lines.append(f"| {r['run']} | {r['case']} | {'yes' if r['ok'] else 'NO'} | {r['steps']} | {r['recipe_ms']} | {' + '.join(map(str, r['stage_ms']))} | {r['wall_ms']} | {r['screenshots']} | {'; '.join(r['why'])} |")
    print("\n".join(lines))
    json.dump({"label": a.label, "recipe": os.path.basename(a.recipe), "derive": a.derive, "runs": out_rows}, open(os.path.join(a.out, "results.json"), "w"), indent=2)
    open(os.path.join(a.out, "results.md"), "w").write("\n".join(lines) + "\n")
    sys.exit(0 if out_rows and all(r["ok"] for r in out_rows) else 1)


main()
