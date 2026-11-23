"""Release-version manifest rewriting."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "set_release_version.py"
_SPEC = importlib.util.spec_from_file_location("set_release_version", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

set_version = _MODULE.set_version


class SetReleaseVersionTests(unittest.TestCase):
    def write_tree(self, root: Path, nsh_json: str | None = None) -> None:
        (root / "crates/bir-print").mkdir(parents=True)
        (root / "nsh").mkdir()
        (root / "Cargo.toml").write_text(
            '[workspace.package]\nversion = "0.2.0"\nedition = "2024"\n',
            encoding="utf-8",
        )
        (root / "crates/bir-print/Cargo.toml").write_text(
            '[package]\nname = "bir-print"\nversion = "0.2.0"\n',
            encoding="utf-8",
        )
        (root / "nsh/Cargo.toml").write_text(
            '[package]\nname = "nsh-app-ebirforms"\nversion = "0.2.0"\n',
            encoding="utf-8",
        )
        (root / "nsh/nsh.json").write_text(
            nsh_json
            if nsh_json is not None
            else '{\n  "name": "eBIRForms",\n  "version": "0.2.0",\n  "build": 27\n}\n',
            encoding="utf-8",
        )

    def test_updates_every_manifest_without_reformatting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_tree(root)
            set_version(root, "1.2.3")
            self.assertEqual(
                (root / "Cargo.toml").read_text(encoding="utf-8"),
                '[workspace.package]\nversion = "1.2.3"\nedition = "2024"\n',
            )
            self.assertEqual(
                (root / "crates/bir-print/Cargo.toml").read_text(encoding="utf-8"),
                '[package]\nname = "bir-print"\nversion = "1.2.3"\n',
            )
            self.assertEqual(
                (root / "nsh/Cargo.toml").read_text(encoding="utf-8"),
                '[package]\nname = "nsh-app-ebirforms"\nversion = "1.2.3"\n',
            )
            self.assertEqual(
                (root / "nsh/nsh.json").read_text(encoding="utf-8"),
                '{\n  "name": "eBIRForms",\n  "version": "1.2.3",\n  "build": 27\n}\n',
            )

    def test_refuses_a_non_semver_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_tree(root)
            with self.assertRaises(ValueError):
                set_version(root, "1.2")

    def test_a_missing_nsh_version_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_tree(root, '{\n  "name": "eBIRForms"\n}\n')
            cargo_before = (root / "Cargo.toml").read_bytes()
            with self.assertRaises(ValueError):
                set_version(root, "1.2.3")
            self.assertEqual((root / "Cargo.toml").read_bytes(), cargo_before)

    def test_a_missing_bir_print_manifest_is_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_tree(root)
            (root / "crates/bir-print/Cargo.toml").unlink()
            set_version(root, "1.2.3")
            self.assertIn('version = "1.2.3"', (root / "Cargo.toml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
