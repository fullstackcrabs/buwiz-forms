from __future__ import annotations

import hashlib
import io
import os
import platform
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "packaging/linux/preview/install-linux.sh"
LAUNCHER = INSTALLER.with_name("launch-preview.sh")
PACKAGE = "ebirforms-nsh-preview"


@unittest.skipUnless(platform.system() == "Linux", "uses Linux installer utilities")
class LinuxNshInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home with spaces & symbols"
        self.home.mkdir()
        self.downloads = Path(self.temp.name) / "downloads"
        self.downloads.mkdir()
        self.arch = "x64" if platform.machine() == "x86_64" else "arm64"
        self.data = Path(self.temp.name) / "xdg"
        self.binary = (
            b"#!/bin/sh\n"
            b"printf 'arg=%s\\nBIR_DATABASE_PATH=%s\\nBIR_SFTP_DRY_RUN=%s\\n' "
            b"\"$1\" \"$BIR_DATABASE_PATH\" \"$BIR_SFTP_DRY_RUN\"\n"
            b"test \"${BIR_SFTP_LIVE+x}${BIR_RELAY_URL+x}\" = ''\n"
        )
        self.entries = (
            ("eBIRForms", self.binary, 0o755),
            ("launch-preview.sh", LAUNCHER.read_bytes(), 0o755),
            ("ebirforms-no-self-update", b"", 0o644),
            ("nsh/app.json", b"{}", 0o644),
            ("dev.goldcoders.bir.preview.desktop", b"[Desktop Entry]\nExec=unused\n", 0o644),
            ("dev.goldcoders.bir.png", b"fixture", 0o644),
        )
        self.write_tarball("0.2.0-pr", self.entries)

    def write_tarball(self, version, entries) -> None:
        self.archive = self.downloads / f"eBIRForms-Linux-{self.arch}-{version}.tar.gz"
        with tarfile.open(self.archive, "w:gz") as archive:
            for name, data, mode in entries:
                info = tarfile.TarInfo(f"eBIRForms/{name}")
                info.size = len(data)
                info.mode = mode
                archive.addfile(info, io.BytesIO(data))
        checksum = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        (self.downloads / f"SHA256SUMS-linux-{self.arch}.txt").write_text(
            f"{checksum}  {self.archive.name}\n"
        )

    def run_installer(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", str(INSTALLER), *args],
            env={**os.environ, "HOME": str(self.home), "XDG_DATA_HOME": str(self.data)},
            text=True, capture_output=True, check=False,
        )

    def install(self, version="0.2.0-pr") -> subprocess.CompletedProcess[str]:
        return self.run_installer(
            "--tarball", "--from-dir", str(self.downloads), "--version", version,
        )

    def test_tarball_install_and_uninstall_preserves_nsh_layout(self) -> None:
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        app = self.home / ".local/share" / PACKAGE
        link = self.home / ".local/bin" / PACKAGE
        self.assertEqual(link.resolve(), app / "launch-preview.sh")
        self.assertTrue((app / "nsh/app.json").is_file())
        self.assertEqual((app / "ebirforms-no-self-update").read_bytes(), b"")
        desktop = self.data / "applications/dev.goldcoders.bir.preview.desktop"
        icon = self.data / "icons/hicolor/512x512/apps/dev.goldcoders.bir.preview.png"
        self.assertIn(f'Exec="{app}/launch-preview.sh"', desktop.read_text())
        self.assertTrue(icon.is_file())
        launch = subprocess.run(
            [str(link), "two words"], text=True, capture_output=True, check=True,
            env={**os.environ, "HOME": str(self.home), "XDG_DATA_HOME": str(self.data),
                 "BIR_SFTP_LIVE": "1", "BIR_RELAY_URL": "http://127.0.0.1:7",
                 "BIR_DATABASE_PATH": "existing-live.db", "BIR_SFTP_DRY_RUN": "0"},
        )
        self.assertIn("arg=two words", launch.stdout.splitlines())
        preview_data = self.data / f"{PACKAGE}-data"
        self.assertIn(f"BIR_DATABASE_PATH={preview_data}/filing.db", launch.stdout.splitlines())
        self.assertIn("BIR_SFTP_DRY_RUN=1", launch.stdout.splitlines())
        result = self.run_installer("--uninstall", "--tarball")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(app.exists())
        self.assertFalse(desktop.exists())
        self.assertFalse(icon.exists())
        self.assertFalse(link.is_symlink())
        self.assertTrue(preview_data.is_dir())

    def test_preview_install_and_uninstall_leave_live_install_alone(self) -> None:
        live_paths = (
            self.home / ".local/share/ebirforms/bir",
            self.home / ".local/bin/ebirforms",
            self.data / "applications/dev.goldcoders.bir.desktop",
            self.data / "icons/hicolor/512x512/apps/dev.goldcoders.bir.png",
        )
        for live in live_paths:
            live.parent.mkdir(parents=True, exist_ok=True)
            live.write_bytes(b"live")
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(self.run_installer("--uninstall", "--tarball").returncode, 0)
        self.assertTrue(all(live.read_bytes() == b"live" for live in live_paths))

    def test_live_version_is_rejected(self) -> None:
        result = self.install("v0.1.0")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Invalid preview version", result.stderr)

    def test_incomplete_tarball_does_not_modify_existing_install(self) -> None:
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write_tarball("0.2.1-pr", (("eBIRForms", b"replacement", 0o755), *self.entries[1:-1]))
        result = self.install("0.2.1-pr")
        self.assertNotEqual(result.returncode, 0)
        runner = self.home / ".local/share" / PACKAGE / "eBIRForms"
        self.assertEqual(runner.read_bytes(), self.binary)

    def test_requires_local_artifacts(self) -> None:
        result = self.run_installer("--version", "0.2.0-pr")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--from-dir", result.stderr)

    def test_empty_download_directory_is_rejected(self) -> None:
        for path in self.downloads.iterdir():
            path.unlink()
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing checksum file", result.stderr)

    def test_corrupt_archive_is_rejected_before_install(self) -> None:
        self.archive.write_bytes(b"corrupt")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / ".local/bin" / PACKAGE).exists())

    def test_invalid_version_is_rejected(self) -> None:
        result = self.run_installer("--version", "../bad", "--tarball")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Invalid preview version", result.stderr)
