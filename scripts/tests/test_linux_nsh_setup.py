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
    def test_runtime_requires_current_pin_and_all_artifacts(self):
        artifacts = ["classes.dex", "nsh-ref"] + [
            f"lib/{abi}/libnsh.so" for abi in ("arm64-v8a", "armeabi-v7a", "x86_64")
        ]
        for case in ("valid", "empty", "stale", *artifacts):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "tools/runtime/android/dev"
                dest.mkdir(parents=True)
                if case != "empty":
                    for artifact in artifacts:
                        if artifact != case:
                            file = dest / artifact
                            file.parent.mkdir(parents=True, exist_ok=True)
                            file.write_text("old" if artifact == "nsh-ref" and case == "stale"
                                            else "current")
                result = self.run_shell(function("nsh_android_runtime_current") + '''
WORK="$PWD"
REF=current
nsh_android_runtime_current
''', tmp)
                self.assertEqual(result.returncode == 0, case == "valid", result.stderr)

    def test_runtime_install_writes_pin_and_skips_current_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / "nsh/target/android/debug-dev"
            for artifact in ("classes.dex", "lib/arm64-v8a/libnsh.so",
                             "lib/armeabi-v7a/libnsh.so", "lib/x86_64/libnsh.so"):
                file = runtime / artifact
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("built")
            result = self.run_shell(function("nsh_android_runtime_current") + "\n" +
                                    function("install_android_runtime") + r'''
WORK="$PWD"
NSH="$PWD/nsh"
REF=current
ANDROID_HOME="$PWD/sdk"
JAVA_HOME_IMAGE=jdk17
log() { :; }
die() { echo "$*" >&2; exit 1; }
sdk_mount() { :; }
in_image() { echo build >> builds; }
install_android_runtime
install_android_runtime
''', tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "builds").read_text(), "build\n")
            self.assertEqual((root / "tools/runtime/android/dev/nsh-ref").read_text(),
                             "current\n")

    def test_checkout_accepts_git_directory_or_worktree_file(self):
        for linked in (False, True):
            with self.subTest(linked=linked), tempfile.TemporaryDirectory() as tmp:
                git = Path(tmp) / ".git"
                if linked:
                    git.write_text("gitdir: elsewhere\n")
                else:
                    git.mkdir()
                result = self.run_shell(function("checkout_nsh") + r'''
NSH="$PWD"
REF=current
git() { [ "$*" = "-C $NSH rev-parse HEAD" ]; echo current; }
checkout_nsh
''', tmp)
                self.assertEqual(result.returncode, 0, result.stderr)

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
