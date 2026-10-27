import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'scripts/collect-build-info.py'


class BuildInfoTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        self.output = self.root / 'logs/build-info.txt'

    def create_repository(self, path):
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'init', '-q', str(path)], check=True)
        subprocess.run(['git', '-C', str(path), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.invalid', 'commit', '-q',
                        '--allow-empty', '-m', 'Test source'], check=True)
        return subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()

    def collect(self):
        env = dict(os.environ, GITHUB_SHA='a' * 40, GITHUB_SERVER_URL='https://github.com',
                   GITHUB_REPOSITORY='test/build', GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='2')
        subprocess.run(['python3', str(SCRIPT), '--source-dir', str(self.source),
                        '--output', str(self.output)], env=env, check=True)
        return self.output.read_text()

    def test_missing_checkout_still_records_run(self):
        info = self.collect()
        self.assertIn('Source commit: unavailable', info)
        self.assertIn('Config commit: ' + 'a' * 40, info)
        self.assertIn('Run: https://github.com/test/build/actions/runs/123', info)
        self.assertIn('Attempt: 2', info)

    def test_uninitialized_checkout_does_not_inherit_parent_commit(self):
        self.create_repository(self.root)
        self.source.mkdir()
        self.assertIn('Source commit: unavailable', self.collect())

    def test_partial_feeds_record_actual_and_missing_commits(self):
        upstream = self.create_repository(self.source)
        packages = self.create_repository(self.source / 'feeds/packages')
        (self.source / 'feeds/luci').mkdir()
        info = self.collect()
        self.assertIn(f'Source commit: {upstream}', info)
        self.assertIn(f'Feed packages: {packages}', info)
        self.assertIn('Feed luci: unavailable', info)


if __name__ == '__main__':
    unittest.main()
