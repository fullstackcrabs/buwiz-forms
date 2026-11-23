import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "setup-linux-nsh.sh"


def function(name):
    source = SCRIPT.read_text()
    start = source.index(f"{name}() {{")
    return source[start:source.index("\n}", start) + 2]


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux-only Bash setup tests")
class LinuxNshSetupTests(unittest.TestCase):
    def test_runtime_requires_current_build_settings_and_all_artifacts(self):
        artifacts = ["classes.dex", "nsh-build"] + [
            f"lib/{abi}/libnsh.so" for abi in ("arm64-v8a", "armeabi-v7a", "x86_64")
        ]
        for case in ("valid", "empty", "stale", "other-ndk", "debug", *artifacts):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "tools/runtime/android/dev"
                dest.mkdir(parents=True)
                if case != "empty":
                    for artifact in artifacts:
                        if artifact != case:
                            file = dest / artifact
                            file.parent.mkdir(parents=True, exist_ok=True)
                            stamp = {"stale": "old\n27\n0\n",
                                     "other-ndk": "current\n28\n0\n",
                                     "debug": "current\n27\n2\n"}.get(case, "current\n27\n0\n")
                            file.write_text(stamp if artifact == "nsh-build" else "built")
                result = self.run_shell(function("android_runtime_stamp") + "\n" +
                                        function("nsh_android_runtime_current") + '''
WORK="$PWD"
REF=current
NDK_VERSION=27
ANDROID_RUNTIME_DEBUG=0
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
            result = self.run_shell(function("android_runtime_stamp") + "\n" +
                                    function("nsh_android_runtime_current") + "\n" +
                                    function("install_android_runtime") + r'''
WORK="$PWD"
NSH="$PWD/nsh"
REF=current
ANDROID_HOME="$PWD/sdk"
NDK_VERSION=27
ANDROID_RUNTIME_DEBUG=0
log() { :; }
die() { echo "$*" >&2; exit 1; }
sdk_mount() { :; }
in_image() {
    [[ " $* " == *" -e ANDROID_NDK_HOME=$ANDROID_HOME/ndk/27 "* ]]
    [[ " $* " == *" -e CARGO_PROFILE_DEV_DEBUG=0 "* ]]
    echo build >> builds
}
install_android_runtime
install_android_runtime
''', tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "builds").read_text(), "build\n")
            self.assertEqual((root / "tools/runtime/android/dev/nsh-build").read_text(),
                             "current\n27\n0\n")

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

    def run_shell(self, source, directory, *args):
        return subprocess.run(
            ["bash", "-euo", "pipefail", "-c", source, "test", *args],
            cwd=directory, text=True, capture_output=True,
            env={**os.environ, "JAVA_HOME": "/old-java-11"},
        )

    def test_wrapper_passes_literal_paths_and_pinned_ndk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / 'repo # & "quote" $(false)'
            sdk = root / 'SDK # & "quote" $HOME'
            (repo / "nsh").mkdir(parents=True)
            sdk.mkdir()
            bin_dir = root / "bin"
            bin_dir.mkdir()
            docker = bin_dir / "docker"
            docker.write_text('#!/bin/bash\nprintf "%s\\n" "$@"\n')
            docker.chmod(0o755)
            result = self.run_shell(
                "\n".join(function(name) for name in
                          ("outside_home", "sdk_mount", "write_wrapper")) + r'''
export HOME="$PWD/home" PATH="$PWD/bin:$PATH"
REPO="$1"
ANDROID_HOME="$2"
NDK_VERSION=27
WORK="$PWD"
MOUNTS=(-v "$HOME:$HOME")
write_wrapper
bash -n "$WORK/nsh2404.sh"
bash "$WORK/nsh2404.sh" nsh run --target android
''',
                tmp, str(repo), str(sdk),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            args = result.stdout.splitlines()
            self.assertIn(str(repo / "nsh"), args)
            self.assertIn(f"ANDROID_HOME={sdk}", args)
            self.assertIn(f"{sdk}:{sdk}", args)
            self.assertIn(f"ANDROID_NDK_HOME={sdk}/ndk/27", args)
            self.assertIn("BUWIZ_ANDROID_DEV_ENV=EBIR_TEST_ENV=1;"
                          "BUWIZ_NO_KEYCHAIN=1;BIR_SFTP_DRY_RUN=1", args)

    def test_sdk_selects_java_home_then_path_then_install(self):
        for case in ("home", "path", "old", "missing"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for home, major in (("custom-jdk", 21), ("path-jdk", 17 if case == "path" else 11)):
                    java = root / home / "bin/java"
                    java.parent.mkdir(parents=True)
                    java.write_text(f'#!/bin/bash\necho \'openjdk version "{major}.0.1"\' >&2\n'
                                    f'echo \'    java.home = {root / home}\' >&2\n')
                    java.chmod(0o755)
                tools = root / "sdk/cmdline-tools/latest/bin"
                tools.mkdir(parents=True)
                manager = tools / "sdkmanager"
                manager.write_text('#!/bin/bash\necho "$JAVA_HOME" >> java-used\n')
                manager.chmod(0o755)
                emulator = root / "sdk/emulator/emulator"
                emulator.parent.mkdir()
                emulator.write_text('#!/bin/bash\necho buwiz\n')
                emulator.chmod(0o755)
                result = self.run_shell(function("find_java_home") + "\n" +
                                        function("install_android_sdk") + f'\ncase={case}\n' + r'''
JAVA_HOME="$PWD/not-installed"
[ "$case" != home ] || JAVA_HOME="$PWD/custom-jdk"
command() {
    if [ "$*" = '-v java' ]; then
        [ "$case" != missing ] || return 1
        echo "$PWD/path-jdk/bin/java"
    else builtin command "$@"; fi
}
ANDROID_HOME="$PWD/sdk"
NDK_VERSION=27
SYSTEM_IMAGE=image
AVD=buwiz
SUDO=""
log() { :; }
unzip() { :; }
apt-get() {
    echo "$*" > apt-called
    mkdir -p "$PWD/jdk17/bin"; touch "$PWD/jdk17/bin/java"; chmod +x "$PWD/jdk17/bin/java"
}
dpkg-query() { echo "$PWD/jdk17/bin/javac"; }
rustup() { :; }
install_android_sdk
''', tmp)
                self.assertEqual(result.returncode, 0, result.stderr)
                selected = {"home": "custom-jdk", "path": "path-jdk"}.get(case, "jdk17")
                self.assertEqual((root / "java-used").read_text().splitlines(),
                                 [str(root / selected)] * 2)
                self.assertEqual((root / "apt-called").exists(), case in ("old", "missing"))


if __name__ == "__main__":
    unittest.main()
