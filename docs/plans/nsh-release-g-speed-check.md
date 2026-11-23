# Track G / 9a: NSH speed check

Branch: `feat/nsh-release-g`, following release-glue commit `55e23d11`.
References: [#198](https://github.com/hexuria/buwiz-forms/pull/198),
[#203](https://github.com/hexuria/buwiz-forms/pull/203).

## Method and limits

Measured on the Ubuntu 22.04 development box, debug Rust, pinned NSH 0.6.1
(`70d8ff26b9e9dccb17a908de97cd4a3f3e381276`). All execution used
`BUWIZ_NO_KEYCHAIN=1 EBIR_TEST_ENV=1 BIR_AUTH_BYPASS=1 BIR_SFTP_DRY_RUN=1`,
without `BIR_SFTP_LIVE`, using fresh scratch databases.

The actual Linux app cannot build here: GTK >=4.14 and Graphene development
libraries are absent; WebKitGTK 6.0 is also unavailable. This is a system-library
limitation, not a missing shell environment. No NSH source, CI configuration or
system package was changed to get around it.

Fallback: the actual pinned NSH headless engine, actual TSX/store/session code,
and actual `bir-app-api`/plain-SQLite `bir-core`. An **external, test-only native
adapter** replaces the GTK-dependent desktop/print/agent glue. Its Door delegates
to the real host module, boots a fresh database per engine, refuses the submission
worker, and implements the same database-token query. It does **not** exercise
the shipped Door boot/guards, the native window, print, desktop integrations or
the agent-enabled network poll. The adapter and raw logs are at
`~/Downloads/nsh-speed-check/` on this development box, not app dependencies.

Decision criteria: any unchanged-payload reactive re-evaluation is a regression;
a synchronous poll blocking >50ms is a regression; sustained form input/scroll
work with p95 >16ms warrants a port. Maxima are reported too, not hidden by
averages. These are debug/headless measurements, not a claim of native 60fps.

## 1. Device-filing poll

**Old fixes:** #198 moves account restoration and device-filing HTTP work off the
UI thread, adds cached account lookup for the synchronous poll setup, and uses an
async host function. #203 retains this and reduces device polling to 60 seconds.

**NSH equivalent:** `shell/app.ts::pullDeviceFilings`, `lib/poll.ts`,
`bir/functions.ts::pull_device_filings`, and
`crates/bir-app-api/src/bir_module.rs::pull_device_filings`.

The wrapper is still synchronous, and the Door dispatch runs on the NSH engine
thread. However, `nsh/Cargo.toml` has `default = []`: without feature `agent`, the
reachable Rust implementation immediately returns null. Timing 1,000 real host
calls (after boot) gave **9ms total, p95 0ms, max 1ms**, using millisecond clock
resolution. Every result was null. This disproves the initially suspected
8-second HTTP stall **for the default build tested**. No async/interval port.
There is no before/after delta because this path was not changed.

**Unverified configuration:** with feature `agent` and a saved authenticated
account, the other implementation uses blocking reqwest with an 8-second timeout.
It remains a risk, not a measured/cleared path. The scheduler already awaits each
task before scheduling its next run. A separately authenticated, loopback-only
agent-feature benchmark is needed before deciding to port that implementation.

## 2. Unchanged idle event polls

**Old fix:** #198 adds `data_change_token` (connection `total_changes` plus SQLite
`PRAGMA data_version`) and skips idle invalidation; it also avoids idle worker
writes that would otherwise churn the token. #203 carries the no-change behavior
forward alongside its form work.

**NSH equivalent:** `shell/app.ts::pollEvents` called `store.forgetWhere(POLL_KEYS)`
unconditionally. A real NSH `effect` subscribed to `store.returns("filed")`, with
the unchanged real empty host result, counted **20 extra evaluations for 20
polls**, taking 2ms. NSH components mount once; these are reactive expression
evaluations, not React-style whole-component renders.

**Ported:** `Database::total_changes`, `Door.dataChangeToken`, and the handwritten
`bir/door.ts` wrapper. The regular event poll now keeps the cache when a known
token is unchanged. First/changed/unknown/error tokens still refresh. Event-toast
deduplication still runs; the wider queued watch retains unconditional refresh.
No token is synthesized in JS and no payload is serialized for comparison.

**After:** after one priming poll, **0 extra evaluations for 20 unchanged polls,
1ms measured**. A real database write causes one refresh. Tests also cover a
changed token, consecutive null tokens, and a thrown token read. Rust coverage
checks that reads change neither counter, own-connection writes move
`total_changes`, and another connection's writes move `data_version`.

The baseline was recorded before the source edit in `idle-baseline.log`.
`shell/idlePoll.test.ts`'s zero-evaluation assertion would fail on the old
unconditional invalidation. `shell/queuedWatch.test.ts` remains passing.

## 3. Annual forms: scrolling and typing

**Old fixes:** #203 uses lazy lists for wide forms, retained rows with cheap
`set_props` updates, live props, and no redundant update pass. #198's poll work
also removes unrelated stalls while editing.

**NSH equivalent:** `screens/form/FormPage.tsx::PartRows` already uses
`List viewport="parent"`, stable row identities, per-part proximity mounting,
and `screens/form/session.ts` has per-field signals and debounced host work.

The schema's annual forms include 1701 (946 extracted fields), 1702MX (663), and
1702RT (269). Tested **1701**, the largest annual schema, and **1702RT**, the
existing heavy-form regression fixture. Actual sessions exposed 379 and 364
controls respectively after normalization/derived controls.

`screens/form/speedAnnual.test.tsx` opens each at 1440x900, expands all parts,
performs 30 800pt scroll gestures (15 down/15 up), then 100 real accepted
one-character edits. Each edit is preceded by clearing the field, and its value
is asserted afterward: the benchmark cannot silently time ignored/max-length
keystrokes. A manual app clock avoids real-time animation waits. `--trace` gives
native commit/engine-turn timings; test-API gesture wall time is **not** frame
time.

| Measurement | 1701 | 1702RT |
| --- | ---: | ---: |
| First open (includes host/schema work) | 2670ms | 820ms |
| Accepted keystroke API p50 / p95 / max, 100 samples | 3 / 4 / 35ms | 5 / 6 / 11ms |
| Scroll gesture API p50 / p95 / max, 30 gestures | 98 / 147 / 151ms | 95 / 145 / 204ms |
| Scroll native commit p50 / p95 / max | .808 / 6.992 / 22.669ms | 1.541 / 8.248 / 20.287ms |
| Scroll engine turn p50 / p95 / max | 1.514 / 8.729 / 28.824ms | 1.973 / 9.466 / 20.566ms |

Scroll commit samples: 419 / 431; commits >16ms: 3 / 5. Sparse tracing suppresses
some very short turns, so these distributions are trace samples, not every
display frame. Headless disables NSH's platform content culling, and has no GPU
or native text widgets. The first heavier 1702RT fixture also showed deferred
validation/save turns up to 53.211ms; immediate typing is not the whole workload.

**No form code ported:** the old lazy-list/per-field equivalents are already
present, and measured p95 scroll work and accepted input stay below 16ms. The
isolated maxima, initial-open/debounced work, and native scrolling remain follow-up
profiling targets; this is not an assertion that every frame meets budget. There
are no after numbers for a form optimization that was not made.

## Reproduction and checks

On a supported machine (production native glue):

```sh
just nsh-test shell/idlePoll.test.ts --trace
just nsh-test shell/queuedWatch.test.ts
just nsh-test screens/form/speedAnnual.test.tsx --trace
just nsh-check -v
just nsh-build
just nsh-test
just core-plain-test
```

On this box, in the external adapter app, the first three commands' underlying
`nsh test` runs yielded respectively **2 passed**, **5 passed**, **2 passed**.
The pre-existing `FormPageHeavy.test.tsx` also passed before the change.

Production `just nsh-check -v`, `just nsh-build`, and a targeted `just nsh-test`
all failed before app compilation on missing `gtk4`/`graphene-gobject-1.0`.
An initial full `just nsh-test` was stopped after the same Rust build failure
instead of repeating the identical dependency failure for every test file.
Thus production app type-checking, Rust Door integration tests, and the full
production NSH test suite are **not verified**. The external adapter is not a
substitute for these gates. `cargo fmt --manifest-path nsh/Cargo.toml -- --check`
also reports existing formatting drift in unrelated NSH files; no broad formatter
rewrite was made. No real window/visual verification was possible.

`just core-plain-test` completed successfully after the database edit. Selected
output (the gate also runs the other core integration tests and doc-tests):

```text
test db::tests::change_counters_stay_idle_for_reads_and_detect_local_and_external_writes ... ok
test result: ok. 1581 passed; 0 failed; 11 ignored; 0 measured; 0 filtered out; finished in 19.79s
test result: ok. 142 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out; finished in 198.03s
test result: ok. 751 passed; 0 failed; 7 ignored; 0 measured; 0 filtered out; finished in 153.36s
```

Existing warnings: unused `ContextFingerprint` import in core's test-only shadow
module, and future incompatibility in `imap-proto v0.10.2`. The external adapter
also warns about its own undocumented Door exports (not production exports).
`git diff --check` is clean. No GitHub release was dispatched and no live filing
or account HTTP request was made by the benchmarks.
