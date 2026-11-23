import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PREVIEW = ROOT / '.github/workflows/package-nsh-windows.yml'


class NshWindowsReleaseTests(unittest.TestCase):
    def test_packaging_is_reusable_and_does_not_publish(self):
        workflow = PREVIEW.read_text()
        self.assertIn('workflow_dispatch:', workflow)
        self.assertIn('workflow_call:', workflow)
        self.assertIn('nsh package --target windows', workflow)
        self.assertIn('actions/upload-artifact@v4', workflow)
        self.assertNotIn('contents: write', workflow)
        self.assertNotIn('gh-release', workflow)
        self.assertNotIn('bir-shell', workflow)

    def test_tagged_release_keeps_the_legacy_windows_app(self):
        ci = (ROOT / '.github/workflows/ci.yml').read_text()
        release = (ROOT / '.github/workflows/release.yml').read_text()
        public_windows = (ROOT / '.github/workflows/release-windows.yml').read_text()
        self.assertIn('uses: ./.github/workflows/package-nsh-windows.yml', ci)
        self.assertNotIn('package-nsh-windows', release)
        self.assertIn('uses: ./.github/workflows/release-windows.yml', release)
        self.assertIn('crates/bir-shell/Cargo.toml', public_windows)
        self.assertNotIn('windows-nsh-preview', release)
        self.assertNotIn('artifacts/**/*-windows-x86_64.zip', release)

    def test_setup_and_updater_zip_do_not_require_a_vc_redistributable(self):
        workflow = PREVIEW.read_text()
        msix = (ROOT / 'scripts/package_msix.ps1').read_text()
        self.assertIn('CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_RUSTFLAGS: "-C target-feature=+crt-static"', workflow)
        self.assertIn('if ($NshPayload -and $runtimeImports.Count -gt 0)', msix)
        self.assertIn('if (-not $NshPayload -and $runtimeImports.Count -eq 0)', msix)

    def test_nsh_feed_does_not_replace_the_legacy_manifest(self):
        updater = json.loads((ROOT / 'nsh/nsh.json').read_text(encoding='utf-8'))['updater']
        name = updater['url'].rsplit('/', 1)[-1]
        self.assertEqual(name, 'latest-nsh.json')
        self.assertNotIn('github', updater)
        preview = PREVIEW.read_text()
        release = (ROOT / '.github/workflows/release.yml').read_text()
        for asset in (name, 'latest.json.sig'):
            self.assertNotIn(asset, preview)
            self.assertNotIn(asset, release)
        self.assertIn('NshSignedUpdateTests', preview)
        self.assertIn('scripts/publish_update_manifest.py', release)

    @unittest.skipUnless(shutil.which('pwsh'), 'requires PowerShell')
    def test_missing_key_does_not_publish_an_unsigned_feed(self):
        with tempfile.TemporaryDirectory() as scratch:
            archive = Path(scratch) / 'eBIRForms-0.2.0-windows-x86_64.zip'
            archive.touch()
            result = subprocess.run(
                ['pwsh', '-NoProfile', '-File', str(ROOT / 'scripts/package_nsh_update.ps1'),
                 '-Archive', str(archive), '-BaseUrl', 'https://example.com/releases/v0.2.0'],
                env={**os.environ, 'NSH_UPDATE_SIGNING_KEY': ''},
                capture_output=True, text=True, check=True, timeout=20,
            )
            self.assertIn('NSH_UPDATE_SIGNING_KEY', result.stdout)
            self.assertEqual(list(archive.parent.iterdir()), [archive])

    @unittest.skipUnless(shutil.which('pwsh'), 'requires PowerShell')
    def test_invalid_version_tag_or_payload_fails_before_packaging(self):
        cases = (
            ('0.2.00', 'v0.2.00', '0.2.00', 'demo.id', 'Invalid Windows release version'),
            ('256.0.0', 'v256.0.0', '256.0.0', 'demo.id', 'exceeds MSI limits'),
            ('0.2.0', 'v0.2.1', '0.2.0', 'demo.id', 'does not match Windows app version'),
            ('0.2.0', 'v0.2.0', '0.2.1', 'demo.id', 'payload identity or version does not match'),
            ('0.2.0', 'v0.2.0', '0.2.0', 'other.id', 'payload identity or version does not match'),
        )
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            script = scratch / 'scripts/package_nsh_windows.ps1'
            script.parent.mkdir()
            shutil.copyfile(ROOT / 'scripts/package_nsh_windows.ps1', script)
            config = scratch / 'nsh/nsh.json'
            config.parent.mkdir()
            package = scratch / 'package'
            app = package / 'eBIRForms/nsh/app.json'
            app.parent.mkdir(parents=True)
            out = scratch / 'out'
            for version, tag, app_version, app_id, error in cases:
                with self.subTest(version=version, tag=tag, app_version=app_version, app_id=app_id):
                    config.write_text(json.dumps({'version': version, 'id': 'demo.id'}), encoding='utf-8')
                    app.write_text(json.dumps({'version': app_version, 'id': app_id}), encoding='utf-8')
                    result = subprocess.run(
                        ['pwsh', '-NoProfile', '-File', str(script), '-PackageRoot', str(package), '-OutDir', str(out)],
                        env={**os.environ, 'GITHUB_REF_TYPE': 'tag', 'GITHUB_REF_NAME': tag, 'NO_COLOR': '1'},
                        capture_output=True, text=True, timeout=20,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(error, result.stderr)
                    self.assertFalse(out.exists())

    def test_msi_has_new_per_user_identity_and_distinct_install_directory(self):
        ns = {'w': 'http://schemas.microsoft.com/wix/2006/wi'}
        product = ET.parse(ROOT / 'packaging/windows/nsh.wxs').find('w:Product', ns)
        self.assertNotEqual(product.attrib['UpgradeCode'], 'e8a5f36b-9c17-4e62-9721-a1b2c3d4e5f6')
        self.assertEqual(product.find('w:Package', ns).attrib['InstallScope'], 'perUser')
        self.assertIsNotNone(product.find('.//w:Directory[@Id="LocalAppDataFolder"]', ns))
        self.assertIsNotNone(product.find('.//w:Directory[@Id="INSTALLDIR"][@Name="eBIRForms MSI"]', ns))
        self.assertIsNotNone(product.find('.//w:RegistryValue[@Root="HKCU"][@KeyPath="yes"]', ns))


@unittest.skipUnless(shutil.which('nsh') and shutil.which('pwsh'), 'requires the pinned NSH CLI and PowerShell')
class NshSignedUpdateTests(unittest.TestCase):
    def test_signs_windows_zip_for_custom_feed_and_rejects_wrong_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key, wrong_key = root / 'test', root / 'wrong'
            for path in (key, wrong_key):
                subprocess.run(['nsh', 'keygen', str(path)], check=True, capture_output=True, timeout=20)

            app = root / 'app'
            app.mkdir()
            (app / 'App.tsx').touch()
            version = '0.2.1'
            app_id = 'dev.goldcoders.bir'
            release_url = 'https://example.com/releases'
            config = {
                'name': 'eBIRForms', 'id': app_id, 'version': version,
                'updater': {
                    'url': f'{release_url}/latest/download/latest-nsh.json',
                    'publicKey': key.with_suffix('.pub').read_text(encoding='utf-8').strip(),
                },
            }
            (app / 'nsh.json').write_text(json.dumps(config), encoding='utf-8')
            base_url = f'{release_url}/download/v{version}'

            for signing_key in (key, wrong_key):
                with self.subTest(key=signing_key.name):
                    output = root / f'out-{signing_key.name}'
                    output.mkdir()
                    archive = output / f'eBIRForms-{version}-windows-x86_64.zip'
                    with zipfile.ZipFile(archive, 'w') as package:
                        package.writestr('eBIRForms/nsh/app.json', json.dumps(config))
                    result = subprocess.run(
                        ['pwsh', '-NoProfile', '-File', str(ROOT / 'scripts/package_nsh_update.ps1'),
                         '-Archive', str(archive), '-BaseUrl', base_url, '-AppDir', str(app)],
                        env={**os.environ, 'NO_COLOR': '1',
                             'NSH_UPDATE_SIGNING_KEY': signing_key.with_suffix('.secret').read_text(encoding='utf-8').strip()},
                        capture_output=True, text=True, timeout=20,
                    )
                    if signing_key == wrong_key:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('not the key', result.stderr)
                        self.assertEqual(list(output.iterdir()), [archive])
                        continue

                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual({file.name for file in output.iterdir()},
                                     {archive.name, 'latest-nsh.json', 'latest.json.sig'})
                    self.assertTrue((output / 'latest.json.sig').read_bytes().strip())
                    manifest = json.loads((output / 'latest-nsh.json').read_text(encoding='utf-8'))
                    self.assertEqual((manifest['id'], manifest['version']), (app_id, version))
                    self.assertEqual(manifest['platforms'], {
                        'windows-x86_64': {
                            'url': f'{base_url}/{archive.name}',
                            'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                            'size': archive.stat().st_size,
                        },
                    })


if __name__ == '__main__':
    unittest.main()
