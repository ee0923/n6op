import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('firmware', ROOT / 'scripts/check-firmware.py')
firmware = importlib.util.module_from_spec(spec)
spec.loader.exec_module(firmware)

# Independent fixture so deleting a production requirement cannot weaken this test.
PACKAGES = '''base-files
openssh-server
openssh-client
openssh-keygen
openssh-sftp-server
nikki
luci-app-nikki
luci-i18n-nikki-zh-cn
mihomo-meta
luci
luci-ssl
luci-theme-argon
luci-i18n-base-zh-cn
luci-i18n-firewall-zh-cn'''.splitlines()


class FirmwareManifestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.target = Path(temporary.name)
        prefix = 'immortalwrt-mediatek-filogic-netcore_n60-pro'
        self.image = self.target / (prefix + '-squashfs-sysupgrade.itb')
        self.image.write_bytes(b'fixture image, not flashable')
        self.manifest = self.target / (prefix + '.manifest')
        self.write_packages(PACKAGES)

    def write_packages(self, packages):
        self.manifest.write_text(''.join(f'{package} - 1.0-r1\n' for package in packages))

    def test_complete_firmware_is_accepted(self):
        self.assertEqual(firmware.verify(self.target), (self.image, self.manifest))

    def test_required_packages_cannot_be_missing(self):
        for package in PACKAGES[1:]:
            with self.subTest(package=package):
                self.write_packages([item for item in PACKAGES if item != package])
                with self.assertRaisesRegex(ValueError, package):
                    firmware.verify(self.target)

    def test_dropbear_in_image_is_rejected(self):
        self.write_packages(PACKAGES + ['dropbear'])
        with self.assertRaisesRegex(ValueError, 'dropbear=True'):
            firmware.verify(self.target)

    def test_missing_and_empty_image_are_rejected(self):
        self.image.write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'nonempty'):
            firmware.verify(self.target)
        self.image.unlink()
        with self.assertRaisesRegex(ValueError, 'nonempty'):
            firmware.verify(self.target)

    def test_manifest_from_other_device_cannot_satisfy_check(self):
        self.manifest.rename(self.target / 'immortalwrt-netis_nx30v2.manifest')
        with self.assertRaisesRegex(ValueError, 'package manifest'):
            firmware.verify(self.target)

    def test_manifest_from_different_build_cannot_satisfy_check(self):
        self.manifest.rename(self.target / ('other-' + self.manifest.name))
        with self.assertRaisesRegex(ValueError, 'prefixes'):
            firmware.verify(self.target)

    def test_ambiguous_manifests_are_rejected(self):
        (self.target / ('other-' + self.manifest.name)).write_text(self.manifest.read_text())
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            firmware.verify(self.target)

    def test_malformed_manifest_is_rejected(self):
        self.manifest.write_text(self.manifest.read_text() + 'openssh-server\n')
        with self.assertRaisesRegex(ValueError, 'Invalid package manifest'):
            firmware.verify(self.target)


if __name__ == '__main__':
    unittest.main()
