#!/usr/bin/env python3
"""Record available source revisions, including incomplete build checkouts."""

import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def git_commit(directory):
    # A missing checkout must not resolve to the enclosing configuration repo.
    if not (directory / '.git').exists():
        return 'unavailable'
    result = subprocess.run(['git', '-C', str(directory), 'rev-parse', 'HEAD'],
                            text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else 'unavailable'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    lines = [
        'Upstream: https://github.com/immortalwrt/immortalwrt',
        f'Source commit: {git_commit(args.source_dir)}',
        f'Config commit: {os.environ.get("GITHUB_SHA") or git_commit(ROOT)}',
    ]
    if os.environ.get('GITHUB_RUN_ID'):
        lines.append('Run: {}/{}/actions/runs/{}'.format(
            os.environ.get('GITHUB_SERVER_URL', 'https://github.com'),
            os.environ.get('GITHUB_REPOSITORY', ''), os.environ['GITHUB_RUN_ID']))
        lines.append(f'Attempt: {os.environ.get("GITHUB_RUN_ATTEMPT", "unknown")}')
    feeds = args.source_dir / 'feeds'
    if feeds.is_dir():
        for feed in sorted(feeds.iterdir()):
            if feed.is_dir():
                lines.append(f'Feed {feed.name}: {git_commit(feed)}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
