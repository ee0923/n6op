#!/usr/bin/env python3
"""Verify the N60 Pro image and installed package manifest before publishing."""

import argparse
from pathlib import Path
import re

REQUIRED = {
    'kmod-usb-net-rndis', 'kmod-usb-net-cdc-ether', 'kmod-usb-net-cdc-ncm', 'ip-full',
    'openssh-server', 'openssh-client', 'openssh-keygen', 'openssh-sftp-server',
    'nikki', 'luci-app-nikki', 'luci-i18n-nikki-zh-cn', 'mihomo-meta',
    'luci', 'luci-ssl', 'luci-theme-argon',
    'luci-i18n-base-zh-cn', 'luci-i18n-firewall-zh-cn',
}


def verify(target):
    images = list(target.glob('*-netcore_n60-pro-squashfs-sysupgrade.itb'))
    manifests = list(target.glob('*-netcore_n60-pro.manifest'))
    if len(images) != 1 or not images[0].is_file() or images[0].stat().st_size == 0:
        raise ValueError('Expected exactly one nonempty N60 Pro squashfs sysupgrade image')
    if len(manifests) != 1 or not manifests[0].is_file():
        raise ValueError('Expected exactly one N60 Pro package manifest')
    prefix = images[0].name.removesuffix('-squashfs-sysupgrade.itb')
    if manifests[0].name != prefix + '.manifest':
        raise ValueError('Image and manifest prefixes do not match')
    packages = set()
    for line in manifests[0].read_text().splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'(\S+) - (\S.*)', line)
        if not match:
            raise ValueError(f'Invalid package manifest line: {line!r}')
        packages.add(match[1])
    missing = sorted(REQUIRED - packages)
    if missing or 'dropbear' in packages:
        raise ValueError(f'Invalid firmware packages: missing={missing}, dropbear={"dropbear" in packages}')
    return images[0], manifests[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', type=Path)
    args = parser.parse_args()
    try:
        image, manifest = verify(args.target)
    except ValueError as error:
        parser.exit(1, f'{error}\n')
    print(f'Verified {image.name} against {manifest.name}: OpenSSH, SFTP, Nikki and Chinese Argon LuCI; no Dropbear.')


if __name__ == '__main__':
    main()
