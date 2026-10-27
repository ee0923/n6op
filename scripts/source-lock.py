#!/usr/bin/env python3
"""Refresh, render and verify pinned ImmortalWrt build inputs."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_URL = "https://github.com/immortalwrt/immortalwrt.git"


def repository(url):
    match = re.fullmatch(r"https://github\.com/([\w.-]+/[\w.-]+)\.git", url)
    if not match:
        raise ValueError(f"Unsupported repository URL: {url}")
    return match[1]


def download(url, api=False):
    headers = {"User-Agent": "netcore-n60-pro-source-lock"}
    if api and os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urlopen(Request(url, headers=headers), timeout=60) as response:
        return response.read().decode()


def resolve(url, ref):
    endpoint = f"https://api.github.com/repos/{repository(url)}/commits/{quote(ref, safe='')}"
    commit = json.loads(download(endpoint, api=True))["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid resolved commit")
    return commit


def parse_feeds(contents):
    feeds = []
    for line in contents.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"src-git(?:-full)?\s+(\w+)\s+(\S+)", line)
        if not match:
            raise ValueError(f"Unsupported feed definition: {line}")
        url_ref = re.split(r"[;^]", match[2], maxsplit=1)
        url, ref = url_ref[0], url_ref[1] if len(url_ref) > 1 else "HEAD"
        repository(url)
        feeds.append({"name": match[1], "url": url, "ref": ref})
    if len({feed["name"] for feed in feeds}) != len(feeds):
        raise ValueError("Duplicate feed names")
    return feeds


def validate(lock):
    if lock.get("version") != 1 or lock["upstream"]["url"] != UPSTREAM_URL:
        raise ValueError("Unsupported source lock format or upstream")
    if not lock["feeds"] or "nikki" not in {feed["name"] for feed in lock["feeds"]}:
        raise ValueError("Source lock must contain the Nikki feed")
    names = set()
    for item in [lock["upstream"], *lock["feeds"]]:
        repository(item["url"])
        if not re.fullmatch(r"[0-9a-f]{40}", item["commit"]):
            raise ValueError("Every source must use a full commit SHA")
        if "name" in item:
            if not re.fullmatch(r"\w+", item["name"]) or item["name"] in names:
                raise ValueError("Invalid or duplicate feed name")
            names.add(item["name"])


def git_commit(directory):
    return subprocess.check_output(["git", "-C", str(directory), "rev-parse", "HEAD"], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["update", "outputs", "feeds", "verify"])
    parser.add_argument("--lock", type=Path, default=ROOT / "configs/source-lock.json")
    parser.add_argument("--upstream-ref", default="openwrt-25.12")
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()

    if args.command == "update":
        commit = resolve(UPSTREAM_URL, args.upstream_ref)
        definitions = download(f"https://raw.githubusercontent.com/immortalwrt/immortalwrt/{commit}/feeds.conf.default")
        definitions += "\n" + (ROOT / "configs/feeds.conf.append").read_text()
        feeds = parse_feeds(definitions)
        with ThreadPoolExecutor(max_workers=6) as executor:
            commits = list(executor.map(lambda feed: resolve(feed["url"], feed["ref"]), feeds))
        for feed, revision in zip(feeds, commits):
            feed["commit"] = revision
        lock = {"version": 1, "upstream": {"url": UPSTREAM_URL, "ref": args.upstream_ref, "commit": commit}, "feeds": feeds}
        validate(lock)
        temporary = args.lock.with_suffix(".tmp")
        temporary.write_text(json.dumps(lock, indent=2) + "\n")
        temporary.replace(args.lock)
        print(f"Locked upstream {commit} and {len(feeds)} feeds in {args.lock}")
        return

    lock = json.loads(args.lock.read_text())
    validate(lock)
    if args.command == "outputs":
        print(f"upstream_commit={lock['upstream']['commit']}")
    elif args.command == "feeds":
        for feed in lock["feeds"]:
            print(f"src-git {feed['name']} {feed['url']}^{feed['commit']}")
    else:
        if not args.source_dir:
            parser.error("verify requires --source-dir")
        expected = [(args.source_dir, lock["upstream"]["commit"])]
        expected += [(args.source_dir / "feeds" / feed["name"], feed["commit"]) for feed in lock["feeds"]]
        for directory, commit in expected:
            actual = git_commit(directory)
            if actual != commit:
                raise ValueError(f"Source lock mismatch for {directory}: expected {commit}, got {actual}")
        print("Source and all feed commits match the source lock.")


if __name__ == "__main__":
    main()
