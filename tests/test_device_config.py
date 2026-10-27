from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class DeviceConfigTests(unittest.TestCase):
    def check_config(self, transform=lambda config: config, model='N60 Pro'):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            image = source / 'target/linux/mediatek/image/filogic.mk'
            image.parent.mkdir(parents=True)
            image.write_text(f'define Device/netcore_n60-pro\n  DEVICE_MODEL := {model}\nendef\n')
            config = (ROOT / 'configs/netcore-n60-pro.config').read_text()
            (source / '.config').write_text(transform(config))
            return subprocess.run(
                ['bash', str(ROOT / 'scripts/check-device.sh'), str(source)],
                text=True, capture_output=True,
            )

    def test_valid_n60_pro_config(self):
        result = self.check_config()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_device_rejected(self):
        for device in ['netcore_n60', 'netis_nx30v2']:
            with self.subTest(device=device):
                result = self.check_config(lambda config: config.replace('DEVICE_netcore_n60-pro=y', f'DEVICE_{device}=y'))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Invalid build config', result.stderr)

    def test_second_device_rejected(self):
        result = self.check_config(lambda config: config + 'CONFIG_TARGET_mediatek_filogic_DEVICE_netcore_n60=y\n')
        self.assertNotEqual(result.returncode, 0)

    def test_missing_ssh_packages_rejected(self):
        for package in ['openssh-server', 'openssh-client', 'openssh-keygen', 'openssh-sftp-server']:
            with self.subTest(package=package):
                result = self.check_config(lambda config: config.replace(f'CONFIG_PACKAGE_{package}=y\n', ''))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f'CONFIG_PACKAGE_{package}=y', result.stderr)

    def test_dropbear_reenabled_by_dependencies_rejected(self):
        for selection in ['y', 'm']:
            with self.subTest(selection=selection):
                result = self.check_config(lambda config: config + f'CONFIG_PACKAGE_dropbear={selection}\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('dropbear_enabled=True', result.stderr)

    def test_upstream_model_mismatch_rejected(self):
        result = self.check_config(model='N60')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('does not explicitly support', result.stderr)


if __name__ == '__main__':
    unittest.main()
