#!/usr/bin/env python3
"""Time each recipe against the same steps sent one CLI call at a time.

Usage: GPUI_AGENT_TOKEN=... python3 bench.py --cli path/to/gpui-agent --addr 127.0.0.1:17431 [--runs 3]
Prints a Markdown table and writes bench-result.json. The host must be running.
"""
import argparse, json, os, platform, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
FLOWS = [
    ("add-tax-profile", {"tin": "12345678800000", "name": "TEST", "rdo": "040", "address": "Quezon City", "zip": "1100"}),
    ("navigate-app", {}),
    ("fill-1701q", {"tin": "12345678800000", "year": "2026", "period": "1", "sheets": "3"}),
    ("fill-1701q-complex", {
        "tin": "12345678800000", "year": "2026", "period": "1", "sheets": "2",
        "filer_type": "Professional", "atc": "II014", "birth_month": "01", "birth_day": "15",
        "birth_year": "1990", "citizenship": "Filipino", "deduction": "I",
        "sales": "250000.00", "cost_of_sales": "40000.00", "deductions": "35000.00",
        "prior_income": "0.00", "non_op_desc": "Interest", "non_op_income": "1500.00",
        "prior_credits": "0.00", "prior_payments": "0.00", "withheld_2307": "5000.00",
    }),
]


def run(cmd):
    start = time.perf_counter()
    out = subprocess.run(cmd, capture_output=True, text=True)
    return (time.perf_counter() - start) * 1000, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True)
    ap.add_argument("--addr", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--label", default=platform.system())
    a = ap.parse_args()
    base = [a.cli, "--addr", a.addr]
    schema = os.path.join(HERE, "bir.schema.json")
    rows, failed = [], False
    for name, sets in FLOWS:
        path = os.path.join(HERE, name + ".json")
        set_args = [x for k, v in sets.items() for x in ("--set", f"{k}={v}")]
        _, plan = run([a.cli, "recipe", "plan", path, "--schema", schema] + set_args)
        steps = json.loads(plan.stdout)["steps"]
        per_op, recipe, ok = [], [], True
        for _ in range(a.runs):
            total = 0.0
            for step in steps:
                op = step["op"]
                cmd = base + ["invoke", op["name"]]
                for k, v in (op.get("args") or {}).items():
                    cmd += ["--arg", f"{k}={json.dumps(v)}"]
                ms, out = run(cmd)
                total += ms
                if out.returncode != 0:
                    ok = False
                    print(f"per-op {name}/{step['id']} failed: {out.stdout} {out.stderr}", file=sys.stderr)
            per_op.append(total)
            ms, out = run(base + ["recipe", "run", path, "--schema", schema] + set_args)
            recipe.append(ms)
            receipt = json.loads(out.stdout or "{}")
            if not (out.returncode == 0 and receipt.get("ok") and receipt.get("session_reused")):
                ok = False
                print(f"recipe {name} failed: {out.stdout} {out.stderr}", file=sys.stderr)
        failed |= not ok
        rows.append({"flow": name, "steps": len(steps), "ok": ok,
                     "per_op_ms": round(min(per_op)), "recipe_ms": round(min(recipe)),
                     "speedup": round(min(per_op) / min(recipe), 2)})
    print(f"| {a.label} flow | steps | pass | per-op ms | recipe ms | speed-up |\n|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['flow']} | {r['steps']} | {'yes' if r['ok'] else 'NO'} | {r['per_op_ms']} | {r['recipe_ms']} | {r['speedup']}x |")
    json.dump({"label": a.label, "rows": rows}, open(os.path.join(HERE, "bench-result.json"), "w"), indent=2)
    sys.exit(1 if failed else 0)


main()
