# eBIRForms Linux Native Shell preview

The [published Linux packages](linux.md) still use the live-filing app. Native
Shell is a CI-only preview with a separate install and data directory. It does
not migrate existing encrypted filings. Do not use real filing data or submit a
return. The public cutover waits until both migration and live filing are verified.

## Requirements and safety

Use Ubuntu 24.04 or newer, a recent Fedora, or current Arch Linux: GTK **4.14+**,
WebKitGTK **6.0 / 2.42+**, GStreamer base/good plug-ins, D-Bus and fonts are required.
Ubuntu 22.04 and Debian 12 are not supported by these binaries. Build each architecture
on its own runner (`ubuntu-24.04`, `ubuntu-24.04-arm`). Arch packages are x64 only.
The NSH checkout must remain beside buwiz-forms at the pin in `.github/workflows/nsh.yml`.
See [NSH development](nsh.md) and [machine setup](devin-environment.md) for source builds.

Use `ebirforms-nsh-preview` (or `./eBIRForms/launch-preview.sh` after extracting
the tarball), not the raw runner. The launcher enables dry-run mode, ignores any
configured live database path and stores scratch data separately. To put smoke
test data in a throwaway directory, set:

```sh
export XDG_DATA_HOME="$HOME/ebirforms-package-test/data"
export XDG_CACHE_HOME="$HOME/ebirforms-package-test/cache"
mkdir -p "$XDG_DATA_HOME" "$XDG_CACHE_HOME"
```

Never set `BIR_SFTP_LIVE`. Never launch bir-shell or `just run` for this handover.
**Release builds deliberately compile out `BIR_AUTH_BYPASS`.** Use the local
account mock below to sign in to a packaged release without real credentials.
Do not weaken the gate or claim a form screenshot was checked when only the
sign-in window was rendered. A debug/test build is not evidence for the released
package.

### Local account sign-in with a release package

Start `just mock-account --auto-approve` from the repository root. It listens only
on loopback by default; never expose it publicly. Launch the installed release
with the safety/scratch variables above and these additional variables:

```sh
export BUWIZ_SERVER_URL=http://127.0.0.1:3008
export BUWIZ_ACCOUNT_URL=http://127.0.0.1:3008
ebirforms-nsh-preview
```

For a Linux Docker sidecar, use `--network host` and pass both URL variables and
the safety/scratch variables into the container. `configured_server()` and
`configured_account()` in `crates/bir-core/src/cloud_account.rs` honor runtime
URL overrides in release builds too; `EBIR_TEST_ENV` isolates the account state,
but is not what enables the URL overrides. With `BUWIZ_NO_KEYCHAIN=1`, the mock
session is saved as `buwiz-cloud-account.json` beside the scratch database
(mode `0600`), not in the real account's keychain. Never print or commit that file.

Choose **Sign in**. The mock approves the real device-code flow automatically
as `dev@buwiz.local`; no browser interaction or password is needed. On first run:

1. Choose **Just me or my business**.
2. Create the demo taxpayer: TIN `000123453`, name `Juana Santos`, head-office
   address `Quezon City`. Optional fields can remain blank.
3. Add a tax year, choose form `0605` (Payment Form), and save the forms.
4. Choose **New return**, then **Open form**, and capture the populated form UI.

This exercises the released package with a real mock-issued session, not the
compiled-out bypass. Do not queue or submit the return. The mock does not model
production account or filing services. See [Cloud account](../cloud-account.md).

## Download and verify

