import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "setup-linux-nsh.sh"


def function(name):
    source = SCRIPT.read_text()
    start = source.index(f"{name}() {{")
    return source[start:source.index("\n}", start) + 2]


class LinuxNshSetupTests(unittest.TestCase):
    def run_shell(self, source, directory):
        return subprocess.run(
            ["bash", "-euo", "pipefail", "-c", source],
            cwd=directory, text=True, capture_output=True,
            env={**os.environ, "JAVA_HOME": "/old-java-11"},
        )

    def test_sdk_uses_java_17_even_with_java_11_on_path(self):
        for installed in (False, True):
            with self.subTest(installed=installed), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                java = root / "jdk17/bin/java"
                java.parent.mkdir(parents=True)
                if installed:
                    java.touch(mode=0o755)
                tools = root / "sdk/cmdline-tools/latest/bin"
                tools.mkdir(parents=True)
                manager = tools / "sdkmanager"
                manager.write_text('#!/bin/bash\necho "$JAVA_HOME" >> java-used\n')
                manager.chmod(0o755)
                emulator = root / "sdk/emulator/emulator"
                emulator.parent.mkdir()
                emulator.write_text('#!/bin/bash\necho buwiz\n')
                emulator.chmod(0o755)
                result = self.run_shell(function("install_android_sdk") + r'''
JAVA_HOME_IMAGE="$PWD/jdk17"
ANDROID_HOME="$PWD/sdk"
NDK_VERSION=27
SYSTEM_IMAGE=image
AVD=buwiz
SUDO=""
log() { :; }
java() { echo 'java version "11"' >&2; }
unzip() { :; }
apt-get() { echo "$*" > apt-called; touch "$JAVA_HOME_IMAGE/bin/java"; chmod +x "$JAVA_HOME_IMAGE/bin/java"; }
rustup() { :; }
install_android_sdk
''', tmp)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((root / "java-used").read_text().splitlines(),
                                 [str(root / "jdk17")] * 2)
                self.assertEqual((root / "apt-called").exists(), not installed)


if __name__ == "__main__":
    unittest.main()
