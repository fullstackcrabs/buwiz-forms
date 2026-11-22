#!/usr/bin/env python3
"""Run the UI recipes of ui/ once per row of the 1701Q data set against the NSH app's window plane, and check each run.

Usage: GPUI_AGENT_TOKEN=... python3 run_ui_datasets.py --cli path/to/gpui-agent --addr 127.0.0.1:PORT
       [--data datasets/1701q.csv] [--rows 1-10] [--out DIR] [--pause-ms 0] [--label NAME]

Per row: ui/ui-fill-1701q-dataset-windows.wants (a return started from the saved template, filled from the row, the floating
pill pressed forward and back, its section list used, the boxes read back), ui/ui-1701q-itemized.wants when the row
itemizes, then ui/ui-1701q-pill-clear.wants when the row must end valid, or ui/ui-1701q-pill-error.wants when
`expect_errors` is 1 (the pill counts the error, lands on it, the box is corrected, the count is gone). A run passes
when every receipt is ok. `--pause-ms` waits between runs only, never inside a timed recipe. Writes OUT/<nn>-<case>/<recipe>.json and shots/, OUT/results.json and OUT/results.md.

The app must show the taxpayer with the rows' tax years, 1701Q among each year's forms and a saved 1701Q template
(ui-signup-taxpayer.wants, then ui-add-tax-year-windows.wants and ui-set-eopt-tier-windows.wants for each year, ui-save-1701q-template.wants;
without a year's EOPT tier Item 64 stays on the pill and a valid row never clears), and no draft for the rows' periods.
"""
import argparse, csv, json, os, platform, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
AMOUNTS = ["sales", "prior_income", "non_op_income", "prior_credits", "prior_payments", "withheld_2307"]
FILER = {"Single": "1", "Professional": "2"}
ATC = {"II012": "1", "II014": "2"}
DEDUCTION = {"I": "1", "O": "2"}
# expect_error_fields -> what ui-1701q-pill-error.wants needs: the row the pill lands on and its message, the box at
# fault and what makes it valid. (The app shows item 36's message on the row of Item 41, which is computed from it.)
ERRORS = {
    "item_36_taxpayer": lambda row: {
        "error_item": "Item 41 · Net Income/(Loss) This Quarter (If Itemized: Item 38 Less Item 39; If OSD: Item 38 Less Item 40)",
        "error_msg": "fp-msg-4:5", "error_text": "Item 36A takes whole pesos only.",
        "fix_section": "4", "fix_target": "fp-frm1701q:txt36A", "fix_value": row["sales"].split(".")[0] + ".00"},
    "email": lambda row: {
        "error_item": "Item 12 · Email Address", "error_msg": "fp-msg-1:8",
        "error_text": "Enter the email address BIR sends the filing confirmation to.",
        "fix_section": "1", "fix_target": "fp-txtEmail", "fix_value": "test5@example.com"},
}


def other(n):
    return "2" if n == "1" else "1"


def shown(amount):
    whole, _, cents = amount.partition(".")
    return f"{int(whole):,}.{cents or '00'}"


def bindings(row):
    b = {k: row[k] for k in ["email", "year", "period", "sheets", "citizenship", "non_op_desc"] + AMOUNTS}
    b["filer_n"], b["atc_n"], b["ded_n"] = FILER[row["filer_type"]], ATC[row["atc"]], DEDUCTION[row["deduction"]]
    b["filer_other"], b["atc_other"], b["ded_other"] = other(b["filer_n"]), other(b["atc_n"]), other(b["ded_n"])
    b["birth"] = f"{int(row['birth_month']):02d}{int(row['birth_day']):02d}{row['birth_year']}"
    b["part1_todos"] = "2" if row["email"] else "3"
    for k in AMOUNTS:
        b[k + "_shown"] = shown(row[k])
    return b


