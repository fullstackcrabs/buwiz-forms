# eBIRForms Linux downloads (Native Shell)

## Requirements and safety

Use Ubuntu 24.04 or newer, a recent Fedora, or current Arch Linux: GTK **4.14+**,
WebKitGTK **6.0 / 2.42+**, GStreamer base/good plug-ins, D-Bus and fonts are required.
Ubuntu 22.04 and Debian 12 are not supported by these binaries. Build each architecture
on its own runner (`ubuntu-24.04`, `ubuntu-24.04-arm`). Arch packages are x64 only.
The NSH checkout must remain beside buwiz-forms at the pin in `.github/workflows/nsh.yml`.
See [NSH development](nsh.md) and [machine setup](devin-environment.md) for source builds.

Never use a real filing database or credentials for a packaging smoke test. Set:

```sh
export BUWIZ_NO_KEYCHAIN=1 EBIR_TEST_ENV=1 BIR_AUTH_BYPASS=1 BIR_SFTP_DRY_RUN=1
export XDG_DATA_HOME="$HOME/ebirforms-package-test/data"
export XDG_CACHE_HOME="$HOME/ebirforms-package-test/cache"
export BIR_DATABASE_PATH="$HOME/ebirforms-package-test/filing.db"
mkdir -p "$XDG_DATA_HOME" "$XDG_CACHE_HOME"
```

Never set `BIR_SFTP_LIVE`. Never launch bir-shell or `just run` for this handover.
**Release builds deliberately compile out `BIR_AUTH_BYPASS`.** They can show the
Buwiz sign-in window but cannot open a form on a fresh scratch database without a
valid account session. Do not weaken the gate, sign in, or claim a form screenshot
was checked when only the sign-in window was rendered. Opening a sample form on a
real machine with an authorized session is an owner check. A debug/test build is
not evidence for the released package.

## Download and verify

Download the chosen file and `SHA256SUMS-linux-<arch>.txt` from the same release at
<https://github.com/hexuria/buwiz-forms/releases>. `<arch>` is `x64` or `arm64`;
`<v>` has no leading `v`. Verify that file's entry with `sha256sum -c` before install
(other missing downloads in the checksum list may be ignored with `--ignore-missing`).
Checksums detect corruption, not a malicious release publisher.

## Install, update and uninstall

| Download | Install | Update | Uninstall |
| --- | --- | --- | --- |
| `eBIRForms-Linux-<arch>-<v>.deb` | `sudo apt install ./eBIRForms-Linux-<arch>-<v>.deb` | Quit the app, install the newer `.deb` with the same command | `sudo apt remove ebirforms` |
| `eBIRForms-Linux-<arch>-<v>.rpm` | `sudo dnf install ./eBIRForms-Linux-<arch>-<v>.rpm` | Quit the app, `sudo dnf upgrade ./eBIRForms-Linux-<arch>-<new>.rpm` | `sudo dnf remove ebirforms` |
| `eBIRForms-Linux-x64-<v>.pkg.tar.zst` | `sudo pacman -U ./eBIRForms-Linux-x64-<v>.pkg.tar.zst` | Quit the app, install the newer package with `pacman -U` | `sudo pacman -Rns ebirforms` |
| `ebirforms-bin.PKGBUILD` (x64) | Copy to an empty folder as `PKGBUILD`; inspect it; `makepkg -si` as an ordinary user | Use the newer release's recipe and repeat | `sudo pacman -Rns ebirforms` |
| `eBIRForms-Linux-<arch>-<v>.tar.gz` | Install runtime dependencies first; extract into a user-writable folder; run `eBIRForms/eBIRForms` | In-app NSH updater, or quit and replace the **whole** extracted folder with a newer tarball | Quit; remove the extracted folder and any links/desktop entries you created |
| `install-linux.sh` (x64 download, detects host architecture) | `sh install-linux.sh --version <v>` selects the distribution package | Run the installer with the newer version | `sh install-linux.sh --uninstall` |
| Installer with tarball | `sh install-linux.sh --tarball --version <v>` | In-app NSH updater, or re-run with newer version | `sh install-linux.sh --tarball --uninstall` |

For an offline/local release test, add `--from-dir /path/to/downloads --version <v>`
to the installer. That directory must contain the package and matching checksum list.
`--tarball` uses `~/.local/share/ebirforms`, `~/.local/bin/ebirforms` and user launcher/icon
entries. Put `~/.local/bin` on PATH. Runtime dependencies are not installed by tarball mode:

```sh
sudo apt install libgtk-4-1 libwebkitgtk-6.0-4 gstreamer1.0-plugins-base gstreamer1.0-plugins-good fonts-noto-core
```

System packages install `/usr/bin/ebirforms` as a symlink to
`/usr/lib/ebirforms/eBIRForms`, with `nsh/` and `print-overrides/` beside it.
The empty `/usr/lib/ebirforms/ebirforms-no-self-update` marker disables in-app
updates; use your package manager instead. Desktop entries are
`/usr/share/applications/dev.goldcoders.bir.desktop` and icons are under
`/usr/share/icons/hicolor/<size>x<size>/apps/dev.goldcoders.bir.png`.
The tarball and updater archive have **no marker**. Keep the runner with its entire
`nsh/` folder. No legacy `app/` or full legacy `assets/` tree is needed: forms/HTML
are compiled into Rust, TSX-imported assets are in NSH's bundle; print CSS overrides
are still read from disk and are included beside the executable.

`eBIRForms-0.2.0-linux-x86_64.tar.gz` (or `linux-aarch64`) is the NSH updater
archive, not a second system package. Its version is from `nsh/nsh.json`, and its
platform name uses Rust's architecture, not the public download's `x64`/`arm64`.
Track G signs the update manifest; a package build alone does not prove feed signing
or a two-version self-update. The updater archive includes the same print resources
as the public tarball. Do not publish a test build as the latest GitHub release.

Uninstall leaves user databases/settings intact. After checking there is no real data,
remove only the scratch folder you created above. Ordinary app data follows
`$XDG_DATA_HOME/dev.goldcoders.bir` (normally `~/.local/share/dev.goldcoders.bir`);
this handover never migrates or deletes the older application's data.

## Real-machine acceptance

For each download: install, launch `ebirforms` (or the extracted runner), record
distribution/architecture and dependency versions, capture the app window, then
with an authorized test session open a Form library sample and capture it. Quit,
update to the next test version, relaunch, then uninstall. Confirm executable,
resources, desktop file and icons are removed; keep data until explicitly approved
for deletion. For tarballs also verify the marker is absent; for system packages verify
it is empty beside the resolved executable and Settings directs updates to the package manager.

## Container gate

```sh
packaging/linux/build-packages.sh --version 0.2.0-pr --target x86_64-unknown-linux-gnu --out target/release-artifacts
packaging/linux/smoke-test.sh --out target/release-artifacts --arch x64
```

Run the build inside Ubuntu 24.04 with both repositories mounted side by side and
the NSH CLI on PATH. Install the workflow's build dependencies plus `rpm` and `zstd`.
The smoke script uses fresh Ubuntu 24.04, Fedora and Arch containers; verifies runtime
linking, marker placement and desktop integration; launches under Xvfb/D-Bus with
scratch data; saves app-window screenshots and uninstall evidence in
`target/linux-smoke/` (or `SMOKE_EVIDENCE`). Each container has a bounded timeout.
The smoke gate proves installation, the sign-in window, and uninstall, **not form
opening or self-update**. Containers do not substitute for the owner's desktop check.
