# Netcore N60 Pro · ImmortalWrt GitHub Actions

本仓库参考 `netcore_n30_pro/openwrt`，保存 N60 Pro 的编译配置与工作流，不包含完整 ImmortalWrt 源码。GitHub Actions 会拉取官方 [`immortalwrt/immortalwrt`](https://github.com/immortalwrt/immortalwrt)，为磊科 Netcore N60 Pro 编译固件。

## 设备适配

- 默认使用 `configs/source-lock.json` 中锁定的 `openwrt-25.12` 源码提交和所有 feeds 提交。
- 平台：`mediatek/filogic`，设备配置：`netcore_n60-pro`。
- 官方设备定义为 `Netcore N60 Pro`，使用独立的 `netcore_n60-pro` 配置，不与 N60 或 N30 Pro 混用。
- 使用官方 DTS、网络配置及 mt76 无线驱动，不引入第三方设备补丁。
- 保留设备默认软件包，额外启用 LuCI、HTTPS 及基础界面/防火墙中文语言包。
- 内置官方 feed 的 `luci-theme-argon`，首次启动设置 Argon 为默认主题。
- 默认内置 [Nikki](https://github.com/nikkinikki-org/OpenWrt-nikki)、LuCI 管理界面、中文语言包及 Mihomo Meta 稳定内核。
- 默认 LAN 地址：`192.168.11.1/24`，DHCP 地址池：`192.168.11.100–192.168.11.249`。

对应源码：[设备定义](https://github.com/immortalwrt/immortalwrt/blob/openwrt-25.12/target/linux/mediatek/image/filogic.mk)、[设备树](https://github.com/immortalwrt/immortalwrt/blob/openwrt-25.12/target/linux/mediatek/dts/mt7986a-netcore-n60-pro.dts)。

## 在 GitHub 上编译

1. 在自己的 GitHub 账号下创建空仓库，不勾选初始化 README。
2. 在本地添加远程地址并推送：

   ```sh
   git remote add origin https://github.com/<用户名>/<仓库名>.git
   git push -u origin main
   ```

3. 首次推送会触发编译。后续可在 **Actions → Build ImmortalWrt for Netcore N60 Pro → Run workflow** 手动启动。
4. 默认保持 `update_sources=false`，使用仓库提交的锁定版本。需要更新时设置 `update_sources=true`，并在 `upstream_ref` 填写支持该设备的分支、tag 或完整 commit SHA。只有更新模式会使用此字段；缺少官方设备适配时检查步骤会失败。
5. 编译成功后会自动发布到仓库 **Releases**，可直接下载固件、配置、校验文件和完整产物压缩包。也可以在该次运行的 **Artifacts** 下载 `immortalwrt-netcore-n60-pro-*`；失败时下载 `n60-pro-build-logs-*` 排查。Artifacts 保留 14 天。

修改编译配置、脚本、固件文件或工作流后推送到 `main` 也会触发编译。没有定时任务。

## Release 自动发布

每次成功编译后，独立的 `release` job 会校验构建产物，创建 `n60-pro-<run_id>-<run_attempt>` 标签，将所有顶层产物和包含完整目录的 `immortalwrt-netcore-n60-pro.tar.gz` 上传为附件。全部附件上传成功后才公开 Release 并标记为 Latest。重跑工作流使用新的 attempt 标签，不覆盖历史固件。

Release 使用 Actions 自带的 `GITHUB_TOKEN`，仅发布 job 请求 `contents: write`，无需额外配置个人访问令牌。如果发布步骤因组织策略或仓库权限失败，可先从 Artifacts 下载固件；失败后可能留下未公开的草稿 Release。

Release 附件统一使用 `release-checksums.txt` 校验，包含完整压缩包的校验值；Artifacts 和压缩包内部使用 `SHA256SUMS` 校验构建原始文件。为避免附件重名，发布时会过滤上游 `sha256sums` 和构建生成的 `SHA256SUMS`，并检查附件名忽略大小写后没有重复。相同标签的上传重试会覆盖同名附件，上传全部成功后才公开 Release。

只下载部分 Release 附件时可使用 `sha256sum --ignore-missing -c release-checksums.txt`；解压完整产物压缩包后使用 `sha256sum -c SHA256SUMS`。

## 默认网络与 Nikki

LuCI 默认使用 Argon 主题。初始化配置位于 `files/etc/uci-defaults/30_luci-theme-argon`，覆盖主题包自身的初始化文件，避免其先改掉用户选择。只有主题未设置或仍为 Bootstrap/OpenWrt 2020 时才切换到 Argon；保留配置升级时，其他自定义主题及已选 Argon 都保持原样。之后可在 LuCI 的系统设置中更换主题，所选主题仍需安装在固件中。

全新安装或恢复出厂后，通过 `https://192.168.11.1` 访问 LuCI。首次启动脚本兼容旧版 `192.168.1.1` 与 25.12 的地址列表 `192.168.1.1/24`，统一改为 `192.168.11.1/24`，客户端自动获取 `192.168.11.x` 地址。保留配置升级时，如果已有其他自定义 LAN 地址，脚本不会覆盖它；需要手动调整或不保留配置升级才能使用这里的默认网段。

如果已刷入旧版本、客户端仍获取 `192.168.1.x`，可以在路由器 SSH 中执行以下命令立即修正，无需重新编译。最后一条命令会使当前连接断开，重新连接网络或更新 DHCP 租约后，通过 `192.168.11.1` 访问路由器：

```sh
uci -q delete network.lan.ipaddr
uci add_list network.lan.ipaddr='192.168.11.1/24'
uci -q delete network.lan.netmask
uci set dhcp.lan.start='100'
uci set dhcp.lan.limit='150'
uci commit network
uci commit dhcp
/etc/init.d/dnsmasq restart
/etc/init.d/network restart
```

Nikki 按[官方编译方法](https://github.com/nikkinikki-org/OpenWrt-nikki#compilation)作为源码 feed 接入，更新来源保存在 `configs/feeds.conf.append`，实际构建使用 `configs/source-lock.json` 的完整 commit SHA。编译时优先使用该 feed 的 Nikki、LuCI 页面和 Mihomo Meta，并自动解析所需内核模块等依赖。`make defconfig` 后会检查 Nikki、中文语言包及 Mihomo Meta 都选为内置软件包，缺失则停止编译。

安装后需在 LuCI 的 Nikki 页面配置自己的订阅或配置文件，再启用服务；保留上游默认关闭状态，不预置订阅。Nikki 更新来源为 `main` 分支，默认构建仍使用锁定提交；实际提交记录在 `build-info.txt`。

## 产物与刷机

- `*netcore_n60-pro*squashfs-sysupgrade.itb`：适用于已经安装兼容 OpenWrt/ImmortalWrt、且引导和分区布局一致的设备升级。
- `*netcore_n60-pro*initramfs*.itb`：用于相应引导环境下的临时启动或恢复。
- `*preloader.bin`、`*bl31-uboot.fip`：官方构建可能生成的引导程序文件；它们不是普通升级固件。
- `build.config`、`diffconfig`、`build-info.txt`：完整配置、配置差异及本次源码/feeds 提交记录。
- `source-lock.json`：本次实际使用的源码与全部 feeds 锁定文件，可用于后续复用相同版本。
- `SHA256SUMS`：下载解压后可运行 `sha256sum -c SHA256SUMS` 校验文件。

**从原厂固件首次刷入时，先核对设备硬件版本、现有引导程序与分区布局，并备份 Factory/校准数据。不能把 sysupgrade 文件当作通用原厂升级包，也不能仅凭型号刷写引导程序。** 如果你此前使用的是第三方 `netcore_n60-pro-mod` 或扩容设备补丁，其引导与分区布局可能不同，不应强制跨布局升级。本仓库负责构建，不提供未经实机验证的首次安装命令。

## 修改软件包

编辑 `configs/netcore-n60-pro.config`，添加需要的 `CONFIG_PACKAGE_<包名>=y`。工作流在更新 feeds 后运行 `make defconfig`，并检查设备、中文 LuCI 和 Nikki 配置没有被静默移除。完整解析后的配置会随固件上传。自定义固件文件放在 `files/`，会复制到固件根目录；LAN 默认配置位于 `files/etc/uci-defaults/99-custom-lan`。

## 更新锁定版本

默认构建不会跟随上游分支变化。`configs/source-lock.json` 固定 ImmortalWrt 及 packages、LuCI、routing、telephony、video、Nikki 的全部提交，工作流用这些提交生成 `source/feeds.conf`，并在 feeds 更新后验证实际 checkout 完全一致。锁定的是源码输入，不保证每次构建生成逐字节一致的文件。

手动设置 `update_sources=true` 可为当次运行刷新全部提交。刷新后的 `source-lock.json` 随 Artifact 和 Release 上传，不会自动提交回仓库；验证成功后，可用它替换 `configs/source-lock.json` 并提交，后续默认编译即可沿用。初始锁定文件沿用 n30pro 参考仓库的源码与 feeds 提交；已核对该源码包含 N60 Pro 设备定义与 DTS，尚未经过本仓库的云端编译及实机验证。

本地也可以刷新并检查：

```sh
python3 scripts/source-lock.py update --upstream-ref openwrt-25.12
python3 -m unittest discover -s tests
git add configs/source-lock.json
git commit -m "Update pinned ImmortalWrt and feed revisions"
```

更新脚本通过 GitHub API 解析分支/tag/提交，并读取对应源码的 feeds 清单；只有全部来源成功解析后才替换锁定文件。可选的 `GH_TOKEN` 环境变量用于提高 API 限额。

## 本地检查

编译启用 ccache，缓存目录为 `source/.ccache`，大小上限 2 GiB；Actions 同时缓存 `source/dl` 中的源码下载文件。ccache 恢复优先匹配相同配置和源码提交，再退回相同配置；每次成功运行保存新的缓存快照。下载缓存仍经过构建系统的来源校验。首次运行没有缓存，后续运行的加速程度取决于源码变化和缓存是否被 GitHub 淘汰。ccache 主要缓存 C/C++ 编译，不等于缓存 Mihomo 的完整 Go 构建。

```sh
bash -n scripts/check-device.sh
sh -n files/etc/uci-defaults/99-custom-lan
sh -n files/etc/uci-defaults/30_luci-theme-argon
# 在已经生成 .config 的官方源码目录上验证：
bash scripts/check-device.sh /path/to/immortalwrt
```

工作流使用 Ubuntu 24.04 编译，失败会自动切换单线程详细日志重试。首次全量编译可能耗时数小时；本地配置检查成功不代表云端编译通过或设备刷机验证通过。
