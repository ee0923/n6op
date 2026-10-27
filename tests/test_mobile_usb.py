import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_lan_defaults import MOCK_UCI

ROOT = Path(__file__).resolve().parent.parent
# Extend the existing UCI transaction fixture with named-section merge import.
MOCK = MOCK_UCI.replace("elif command == 'commit':", '''elif command == 'import':
    import shlex
    package = args[-1]
    section = None
    for line in sys.stdin:
        fields = shlex.split(line, comments=True)
        if not fields:
            continue
        if fields[0] == 'config':
            section = package + '.' + fields[2]
            state['pending'][section] = fields[1]
        elif fields[0] in ('option', 'list'):
            key = section + '.' + fields[1]
            state['pending'][key] = fields[2]
elif command == 'commit':''')


class MobileUsbTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = self.root / 'uci.json'
        self.log = self.root / 'ip.jsonl'
        (self.root / 'uci').write_text(MOCK)
        (self.root / 'uci').chmod(0o755)
        (self.root / 'ip').write_text('''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['TEST_IP_LOG'], 'a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
if os.environ.get('TEST_IP_FAIL') == '1':
    sys.exit(1)
''')
        (self.root / 'ip').chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ['PATH'],
                        TEST_UCI_STATE=str(self.state), TEST_IP_LOG=str(self.log))
        self.reset()

    def reset(self, values=None, failure=None):
        self.state.write_text(json.dumps({'committed': values or {}, 'pending': {}, 'fail_once': failure}))

    def run_file(self, name, event=None, **env):
        args = ['sh', str(ROOT / 'files' / name)] + ([event] if event else [])
        return subprocess.run(args, env=dict(self.env, **env), capture_output=True, text=True)

    def initialize(self):
        result = self.run_file('etc/uci-defaults/90-mobile-usb')
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(self.state.read_text())['committed']

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_network_is_opt_in_per_socket_and_mobile_is_not_a_lan_forward(self):
        values = self.initialize()
        self.assertEqual(values['network.mobile.device'], 'usb0')
        for option in ['defaultroute', 'peerdns', 'ipv6', 'delegate', 'classlessroute']:
            self.assertEqual(values['network.mobile.' + option], '0')
        self.assertNotIn('network.mobile.ip4table', values)  # no netifd automatic local fallback
        self.assertEqual(values['network.mobile_lookup.mark'], '106/0xffffffff')
        self.assertEqual(values['network.mobile_lookup.lookup'], '106')
        self.assertLess(int(values['network.mobile_lookup.priority']), int(values['network.mobile_reject.priority']))
        self.assertEqual(values['network.mobile_reject.action'], 'unreachable')
        self.assertEqual(values['network.mobile_reject6.action'], 'unreachable')
        self.assertEqual(values['firewall.mobile_usb.input'], 'REJECT')
        self.assertEqual(values['firewall.mobile_usb.forward'], 'REJECT')
        self.assertEqual(values['firewall.mobile_usb.masq'], '1')
        self.assertEqual(values['firewall.mobile_usb_dhcp.dest_port'], '68')
        self.assertNotIn('forwarding', values.values())

    def test_unrelated_settings_and_custom_mobile_interface_are_preserved(self):
        original = {'network.lan.ipaddr': '192.168.6.1/24', 'network.wan.device': 'eth1'}
        self.reset(original)
        values = self.initialize()
        self.assertTrue(original.items() <= values.items())
        for section in ['network.mobile', 'network.mobile_lookup', 'firewall.mobile_usb']:
            custom = dict(original, **{section: 'interface', section + '.device': 'custom0'})
            self.reset(custom)
            self.assertEqual(self.initialize(), custom)

    def test_upgrades_preserve_customized_owned_sections(self):
        values = self.initialize()
        values['network.mobile.device'] = 'eth2'
        values['firewall.mobile_usb.mtu_fix'] = '0'
        self.reset(values)
        self.assertEqual(self.initialize(), values)

    def test_partial_commit_retries_after_reboot(self):
        self.reset(failure='commit firewall')
        result = self.run_file('etc/uci-defaults/90-mobile-usb')
        self.assertNotEqual(result.returncode, 0)
        state = json.loads(self.state.read_text())
        state['pending'] = {}
        self.state.write_text(json.dumps(state))
        values = self.initialize()
        self.assertEqual(values['firewall.mobile_usb.network'], 'mobile')
        self.assertEqual(json.loads(self.state.read_text())['pending'], {})

    def lease(self, event='bound', **env):
        return self.run_file('etc/udhcpc.user.d/70-mobile-usb', event,
                             **dict(dict(INTERFACE='mobile', interface='usb0', router='192.168.42.129',
                                         ip='192.168.42.2'), **env))

    def test_lease_renewal_uses_actual_device_and_only_reserved_table(self):
        self.initialize()
        for event in ['bound', 'renew']:
            self.log.unlink(missing_ok=True)
            self.assertEqual(self.lease(event, interface='eth2', router='192.168.42.129 192.168.42.130').returncode, 0)
            self.assertEqual(self.calls(), [
                ['-4', 'route', 'replace', 'unreachable', 'default', 'table', '106'],
                ['-4', 'route', 'replace', 'table', '106', 'default', 'via', '192.168.42.129',
                 'dev', 'eth2', 'onlink', 'src', '192.168.42.2'],
            ])

    def test_missing_gateway_and_disconnect_remove_old_route(self):
        self.initialize()
        for event in ['renew', 'deconfig']:
            self.log.unlink(missing_ok=True)
            self.assertEqual(self.lease(event, router='').returncode, 0)
            self.assertEqual(self.calls(), [['-4', 'route', 'replace', 'unreachable', 'default', 'table', '106']])
        self.log.unlink()
        self.assertEqual(self.run_file('etc/hotplug.d/iface/70-mobile-usb', INTERFACE='mobile', ACTION='ifdown').returncode, 0)
        self.assertEqual(self.calls(), [['-4', 'route', 'replace', 'unreachable', 'default', 'table', '106']])

    def test_other_interfaces_and_custom_mobile_interfaces_are_untouched(self):
        self.initialize()
        self.assertEqual(self.lease(INTERFACE='wan').returncode, 0)
        self.assertEqual(self.calls(), [])
        self.reset({'network.mobile': 'interface'})
        self.assertEqual(self.lease().returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_route_failure_is_reported(self):
        self.initialize()
        self.assertNotEqual(self.lease(TEST_IP_FAIL='1').returncode, 0)
