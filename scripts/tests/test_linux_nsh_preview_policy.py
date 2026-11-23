from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class LinuxNshPreviewPolicyTests(unittest.TestCase):
    def test_public_release_keeps_the_live_filing_workflow(self) -> None:
        release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        live = (ROOT / ".github/workflows/release-linux.yml").read_text(encoding="utf-8")
        self.assertIn("uses: ./.github/workflows/release-linux.yml", release)
        self.assertNotIn("preview-linux-nsh", release)
        self.assertNotIn("linux-nsh-preview", release)
        self.assertIn("--manifest-path crates/bir-shell/Cargo.toml", live)
        self.assertIn("run: packaging/linux/build-packages.sh", live)
        self.assertNotIn("packaging/linux/preview/", live)

    def test_nsh_workflow_only_uploads_preview_run_artifacts(self) -> None:
        preview = (ROOT / ".github/workflows/preview-linux-nsh.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", preview)
        self.assertIn("workflow_dispatch:", preview)
        self.assertNotIn("workflow_call:", preview)
        self.assertNotIn("push:", preview)
        self.assertIn("contents: read", preview)
        self.assertIn("ubuntu-24.04-arm", preview)
        self.assertIn("version=${app_version}-pr", preview)
        self.assertIn("run: packaging/linux/preview/build-packages.sh", preview)
        self.assertIn("name: linux-nsh-preview-${{ matrix.arch }}", preview)
        self.assertNotIn("action-gh-release", preview)
