# kit-39-windows — OtpInput burst-fix proof on Windows

Proof for hexuria/nsh pull request #39 (`fix/otp-input-burst`), tested on a
Windows Server 2022 build machine at head `62e436ff170e` (the branch head at
test time; earlier results in the same session were at `e1a6226a1` before
three small follow-up commits landed).

The kit's own gallery example (`examples/gallery`, the `OtpInput` demo — a
six-digit one-time-code box) was built and run on Windows with the kit's own
command, `cargo run -- otpinput` from the repository root (which builds
`nsh-cli` and runs `nsh run examples/gallery` on the Win32 host).

- `otp-typed-fast.png` — `123456789` typed fast (SendKeys burst) into the
  six-digit box: the first six land **in order** (1 2 3 4 5 6), the rest are
  capped by the box's length, and the demo's Last event reads
  "Code complete: 123456". ("That code is not right" is the demo's own
  wrong-code shake styling — the demo's correct code is 246810.)
- `otp-pasted.png` — `987654321` pasted (Ctrl+V) into the cleared box: the
  first six digits fill the boxes in order (9 8 7 6 5 4), capped at the box
  length, Last event "Code complete: 987654".

Before the fix, a fast burst could land digits out of order because a stale
selection write pulled the caret back into the text mid-burst. The fix adds
an edit count to selection writes so a stale one is dropped on every
platform; the Windows selection write
(`crates/nsh-platform-windows/src/text_input.rs::set_selection`) drops the
write when its count is older than the input's own edit count, matching the
macOS behavior.

No application or kit code was modified on this machine; report only.
