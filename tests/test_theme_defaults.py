import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "files/etc/uci-defaults/30_luci-theme-argon"


class ThemeDefaultsTests(unittest.TestCase):
    def run_initializer(self, theme):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "luci.json"
            state.write_text(json.dumps({"luci.main.mediaurlbase": theme}))
            mock = root / "uci"
            mock.write_text('''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
path = Path(os.environ['TEST_UCI_STATE'])
state = json.loads(path.read_text())
args = [arg for arg in sys.argv[1:] if arg != '-q']
if args[0] == 'get':
    if args[1] not in state:
        sys.exit(1)
    print(state[args[1]])
elif args[0] == 'set':
    key, value = args[1].split('=', 1)
    state[key] = value
    path.write_text(json.dumps(state))
elif args[0] == 'commit':
    pass
else:
    sys.exit(1)
''')
            mock.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"], TEST_UCI_STATE=str(state))
            subprocess.run(["sh", str(SCRIPT)], env=env, check=True)
            result = json.loads(state.read_text())
            self.assertEqual(result["luci.themes.Argon"], "/luci-static/argon")
            return result["luci.main.mediaurlbase"]

    def test_stock_or_unset_theme_uses_argon(self):
        for theme in ["", "/luci-static/bootstrap", "/luci-static/openwrt2020"]:
            with self.subTest(theme=theme):
                self.assertEqual(self.run_initializer(theme), "/luci-static/argon")

    def test_user_theme_is_preserved(self):
        for theme in ["/luci-static/argon", "/luci-static/material", "/luci-static/design"]:
            with self.subTest(theme=theme):
                self.assertEqual(self.run_initializer(theme), theme)


if __name__ == "__main__":
    unittest.main()
