from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SSHD = shutil.which('sshd') or ('/usr/sbin/sshd' if Path('/usr/sbin/sshd').exists() else None)


@unittest.skipUnless(SSHD and shutil.which('ssh-keygen'), 'Host OpenSSH server and keygen are required')
class SshDefaultsTests(unittest.TestCase):
    def test_effective_server_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'sshd_config.d').mkdir()
            # Use isolated includes and disposable host keys, never the host's SSH configuration.
            config = root / 'sshd_config'
            config.write_text((ROOT / 'files/etc/ssh/sshd_config').read_text().replace('/etc/ssh/', str(root) + '/'))
            for kind in ['rsa', 'ed25519']:
                subprocess.run(['ssh-keygen', '-q', '-t', kind, '-N', '',
                                '-f', str(root / f'ssh_host_{kind}_key')], check=True)
            result = subprocess.run([str(Path(SSHD).resolve()), '-T', '-f', str(config)],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            values = {}
            for line in result.stdout.splitlines():
                key, _, value = line.partition(' ')
                # OpenSSH 9.6 appends a space to Subsystem output.
                values.setdefault(key, []).append(value.rstrip())
            expected = {
                'port': ['22'],
                'permitrootlogin': ['yes'],
                'pubkeyauthentication': ['yes'],
                'passwordauthentication': ['yes'],
                'permitemptypasswords': ['no'],
                'authorizedkeysfile': ['.ssh/authorized_keys /etc/dropbear/authorized_keys'],
                'subsystem': ['sftp /usr/lib/sftp-server'],
                'hostkey': [str(root / 'ssh_host_ed25519_key'), str(root / 'ssh_host_rsa_key')],
            }
            for key, value in expected.items():
                with self.subTest(directive=key):
                    self.assertEqual(values.get(key), value)


if __name__ == '__main__':
    unittest.main()
