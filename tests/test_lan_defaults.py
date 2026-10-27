import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
PENDING = '/etc/uci-defaults/.99-custom-lan.pending'

# Model UCI's volatile deltas separately from files saved by commit.
MOCK_UCI = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
path = Path(os.environ['TEST_UCI_STATE'])
state = json.loads(path.read_text())
args = [arg for arg in sys.argv[1:] if arg != '-q']
operation = ' '.join(args)
if state.get('fail_once') == operation:
    state.pop('fail_once')
    path.write_text(json.dumps(state))
    sys.exit(1)
command = args[0]
values = dict(state['committed'], **state['pending'])
if command == 'get':
    value = values.get(args[1])
    if value is None:
        sys.exit(1)
    print(value)
elif command == 'show':
    for key, value in values.items():
        if key.startswith(args[1] + '.') and value is not None:
            print(key + '=' + value)
elif command == 'delete':
    if values.get(args[1]) is None:
        sys.exit(1)
    state['pending'][args[1]] = None
elif command in ('set', 'add_list'):
    key, value = args[1].split('=', 1)
    if command == 'add_list' and values.get(key) is not None:
        value = values[key] + ' ' + value
    state['pending'][key] = value
elif command == 'commit':
    for key in list(state['pending']):
        if key.startswith(args[1] + '.'):
            value = state['pending'].pop(key)
            if value is None:
                state['committed'].pop(key, None)
            else:
                state['committed'][key] = value
else:
    sys.exit(1)
path.write_text(json.dumps(state))
'''


class LanDefaultsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / 'state.json'
        self.marker = self.root / 'pending'
        self.script = self.root / 'initializer'
        source = (ROOT / 'files/etc/uci-defaults/99-custom-lan').read_text()
        self.assertIn(PENDING, source)
        self.script.write_text(source.replace(PENDING, str(self.marker)))
        mock = self.root / 'uci'
        mock.write_text(MOCK_UCI)
        mock.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ['PATH'], TEST_UCI_STATE=str(self.state))

    def initialize(self, address='192.168.1.1/24', failure=None):
        values = {'dhcp.lan.start': '20', 'dhcp.lan.limit': '50'}
        if address is not None:
            values['network.lan.ipaddr'] = address
            values['network.lan.netmask'] = '255.255.255.0'
        self.state.write_text(json.dumps({'committed': values, 'pending': {}, 'fail_once': failure}))
        self.marker.unlink(missing_ok=True)

    def run_script(self):
        return subprocess.run(['sh', str(self.script)], env=self.env).returncode

    def assert_complete(self):
        state = json.loads(self.state.read_text())
        self.assertEqual(state['committed'], {
            'network.lan.ipaddr': '192.168.6.1/24',
            'dhcp.lan.start': '100', 'dhcp.lan.limit': '150',
        })
        self.assertEqual(state['pending'], {})
        self.assertFalse(self.marker.exists())

    def test_scalar_and_cidr_defaults(self):
        for address in ['192.168.1.1', '192.168.1.1/24']:
            with self.subTest(address=address):
                self.initialize(address)
                self.assertEqual(self.run_script(), 0)
                self.assert_complete()

    def test_custom_addresses_and_dhcp_are_preserved(self):
        for address in ['192.168.6.1/24', '192.168.6.1', '10.0.0.1/24', '192.168.11.1/24']:
            with self.subTest(address=address):
                self.initialize(address)
                original = json.loads(self.state.read_text())['committed']
                self.assertEqual(self.run_script(), 0)
                self.assertEqual(json.loads(self.state.read_text())['committed'], original)
                self.assertFalse(self.marker.exists())

    def test_retries_failed_mutations_with_and_without_reboot(self):
        failures = ['delete network.lan.ipaddr', 'add_list network.lan.ipaddr=192.168.6.1/24',
                    'set dhcp.lan.start=100', 'set dhcp.lan.limit=150',
                    'commit network', 'commit dhcp']
        for failure in failures:
            for reboot in [False, True]:
                with self.subTest(failure=failure, reboot=reboot):
                    self.initialize(failure=failure)
                    self.assertNotEqual(self.run_script(), 0)
                    self.assertTrue(self.marker.exists())
                    if reboot:
                        state = json.loads(self.state.read_text())
                        state['pending'] = {}
                        self.state.write_text(json.dumps(state))
                    self.assertEqual(self.run_script(), 0)
                    self.assert_complete()

    def test_missing_address_is_not_silently_accepted(self):
        self.initialize(address=None)
        self.assertNotEqual(self.run_script(), 0)
        self.assertFalse(self.marker.exists())

    def test_transient_read_failure_can_retry(self):
        self.initialize(failure='get network.lan.ipaddr')
        self.assertNotEqual(self.run_script(), 0)
        self.assertEqual(self.run_script(), 0)
        self.assert_complete()

    def test_transient_read_failure_during_resume_is_retried_safely(self):
        self.initialize(failure='commit dhcp')
        self.assertNotEqual(self.run_script(), 0)
        state = json.loads(self.state.read_text())
        state['fail_once'] = 'get network.lan.ipaddr'
        self.state.write_text(json.dumps(state))
        self.assertNotEqual(self.run_script(), 0)
        self.assertTrue(self.marker.exists())
        self.assertEqual(self.run_script(), 0)
        self.assert_complete()

    def test_custom_address_after_failure_is_preserved(self):
        self.initialize(failure='commit dhcp')
        self.assertNotEqual(self.run_script(), 0)
        state = json.loads(self.state.read_text())
        state['pending'] = {}
        state['committed']['network.lan.ipaddr'] = '10.0.0.1/24'
        self.state.write_text(json.dumps(state))
        self.assertEqual(self.run_script(), 0)
        self.assertEqual(json.loads(self.state.read_text())['committed'], state['committed'])
        self.assertFalse(self.marker.exists())

    def test_successful_initializer_does_not_reset_later_dhcp_changes(self):
        self.initialize()
        self.assertEqual(self.run_script(), 0)
        state = json.loads(self.state.read_text())
        state['committed']['dhcp.lan.start'] = '42'
        self.state.write_text(json.dumps(state))
        self.assertEqual(self.run_script(), 0)
        self.assertEqual(json.loads(self.state.read_text())['committed']['dhcp.lan.start'], '42')


if __name__ == '__main__':
    unittest.main()
