<div align="center">

# ImmortalWrt for Gemtek / Brightspeed XR1710G

**ImmortalWrt 25.12 定制固件 · KixDNS + DaedNext · footstrap 默认主题 · GitHub Actions 构建**

[![Build](https://img.shields.io/github/actions/workflow/status/Quan-0505/ImmortalWrt-XR1710G/build-firmware.yml?branch=master&label=Build&style=flat-square)](https://github.com/Quan-0505/ImmortalWrt-XR1710G/actions/workflows/build-firmware.yml)
[![Sync](https://img.shields.io/github/actions/workflow/status/Quan-0505/ImmortalWrt-XR1710G/sync-upstream.yml?branch=master&label=Sync&style=flat-square)](https://github.com/Quan-0505/ImmortalWrt-XR1710G/actions/workflows/sync-upstream.yml)
[![Upstream](https://img.shields.io/badge/upstream-naoki66%2FImmortalWrt--for--Gemtek--brightspeed-blue?style=flat-square)](https://github.com/naoki66/ImmortalWrt-for-Gemtek-brightspeed)
[![Target](https://img.shields.io/badge/target-airoha%2Fan7581-0b5?style=flat-square)](target/linux/airoha/an7581)
[![Kernel](https://img.shields.io/badge/kernel-6.18-orange?style=flat-square)](target/linux/airoha/patches-6.18)
[![License](https://img.shields.io/badge/license-GPL--2.0--only-blue?style=flat-square)](https://spdx.org/licenses/GPL-2.0-only.html)
[![Downloads](https://img.shields.io/github/downloads/Quan-0505/ImmortalWrt-XR1710G/total?style=flat-square&label=downloads)](https://github.com/Quan-0505/ImmortalWrt-XR1710G/releases)

**只维护 XR1710G**（Airoha AN7581GT，2 GB RAM / 512 MB NAND）· 基于
[naoki66/ImmortalWrt-for-Gemtek-brightspeed](https://github.com/naoki66/ImmortalWrt-for-Gemtek-brightspeed) 定制

[📦 固件下载](#-固件下载) · [🚀 快速开始](#-快速开始) · [🧩 预装插件](#-预装插件) · [📡 设备与硬件](#-设备与硬件) · [🔧 自行编译](#-自行编译) · [🐞 构建诊断](#-构建期诊断为什么从-2026-09-24-起一直卡在-configure)

</div>

---


只针对 **Gemtek / Brightspeed XR1710G**（Airoha AN7581GT）的 ImmortalWrt 固件。设备树、内核与无线补丁、
分区/刷写方案全部继承自 [naoki66/ImmortalWrt-for-Gemtek-brightspeed](https://github.com/naoki66/ImmortalWrt-for-Gemtek-brightspeed)，
本仓库在原仓库基础上只做三件事：
1. **只预装两个插件**：`kixdns`（含统计）与 `rust-daed`（DaedNext）；
2. **默认管理地址改为 `192.168.2.1`**（与原仓库的 `192.168.50.1` 不同）；
3. **补齐 daed 需要的 eBPF 内核前提**（BTF / BPF / veth / clsact），并裁掉一批用不到的第三方插件。
> 本仓库只维护 XR1710G。CI 实际构建的 profile 是 `DEVICE_gemtek_xr1710g-ubi`
> （`config.buildinfo` 可证：`CONFIG_TARGET_airoha_an7581_DEVICE_gemtek_xr1710g-ubi=y`），
> 即 **OpenWrt U-Boot UBI 布局**那一套镜像；源码树里另有原厂 U-Boot 布局的设备定义
> （`gemtek_xr1710g`），需要时把 profile 切过去自行构建。
> 原仓库里的 XG2010G / PON 支持仍然存在于源码树中（`2010.config` 等），但本仓库不构建、不验证。

---

<a id="diff"></a>
## 🔀 与原仓库的差异


| 项目 | 原仓库 | 本仓库 |
|------|--------|--------|
| 预装插件 | `lucky`、`smartdns`、`vlmcsd`、`msd_lite`、`udpxy`、`ddns-go`、`zerotier`、`rtp2httpd`、`wechatpush`、`timewol` | **只留 `kixdns`（含 `kixdns-stats`、`luci-app-kixdns`）与 `daed`**，上述第三方全部关闭 |
| 默认管理地址 | `192.168.50.1` | **`192.168.2.1`**（`CONFIG_TARGET_PREINIT_IP` / `PREINIT_BROADCAST`） |
| 内核配置 | `CONFIG_DEBUG_INFO=y` + `DEBUG_INFO_REDUCED=y` | 追加 `DEBUG_INFO_BTF`、`BPF`、`BPF_SYSCALL`、`BPF_JIT(_ALWAYS_ON)`、`VETH`、`NET_SCH_INGRESS`、`NET_CLS_ACT`、`NET_CLS_BPF`，并**关闭 `DEBUG_INFO_REDUCED`**（生成完整 BTF，daed 的 eBPF 依赖它） |
| 设备范围 | XR1710G + XG2010G | **仅 XR1710G**（profile = `DEVICE_gemtek_xr1710g-ubi`，UBI 布局） |
| 新增目录 | — | [`PATCH/daed-pkg`](PATCH/daed-pkg)（daed 包定义）、[`PATCH/daed-web`](PATCH/daed-web)（daed WebUI 覆盖层）、[`PATCH/theme-footstrap-zh`](PATCH/theme-footstrap-zh)（主题中文翻译） |
| LuCI 主题 | argon / bootstrap / glass | 追加 **footstrap 并设为默认开机主题**（`target/linux/airoha/an7581/base-files/etc/uci-defaults/91-xr1710g-theme.sh`）；中文包按 luci feed 的实际命名 `luci-i18n-footstrap-zh-cn` 选择 |
| feed 版本 | 全部跟随上游 master | 同样不锁版本（`patches/feeds/**` 与 feed 必须同步演进，见第四节） |
| 保留项 | — | 用户点名的 12 个 LuCI 应用、系统工具类应用（`ttyd`/`usteer`/`watchcat`/`wol`/`ddns`/`wifihistory`/`wifischedule`）、三个主题与中文语言包 |

设备与系统类应用（`luci-app-airoha-npu`、`luci-app-airoha-fancontrol`、`luci-app-airoha-factory`、
`luci-app-airoha-recovery`、`luci-app-mesh-conf`、`luci-app-netmode`、`luci-app-upnp`、`luci-app-firewall`、
`luci-app-arpbind`、`luci-app-mlo`、`luci-app-package-manager`、`luci-app-autoreboot`）全部保留。

---

<a id="plugins"></a>
## 🧩 预装插件


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

---

<a id="downloads"></a>
## 📦 固件下载

最新构建在 [Releases](https://github.com/Quan-0505/ImmortalWrt-XR1710G/releases)：每次 CI 成功后会附上
`*.itb` 镜像与 `config.buildinfo` / `feeds.buildinfo` / `version.buildinfo` / `sha256sums`。
本仓库 CI 产出的是 **OpenWrt U-Boot UBI 布局**那一套（原厂 U-Boot 布局的设备定义在源码树里但未被
profile 选中，两种布局**不能互刷**），刷写细节见
[🚀 快速开始](#-快速开始)。

---

<a id="quick-start"></a>
## 🚀 快速开始


### 登录

- 管理地址：**http://192.168.2.1** 或 **http://immortalwrt.lan**，用户名 `root`，密码**无**（首次登录请立即设置）。
- 首次启动的无线网络为 `ImmortalWrt-2G`、`ImmortalWrt-5G`、`ImmortalWrt-6G`，统一初始密码 `12345678`。
  2.4GHz 使用 WPA2，5GHz 使用 WPA2/WPA3 混合，6GHz 使用 WPA3；请尽快修改管理密码与无线密码。

### 下载与刷写

- 下载：[Releases 页面](https://github.com/Quan-0505/ImmortalWrt-XR1710G/releases) 或对应 Actions 运行的 Artifacts。
- 固件文件（`.itb`）：
  - 原版 U-Boot 分区：`immortalwrt-*-airoha-an7581-gemtek_xr1710g-squashfs-sysupgrade.itb`
  - OpenWrt U-Boot UBI 布局：`immortalwrt-*-airoha-an7581-gemtek_xr1710g-ubi-squashfs-sysupgrade.itb`

  > **本仓库 CI 目前只产出第二条（`-ubi`）**：种子里两个设备符号都写了，但 defconfig 的 choice 会
  > 把单选收敛为一台（构建日志里的 `changes choice state` 警告即此），最终 `config.buildinfo` 里
  > 只有 `CONFIG_TARGET_airoha_an7581_DEVICE_gemtek_xr1710g-ubi=y`。要原厂 U-Boot 布局那套，
  > 需自行把 profile 切到 `gemtek_xr1710g` 再构建。
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

---

<a id="diagnostics"></a>
## 🐞 构建期诊断：为什么从 2026-09-24 起一直卡在 Configure


Actions 日志在本仓库读不到（token 没有 Actions 读取权限），所以 `Apply feed patches` 与
`Configure` 两步都会把输出 tee 到文件（`feed-patches.log` / `configure.log`），失败时随
`gemtek-configure-diagnostics` artifact 上传 —— 任何失败都能在几分钟内看到原文，不必猜。

证据链（run#6 的 `configure.log` + 三份种子对比）：

1. **`make defconfig` 是成功的**：日志里 `### make defconfig` 之后走到了
   `### gemtek profile isolation`，说明链条没有停在 defconfig。日志里那些
   `recursive dependency detected`（`PACKAGE_mpd-full` 自依赖、`squeezelite-custom` 与
   `SQUEEZELITE_WMA_ALAC` 互相依赖）**只是告警**：`sound/squeezelite` 最后一次改动是
   2026-08-11，2026-09-23 的成功构建同样带着它。
2. 真正失败的是 `scripts/check-gemtek-profile-isolation.sh`：
   `xr1710g config is missing required package: airoha-an7581-mt7996-board`。该包是
   `HIDDEN:=1`，它的值由设备定义 `target/linux/airoha/image/an7581.mk` 中
   `Device/gemtek_xr1710g-common` 的 `DEVICE_PACKAGES` 推导，**种子里的显式值会被 defconfig 覆盖**。
3. 所以关键在设备符号。2026-09-23 的绿灯种子用的是主符号
   `CONFIG_TARGET_airoha_an7581_DEVICE_gemtek_xr1710g-ubi=y`
   （`CONFIG_TARGET_PROFILE="DEVICE_gemtek_xr1710g-ubi"`）；从 2026-09-27 那份种子开始，
   主符号变成 `is not set`，只剩派生形式
   `CONFIG_TARGET_DEVICE_airoha_an7581_DEVICE_gemtek_xr1710g=y` —— 于是
   `DEVICE_PACKAGES` 不再推导进 `.config`，隔离检查必然失败。参考仓库 run#62/#63 与本仓库
   前几轮卡的都是这一条（`TARGET_PROFILE` 也从 `-ubi` 变成了非 ubi 那台）。

修复：`1710.config` 用**主符号**把两台设备都选上（`gemtek_xr1710g` 与 `gemtek_xr1710g-ubi` 各一行
`=y`；实测 defconfig 会按 choice 折叠为 `-ubi` 一台，与参考仓库 09-23 成功那次的 profile 一致），
`TARGET_PROFILE` 对齐绿灯种子，并额外显式写
`CONFIG_PACKAGE_airoha-an7581-mt7996-board=y` 作为双保险。

另外两条经验：

- **feed 不要锁版本**。曾把 `packages` 锁到 2026-09-23 想绕过上游告警，`Apply feed patches`
  立刻失败：`patches/feeds/**` 是按当前 feed 上下文写的，`git apply` 在旧 feed 上找不到上下文
  （脚本对「feed 存在但补丁打不上」是 `exit 1`）。上游出问题就加 `patches/feeds/**` 补丁。
- **不要在条件上下文里用函数包装会失败的步骤**：bash 连函数体内的 `set -e` 也不生效（手册明文），
  失败会被后面的 `grep` 成功掩盖 —— 第一版就是这样做出了假绿灯。现在改成
  `step && step` 链 + `rc=$?` 显式判定，并用 `### 步骤名` 标出失败位置。

---

<a id="build"></a>
## 🔧 自行编译


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

---

<a id="hardware"></a>
## 📡 设备与硬件


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

---

<a id="defaults"></a>
## ⚙️ 固件特性与默认行为


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

---

<a id="packages"></a>
## 📦 主要软件包


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

---

<a id="structure"></a>
## 📂 仓库结构


```
.github/workflows/     build-firmware.yml（构建+发布）、sync-upstream.yml（跟随上游）
1710.config            仅 XR1710G：profile = DEVICE_gemtek_xr1710g-ubi（UBI 布局）
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
| [build-firmware.yml](.github/workflows/build-firmware.yml) | 手动 | 装配插件 → 构建（UBI 布局） → 闸门校验 → 上传 Artifacts / 发布 Release |
| [sync-upstream.yml](.github/workflows/sync-upstream.yml) | 每 3 天 + 手动 | 同步 ImmortalWrt 上游 |

Release 约定：Tag 形如 `YYYYMMDD-<short-hash>`，名称含构建日期与短 hash；构建时会通过
[scripts/set-build-version.sh](scripts/set-build-version.sh) 写入 LuCI 可见的构建日期与 commit。

---

<a id="credits"></a>
## 🤝 致谢与许可


**设备支持与补丁全部来自上游项目**，本仓库只做插件装配与配置裁剪：

- [naoki66/ImmortalWrt-for-Gemtek-brightspeed](https://github.com/naoki66/ImmortalWrt-for-Gemtek-brightspeed) —— XR1710G/XG2010G 移植与全部内核/无线补丁
- [immortalwrt/immortalwrt](https://github.com/immortalwrt/immortalwrt)、[immortalwrt/luci](https://github.com/immortalwrt/luci)、[immortalwrt/packages](https://github.com/immortalwrt/packages)
- [openwrt/mt76](https://github.com/openwrt/mt76)（MediaTek Wi-Fi 驱动）、[openwrt/routing](https://github.com/openwrt/routing)
- [YYH2913/openwrt](https://github.com/YYH2913/openwrt)（XR1710G 6.18 内核集成参考）、[hurrian/openwrt-w1700k](https://github.com/hurrian/openwrt-w1700k)（PCIe 3.0 x2 补丁参考）、[lvcdy/openwrt_xr1710g](https://github.com/lvcdy/openwrt_xr1710g)（早期移植参考）
- [naoki66/luci-app-airoha](https://github.com/naoki66/luci-app-airoha)（Airoha LuCI 应用 feed）、[Gilly1970/Gemtek-W1700K](https://github.com/Gilly1970/Gemtek-W1700K)（风扇控制与 FlowSense）

**插件来源**：[JohnsonRan/luci-app-kixdns](https://github.com/JohnsonRan/luci-app-kixdns)（kixdns）、
[Quan-0505/rust-daed](https://github.com/Quan-0505/rust-daed)（daed / DaedNext）。

许可证：[GPL-2.0-only](https://spdx.org/licenses/GPL-2.0-only.html)（继承 ImmortalWrt）。