def run(a, recipe, sets, run_dir):
    name = os.path.splitext(recipe)[0]
    cmd = [a.cli, "--addr", a.addr, "recipe", "run", os.path.join(HERE, "ui", recipe)]
    cmd += [x for k, v in sets.items() for x in ("--set", f"{k}={v}")]
    cmd += ["--receipt-out", os.path.join(run_dir, name + ".json"), "--screenshot-dir", os.path.join(run_dir, "shots", name), "--screenshot-flagged"]
    start = time.perf_counter()
    ran = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    wall = round((time.perf_counter() - start) * 1000)
    try:
        receipt = json.loads(ran.stdout)
    except ValueError:
        receipt = {"ok": False, "steps": [], "error": (ran.stdout or ran.stderr).strip()[:300]}
    why = ""
    if not receipt.get("ok"):
        failed = next((s for s in receipt.get("steps", []) if not s.get("ok")), {})
        why = f"{recipe} {failed.get('id', '')}: {failed.get('error') or receipt.get('error') or ran.stderr.strip()[:300]}"
    shots = len([s for s in receipt.get("screenshots", []) if s.get("ok")])
    return {"recipe": recipe, "ok": bool(receipt.get("ok")), "steps": len(receipt.get("steps", [])),
            "recipe_ms": receipt.get("elapsed_ms"), "wall_ms": wall, "screenshots": shots, "why": why}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True)
    ap.add_argument("--addr", required=True)
    ap.add_argument("--data", default=os.path.join(HERE, "datasets", "1701q.csv"))
    ap.add_argument("--rows", default="1-10")
    ap.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "runs-ui"),
                    help="receipts and real-window screenshots; outside the worktree by default")
    ap.add_argument("--pause-ms", type=int, default=0)
    ap.add_argument("--label", default=platform.system())
    a = ap.parse_args()
    first, _, last = a.rows.partition("-")
    out_rows = []
    for n, row in enumerate(csv.DictReader(open(a.data, encoding="utf-8")), 1):
        if not int(first) <= n <= int(last or first):
            continue
        if out_rows and a.pause_ms:
            time.sleep(a.pause_ms / 1000)
        run_dir = os.path.join(a.out, f"{n:02d}-{row['case']}")
        os.makedirs(run_dir, exist_ok=True)
        parts = [run(a, "ui-fill-1701q-dataset-windows.wants", bindings(row), run_dir)]
        errors = [f for f in row.get("expect_error_fields", "").split(";") if f]
        if parts[0]["ok"] and row["deduction"] == "I":
            sets = {k: v for n in ("cost_of_sales", "deductions") for k, v in ((n, row[n]), (n + "_shown", shown(row[n])))}
            parts.append(run(a, "ui-1701q-itemized.wants", sets, run_dir))
        if not parts[-1]["ok"]:
            pass
        elif not errors:
            parts.append(run(a, "ui-1701q-pill-clear.wants", {}, run_dir))
        else:
            sets = ERRORS[errors[0]](row)
            parts.append(run(a, "ui-1701q-pill-error.wants", sets, run_dir))
        out_rows.append({"run": n, "case": row["case"], "ok": all(p["ok"] for p in parts), "expect_errors": row.get("expect_errors", ""),
                         "steps": sum(p["steps"] for p in parts), "fill_ms": parts[0]["recipe_ms"],
                         "recipe_ms": sum(p["recipe_ms"] or 0 for p in parts),
                         "wall_ms": sum(p["wall_ms"] for p in parts), "screenshots": sum(p["screenshots"] for p in parts),
                         "why": [p["why"] for p in parts if p["why"]], "parts": parts})
        print(json.dumps({k: v for k, v in out_rows[-1].items() if k != "parts"}), flush=True)
    lines = [f"| {a.label} run | data set | pass | expected errors | recipes | steps | fill recipe ms | all recipes ms | wall ms | screenshots | notes |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in out_rows:
        lines.append(f"| {r['run']} | {r['case']} | {'yes' if r['ok'] else 'NO'} | {r['expect_errors']} | {len(r['parts'])} | {r['steps']} | {r['fill_ms']} | {r['recipe_ms']} | {r['wall_ms']} | {r['screenshots']} | {'; '.join(r['why'])} |")
    print("\n".join(lines))
    json.dump({"label": a.label, "runs": out_rows}, open(os.path.join(a.out, "results.json"), "w"), indent=2)
    open(os.path.join(a.out, "results.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    sys.exit(0 if out_rows and all(r["ok"] for r in out_rows) else 1)


main()
