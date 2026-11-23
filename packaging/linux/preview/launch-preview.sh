#!/bin/sh
set -eu
root=$(dirname "$(readlink -f -- "$0")")
case "${XDG_DATA_HOME:-}" in
    /*) XDG_DATA_HOME="$XDG_DATA_HOME/ebirforms-nsh-preview-data" ;;
    *) XDG_DATA_HOME="$HOME/.local/share/ebirforms-nsh-preview-data" ;;
esac
case "${XDG_CACHE_HOME:-}" in
    /*) XDG_CACHE_HOME="$XDG_CACHE_HOME/ebirforms-nsh-preview" ;;
    *) XDG_CACHE_HOME="$HOME/.cache/ebirforms-nsh-preview" ;;
esac
mkdir -p "$XDG_DATA_HOME" "$XDG_CACHE_HOME"
BIR_DATABASE_PATH="$XDG_DATA_HOME/filing.db"
export XDG_DATA_HOME XDG_CACHE_HOME BIR_DATABASE_PATH
export EBIR_TEST_ENV=1 BUWIZ_NO_KEYCHAIN=1 BIR_SFTP_DRY_RUN=1
unset BIR_SFTP_LIVE BIR_RELAY_URL
exec "$root/eBIRForms" "$@"
