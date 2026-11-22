@echo off
rem Windows counterpart of cargo-with-agent.sh: stands in for `cargo` while nsh builds the app's generated hosts, so
rem they carry the app's `agent` feature. Only a `cargo build` in the generated workspace (nsh\.nsh\rust) is changed;
rem every other command passes through. Used by `just nsh-run-agent` on Windows; nothing else sets %CARGO%.
setlocal
set "real=%NSH_REAL_CARGO%"
if not defined real set "real=cargo"
if /I not "%~1"=="build" goto pass
rem nsh names the manifest with either slash, even both (...\nsh\.nsh/rust\Cargo.toml): compare with one kind.
set given=%*
set given=%given:/=\%
set given=%given:"=%
if "%given:.nsh\rust\Cargo.toml=%"=="%given%" goto pass
"%real%" %* --features app_nsh_app_ebirforms/agent
exit /b %errorlevel%
:pass
"%real%" %*
exit /b %errorlevel%