Download the `linux-nsh-preview-<arch>` artifact from the [Linux NSH Preview
Packages workflow](https://github.com/hexuria/buwiz-forms/actions/workflows/preview-linux-nsh.yml).
Unzip it and keep the chosen file with `SHA256SUMS-linux-<arch>.txt`. Use a throwaway
VM or container, not a machine with an existing live-filing install. `<arch>` is
`x64` or `arm64`; `<v>` is the app version plus `-pr`, without a leading `v`.
Verify that file's entry with `sha256sum -c` before install
(other missing downloads in the checksum list may be ignored with `--ignore-missing`).
Checksums detect corruption, not a malicious release publisher.

## Install, update and uninstall

| Download | Install | Update | Uninstall |
| --- | --- | --- | --- |
| `eBIRForms-Linux-<arch>-<v>.deb` | `sudo apt install ./eBIRForms-Linux-<arch>-<v>.deb` | Quit the app, install the newer `.deb` with the same command | `sudo apt remove ebirforms-nsh-preview` |
| `eBIRForms-Linux-<arch>-<v>.rpm` | `sudo dnf install ./eBIRForms-Linux-<arch>-<v>.rpm` | Quit the app, `sudo dnf upgrade ./eBIRForms-Linux-<arch>-<new>.rpm` | `sudo dnf remove ebirforms-nsh-preview` |
| `eBIRForms-Linux-x64-<v>.pkg.tar.zst` | `sudo pacman -U ./eBIRForms-Linux-x64-<v>.pkg.tar.zst` | Quit the app, install the newer package with `pacman -U` | `sudo pacman -Rns ebirforms-nsh-preview` |
| `ebirforms-nsh-preview-bin.PKGBUILD` (x64) | Copy to an empty folder as `PKGBUILD` beside its `.pkg.tar.zst`; inspect it; `makepkg -si` as an ordinary user | Use the newer artifact's recipe and repeat | `sudo pacman -Rns ebirforms-nsh-preview-bin` |
| `eBIRForms-Linux-<arch>-<v>.tar.gz` | Install runtime dependencies first; extract into a user-writable folder; run `eBIRForms/launch-preview.sh` | Quit and replace the **whole** extracted folder with a newer preview tarball | Quit; remove the extracted folder and any links/desktop entries you created |
| `install-linux.sh` (detects host architecture) | `sh install-linux.sh --from-dir ./downloads --version <v>` selects the distribution package | Run the installer with the newer version | `sh install-linux.sh --uninstall` |
| Installer with tarball | `sh install-linux.sh --from-dir ./downloads --tarball --version <v>` | Re-run with the newer preview artifact | `sh install-linux.sh --tarball --uninstall` |

The installer never downloads public releases. The directory passed to `--from-dir`
must contain the package and matching checksum list. `--tarball` uses
`~/.local/share/ebirforms-nsh-preview`, `~/.local/bin/ebirforms-nsh-preview`, and launcher/icon entries under
`$XDG_DATA_HOME` (normally `~/.local/share`). Put `~/.local/bin` on PATH. Runtime
dependencies are not installed by tarball mode:

```sh
sudo apt install libgtk-4-1 libwebkitgtk-6.0-4 gstreamer1.0-plugins-base gstreamer1.0-plugins-good fonts-noto-core
```

System packages install `/usr/bin/ebirforms-nsh-preview` as a symlink to
`/usr/lib/ebirforms-nsh-preview/launch-preview.sh`, with `nsh/` and `print-overrides/`
beside it. Every preview bundle carries the empty `ebirforms-no-self-update`
marker so it cannot replace itself with a public build. The desktop entry and
icon use `dev.goldcoders.bir.preview`, separate from the live app.
Keep the runner with its entire
`nsh/` folder. No legacy `app/` or full legacy `assets/` tree is needed: forms/HTML
are compiled into Rust, TSX-imported assets are in NSH's bundle; print CSS overrides
are still read from disk and are included beside the executable.

Uninstall leaves preview databases and settings intact, under
`$XDG_DATA_HOME/ebirforms-nsh-preview-data` (normally
`~/.local/share/ebirforms-nsh-preview-data`). Remove only that scratch folder if
you no longer need it. This workflow does not build or publish an update feed.

## Real-machine acceptance

For each download: install, launch the preview, record
distribution/architecture and dependency versions, capture the app window, then
with an authorized test session open a Form library sample and capture it. Quit,
update to the next test version, relaunch, then uninstall. Confirm executable,
resources, desktop file and icons are removed; keep data until explicitly approved
for deletion. Verify the update marker is empty beside the actual app binary.

## Container gate

```sh
packaging/linux/preview/build-packages.sh --version 0.2.0-pr --target x86_64-unknown-linux-gnu --out target/linux-nsh-preview
packaging/linux/preview/smoke-test.sh --out target/linux-nsh-preview --arch x64
```

Run the build inside Ubuntu 24.04 with both repositories mounted side by side and
the NSH CLI on PATH. Install the workflow's build dependencies plus `rpm` and `zstd`.
The smoke script uses fresh Ubuntu 24.04, Fedora and Arch containers; verifies runtime
linking, marker placement and desktop integration; launches under Xvfb/D-Bus with
scratch data; saves app-window screenshots and uninstall evidence in
`target/linux-nsh-smoke/` (or `SMOKE_EVIDENCE`). Each container has a bounded timeout.
The smoke gate proves installation, the sign-in window, and uninstall, **not form
opening or self-update**. Containers do not substitute for the owner's desktop check.
