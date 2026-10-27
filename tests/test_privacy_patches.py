import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('privacy', ROOT / 'scripts/privacy-patch.py')
privacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(privacy)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class PrivacyPatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        self.patch_dir = self.root / 'patches'
        self.patch_dir.mkdir()
        self.series = {'version': 1, 'patches': [], 'mihomo': {'files': []}}

    def add_patch(self, name, before, after):
        scope = self.source / 'feeds' / name
        scope.mkdir(parents=True)
        (scope / 'config').write_text(before)
        filename = name + '.patch'
        patch = ''.join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile='a/config', tofile='b/config'))
        (self.patch_dir / filename).write_text(patch)
        self.series['patches'].append({'name': name, 'scope': name, 'patch': filename,
                                      'files': [{'path': 'config', 'before': digest(before), 'after': digest(after)}]})
        self.save_series()
        return scope / 'config'

    def save_series(self):
        (self.patch_dir / 'series.json').write_text(json.dumps(self.series))

    def test_nikki_application_and_luci_are_not_customized(self):
        series = json.loads((ROOT / 'patches/privacy/series.json').read_text())
        for entry in series['patches']:
            if entry['scope'] != 'nikki':
                continue
            declared = {item['path'] for item in entry['files']}
            patch = (ROOT / 'patches/privacy' / entry['patch']).read_text()
            changed = set(re.findall(r'^\+\+\+ b/(.+)$', patch, re.M))
            self.assertEqual(declared, changed)
            self.assertTrue(all(path.startswith('mihomo-meta/') for path in changed))
        for directory in ['files/etc/nikki', 'files/www/luci-static/resources/view/nikki']:
            self.assertEqual([p for p in (ROOT / directory).rglob('*') if p.is_file()], [])

    def test_apply_is_repeatable_and_verify_checks_result(self):
        path = self.add_patch('theme', 'network = yes\n', 'network = no\n')
        privacy.process(self.source, apply=True, patch_dir=self.patch_dir)
        self.assertEqual(path.read_text(), 'network = no\n')
        privacy.process(self.source, apply=True, patch_dir=self.patch_dir)
        privacy.process(self.source, patch_dir=self.patch_dir)

    def test_source_drift_is_rejected_before_any_group_changes(self):
        first = self.add_patch('theme', 'network = yes\n', 'network = no\n')
        second = self.add_patch('proxy', 'update = yes\n', 'update = no\n')
        second.write_text('unexpected upstream change\n')
        with self.assertRaisesRegex(ValueError, 'Audited source changed'):
            privacy.process(self.source, apply=True, patch_dir=self.patch_dir)
        self.assertEqual(first.read_text(), 'network = yes\n')

    def test_invalid_later_patch_cannot_leave_first_group_applied(self):
        first = self.add_patch('theme', 'network = yes\n', 'network = no\n')
        self.add_patch('proxy', 'update = yes\n', 'update = no\n')
        (self.patch_dir / 'proxy.patch').write_text('invalid diff\n')
        with self.assertRaisesRegex(ValueError, 'Cannot apply'):
            privacy.process(self.source, apply=True, patch_dir=self.patch_dir)
        self.assertEqual(first.read_text(), 'network = yes\n')

    def test_verify_rejects_unpatched_or_tampered_source(self):
        path = self.add_patch('theme', 'network = yes\n', 'network = no\n')
        with self.assertRaises(ValueError):
            privacy.process(self.source, patch_dir=self.patch_dir)
        privacy.process(self.source, apply=True, patch_dir=self.patch_dir)
        path.write_text('network = yes\n')
        with self.assertRaises(ValueError):
            privacy.process(self.source, patch_dir=self.patch_dir)

    def test_paths_cannot_escape_source(self):
        with self.assertRaisesRegex(ValueError, 'escapes'):
            privacy.checked_path(self.source, '../outside')

    def test_prepared_core_must_have_patched_contents(self):
        prepared = self.source / 'build_dir/target-aarch64/mihomo-meta-1.19.31'
        file = prepared / 'component/updater/update_core.go'
        file.parent.mkdir(parents=True)
        file.write_text('self update disabled\n')
        self.series['mihomo']['files'] = [{'path': 'component/updater/update_core.go', 'after': digest(file.read_text())}]
        self.assertEqual(privacy.verify_built(self.source, self.series), prepared)
        file.write_text('unpatched core\n')
        with self.assertRaisesRegex(ValueError, 'verification failed'):
            privacy.verify_built(self.source, self.series)

    def test_prepared_core_must_exist(self):
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            privacy.verify_built(self.source, self.series)


if __name__ == '__main__':
    unittest.main()
