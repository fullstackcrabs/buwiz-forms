#!/bin/sh
set -eu

APP_VERSION=""
USE_TARBALL=0
UNINSTALL=0
FROM_DIR=""
TEMP_DIR=""
APP_ID=dev.goldcoders.bir
INSTALL_ROOT="$HOME/.local/share/ebirforms"
BIN_DIR="$HOME/.local/bin"
case "${XDG_DATA_HOME:-}" in
    /*) DESKTOP_DATA=$XDG_DATA_HOME ;;
    *) DESKTOP_DATA="$HOME/.local/share" ;;
esac
DESKTOP_ENTRY="$DESKTOP_DATA/applications/$APP_ID.desktop"
ICON_SIZES="48 64 128 256 512"

usage() {
    cat <<'USAGE'
Usage: install-linux.sh --from-dir <directory> --version <version> [--tarball]
       install-linux.sh --uninstall [--tarball]
This preview installer uses downloaded workflow artifacts, not published releases.
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --version)
            [ "$#" -ge 2 ] || { echo "--version needs a value" >&2; exit 2; }
            APP_VERSION=$2
            shift 2
            ;;
        --tarball)
            USE_TARBALL=1
            shift
            ;;
        --uninstall)
            UNINSTALL=1
            shift
            ;;
        --from-dir)
            [ "$#" -ge 2 ] || { echo "--from-dir needs a directory" >&2; exit 2; }
            FROM_DIR=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 2
            ;;
    esac
done

cleanup() {
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
}
trap cleanup 0 HUP INT TERM

if [ "$UNINSTALL" -eq 1 ]; then
    # shellcheck source=/dev/null
    . /etc/os-release 2>/dev/null || true
    ID=${ID:-unknown}
    ID_LIKE=${ID_LIKE:-}
    if [ "$USE_TARBALL" -eq 0 ]; then
    case "$ID $ID_LIKE" in
        *debian*|*ubuntu*)
            if [ "$(id -u)" -eq 0 ]; then apt-get remove -y ebirforms; else sudo apt-get remove -y ebirforms; fi
            ;;
        *fedora*|*rhel*|*centos*|*suse*)
            if command -v dnf >/dev/null 2>&1; then
                if [ "$(id -u)" -eq 0 ]; then dnf remove -y ebirforms; else sudo dnf remove -y ebirforms; fi
            elif command -v zypper >/dev/null 2>&1; then
                if [ "$(id -u)" -eq 0 ]; then zypper --non-interactive remove ebirforms; else sudo zypper --non-interactive remove ebirforms; fi
            fi
            ;;
        *arch*|*manjaro*|*endeavouros*)
            if [ "$(id -u)" -eq 0 ]; then pacman -Rns --noconfirm ebirforms; else sudo pacman -Rns --noconfirm ebirforms; fi
            ;;
    esac
    fi
    if [ "$USE_TARBALL" -eq 1 ]; then
        rm -f "$BIN_DIR/ebirforms" "$DESKTOP_ENTRY"
        for size in $ICON_SIZES; do
            rm -f "$DESKTOP_DATA/icons/hicolor/${size}x${size}/apps/$APP_ID.png"
        done
        rm -rf "$INSTALL_ROOT"
    fi
    echo "Removed eBIRForms."
    exit 0
fi

APP_VERSION=${APP_VERSION#v}
case "$APP_VERSION" in
    ""|*[!A-Za-z0-9.+~-]*)
        echo "Invalid release version: $APP_VERSION" >&2
        exit 2
        ;;
esac
[ -n "$FROM_DIR" ] || { usage >&2; exit 2; }
[ -d "$FROM_DIR" ] || { echo "Package directory does not exist: $FROM_DIR" >&2; exit 1; }
FROM_DIR=$(CDPATH='' cd -- "$FROM_DIR" && pwd)

MACHINE=$(uname -m)
case "$MACHINE" in
    x86_64|amd64) ARCH=x64 ;;
    aarch64|arm64) ARCH=arm64 ;;
    *) echo "Unsupported Linux architecture: $MACHINE" >&2; exit 1 ;;
esac

# shellcheck source=/dev/null
. /etc/os-release 2>/dev/null || true
ID=${ID:-unknown}
ID_LIKE=${ID_LIKE:-}
case "$ID $ID_LIKE" in
    *debian*|*ubuntu*) FAMILY=debian ;;
    *fedora*|*rhel*|*centos*|*suse*) FAMILY=rpm ;;
    *arch*|*manjaro*|*endeavouros*) FAMILY=arch ;;
    *) FAMILY=unknown ;;
esac

if [ "$FAMILY" = arch ] && [ "$ARCH" != x64 ] && [ "$USE_TARBALL" -eq 0 ]; then
    echo "The Arch package is available for x86_64 only; use --tarball on $ARCH." >&2
    exit 1
fi

FONT_COMMAND=""
case "$FAMILY" in
    debian) FONT_COMMAND="sudo apt-get install fonts-noto-core" ;;
    rpm)
        case "$ID" in
            *opensuse*|suse) FONT_COMMAND="sudo zypper install google-noto-sans-fonts" ;;
            *) FONT_COMMAND="sudo dnf install google-noto-sans-fonts" ;;
        esac
        ;;
    arch) FONT_COMMAND="sudo pacman -S noto-fonts" ;;
    *) FONT_COMMAND="install Noto Sans using your distribution's package manager" ;;
esac
warn_missing_font() {
    if ! command -v fc-list >/dev/null 2>&1 || ! fc-list : family 2>/dev/null | grep -qi 'Noto Sans'; then
        echo "Warning: Noto Sans was not found. Install it with: $FONT_COMMAND" >&2
    fi
}

run_privileged() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        echo "Run as root or install sudo to install a system package." >&2
        exit 1
    fi
}

TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ebirforms-install.XXXXXX")
SUMS="SHA256SUMS-linux-${ARCH}.txt"
[ -f "$FROM_DIR/$SUMS" ] || { echo "Missing checksum file: $FROM_DIR/$SUMS" >&2; exit 1; }
cp "$FROM_DIR/$SUMS" "$TEMP_DIR/$SUMS"

download_and_verify() {
    asset=$1
    [ -f "$FROM_DIR/$asset" ] || { echo "Missing package asset: $FROM_DIR/$asset" >&2; exit 1; }
    cp "$FROM_DIR/$asset" "$TEMP_DIR/$asset"
    expected=$(awk -v name="$asset" '$2 == name { print $1; exit }' "$TEMP_DIR/$SUMS")
    [ -n "$expected" ] || { echo "No checksum entry for $asset" >&2; exit 1; }
    printf '%s  %s\n' "$expected" "$asset" | (CDPATH='' cd -- "$TEMP_DIR" && sha256sum -c -)
}

install_tarball() {
    asset="eBIRForms-Linux-${ARCH}-${APP_VERSION}.tar.gz"
    download_and_verify "$asset"
    payload="$TEMP_DIR/payload"
    mkdir "$payload"
    tar -xzf "$TEMP_DIR/$asset" -C "$payload" --strip-components=1
    if [ -x "$payload/eBIRForms" ] && [ -f "$payload/nsh/app.json" ] && [ ! -e "$payload/ebirforms-no-self-update" ]; then
        runner=eBIRForms
        entry="$payload/$APP_ID.desktop"
        sizes=512
    elif [ -x "$payload/bir" ] && [ -f "$payload/app/main.js" ]; then
        runner=bir
        entry="$payload/assets/linux/$APP_ID.desktop"
        sizes=$ICON_SIZES
    else
        echo "Unrecognized eBIRForms tarball layout" >&2
        exit 1
    fi

    # A desktop Exec value is parsed twice; escape the path as one literal argument.
    exec_path=$(printf '%s' "$INSTALL_ROOT/$runner" | sed 's/\\/\\\\\\\\/g; s/["`$]/\\\\&/g; s/%/%%/g')
    exec_path="$exec_path" awk '/^Exec=/ { print "Exec=\"" ENVIRON["exec_path"] "\""; next } { print }' \
        "$entry" > "$TEMP_DIR/launcher.desktop"
    for size in $sizes; do
        if [ "$runner" = eBIRForms ]; then
            icon="$payload/$APP_ID.png"
        else
            icon="$payload/assets/linux/icons/hicolor/${size}x${size}/apps/$APP_ID.png"
        fi
        install -m644 "$icon" "$TEMP_DIR/icon-$size.png"
    done

    mkdir -p "$INSTALL_ROOT" "$BIN_DIR"
    cp -a "$payload/." "$INSTALL_ROOT/"
    ln -sf "$INSTALL_ROOT/$runner" "$BIN_DIR/ebirforms"
    install -Dm644 "$TEMP_DIR/launcher.desktop" "$DESKTOP_ENTRY"
    for size in $sizes; do
        install -Dm644 "$TEMP_DIR/icon-$size.png" "$DESKTOP_DATA/icons/hicolor/${size}x${size}/apps/$APP_ID.png"
    done
    echo "Installed eBIRForms to $INSTALL_ROOT"
    echo "Add $BIN_DIR to PATH if it is not already present."
}

case "$FAMILY:$USE_TARBALL" in
    *:1|unknown:*)
        install_tarball
        ;;
    debian:0)
        asset="eBIRForms-Linux-${ARCH}-${APP_VERSION}.deb"
        download_and_verify "$asset"
        run_privileged apt-get update
        run_privileged apt-get install -y "$TEMP_DIR/$asset"
        ;;
    rpm:0)
        asset="eBIRForms-Linux-${ARCH}-${APP_VERSION}.rpm"
        download_and_verify "$asset"
        if command -v dnf >/dev/null 2>&1; then
            run_privileged dnf install -y "$TEMP_DIR/$asset"
        elif command -v zypper >/dev/null 2>&1; then
            run_privileged zypper --non-interactive --no-gpg-checks install --allow-unsigned-rpm "$TEMP_DIR/$asset"
        else
            echo "Neither dnf nor zypper is available to install the RPM." >&2
            exit 1
        fi
        ;;
    arch:0)
        asset="eBIRForms-Linux-${ARCH}-${APP_VERSION}.pkg.tar.zst"
        download_and_verify "$asset"
        run_privileged pacman -Syu --noconfirm
        run_privileged pacman -U --noconfirm "$TEMP_DIR/$asset"
        ;;
esac

warn_missing_font
