# N60 Pro 固件隐私审计与补丁

审计日期：2026-10-27。范围为本仓库锁定的源码、默认设备软件包和额外选择的软件包。源码结论不等于路由器抓包结论，也不能覆盖用户以后安装的第三方包、面板或订阅内容。

## 来源

- ImmortalWrt：`313718c25f206cdeee399bdc6c002b7388c9a513`。
- packages：`84bd86384928955b568988ca0e09e2c78c75173d`。
- LuCI：`d6167ea0645cbd1327708d85f94824f42d0eb872`，Argon 2.4.7。
- Nikki：`7b203f6c4c5e94c6c0026acb301090aa1d310e7f`。
- Mihomo：由 Nikki 的 `mihomo-meta/Makefile` 选择 `v1.19.31`，保留其原始 `PKG_MIRROR_HASH` 下载校验。
- Mihomo 的 Tailscale 依赖：`github.com/metacubex/tailscale v0.0.0-20260821153257-ff0ecd818181`。

审计下载的源码归档 SHA256 记录在 [privacy-source-snapshots.json](privacy-source-snapshots.json)。构建仍使用原有源码锁定与构建系统下载校验，不用审计归档替代包来源。

## 发现与处理

| 路径 | 审计结果 | 本仓库处理 |
| --- | --- | --- |
| 系统默认服务、default-settings、基础 LuCI | 在检查的默认配置、启动脚本和界面路径中，未找到默认启用的使用分析、崩溃上传或厂商统计上报。默认服务包含 DHCP/DNS、NTP、SSH、Web 管理等功能联网。 | 保留网络功能；不把本地日志、计数器或功能请求当作遥测。 |
| Argon `sysauth.ut` → `luci.argon_wallpaper` RPC | 在线壁纸属于可选外联：配置启用后，路由器和浏览器会访问 Bing、vvhan、Unsplash 或 Wallhaven；保存的旧配置也能启用。不是已证实的使用统计上传。 | 删除登录页在线壁纸调用，RPC 改为固定空 URL，删除仅供壁纸使用的 wget/jsonfilter 依赖；保留内置图片、视频和字体。旧在线壁纸配置也不能触发此路径。 |
| Nikki 配置与 LuCI 页面 | 未发现默认统计上传。订阅更新是用户配置的功能请求。默认面板 URL 指向 `dist-cdn-fonts.zip`。 | 默认改为 `dist.zip`，移除 CDN 字体版本的预设选项；混入配置时将保存的同一默认 CDN URL 规范为非 CDN 版本。自定义 URL 不替用户改写。 |
| Mihomo `updateUpdater` → `AutoDownloadUI` | 启动/配置更新时，面板目录为空可触发下载，URL 可以来自配置。 | `AutoDownloadUI` 改为空操作。首次使用面板，须在 Nikki 点击“更新面板 / Update Dashboard”；显式下载 API 保留。 |
| Mihomo `/upgrade` → `CoreUpdater.Update` | 这是手动触发的核心替换功能，不是默认遥测，但可以用未打补丁的上游二进制覆盖隐私修改。 | 删除核心下载、解包、备份及自替换实现，保留明确的禁用错误。升级应重编译本仓库或安装同样审计过的包。 |
| Mihomo Tailscale 适配器与其依赖 | 适配器已有 `SetNoLogsNoSupport()`；依赖的 logtail 和客户端指标为禁用/空实现，不能声称它们原来默认在上传。其余网络日志、TUN 设备统计和客户端更新有独立编译开关。 | 增加真实受支持的 `ts_omit_netlog`、`ts_omit_tundevstats`、`ts_omit_clientupdate`。原生测试检查这五项功能常量均为 false，并确认日志保护已启用。不删除 Mihomo 本地流量/连接指标，也不禁用 Tailscale 协议本身。 |
| Mihomo geodata、DNS、NTP、代理健康检查 | 内置 GeoIP/GeoSite/ASN 资源下载、配置中的 DNS/NTP、测速 URL 是功能性外联。geodata 缺失或损坏时仍可能下载；订阅还能指定 provider 和更新周期。 | 保留，避免破坏解析、时间、规则和代理。此固件并非离线固件。 |

## 手机分流自动回退

`usb-mobile-auto.yaml` 示例或包含相同策略的完整订阅使用原生 `select` 组 `MOBILE`，在自动回退 `MOBILE-AUTO` 与仅手机 `MOBILE-USB` 之间切换。只有 Nikki 启用包含自动组的配置时，才会通过手机和有线出口分别每 10 秒向 `https://cp.cloudflare.com/generate_204` 发送 HTTP HEAD 请求，超时为 3 秒，期待状态码 204。fallback 组据此选择首个可用出口；`lazy: false` 使无业务流量时也能发现手机恢复。

面板选择 `MOBILE-USB` 只改变业务连接的策略，不会停止自动组的后台探测；如需完全停用该探测，应使用不含自动组的 `usb-mobile.yaml` 或相应的完整订阅。此项差异在使用说明中明确列出。选择缓存保存在本地，用于重启或订阅更新后恢复策略选择；切换不改写订阅内容。

连通性检查会产生少量流量；请求 URL 不包含设备标识、域名规则或业务内容。探测服务可观察到常规请求及出口地址，不应把它描述为“无外联”。Nikki 默认关闭，域名列表为空；本功能没有新增统计、崩溃上传或远程日志 SDK。

