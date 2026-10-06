<img src="https://avatars.githubusercontent.com/u/53193414?s=200&v=4" alt="logo" width="180" height="180" align="right">

# ImmortalWrt-XR1710G（个人定制版）

[![Build](https://img.shields.io/github/actions/workflow/status/Quan-0505/ImmortalWrt-XR1710G/build-firmware.yml?branch=master&label=Build)](https://github.com/Quan-0505/ImmortalWrt-XR1710G/actions/workflows/build-firmware.yml)
[![Sync](https://img.shields.io/github/actions/workflow/status/Quan-0505/ImmortalWrt-XR1710G/sync-upstream.yml?branch=master&label=Sync)](https://github.com/Quan-0505/ImmortalWrt-XR1710G/actions/workflows/sync-upstream.yml)
[![Upstream](https://img.shields.io/badge/upstream-naoki66%2FImmortalWrt--for--Gemtek--brightspeed-blue)](https://github.com/naoki66/ImmortalWrt-for-Gemtek-brightspeed)
[![Kernel](https://img.shields.io/badge/kernel-6.18-orange)](target/linux/airoha/patches-6.18)

只针对 **Gemtek / Brightspeed XR1710G**（Airoha AN7581GT）的 ImmortalWrt 固件。设备树、内核与无线补丁、
分区/刷写方案全部继承自 [naoki66/ImmortalWrt-for-Gemtek-brightspeed](https://github.com/naoki66/ImmortalWrt-for-Gemtek-brightspeed)，
本仓库在原仓库基础上只做三件事：

1. **只预装两个插件**：`kixdns`（含统计）与 `rust-daed`（DaedNext）；
2. **默认管理地址改为 `192.168.2.1`**（与原仓库的 `192.168.50.1` 不同）；
3. **补齐 daed 需要的 eBPF 内核前提**（BTF / BPF / veth / clsact），并裁掉一批用不到的第三方插件。

> 本仓库只维护 XR1710G（一次构建出「原版 U-Boot 分区」和「OpenWrt U-Boot UBI 布局」两套镜像）。
> 原仓库里的 XG2010G / PON 支持仍然存在于源码树中（`2010.config` 等），但本仓库不构建、不验证。

## 目录

- [一、与原仓库的差异](#一与原仓库的差异)
- [二、预装插件](#二预装插件)
- [三、快速开始](#三快速开始)
- [四、上游 packages feed 回归与规避](#四上游-packages-feed-回归与规避重要)
- [五、构建](#五构建)
- [六、设备与硬件](#六设备与硬件)
- [七、固件特性与默认行为](#七固件特性与默认行为)
- [八、主要软件包](#八主要软件包)
- [九、仓库结构](#九仓库结构)
- [十、致谢与许可证](#十致谢与许可证)

## 一、与原仓库的差异

| 项目 | 原仓库 | 本仓库 |
|------|--------|--------|
| 预装插件 | `lucky`、`smartdns`、`vlmcsd`、`msd_lite`、`udpxy`、`ddns-go`、`zerotier`、`rtp2httpd`、`wechatpush`、`timewol` | **只留 `kixdns`（含 `kixdns-stats`、`luci-app-kixdns`）与 `daed`**，上述第三方全部关闭 |
| 默认管理地址 | `192.168.50.1` | **`192.168.2.1`**（`CONFIG_TARGET_PREINIT_IP` / `PREINIT_BROADCAST`） |
| 内核配置 | `CONFIG_DEBUG_INFO=y` + `DEBUG_INFO_REDUCED=y` | 追加 `DEBUG_INFO_BTF`、`BPF`、`BPF_SYSCALL`、`BPF_JIT(_ALWAYS_ON)`、`VETH`、`NET_SCH_INGRESS`、`NET_CLS_ACT`、`NET_CLS_BPF`，并**关闭 `DEBUG_INFO_REDUCED`**（生成完整 BTF，daed 的 eBPF 依赖它） |
| 设备范围 | XR1710G + XG2010G | **仅 XR1710G**（`1710.config` 一次出两套镜像） |
| 新增目录 | — | [`PATCH/daed-pkg`](PATCH/daed-pkg)（daed 包定义）、[`PATCH/daed-web`](PATCH/daed-web)（daed WebUI 覆盖层）、[`PATCH/theme-footstrap-zh`](PATCH/theme-footstrap-zh)（主题中文翻译） |
| LuCI 主题 | argon / bootstrap / glass | 追加 **footstrap 并设为默认开机主题**（`target/linux/airoha/an7581/base-files/etc/uci-defaults/91-xr1710g-theme.sh`）；中文包按 luci feed 的实际命名 `luci-i18n-footstrap-zh-cn` 选择 |
| feed 版本 | 全部跟随上游 master | `packages` 锁到 `2026-09-23` 的 `^10f1f42ef46f`（规避上游 Kconfig 递归回归，见下文） |
| 保留项 | — | 用户点名的 12 个 LuCI 应用、系统工具类应用（`ttyd`/`usteer`/`watchcat`/`wol`/`ddns`/`wifihistory`/`wifischedule`）、三个主题与中文语言包 |

设备与系统类应用（`luci-app-airoha-npu`、`luci-app-airoha-fancontrol`、`luci-app-airoha-factory`、
`luci-app-airoha-recovery`、`luci-app-mesh-conf`、`luci-app-netmode`、`luci-app-upnp`、`luci-app-firewall`、
`luci-app-arpbind`、`luci-app-mlo`、`luci-app-package-manager`、`luci-app-autoreboot`）全部保留。

## 二、预装插件

### kixdns

| 项目 | 说明 |
|------|------|
| 来源 | [JohnsonRan/luci-app-kixdns](https://github.com/JohnsonRan/luci-app-kixdns) v1.6.0（预编译二进制，作者发布包） |
| 组成 | `kixdns`（DNS 内核）、`kixdns-stats`（统计）、`luci-app-kixdns` + 中文语言包 |
| 安装方式 | 构建时从 24.10 的 `aarch64_cortex-a53` 发布包中解出 `usr/bin/kixdns`、`usr/libexec/kixdns-stats-core`，放入 `package/new/*/prebuilt/` 后随包编译 |
| LuCI 入口 | 服务 → KixDNS |

### rust-daed（DaedNext）

| 项目 | 说明 |
|------|------|
| 来源 | [Quan-0505/rust-daed](https://github.com/Quan-0505/rust-daed) v3.1.3 的 `rust-daed-r2s.apk` 载荷 |
| 二进制 | `usr/bin/daed`：**静态链接 AArch64**（Cortex-A53，与本机同架构），无动态依赖 |
| 随包内容 | `etc/init.d/daed`（procd 服务）、`/etc/config/daed`、`usr/share/daed/web`（内嵌 UI，构建时用本仓库 `PATCH/daed-web` 覆盖为最新 WebUI） |
| 内核前提 | eBPF/CO-RE 需要 **BTF**，因此本仓库在内核配置里启用 `DEBUG_INFO_BTF` 并关闭 `DEBUG_INFO_REDUCED`（见上表） |
| 访问方式 | 启动后浏览器打开 `http://192.168.2.1:2023`（首次访问在页面内设置面板账号密码） |
| 服务管理 | `/etc/init.d/daed start\|stop\|restart`；配置在 `/etc/config/daed` |

升级插件版本：改 `.github/workflows/build-firmware.yml` 里 `Fetch plugin prebuilt payloads` 步骤的
release tag（daed）与 `Prepare kixdns and daed packages` 步骤的 kixdns 版本号即可，无需改包定义。

### footstrap（LuCI 主题，默认主题）

| 项目 | 说明 |
|------|------|
| 来源 | [VizzleTF/luci-theme-footstrap](https://github.com/VizzleTF/luci-theme-footstrap)，锁 commit `246337d5…`（与你 OpenWrt 仓库用的是同一个 pin，两台设备主题版本一致） |
| 预装 | `luci-theme-footstrap` + 自译简体中文包（`PATCH/theme-footstrap-zh/zh_Hans/footstrap.po` → 由 luci.mk 生成 `luci-i18n-footstrap-zh-cn`） |
| 默认主题 | 首次开机即 footstrap：`target/linux/airoha/an7581/base-files/etc/uci-defaults/91-xr1710g-theme.sh` 把 `luci.main.mediaurlbase` 写成 `/luci-static/footstrap`（编号 91 保证排在主题包自带默认值之后） |
| 手动切换 | LuCI → 系统 → 系统 → 语言和界面 → 设计；也可 `uci set luci.main.mediaurlbase='/luci-static/footstrap' && uci commit luci` |

## 三、快速开始

### 登录

- 管理地址：**http://192.168.2.1** 或 **http://immortalwrt.lan**，用户名 `root`，密码**无**（首次登录请立即设置）。
- 首次启动的无线网络为 `ImmortalWrt-2G`、`ImmortalWrt-5G`、`ImmortalWrt-6G`，统一初始密码 `12345678`。
  2.4GHz 使用 WPA2，5GHz 使用 WPA2/WPA3 混合，6GHz 使用 WPA3；请尽快修改管理密码与无线密码。

### 下载与刷写

- 下载：[Releases 页面](https://github.com/Quan-0505/ImmortalWrt-XR1710G/releases) 或对应 Actions 运行的 Artifacts。
- 固件文件（`.itb`）：
  - 原版 U-Boot 分区：`immortalwrt-*-airoha-an7581-gemtek_xr1710g-squashfs-sysupgrade.itb`
  - OpenWrt U-Boot UBI 布局：`immortalwrt-*-airoha-an7581-gemtek_xr1710g-ubi-squashfs-sysupgrade.itb`
- 常规升级：LuCI → 系统 → 备份/升级 → 刷写固件（选择与当前布局**匹配**的那个文件）。

> [!WARNING]
> 上面两个文件对应**不同的闪存布局，不能互刷**。只有当前设备已经运行 OpenWrt U-Boot UBI 布局时，
> 才能使用 `-ubi` 版本；从原厂固件首次刷入请用原版分区版本，并先完成原厂分区备份。
> UBI 布局下 `bl2` 位于 NAND 起始的 `0x20000`，`ubi` 从 `0x00020000` 起延伸到 NAND 末尾；
> 用 U-Boot Web Recovery 重建 UBI 时会创建**空的**静态 `factory` 卷，首次启动 Linux 前必须把原厂
> `dsd` 分区去掉 OOB 后的完整 2 MiB 主数据写回该卷，否则无线校准数据与 MAC 会丢失。

> [!WARNING]
> LuCI 的「保留配置」不会保留额外安装的软件包。升级前请备份配置并记录已装软件包；升级后需重新安装
> OpenClash、PassWall、AdGuard Home 等**非预装**组件，且必须使用与新固件同源的软件包，不要恢复旧固件的 `kmod-*`。

## 四、上游 packages feed 回归与规避（重要）

2026-09-24 之后上游 `immortalwrt/packages` 引入了 Kconfig 递归依赖（例如 2026-09-29 的
`treewide: depend on audio-support for the audio group` 牵动 `sound/mpd`）：

1. `make defconfig` 直接 `error: recursive dependency detected!`（同时还有 `squeezelite-custom`
   与 `SQUEEZELITE_WMA_ALAC` 的互相依赖）并以非 0 退出；
2. defconfig 中断后，种子里 `CONFIG_PACKAGE_airoha-an7581-mt7996-board=m` 的 `=m → =y`
   归一化不会发生；
3. 紧接着 `scripts/check-gemtek-profile-isolation.sh` 报
   `xr1710g config is missing required package: airoha-an7581-mt7996-board`，CI 就卡在 `Configure`。

参考仓库 run#60（2026-09-23 成功）与 run#61（2026-09-24 失败）**用的是同一个 commit**，这正是
「变的不是源码树、而是未锁定的 feed」的直接证据。

规避：`feeds.conf.default` 把 `packages` 锁到 `^10f1f42ef46f`（2026-09-23，最后一次成功构建当天），
并把种子里板级包写成显式 `=y`。上游修复后去掉 `^commit` 后缀即可恢复跟随 master；其余 feed 不锁。

## 五、构建

### GitHub Actions（推荐）

1. Actions → **Build Firmware** → Run workflow；
2. 参数：`config_seed = 1710.config`（默认）、`release_type = none | prerelease | release`；
3. 产物：运行页面的 Artifacts（`gemtek-1710.config-firmware`），或 `release_type` 非 `none` 时自动创建 Release。

构建流程（`.github/workflows/build-firmware.yml`）在标准 ImmortalWrt 流程之上多了三步：

| 步骤 | 作用 |
|------|------|
| `Prepare kixdns and daed packages` | 拉取 kixdns 源码与 daed 包定义到 `package/new/`，并把 BTF/BPF/veth/clsact 写进 airoha 子目标的内核片段（`target/linux/airoha/*/config-6.*`） |
| `Fetch plugin prebuilt payloads (kixdns + daed)` | 下载两个插件的预编译载荷并解包到 `package/new/*/prebuilt*/`，并把 `PATCH/daed-web` 覆盖到 daed WebUI 目录 |
| `Prepare footstrap theme (LuCI)` | 按 pin 拉取 footstrap 主题源码放进 `package/new/`，并带上自译中文 po（生成 `luci-i18n-footstrap-zh-cn`） |
| `Verify plugin integration (kixdns + daed)` | **构建后闸门**：校验 `.config` 插件与主题开关、内核 `.config` 里的 BTF/BPF/veth/clsact、产物中的插件包与镜像文件、以及**镜像 manifest 里确实有 footstrap 主题**；任一项缺失即判定失败，避免产出「插件/主题没装上」的固件 |

### 本地构建（可选）

```bash
git clone https://github.com/Quan-0505/ImmortalWrt-XR1710G.git
cd ImmortalWrt-XR1710G
./scripts/feeds update -a
./scripts/feeds install -a
bash scripts/fix-stale-golang-host.sh
bash scripts/apply-feed-patches.sh

# 插件装配（与 CI 一致）：kixdns 源码 + daed 包定义
git clone -q --depth 1 -b v1.6.0 https://github.com/JohnsonRan/luci-app-kixdns /tmp/luci-app-kixdns
mkdir -p package/new && cp -rf /tmp/luci-app-kixdns/{kixdns,luci-app-kixdns,kixdns-stats} package/new/
cp -rf PATCH/daed-pkg/daed package/new/daed
# 以及 workflow 中「Fetch plugin prebuilt payloads」两步（下载解包预编译载荷）

cp 1710.config .config
bash scripts/set-build-version.sh .config
make defconfig
make -j$(nproc) world 2>&1 | tee build.log
bash scripts/summarize-build-errors.sh build.log
```

构建环境：GNU/Linux（Debian 11+ 推荐）、AMD64、≥4GB 内存、≥25GB 磁盘；依赖见
[ImmortalWrt 官方文档](https://openwrt.org/docs/guide-developer/build-system/install-buildsystem)。
本地构建后请确认内核 `.config` 与产物中确实包含 BTF 与两个插件（可直接复用 CI 的
`Verify plugin integration` 步骤作为检查脚本）。

## 六、设备与硬件

默认管理地址 **http://192.168.2.1** 或 **http://immortalwrt.lan**，用户名 `root`，密码*无*。

| 项目 | 参数 |
|------|------|
| **SoC** | Airoha AN7581GT（1.3GHz 4 核 CPU + 8 核 NPU） |
| **内存 / 闪存** | 2GB / 512MB |
| **网口** | 2×10G RTL8261BE + 2×1G（AN7581 内置交换） |
| **无线** | MediaTek MT7996AV，2.4/5/6GHz 三频 Wi-Fi 7 |
| **PWM 风扇** | 新唐 NCT7802 |
| **电源** | 12V 5A |

| 设备 | 构建配置 | 设备树 |
|------|----------|--------|
| Gemtek/Brightspeed XR1710G（原版 U-Boot 分区） | [`1710.config`](1710.config) | [`an7581-xr1710g.dts`](target/linux/airoha/dts/an7581-xr1710g.dts) |
| Gemtek/Brightspeed XR1710G（OpenWrt U-Boot UBI 布局） | [`1710.config`](1710.config) | [`an7581-gemtek-xr1710g-ubi.dts`](target/linux/airoha/dts/an7581-gemtek-xr1710g-ubi.dts) |

无线规格（MT7996AV，BE19000）：

| 频段 | 芯片 | 规格 | 最高速率 |
|------|------|------|----------|
| WLAN1 | MT7976GN | 2.4GHz 4×4 4096QAM 40MHz | 1376 Mbps |
| WLAN2 | MT7977BN | 5GHz 4×4 4096QAM 160MHz | 5.76 Gbps |
| WLAN3 | MT7977AN | 6GHz 4×5 4096QAM 320MHz（backhaul） | 10 Gbps |

### 原厂数据与分区

- `factory_storage` 与旧写法 `ubi_factory` 只是设备树 phandle 标签，运行时都指向唯一的 UBI 卷 `factory`。
- XR1710G 的完整 DSD 中，`0x006c/0x0086` 是 17 字节文本 WAN/LAN MAC，MT7996 EEPROM/校准位于
  `0x5000`、长度 `0x1e00`。**不要**恢复旧布局那种「EEPROM 放在卷首、原始 MAC 放在 `0x5000/0x6000`」的重排镜像。
- `luci-app-airoha-factory` 会按板型选择旧布局 raw MAC 写入或 DSD 布局整卷读改写；UBI `factory` 卷回写需要 `ubiupdatevol`。

## 七、固件特性与默认行为

### 关键补丁（完整列表见 [patches-6.18](target/linux/airoha/patches-6.18) 与 [generic/pending-6.18](target/linux/generic/pending-6.18)）

- `743`、`744`、`747`：RTL8261BE/RTL8261N SerDes 调优、协商后重试与 USXGMII in-band 配置。
- `182-v7.4`：扩大 Airoha 小型 RX ring，缓解 PPPoE 等突发流量导致的 descriptor 耗尽。
- `221-01`：允许 Airoha 平台启用 CPU PM Domain。
- `675-02~05`：nft_flow_offload 桥接、WDMA 与 VLAN-aware bridge/PVID 映射。
- `910-02`、`912`、`913`：USB/PCIe 时钟、PCIe 3.0 x2 链路与复位修复。
- `181`、`924`、`926`：NPU 异常恢复、固件加载、coherent mailbox DMA 与 mailbox 等待时间限制。
- `915-01`、`916-02`、`9990`、`9993`、`9999-11`：PPE/flowtable 硬件卸载、WLAN 流绑定、VLAN ingress 与 XFRM 流支持。
- 无线栈：mt76 `001`（mt7996 PS sync TLV/MLO 稳定性）与 `9993`（operating-mode rate control）、
  mac80211 `411-mac80211-export-link-sta-capability-limits.patch`、hostapd（6GHz/EHT/radio mask/多 VAP 稳定性）。
- 本仓库追加的内核项：BTF/BPF/veth/clsact（供 daed 使用，见第一节）。

### 启动与设备定制

`03_wifi_defaults`（SSID/加密/US 区域码）、`03_wireless`（射频参数）、`18-xr1710g-firewall-defaults`
（默认软件/硬件 flow offload）、`99-ppe-reload`（无线接口建立后重载防火墙）、`packet-steering.sh`
（Wi-Fi worker/CPU 亲和性）、风扇服务、升级平台脚本，以及由 `airoha` feed 提供的附属 LuCI 应用。

### 网络与无线默认行为

- 默认 LAN 地址由构建配置的 `CONFIG_TARGET_PREINIT_IP` 决定：**本仓库为 `192.168.2.1`**（原仓库为 `192.168.50.1`）。
- IPv6 使用 SLAAC/EUI-64，关闭 DHCPv6/NDP 与 RA DNS/附加标志，减少国内网络环境下的兼容问题。
- 默认开启软件/硬件 flow offload；NPU 与 Wi-Fi 流绑定补丁已包含在内。

## 八、主要软件包

**内核模块**：`kmod-mt7996-firmware`、`kmod-mt7996e`、`airoha-en7581-mt7996-npu-firmware`、
`kmod-crypto-hw-eip93`、`kmod-nft-offload`、`kmod-br-netfilter`、`kmod-tcp-bbr`、`kmod-wireguard`、
`kmod-hwmon-nct7802`、`kmod-airoha-i2c`、`kmod-leds-gpio`、`kmod-gpio-button-hotplug`、
`kmod-phy-realtek`、`kmod-mt76-connac`、`kmod-mt76-core`、`rtl826x-firmware`。

**系统工具**：`bash`、`coreutils`、`curl`、`ip-full`、`ethtool-full`、`pciutils`、`uboot-envtools`、
`luci-theme-argon`、`luci-theme-bootstrap`、`luci-theme-glass`（由 `feeds.conf.default` 的 `glass` feed 安装）、
`default-settings-chn`。

**代理与网络核心**：`xray-core`、`simple-obfs-client`、`chinadns-ng`、`geoview`、`dns2socks`、
`microsocks`、`ipt2socks`。**插件**：`kixdns`(+stats)、`daed`（见第二节）。

**已从原仓库裁剪**：`lucky`、`smartdns`、`vlmcsd`、`msd_lite`、`udpxy`、`ddns-go`、`zerotier`、
`rtp2httpd`、`wechatpush`、`timewol`（含各自的 LuCI 应用与中文语言包）。

## 九、仓库结构

```
.github/workflows/     build-firmware.yml（构建+发布）、sync-upstream.yml（跟随上游）
1710.config            仅 XR1710G：multi-profile，一次构建两套镜像
2010.config            上游遗留（XG2010G），本仓库不构建
PATCH/daed-pkg/daed/   daed 包定义（版本、安装规则、prebuilt-data 装载）
PATCH/daed-web/        daed WebUI 覆盖层（构建时覆盖到 usr/share/daed/web）
scripts/               构建辅助：apply-feed-patches.sh、check-firmware-artifacts.sh、
                       check-gemtek-profile-isolation.sh、set-build-version.sh 等
target/linux/airoha/   设备树、内核与无线补丁、子目标内核片段（an7581）
```

工作流：

| 工作流 | 触发 | 功能 |
|--------|------|------|
| [build-firmware.yml](.github/workflows/build-firmware.yml) | 手动 | 装配插件 → 构建两套镜像 → 闸门校验 → 上传 Artifacts / 发布 Release |
| [sync-upstream.yml](.github/workflows/sync-upstream.yml) | 每 3 天 + 手动 | 同步 ImmortalWrt 上游 |

Release 约定：Tag 形如 `YYYYMMDD-<short-hash>`，名称含构建日期与短 hash；构建时会通过
[scripts/set-build-version.sh](scripts/set-build-version.sh) 写入 LuCI 可见的构建日期与 commit。

## 十、致谢与许可证

**设备支持与补丁全部来自上游项目**，本仓库只做插件装配与配置裁剪：

- [naoki66/ImmortalWrt-for-Gemtek-brightspeed](https://github.com/naoki66/ImmortalWrt-for-Gemtek-brightspeed) —— XR1710G/XG2010G 移植与全部内核/无线补丁
- [immortalwrt/immortalwrt](https://github.com/immortalwrt/immortalwrt)、[immortalwrt/luci](https://github.com/immortalwrt/luci)、[immortalwrt/packages](https://github.com/immortalwrt/packages)
- [openwrt/mt76](https://github.com/openwrt/mt76)（MediaTek Wi-Fi 驱动）、[openwrt/routing](https://github.com/openwrt/routing)
- [YYH2913/openwrt](https://github.com/YYH2913/openwrt)（XR1710G 6.18 内核集成参考）、[hurrian/openwrt-w1700k](https://github.com/hurrian/openwrt-w1700k)（PCIe 3.0 x2 补丁参考）、[lvcdy/openwrt_xr1710g](https://github.com/lvcdy/openwrt_xr1710g)（早期移植参考）
- [naoki66/luci-app-airoha](https://github.com/naoki66/luci-app-airoha)（Airoha LuCI 应用 feed）、[Gilly1970/Gemtek-W1700K](https://github.com/Gilly1970/Gemtek-W1700K)（风扇控制与 FlowSense）

**插件来源**：[JohnsonRan/luci-app-kixdns](https://github.com/JohnsonRan/luci-app-kixdns)（kixdns）、
[Quan-0505/rust-daed](https://github.com/Quan-0505/rust-daed)（daed / DaedNext）。

许可证：[GPL-2.0-only](https://spdx.org/licenses/GPL-2.0-only.html)（继承 ImmortalWrt）。
