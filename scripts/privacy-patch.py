#!/usr/bin/env python3
"""Apply and verify privacy patches against exact audited source contents."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
PATCHES = ROOT / 'patches/privacy'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def checked_path(root, relative):
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes source directory: {relative}')
    return path


def states(root, files):
    return [digest(checked_path(root, entry['path'])) for entry in files]


def assert_after(root, files):
    for entry, actual in zip(files, states(root, files)):
        if actual != entry['after']:
            raise ValueError(f'Privacy patch verification failed: {root / entry["path"]}')


def run_patch(root, patch, dry_run=False):
    command = ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-d', str(root), '-i', str(patch)]
    if dry_run:
        command.append('--dry-run')
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        raise ValueError(f'Cannot apply {patch.name}:\n{result.stdout}{result.stderr}')


def process(source, apply=False, patch_dir=PATCHES):
    series = json.loads((patch_dir / 'series.json').read_text())
    if series.get('version') != 1:
        raise ValueError('Unsupported privacy patch manifest')
    pending = []
    for entry in series['patches']:
        root = checked_path(source, 'feeds/' + entry['scope'])
        actual = states(root, entry['files'])
        if actual == [item['after'] for item in entry['files']]:
            continue
        if not apply or actual != [item['before'] for item in entry['files']]:
            raise ValueError(f'Audited source changed or patch incomplete: {entry["name"]}; review patches before building')
        patch = checked_path(patch_dir, entry['patch'])
        run_patch(root, patch, dry_run=True)
        pending.append((root, patch))
    # Preflight all groups before changing any source files.
    for root, patch in pending:
        run_patch(root, patch)
    for entry in series['patches']:
        assert_after(source / 'feeds' / entry['scope'], entry['files'])
    return series


def verify_built(source, series):
    candidates = [path for path in source.glob('build_dir/target-*/mihomo-meta-*')
                  if (path / 'component/updater').is_dir()]
    if len(candidates) != 1:
        raise ValueError('Expected exactly one prepared Mihomo Meta source directory')
    assert_after(candidates[0], series['mihomo']['files'])
    return candidates[0]


def report(series):
    return {
        'source_lock_sha256': digest(ROOT / 'configs/source-lock.json'),
        'privacy_manifest_sha256': digest(PATCHES / 'series.json'),
        'patches': [{'name': entry['name'], 'sha256': digest(PATCHES / entry['patch']),
                     'files': {item['path']: item['after'] for item in entry['files']}}
                    for entry in series['patches']],
        'mihomo': series['mihomo'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['apply', 'verify', 'verify-built'])
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        series = process(args.source_dir, apply=args.command == 'apply')
        evidence = report(series)
        if args.command == 'verify-built':
            prepared = verify_built(args.source_dir, series)
            evidence['prepared_mihomo'] = str(prepared)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(evidence, indent=2) + '\n')
    except (ValueError, OSError) as error:
        parser.exit(1, f'{error}\n')
    print(f'Privacy patches {args.command}: verified exact source hashes for {len(series["patches"])} patch groups.')


if __name__ == '__main__':
    main()