## 检查的调用位置

- [系统默认软件包](https://github.com/immortalwrt/immortalwrt/blob/313718c25f206cdeee399bdc6c002b7388c9a513/include/target.mk)与 `package/emortal/default-settings/files/`；N60 Pro 的官方设备定义与设备默认包。
- [Argon 登录页](https://github.com/immortalwrt/luci/blob/d6167ea0645cbd1327708d85f94824f42d0eb872/themes/luci-theme-argon/ucode/template/themes/argon/sysauth.ut)、同主题 RPC/Makefile，以及基础 LuCI、状态页、系统页、包管理界面。
- [Nikki 默认配置](https://github.com/nikkinikki-org/OpenWrt-nikki/blob/7b203f6c4c5e94c6c0026acb301090aa1d310e7f/nikki/files/nikki.conf)、`nikki.init`、`ucode/mixin.uc`、LuCI RPC/页面及调试脚本。调试脚本向本地标准输出生成信息，不是上传器；但用户主动运行它时，上游脚本会临时启用原本关闭的 Nikki，可能触发已配置的订阅/代理联网，不能把它当作完全无副作用的离线命令。
- [Mihomo 配置](https://github.com/MetaCubeX/mihomo/blob/v1.19.31/config/config.go)、`hub/executor/executor.go`、`hub/route/upgrade.go`、`component/updater/`、`component/geodata/init.go`、`adapter/outbound/tailscale.go`；对已下载的核心 Go 依赖做了遥测 SDK/上报调用筛查，并追查了 Tailscale 的实际实现和编译开关。
- SDK 关键词命中不能直接等同于遥测：例如 gVisor 的 sentry、代理伪装中的 `/v1/telemetry` 路径，不是由此确认的统计上传器。

## 补丁如何生效

`patches/privacy/series.json` 固定每个受影响文件修改前后的 SHA256。`scripts/privacy-patch.py` 在修改前预检全部补丁，严格匹配源码内容并禁止 patch fuzz；已完整应用时可重复执行。源码变化或只应用了一部分时停止构建，不静默跳过。

Actions 在 feeds 提交校验后应用补丁，再执行 `feeds update -i luci nikki` 仅重建索引，然后安装 feeds。Mihomo 的原生 Go 补丁放进其 OpenWrt 包的 `patches/`，由 `Build/Prepare/Default` 应用；准备后再校验精确的 Go 文件哈希，阻止补丁漂移。编译完成后再次校验实际准备目录，然后才允许收集和发布固件。

`privacy-patches.json` 和 `privacy-built.json` 随固件输出；失败日志附件也收集已生成的报告和补丁清单。它们描述源码及补丁验证，不代表已经检查实际刷入设备的网络流量。

刷新源码时如触发哈希不匹配，应重新审计并更新补丁，不能直接放宽哈希或忽略失败。

## 验证与使用限制

已完成源码补丁的实际应用、重复应用和精确哈希校验，执行了 Argon RPC 的无网络响应检查；仓库测试覆盖漂移拒绝、整批预检和已准备核心的校验。Mihomo 原生测试验证：核心更新被拒绝且文件不变、自动面板下载零请求但手动下载可成功、Tailscale 的日志/指标/统计/更新保护生效。

本地验证结果：

- 50 项仓库 Python 测试通过，无跳过项。
- 3 项 `TestPrivacy` 原生 Go 测试通过，覆盖 updater 和 outbound。
- 补丁后的 Mihomo 核心以相同隐私 tags、`GOOS=linux GOARCH=arm64 CGO_ENABLED=0` 独立交叉编译成功。Go 构建信息确认这些 tags 已写入目标二进制；检查确认旧核心版本查询 URL 已不在其中，禁用错误仍存在。
- 独立验证二进制 SHA256：`aa87183a7c5d22aa3c6b349fad1a999637f04c79882168b77083dc99f32f9ee2`。该产物用于验证核心源码，未经过 OpenWrt 的完整打包及刷机流程。

原生测试使用临时文件和本地 HTTP 测试服务，可在应用补丁后的 Mihomo 目录执行：

```sh
go test -tags 'with_gvisor ts_omit_netlog ts_omit_tundevstats ts_omit_clientupdate' \
  ./component/updater ./adapter/outbound -run '^TestPrivacy' -count=1
```

手动下载的面板不是本仓库锁定的源码，其在线 IP 检测、资源、更新等行为未由本补丁保证；“非 CDN 字体”也不意味着面板没有任何外联。保留配置升级时，已缓存的旧面板不会被自动删除或替换，需要显式更新或自行审计。

手机自动回退配置另用隔离 Linux 容器中的实际 Mihomo 和本地 HTTP 服务验证：手机优先、手机路径无网络后切换网线、恢复后重新优先手机，以及选择仅手机策略后不回退。配置内策略切换不改写配置文件，且核心重载后恢复选择。测试使用真实 socket mark 路由失败，没有连接实体手机；外部探测地址单独确认返回 HTTP 204。

本次未完成完整 OpenWrt 固件构建、刷机或设备抓包；也没有对 Wi-Fi 固件、所有内核/底层依赖和所有可选代理协议做逐行或二进制审计。构建下载和用户主动配置的外部服务仍会联网。
