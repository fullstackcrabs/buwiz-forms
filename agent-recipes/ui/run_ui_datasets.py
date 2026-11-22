#!/usr/bin/env python3
"""Fill 1701Q through the real window, once per row of a CSV data set, starting each return from the saved template.

Usage: GPUI_AGENT_TOKEN=... python3 run_ui_datasets.py --cli path/to/gpui-agent --addr 127.0.0.1:WINDOW_PORT
       [--data ../datasets/1701q.csv] [--rows 1-10] [--out runs-ui] [--setup] [--pause-ms 0] [--label NAME]

The address is the WINDOW's control plane (the one `just nsh-run-agent` serves on GPUI_AGENT_ADDR), not the app's
data plane. The taxpayer of the data must exist (add-tax-profile.json on the data plane) on a fresh database.

--setup, once per database: adds each tax year of the data with 1701Q, then runs ui-setup-1701q-template.wants
(a 2022 Q1 return made from the library sample, the answers every quarter repeats, the 1701Q template).

Each row is three recipes: ui-new-1701q.wants (New return > 1701Q for the row's year), then this script presses
the "Q<period> <year>" option of the Period picker by its text, since NSH's Select gives options no stable id;
ui-fill-1701q-dataset-macos.wants (opens the return, checks the template's answers, types the row);
ui-pill-1701q.wants, or ui-pill-1701q-centavos.wants / ui-pill-1701q-email.wants for a row whose expect_error_fields is
item_36_taxpayer / email
(the floating pill forward, back, its section list, the jump to the part that needs attention, the fix).
A row passes when all three receipts are ok (the pill recipes assert the expected error is shown, then gone).
Writes OUT/<nn>-<case>/*.json and PNGs, OUT/results.json, results.md.
"""
import argparse, csv, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OPT = {"filer_type": {"Single": "1", "Professional": "2", "Estate": "3", "Trust": "4"},
       "atc": {"II012": "1", "II014": "2", "II013": "3", "II015": "4", "II017": "5", "II016": "6"}}
UI_ERRORS = {"item_36_taxpayer": "ui-pill-1701q-centavos.wants", "email": "ui-pill-1701q-email.wants"}


def shown(amount):
    return f"{float(amount):,.2f}"


def shown_tin(tin):
    """A 14 digit TIN as the app shows it: 123-456-788-00000."""
    return "-".join((tin[0:3], tin[3:6], tin[6:9], tin[9:]))


class Agent:
    def __init__(self, cli, addr):
        self.base = [cli, "--addr", addr]
        self.phone = False

    def panel(self):
        """Open the tax profile panel: the title bar's button on a desktop, the account menu's first entry on a phone."""
        if self.phone:
            self.act("click", "nb-avatar")
            self.wait(self.has("nb-menu-profile"), "the account menu")
            self.act("click", "nb-menu-profile")
        else:
            self.act("click", "tb-panel")
        self.wait(self.has("panel-open-forms"), "the tax profile panel")

    def variant(self, name):
        """The recipe for this host: NAME-phone.json where the phone's frame differs (no title bar or side bar), else NAME.wants."""
        phone = name.replace(".wants", "-phone.json")
        return phone if self.phone and os.path.exists(os.path.join(HERE, phone)) else name

    def run(self, *args):
        return subprocess.run(self.base + list(args), capture_output=True, text=True)

    def act(self, *args):
        done = self.run(*args, "--no-read-back")
        if done.returncode:
            raise RuntimeError(f"{' '.join(args)}: {done.stderr.strip().splitlines()[-1] if done.stderr.strip() else 'failed'}")

    def find(self, want):
        def walk(node):
            if isinstance(node, dict):
                if want(node):
                    return node
                node = list(node.values())
            if isinstance(node, list):
                for child in node:
                    hit = walk(child)
                    if hit:
                        return hit
            return None
        return walk(json.loads(self.run("snapshot").stdout or "{}"))

    def wait(self, want, what, seconds=8.0):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            node = self.find(want)
            if node:
                return node
            time.sleep(0.05)
        raise RuntimeError(f"timed out waiting for {what}")

    def has(self, node_id):
        return lambda n: n.get("id") == node_id

    def pick(self, trigger, label):
        """Open an NSH Select and press the option that shows `label` (its id is generated)."""
        self.act("click", trigger)
        option = self.wait(lambda n: n.get("role") == "option" and label in (n.get("value"), n.get("name")), f"option {label!r} of {trigger}")
        self.act("click", option["id"])

    def recipe(self, name, params, shots=None):
        lines = open(os.path.join(HERE, name), encoding="utf-8").read().splitlines()
        used = set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", "\n".join(l for l in lines if not l.startswith("#"))))
        args = ["recipe", "run", os.path.join(HERE, name)]
        for key, value in params.items():
            if key in used:
                args += ["--set", f"{key}={value}"]
        if shots:
            args += ["--screenshot-dir", shots]
        started = time.monotonic()
        done = self.run(*args)
        wall = (time.monotonic() - started) * 1000
        try:
            receipt = json.loads(done.stdout[done.stdout.index("{"):done.stdout.rindex("}") + 1])
        except ValueError:
            receipt = {"ok": False, "error": (done.stderr or done.stdout).strip(), "steps": []}
        if not receipt.get("ok") and not receipt.get("error"):
            bad = next((s for s in receipt.get("steps", []) if not s.get("ok")), None)
            receipt["error"] = f"{bad['id']}: {bad.get('error')}" if bad else (done.stderr.strip() or "not ok")
        receipt["wall_ms"] = round(wall)
        return receipt


