from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "bump_build.py"
SPEC = importlib.util.spec_from_file_location("bump_build", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
bump_build = importlib.util.module_from_spec(SPEC)
with mock.patch.dict(sys.modules, {"jwt": mock.Mock(), "requests": mock.Mock()}):
    SPEC.loader.exec_module(bump_build)


class BumpBuildTests(unittest.TestCase):
    def test_print_next_does_not_modify_tracked_build_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            justfile = root / "justfile"
            original = 'BUILD_NUMBER := env_var_or_default("BUILD_NUMBER", "26")\n'
            justfile.write_text(original, encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(root)
                stdout = io.StringIO()
                stderr = io.StringIO()
                with (
                    mock.patch.object(bump_build, "get_latest_build", return_value=41),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    result = bump_build.main(["--print-next"])
            finally:
                os.chdir(previous)

            self.assertEqual(result, 0)
            self.assertEqual(stdout.getvalue(), "42\n")
            self.assertIn("Fetching latest build number", stderr.getvalue())
            self.assertEqual(justfile.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
