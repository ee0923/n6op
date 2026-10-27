#!/usr/bin/env bash
set -euo pipefail

source_dir=${1:?Usage: check-device.sh SOURCE_DIR}
python3 - "$source_dir" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
image = (root / "target/linux/mediatek/image/filogic.mk").read_text()
match = re.search(r"^define Device/netcore_n60-pro\n(.*?)^endef$", image, re.M | re.S)
if not match or not re.search(r"DEVICE_MODEL\s*:=\s*N60 Pro\s*$", match[1], re.M):
    sys.exit("Selected upstream ref does not explicitly support Netcore N60 Pro via netcore_n60-pro.")
config = (root / ".config").read_text().splitlines()
required = {
    "CONFIG_CCACHE=y",
    "CONFIG_PACKAGE_kmod-usb-net-rndis=y",
    "CONFIG_PACKAGE_kmod-usb-net-cdc-ether=y",
    "CONFIG_PACKAGE_kmod-usb-net-cdc-ncm=y",
    "CONFIG_PACKAGE_ip-full=y",

    "CONFIG_TARGET_mediatek=y",
    "CONFIG_TARGET_mediatek_filogic=y",
    "CONFIG_TARGET_mediatek_filogic_DEVICE_netcore_n60-pro=y",
    "CONFIG_TARGET_ROOTFS_INITRAMFS=y",
    "CONFIG_TARGET_ROOTFS_SQUASHFS=y",
    "CONFIG_PACKAGE_luci=y",
    "CONFIG_PACKAGE_luci-ssl=y",
    "CONFIG_PACKAGE_luci-theme-argon=y",
    "CONFIG_PACKAGE_luci-i18n-base-zh-cn=y",
    "CONFIG_PACKAGE_luci-i18n-firewall-zh-cn=y",
    "CONFIG_PACKAGE_nikki=y",
    "CONFIG_PACKAGE_luci-app-nikki=y",
    "CONFIG_PACKAGE_luci-i18n-nikki-zh-cn=y",
    "CONFIG_PACKAGE_mihomo-meta=y",
    "CONFIG_PACKAGE_openssh-server=y",
    "CONFIG_PACKAGE_openssh-client=y",
    "CONFIG_PACKAGE_openssh-keygen=y",
    "CONFIG_PACKAGE_openssh-sftp-server=y",
    "# CONFIG_PACKAGE_dropbear is not set",
}
missing = sorted(required - set(config))
devices = [line for line in config if re.match(r"CONFIG_TARGET_.*_DEVICE_.*=y$", line)]
dropbear_enabled = any(re.match(r"CONFIG_PACKAGE_dropbear=[ym]$", line) for line in config)
if missing or dropbear_enabled or devices != ["CONFIG_TARGET_mediatek_filogic_DEVICE_netcore_n60-pro=y"]:
    sys.exit(f"Invalid build config: missing={missing}, selected_devices={devices}, dropbear_enabled={dropbear_enabled}")
print("Verified Netcore N60 Pro: mediatek/filogic, netcore_n60-pro, Chinese LuCI with HTTPS and Argon, Nikki, Mihomo Meta and default OpenSSH.")
PY
