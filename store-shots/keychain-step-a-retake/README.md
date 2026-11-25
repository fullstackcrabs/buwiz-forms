# Keychain retake evidence — ad1ff9f3, device A (iPhone 17, iOS 27.0)

The run STOPPED AT STEP 1: zero Keychain rows after a completed sign-in (owner's stop rule). Steps 2-5 never ran.

- `step1-gate.png` — step 1: the account gate on the relaunched app ("Welcome to eBIRForms", Sign in / Create account), before pressing Sign in.
- `step1-signed-in-setup.png` — step 1: the device-setup screen the app advanced to after the mock auto-approved the sign-in (proof the sign-in completed; taken after the fact).
- `genp.txt` — step 1: the Keychain `genp` attribute rows (rowid, pdmn, agrp, svce only — never the data column): zero rows for this app; the 34 rows present are all apple-system items.
- `NOTES.txt` — the full per-step record: launch env verified in-process, the door.rs lines that decide the Keychain, the adhoc-signature/no-entitlements finding, and the dropped "Keychain at launch" log-line finding.

No `.mp4` recordings exist: the owner's video rule arrived after step 1 (the sign-in) had already completed, and the stop-at-step-1 rule meant no further steps (relaunch, reinstall) were ever run — so there was nothing left to record. This is noted in NOTES.txt section 5 per the rule.
