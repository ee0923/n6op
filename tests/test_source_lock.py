import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("source_lock", ROOT / "scripts/source-lock.py")
source_lock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source_lock)


class SourceLockTests(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads((ROOT / "configs/source-lock.json").read_text())

    def test_parse_branch_and_commit(self):
        feeds = source_lock.parse_feeds(
            "src-git luci https://github.com/immortalwrt/luci.git;openwrt-25.12\n"
            "src-git-full nikki https://github.com/nikkinikki-org/OpenWrt-nikki.git^" + "a" * 40
        )
        self.assertEqual(feeds[0]["ref"], "openwrt-25.12")
        self.assertEqual(feeds[1]["ref"], "a" * 40)

    def test_duplicate_feed_rejected(self):
        line = "src-git luci https://github.com/immortalwrt/luci.git;openwrt-25.12\n"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            source_lock.parse_feeds(line + line)

    def test_unpinned_commit_rejected(self):
        lock = copy.deepcopy(self.lock)
        lock["feeds"][0]["commit"] = "openwrt-25.12"
        with self.assertRaisesRegex(ValueError, "full commit"):
            source_lock.validate(lock)

    def test_feed_render_contains_only_locked_commits(self):
        output = io.StringIO()
        with patch("sys.argv", ["source-lock.py", "feeds"]), contextlib.redirect_stdout(output):
            source_lock.main()
        self.assertEqual(len(output.getvalue().splitlines()), len(self.lock["feeds"]))
        for feed in self.lock["feeds"]:
            self.assertIn(f"{feed['url']}^{feed['commit']}", output.getvalue())
        self.assertNotIn(";", output.getvalue())

    def test_verify_all_sources_and_detect_feed_drift(self):
        commits = [self.lock["upstream"]["commit"]] + [feed["commit"] for feed in self.lock["feeds"]]
        argv = ["source-lock.py", "verify", "--source-dir", "source"]
        with patch("sys.argv", argv), patch.object(source_lock, "git_commit", side_effect=commits) as git, contextlib.redirect_stdout(io.StringIO()):
            source_lock.main()
            self.assertEqual(git.call_count, len(commits))
        commits[-1] = "f" * 40
        with patch("sys.argv", argv), patch.object(source_lock, "git_commit", side_effect=commits):
            with self.assertRaisesRegex(ValueError, "Source lock mismatch"):
                source_lock.main()

    def test_failed_update_preserves_previous_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            lock_path = Path(temporary) / "source-lock.json"
            original = json.dumps(self.lock)
            lock_path.write_text(original)
            argv = ["source-lock.py", "update", "--lock", str(lock_path)]
            definition = "src-git luci https://github.com/immortalwrt/luci.git;openwrt-25.12"
            with patch("sys.argv", argv), patch.object(source_lock, "download", return_value=definition), patch.object(source_lock, "resolve", side_effect=["a" * 40, RuntimeError("network unavailable")]):
                with self.assertRaisesRegex(RuntimeError, "network unavailable"):
                    source_lock.main()
            self.assertEqual(lock_path.read_text(), original)


if __name__ == "__main__":
    unittest.main()
