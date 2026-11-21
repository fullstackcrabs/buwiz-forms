#!/usr/bin/env python3
"""Run one parameterised recipe once per row of a CSV data set and check each run.

Usage: GPUI_AGENT_TOKEN=... python3 run_datasets.py RECIPE --data datasets/1701q.csv --cli path/to/gpui-agent
       --addr 127.0.0.1:PORT [--schema bir.schema.json] [--rows 1-10] [--out runs] [--screenshots] [--label NAME]

A CSV column whose name is a recipe parameter is bound with `--set`. `expect_errors` is the number of validation
errors the run must end with and `expect_error_fields` the `;`-separated fields they must name. A run passes when
the receipt is ok, every value written by a `form.fill` step reads back from a later `form.fields` step, and the
last `form.validate` step reports exactly the expected errors. Writes OUT/<nn>-<case>/receipt.json (and PNGs with
--screenshots), OUT/results.json and OUT/results.md. Exit 1 if any run fails.

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
    a = ap.parse_args()
    first, _, last = a.rows.partition("-")
    params = recipe_params(a.recipe)
    schema = ["--schema", a.schema] if a.schema else []
    rows = list(csv.DictReader(open(a.data, encoding="utf-8")))
    out_rows = []
    for n, row in enumerate(rows, 1):
        if not int(first) <= n <= int(last or first):
            continue
        sets = [x for p in params for x in ("--set", f"{p}={row[p]}")]
        run_dir = os.path.join(a.out, f"{n:02d}-{row.get('case', 'run')}")
        os.makedirs(run_dir, exist_ok=True)
        plan = subprocess.run([a.cli, "recipe", "plan", a.recipe] + schema + sets, capture_output=True, text=True)
        cmd = [a.cli, "--addr", a.addr, "recipe", "run", a.recipe] + schema + sets
        cmd += ["--receipt-out", os.path.join(run_dir, "receipt.json")]
        if a.screenshots:
            cmd += ["--screenshot-dir", os.path.join(run_dir, "shots")]
        start = time.perf_counter()
        ran = subprocess.run(cmd, capture_output=True, text=True)
        wall = round((time.perf_counter() - start) * 1000)
        try:
            receipt = json.loads(ran.stdout)
            why = check(receipt, json.loads(plan.stdout), row)
        except (ValueError, KeyError) as error:
            receipt, why = {}, [f"{error}: {(ran.stdout or ran.stderr or plan.stderr).strip()[:300]}"]
        shots = [s for s in receipt.get("screenshots", []) if s.get("ok")]
        out_rows.append({"run": n, "case": row.get("case", ""), "ok": not why, "steps": len(receipt.get("steps", [])),
                         "recipe_ms": receipt.get("elapsed_ms"), "wall_ms": wall, "screenshots": len(shots),
                         "fingerprint": receipt.get("fingerprint"), "why": why})
    lines = [f"| {a.label} run | data set | pass | steps | recipe ms | wall ms | screenshots | notes |", "|---|---|---|---|---|---|---|---|"]
    for r in out_rows:
        lines.append(f"| {r['run']} | {r['case']} | {'yes' if r['ok'] else 'NO'} | {r['steps']} | {r['recipe_ms']} | {r['wall_ms']} | {r['screenshots']} | {'; '.join(r['why'])} |")
    print("\n".join(lines))
    json.dump({"label": a.label, "recipe": os.path.basename(a.recipe), "runs": out_rows}, open(os.path.join(a.out, "results.json"), "w"), indent=2)
    open(os.path.join(a.out, "results.md"), "w").write("\n".join(lines) + "\n")
    sys.exit(0 if out_rows and all(r["ok"] for r in out_rows) else 1)


main()
