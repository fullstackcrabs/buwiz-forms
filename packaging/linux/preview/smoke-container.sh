#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export XDG_DATA_HOME=/scratch/data XDG_CACHE_HOME=/scratch/cache BIR_DATABASE_PATH=/scratch/filing.db
mkdir -p "$XDG_DATA_HOME" "$XDG_CACHE_HOME"
case "$KIND" in
    deb|tarball) apt-get update ;;
esac
case "$KIND" in
    deb) apt-get install -y --no-install-recommends "/packages/$BASE.deb" ;;
    rpm) dnf install -y "/packages/$BASE.rpm" ;;
    arch|arch-recipe)
        pacman -Syu --noconfirm
        if [ "$KIND" = arch-recipe ]; then
            useradd -m builder
            install -d -o builder -g builder /build
            cp /packages/ebirforms-bin.PKGBUILD /build/PKGBUILD
            cp "/packages/$BASE.pkg.tar.zst" /build/
            (cd /build && runuser -u builder -- makepkg --nodeps --noconfirm)
            pacman -U --noconfirm /build/ebirforms-bin-*.pkg.tar.zst
        else
            pacman -U --noconfirm "/packages/$BASE.pkg.tar.zst"
        fi
        ;;
    installer) sh /packages/install-linux.sh --from-dir /packages --version "$VERSION" ;;
    tarball)
        apt-get install -y --no-install-recommends libgtk-4-1 libwebkitgtk-6.0-4 \
            gstreamer1.0-plugins-base gstreamer1.0-plugins-good fonts-noto-core
        sh /packages/install-linux.sh --from-dir /packages --version "$VERSION" --tarball
        ;;
esac
exe=/usr/bin/ebirforms
app=/usr/lib/ebirforms
if [ "$KIND" = tarball ]; then
    app="$HOME/.local/share/ebirforms"
    exe="$HOME/.local/bin/ebirforms"
    desktop="$XDG_DATA_HOME/applications/dev.goldcoders.bir.desktop"
    icons="$XDG_DATA_HOME/icons/hicolor"
    sizes=512
    test ! -e "$app/ebirforms-no-self-update"
    grep -Fx "Exec=\"$app/eBIRForms\"" "$desktop"
else
    desktop=/usr/share/applications/dev.goldcoders.bir.desktop
    icons=/usr/share/icons/hicolor
    sizes='48 64 128 256 512'
    test -f "$app/ebirforms-no-self-update"
    test ! -s "$app/ebirforms-no-self-update"
fi
test "$(readlink -f "$exe")" = "$app/eBIRForms"
test -s "$desktop"
for size in $sizes; do
    test -s "$icons/${size}x${size}/apps/dev.goldcoders.bir.png"
done
test -f "$app/nsh/app.json"
test -d "$app/print-overrides"
ldd "$exe" | tee "/evidence/$KIND-ldd.txt"
if grep -q 'not found' "/evidence/$KIND-ldd.txt"; then exit 1; fi
case "$KIND" in
    deb|installer|tarball)
        apt-get install -y xvfb xauth dbus-x11 xdotool imagemagick
        ;;
    rpm) dnf install -y xorg-x11-server-Xvfb xorg-x11-xauth dbus-x11 xdotool ImageMagick ;;
    arch|arch-recipe) pacman -S --noconfirm xorg-server-xvfb xorg-xauth dbus xdotool imagemagick ;;
esac
export EXE="$exe" GSK_RENDERER=cairo
# shellcheck disable=SC2016
dbus-run-session -- xvfb-run -a -s '-screen 0 1600x1000x24' bash -euc '
    "$EXE" > "/evidence/$KIND-app.log" 2>&1 &
    pid=$!
    trap "kill $pid 2>/dev/null || true" EXIT
    window="$(timeout 90 xdotool search --sync --onlyvisible --name eBIRForms | head -1)"
    test -n "$window"
    kill -0 "$pid"
    import -pause 3 -window "$window" "/evidence/$KIND-app-open.png"
'
case "$KIND" in
    deb) apt-get remove -y ebirforms ;;
    rpm) dnf remove -y ebirforms ;;
    arch) pacman -Rns --noconfirm ebirforms ;;
    arch-recipe) pacman -Rns --noconfirm ebirforms-bin ;;
    installer) sh /packages/install-linux.sh --uninstall ;;
    tarball) sh /packages/install-linux.sh --uninstall --tarball ;;
esac
test ! -e "$app"
test ! -L "$exe"
test ! -e "$exe"
test ! -e "$desktop"
for size in $sizes; do
    test ! -e "$icons/${size}x${size}/apps/dev.goldcoders.bir.png"
done
echo "PASS: $KIND install, visible app window, uninstall (executable, resources, launcher and icons removed)" | tee "/evidence/$KIND-uninstall.txt"
