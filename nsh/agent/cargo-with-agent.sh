#!/bin/sh
# Stands in for `cargo` while nsh builds the app's generated hosts, so they carry the app's `agent` feature.
#
# The generated workspace (nsh/.nsh/rust) lists this crate with no features and nsh's CLI has no flag for one, but it runs the
# program named by $CARGO, and cargo takes `--features <dependency>/<feature>` for a dependency of the host it builds. Only a
# `cargo build` in that generated workspace is changed (the build of the crate itself, and every other command, pass through).
# Used by `just nsh-run-agent`; nothing else sets $CARGO.
real="${NSH_REAL_CARGO:-cargo}"
if [ "$1" = "build" ]; then
    # The generated Android library names NSH's `dev` feature only; the window's control plane is `dev-agent` (the desktop and
    # iOS development hosts already carry it through NSH's host crates).
    features="app_nsh_app_ebirforms/agent"
    for arg in "$@"; do
        case "$arg" in
            nsh-app-nsh-app-ebirforms-android) features="$features,nsh-platform-android/dev-agent" ;;
        esac
    done
    for arg in "$@"; do
        case "$arg" in
            */.nsh/rust/Cargo.toml)
                shift
                exec "$real" build "$@" --features "$features"
                ;;
        esac
    done
fi
exec "$real" "$@"
