#!/usr/bin/env python3
"""Run one recipe either as one `recipe run` or as the same planned steps sent one CLI call at a time, and time it.

Usage: GPUI_AGENT_TOKEN=... python3 bench_ui.py --cli path/to/gpui-agent --addr 127.0.0.1:PORT --mode recipe|per-op
       RECIPE [--schema FILE] [--set k=v]... [--screenshot-dir DIR]
Prints one JSON object: {flow, mode, ok, steps, ms, step_ms, error}. A UI recipe changes the app, so compare the two
modes from the same starting state (a fresh launch for each), not one after the other.
"""
import argparse, json, subprocess, sys, time


def run(cmd):
    start = time.perf_counter()
    out = subprocess.run(cmd, capture_output=True, text=True)
    return (time.perf_counter() - start) * 1000, out


def cli_args(op):
    """The CLI call that sends this planned op."""
    kind, target = op["op"], op.get("target")
    if kind == "invoke":
        args = ["invoke", op["name"]]
        for k, v in (op.get("args") or {}).items():
            args += ["--arg", f"{k}={json.dumps(v)}"]
        return args
    if kind == "click":
        return ["click", target]
    if kind == "type":
        return ["type", target, op["text"]]
    if kind == "set_value":
        return ["set-value", target, op["value"]]
    if kind in ("assert", "wait_until"):
        args = ["assert"] if kind == "assert" else ["wait-until", "--timeout-ms", str(op["timeout_ms"])]
        args += ["--id", target]
        for field in ("name", "value", "role"):
            if field in op:
                args += [f"--{field}", op[field]]
        if op.get("exists") is False:
            args.append("--absent")
        if "checked" in op:
            args += ["--checked", json.dumps(op["checked"])]
        return args
    if kind == "wait":
        return ["wait"]
    raise SystemExit(f"bench_ui.py has no CLI mapping for op `{kind}`")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recipe")
    ap.add_argument("--cli", required=True)
    ap.add_argument("--addr", required=True)
    ap.add_argument("--mode", choices=["recipe", "per-op"], required=True)
    ap.add_argument("--schema")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--screenshot-dir")
    a = ap.parse_args()
    extra = (["--schema", a.schema] if a.schema else []) + [x for s in a.set for x in ("--set", s)]
    _, plan = run([a.cli, "recipe", "plan", a.recipe] + extra)
    if plan.returncode != 0:
        raise SystemExit(plan.stdout + plan.stderr)
    plan = json.loads(plan.stdout)
    base = [a.cli, "--addr", a.addr]
    row = {"flow": plan["name"], "mode": a.mode, "steps": len(plan["steps"]), "ok": True, "error": None}
    if a.mode == "recipe":
        shots = ["--screenshot-dir", a.screenshot_dir, "--screenshot-flagged"] if a.screenshot_dir else []
        ms, out = run(base + ["recipe", "run", a.recipe] + extra + shots)
        # A run that never reached the host (no token, nothing listening) prints no receipt, only the error.
        try:
            receipt = json.loads(out.stdout)
        except json.JSONDecodeError:
            receipt = {}
        row["step_ms"] = {s["id"]: s.get("elapsed_ms") for s in receipt.get("steps", [])}
        row["host_ms"] = receipt.get("elapsed_ms")
        if out.returncode != 0:
            row["ok"], row["error"] = False, out.stderr.strip()
    else:
        ms, row["step_ms"] = 0.0, {}
        for step in plan["steps"]:
            # `recipe run` sends an action without a read-back, so the single calls skip theirs too.
            one, out = run(base + ["--no-read-back"] + cli_args(step["op"]))
            ms += one
            row["step_ms"][step["id"]] = round(one)
            if out.returncode != 0:
                row["ok"], row["error"] = False, f"{step['id']}: {out.stderr.strip()}"
                break
    row["ms"] = round(ms)
    print(json.dumps(row, ensure_ascii=False))
    sys.exit(0 if row["ok"] else 1)


main()
