# Desktop click caret — macOS rig proof (B1c)

Kit branch `fix/otp-input-desktop-click` (commit `774cf65d`, re-authored `971db991` — tree identical,
author/committer hexuria), stacked on `fix/otp-input-android-selection` `151dcf3d`.

**Build line:** app `a1a86ded` (hexuria/buwiz-forms main) · kit sibling + nsh CLI + runtime all at the
branch head (`nsh -V` prints `0.6.1 (971db99)` — the re-author changed only the committer line after the
CLI install; tree identical) · cargo `1.100.0 (3acc79c0c 2026-11-05)` toolchain's own · RUSTC_WRAPPER
empty · folder `/Users/devin/rig/desktopclick/target` (created empty for this rig; nothing else writes
it; the justfile `nsh-*` recipes were not used) · mock account server localhost:3008 built in the same
folder · scratch db · `BUWIZ_NO_KEYCHAIN=1 EBIR_TEST_ENV=1 BIR_AUTH_BYPASS=1 BIR_SFTP_DRY_RUN=1`.

## What is here

- `rig-transcript.txt` — every case with the geometry, inputs and the field reads.
- `desktopclick-cases.mp4` — one take: type 123; click after digit 2 + Backspace leaves `13`;
  click before digit 1 + typing inserts there; double-click selects the run (typing 7 replaces all);
  drag from after digit 2 to before digit 1 selects digits 1–2 (typing 9 leaves `93`).
- `selection-drawn.png`, `sel56.png` — the cells draw the selection the platform holds;
  cutting it leaves exactly the unselected digits (`1234`).
- `window-context.png`, `field-final.png` — context.

## Results (real OS mouse clicks + keys through the running app, New taxpayer TIN)

All PASS — the transcript has each read:
click after digit 2 + Backspace → `13`; click before digit 1 + type 9 → `9123`;
click inside a selection collapses to the nearest edge → `1293`; double-click + type 7 → `7`;
double-click + cut → empty; drag edge2→edge0 + type 9 → `93`;
keyboard matrix unchanged (cut first/middle/last → `23`/`13`/`12`, select-all delete → empty,
bare Backspace → `12`, type over middle → `153`).

## Anomaly found (pre-existing at `151dcf3d`, not this branch)

After cutting a selection (cmd-x), a fast key burst (~80 ms gaps) is swallowed whole — the digits
never land; slow keys land correctly. Reproduced with no click anywhere in the sequence, and this
branch changes no keyboard logic, so it is the reconstruction echo path of the earlier work, not the
click fix. Needs its own investigation; rig cases here used settled typing and pass.
