@echo off
rem Windows counterpart of cargo-with-agent.sh: stands in for `cargo` while nsh builds the app's generated hosts, so
rem they carry the app's `agent` feature. Only a `cargo build` in the generated workspace (nsh\.nsh\rust) is changed;
rem every other command passes through. Used by `just nsh-run-agent` on Windows; nothing else sets %CARGO%.
setlocal
set "real=%NSH_REAL_CARGO%"
if not defined real set "real=cargo"
if /I not "%~1"=="build" goto pass
rem Each argument is read without its quotes into a quoted assignment and compared with delayed expansion, so a path
rem with & or a space is only text. nsh names the manifest with either slash, even both (...\nsh\.nsh/rust\Cargo.toml).
set "hit="
setlocal enabledelayedexpansion
:scan
if "%~1"=="" goto scanned
set "a=%~1"
set "a=!a:/=\!"
if not "!a:.nsh\rust\Cargo.toml=!"=="!a!" set "hit=1"
rem The generated Android library names NSH's `dev` feature only; the window's control plane is `dev-agent`.
if /I "%~1"=="nsh-app-nsh-app-ebirforms-android" set "android=1"
shift
goto scan
:scanned
endlocal & set "hit=%hit%" & set "android=%android%"
if not defined hit goto pass
set "features=app_nsh_app_ebirforms/agent"
if defined android set "features=%features%,nsh-platform-android/dev-agent"
"%real%" %* --features %features%
exit /b %errorlevel%
:pass
"%real%" %*
exit /b %errorlevel%