def setup(agent, years):
    """Tax years with 1701Q, then the template. The year picker's options have generated ids, hence pick()."""
    agent.panel()
    agent.act("click", "panel-open-forms")
    agent.wait(lambda n: n.get("id") in ("tp-add-year-open", "tp-add-year-select-trigger"), "the Forms tab")
    for year in sorted(years, reverse=True):
        if not agent.find(agent.has(f"tp-years-{year}")):
            if not agent.find(agent.has("tp-add-year-select-trigger")):
                agent.act("click", "tp-add-year-open")
                agent.wait(agent.has("tp-add-year-select-trigger"), "the Add tax year card")
            agent.pick("tp-add-year-select-trigger", str(year))
            agent.wait(lambda n: n.get("id") == "tp-add-year-add" and n.get("name") == f"Add {year}", f"Add {year}")
            agent.act("click", "tp-add-year-add")
            agent.wait(agent.has(f"tp-years-{year}"), f"tax year {year}")
        agent.act("click", f"tp-years-{year}")
        time.sleep(0.5)
        if agent.find(agent.has("tp-forms-choose")):
            agent.act("click", "tp-forms-choose")
            agent.wait(agent.has("tp-form-1701Q-check"), "the form list")
            agent.act("click", "tp-form-1701Q-check")
            agent.act("click", "tp-forms-save")
            time.sleep(0.5)
    if not agent.phone:  # the phone's sheet closed when it opened the page
        agent.act("click", "tb-panel")
    return agent.recipe(agent.variant("ui-setup-1701q-template.wants"), {"year": "2022", "quarter": "1", "citizenship": "FILIPINO"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True)
    ap.add_argument("--addr", required=True)
    ap.add_argument("--data", default=os.path.join(HERE, "..", "datasets", "1701q.csv"))
    ap.add_argument("--rows", default="")
    ap.add_argument("--out", default="runs-ui")
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--pause-ms", type=int, default=0, help="pause between runs (never inside a timed recipe)")
    ap.add_argument("--no-screenshots", action="store_true", help="no PNG after each step (for timing: a screenshot costs more than the step)")
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    agent = Agent(a.cli, a.addr)
    hello = agent.run("hello")
    if hello.returncode:
        sys.exit(f"no agent at {a.addr}: {hello.stderr.strip()}")
    agent.phone = json.loads(hello.stdout)["hello"].get("platform") == "mobile"
    rows = list(csv.DictReader(open(a.data, encoding="utf-8")))
    pick = range(len(rows))
    if a.rows:
        lo, _, hi = a.rows.partition("-")
        pick = range(int(lo) - 1, int(hi or lo))
    os.makedirs(a.out, exist_ok=True)
    if a.setup:
        done = setup(agent, {r["year"] for r in rows})
        json.dump(done, open(os.path.join(a.out, "setup.json"), "w"), indent=1)
        if not done.get("ok"):
            sys.exit(f"setup failed: {done.get('error')}")
    results = []
    for i in pick:
        row = rows[i]
        out = os.path.abspath(os.path.join(a.out, f"{i + 1:02d}-{row['case']}"))
        os.makedirs(out, exist_ok=True)
        params = dict(row)
        for column in ("filer_type", "atc"):
            params[f"{column}_opt"] = OPT[column][row[column]]
        params["sales_shown"] = shown(row["sales"])
        params["withheld_shown"] = shown(row["withheld_2307"])
        params["email_fixed"] = row["email"] or "fixed@example.com"
        fill = "ui-fill-1701q-dataset-osd.wants" if row["deduction"] == "O" else "ui-fill-1701q-dataset-macos.wants"
        params["sales_fixed"] = str(int(float(row["sales"])))
        fields = [f for f in row.get("expect_error_fields", "").split(";") if f]
        pill = next((UI_ERRORS[f] for f in fields if f in UI_ERRORS), "ui-pill-1701q.wants")
        why, parts, started = [], {}, time.monotonic()
        try:
            if agent.find(agent.has("new-return-cancel")):  # a failed run left the dialog up
                agent.act("click", "new-return-cancel")
            if not agent.phone and agent.find(agent.has("panel-open-forms")):
                agent.act("click", "tb-panel")
            fill, pill = agent.variant(fill), agent.variant(pill)
            for name in (agent.variant("ui-new-1701q.wants"), fill, pill):
                if name == fill:
                    # The dialog starts a return for the taxpayer the app has selected: it must be the data set's.
                    if not agent.find(lambda n: shown_tin(row["tin"]) in (n.get("value") or "", n.get("name") or "")):
                        raise RuntimeError(f"the Start a return dialog is not for {shown_tin(row['tin'])}: select that taxpayer first")
                    agent.pick("new-return-period-trigger", f"Q{row['period']} {row['year']}")
                receipt = agent.recipe(name, params, None if a.no_screenshots else os.path.join(out, str(len(parts) + 1) + '-' + name[3:].split('.')[0]))
                json.dump(receipt, open(os.path.join(out, os.path.splitext(name)[0] + ".json"), "w"), indent=1)
                parts[name] = receipt
                if not receipt.get("ok"):
                    why.append(f"{name}: {receipt.get('error')}")
                    break
        except RuntimeError as error:
            why.append(str(error))
        wall = (time.monotonic() - started) * 1000
        if not why:
            why += [f"expects a validation error on {f}; the window raises none for it" for f in fields if f not in UI_ERRORS]
        results.append({
            "run": i + 1, "case": row["case"], "pass": not why, "why": why, "pill": pill,
            "steps": sum(len(r.get("steps", [])) for r in parts.values()),
            "recipe_ms": sum(r.get("elapsed_ms") or 0 for r in parts.values()),
            "parts_ms": {n: r.get("elapsed_ms") for n, r in parts.items()}, "wall_ms": round(wall),
            "screenshots": sorted(os.path.join(os.path.basename(d), f) for d, _, fs in os.walk(out) for f in fs if f.endswith(".png")),
        })
        print(f"{i + 1:2d} {row['case']:20s} {'PASS' if not why else 'FAIL'} {results[-1]['recipe_ms']} ms  {'; '.join(why)}", flush=True)
        time.sleep(a.pause_ms / 1000)
    json.dump(results, open(os.path.join(a.out, "results.json"), "w"), indent=1)
    with open(os.path.join(a.out, "results.md"), "w", encoding="utf-8") as md:
        md.write(f"# 1701Q through the window{': ' + a.label if a.label else ''}\n\n")
        md.write(f"{sum(r['pass'] for r in results)} of {len(results)} runs passed.\n\n")
        md.write("| Run | Case | Result | Steps | Recipe ms (new + fill + pill) | Wall ms | Screenshots | Failure |\n|---:|---|---|---:|---:|---:|---:|---|\n")
        for r in results:
            ms = " + ".join(str(v) for v in r["parts_ms"].values())
            md.write(f"| {r['run']} | {r['case']} | {'pass' if r['pass'] else 'FAIL'} | {r['steps']} | {r['recipe_ms']} ({ms}) | {r['wall_ms']} | {len(r['screenshots'])} | {'; '.join(r['why'])} |\n")
    sys.exit(0 if all(r["pass"] for r in results) else 1)


if __name__ == "__main__":
    main()
