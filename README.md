<div align="center">

# ImmortalWrt for Gemtek / Brightspeed XR1710G

**ImmortalWrt 25.12 定制固件 · KixDNS + DaedNext · footstrap 默认主题 · GitHub Actions 构建**

[![Build](https://img.shields.io/github/actions/workflow/status/Quan-0505/ImmortalWrt-XR1710G/build-firmware.yml?branch=master&label=Build&style=flat-square)](https://github.com/Quan-0505/ImmortalWrt-XR1710G/actions/workflows/build-firmware.yml)
[![Upstream](https://img.shields.io/badge/upstream-naoki66%2FImmortalWrt--for--Gemtek--brightspeed-blue?style=flat-square)](https://github.com/naoki66/ImmortalWrt-for-Gemtek-brightspeed)
[![Target](https://img.shields.io/badge/target-airoha%2Fan7581-0b5?style=flat-square)](target/linux/airoha/an7581)
[![Kernel](https://img.shields.io/badge/kernel-6.18-orange?style=flat-square)](target/linux/airoha/patches-6.18)
[![License](https://img.shields.io/badge/license-GPL--2.0--only-blue?style=flat-square)](https://spdx.org/licenses/GPL-2.0-only.html)
[![Downloads](https://img.shields.io/github/downloads/Quan-0505/ImmortalWrt-XR1710G/total?style=flat-square&label=downloads)](https://github.com/Quan-0505/ImmortalWrt-XR1710G/releases)

**只维护 XR1710G**（Airoha AN7581GT，2 GB RAM / 512 MB NAND）· 基于
[naoki66/ImmortalWrt-for-Gemtek-brightspeed](https://github.com/naoki66/ImmortalWrt-for-Gemtek-brightspeed) 定制

[📦 固件下载](#-固件下载) · [🚀 快速开始](#-快速开始) · [📡 设备与硬件](#-设备与硬件) · [🔧 自行编译](#-自行编译)

</div>

---


面向 **Gemtek / Brightspeed XR1710G**（Airoha AN7581GT，2 GB RAM / 512 MB NAND / Wi-Fi 7 MT7996AV）
的 ImmortalWrt 25.12 固件，由 GitHub Actions 构建与发布。

- **预装两个插件**：`kixdns`（含统计与 LuCI 应用）与 `daed`（DaedNext，rust-daed v3.1.3，内嵌 UI）；
- **默认管理地址 `192.168.2.1`**（`CONFIG_TARGET_PREINIT_IP` / `PREINIT_BROADCAST`）；
- **补齐 daed 的 eBPF 内核前提**（BTF / BPF / veth / clsact），并裁掉用不到的第三方插件；
- **只构建 XR1710G**：CI 的 profile 是 `DEVICE_gemtek_xr1710g-ubi`（`config.buildinfo` 可证：
  `CONFIG_TARGET_airoha_an7581_DEVICE_gemtek_xr1710g-ubi=y`），即 **OpenWrt U-Boot UBI 布局**
  那一套镜像；源码树里另有原厂 U-Boot 布局的设备定义（`gemtek_xr1710g`），需要时切过去自行构建。

---

<a id="diff"></a>
## 🧭 本仓库做了什么

- **预装插件**：`kixdns`（含 `kixdns-stats`、`luci-app-kixdns`）与 `daed`（rust-daed 3.1.3，内嵌 UI）；
  其余第三方插件一律关闭。
- **默认管理地址**：`192.168.2.1`（`CONFIG_TARGET_PREINIT_IP` / `PREINIT_BROADCAST`）。
- **内核**：开启 `DEBUG_INFO_BTF`、`BPF`、`BPF_SYSCALL`、`BPF_JIT(_ALWAYS_ON)`、`VETH`、
  `NET_SCH_INGRESS`、`NET_CLS_ACT`、`NET_CLS_BPF`，并关闭 `DEBUG_INFO_REDUCED`，生成完整 BTF
  （daed 的 eBPF/CO-RE 依赖它）。
- **设备范围**：仅 XR1710G，profile = `DEVICE_gemtek_xr1710g-ubi`（UBI 布局）。
- **新增目录**：[`PATCH/daed-pkg`](PATCH/daed-pkg)（daed 包定义）、[`PATCH/theme-footstrap-zh`](PATCH/theme-footstrap-zh)
  （主题中文翻译）。仓库里还留着 [`PATCH/daed-web`](PATCH/daed-web)（旧版 daed WebUI 覆盖层），但它**已不再参与构建** ——
  原因见下方「最近变更」。
- **主题**：LuCI 默认开机主题为 **footstrap**（含简体中文包），由
  `target/linux/airoha/an7581/base-files/etc/uci-defaults/91-xr1710g-theme.sh` 在首次开机时设定。
- **保留项**：设备与系统类 LuCI 应用（`luci-app-airoha-*`、`mesh-conf`、`netmode`、`upnp`、`firewall`、
  `arpbind`、`mlo`、`package-manager`、`autoreboot`）、系统工具类应用（`ttyd`/`usteer`/`watchcat`/`wol`/
  `ddns`/`wifihistory`/`wifischedule`）、三个主题与中文语言包。

### 最近变更（2026-10）

- **同步上游内核 6.18.54**：保留现有 lan2、CPU 频率、daed 与主题修复；CI 定位内核
  `.config` 时限制搜索深度并核对目录类型，避免误选 mac80211 backports 配置。
  run#24 的 UBI 产物已经通过 SHA256、FIT/DTB 与 manifest 核验，详见
  [验证记录](docs/CI-verification-20261010.md)。
- **发布前校验镜像**：每个 ITB 必须有唯一 checksum 记录并通过 SHA256 校验；两种布局
  分别构建，同一 release 只补缺失资产，tag 指向实际构建提交。
- **lan2 万兆口不再抖动**：删掉两份 DTS 里 `phy5`（= lan2）节点上的 `reset-before-id-read;`
  （[`an7581-xr1710g.dts`](target/linux/airoha/dts/an7581-xr1710g.dts) 第 363 行、
  [`an7581-gemtek-xr1710g-ubi.dts`](target/linux/airoha/dts/an7581-gemtek-xr1710g-ubi.dts) 第 389 行）。
  该属性会让 PHY 在读 ID 前多打一次 400 ms 硬复位，而 Realtek 补丁作者已写明「表尾再叠一次复位会清掉固件写入的
  SerDes SDS 位」—— 结果就是铜口显示 up、AN7581 侧收不到 USXGMII 对端字，表现为链路反复掉线。
  **两份都要改**：设备实际刷的是 `-ubi` 布局镜像，只改原版分区那份等于没改。
- **不再超频**：去掉 `airoha,force-direct-pll` 与 1.35 / 1.4 GHz 两档 OPP，CPU 上限回到原厂 **1.3 GHz**。
- **daed WebUI 改用载荷自带的那份**：仓库里那份 `PATCH/daed-web` 是初次提交时的旧前端（576 个文件），
  会把 rust-daed v3.1.3 载荷自带的 UI（103 个文件）整体遮蔽、界面版本号停在旧 UI 的 `v3.1.0`；
  现已不再覆盖，**内核与 UI 同源**，镜像体积也小了约 8 MB。

---

## 📦 固件下载

最新构建在 [Releases](https://github.com/Quan-0505/ImmortalWrt-XR1710G/releases)：每次 CI 成功后附上
`*.itb` 镜像；构建配置与镜像 sha256 见同次 Actions 运行的 Artifacts。
CI 会分别构建**两种闪存布局**，按当前布局选对应文件（两种布局**不能互刷**），刷写细节见
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

## 🔧 自行编译


### GitHub Actions（推荐）

1. Actions → **Build Firmware** → Run workflow；
2. 参数：`config_seed = 1710.config`（UBI 布局，默认）或 `1710-factory.config`（原版 U-Boot 分区）、`release_type = none | prerelease | release`；
3. 产物：运行页面的 Artifacts（`gemtek-<种子名>-firmware`），或 `release_type` 非 `none` 时自动创建 Release。

构建流程（`.github/workflows/build-firmware.yml`）在标准 ImmortalWrt 流程之上多了三步：

| 步骤 | 作用 |
|------|------|
| `Prepare kixdns and daed packages` | 拉取 kixdns 源码与 daed 包定义到 `package/new/`，并把 BTF/BPF/veth/clsact 写进 airoha 子目标的内核片段（`target/linux/airoha/*/config-6.*`） |
| `Fetch plugin prebuilt payloads (kixdns + daed)` | 下载两个插件的预编译载荷并解包到 `package/new/*/prebuilt*/`；daed 的 WebUI **直接用载荷自带的那份**（不再叠加仓库里的旧覆盖层） |
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
rm -rf feeds/packages/net/daed && cp -rf PATCH/daed-pkg/daed feeds/packages/net/daed
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
| Gemtek/Brightspeed XR1710G（原版 U-Boot 分区） | [`1710-factory.config`](1710-factory.config) | [`an7581-xr1710g.dts`](target/linux/airoha/dts/an7581-xr1710g.dts) |
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
- 本仓库追加的内核项：BTF/BPF/veth/clsact（供 daed 使用）。

### 启动与设备定制

`03_wifi_defaults`（SSID/加密/US 区域码）、`03_wireless`（射频参数）、`18-xr1710g-firewall-defaults`
（默认软件/硬件 flow offload）、`99-ppe-reload`（无线接口建立后重载防火墙）、`packet-steering.sh`
（Wi-Fi worker/CPU 亲和性）、风扇服务、升级平台脚本，以及由 `airoha` feed 提供的附属 LuCI 应用。

### 网络与无线默认行为

- 默认 LAN 地址由构建配置的 `CONFIG_TARGET_PREINIT_IP` 决定：**`192.168.2.1`**。
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
`microsocks`、`ipt2socks`。**插件**：`kixdns`(+stats)、`daed`（rust-daed）。

**未收录**：`lucky`、`smartdns`、`vlmcsd`、`msd_lite`、`udpxy`、`ddns-go`、`zerotier`、`rtp2httpd`、
`wechatpush`、`timewol`（含各自的 LuCI 应用与中文语言包）。

---

<a id="structure"></a>
## 📂 仓库结构


```
.github/workflows/     build-firmware.yml（构建+发布）
1710.config            仅 XR1710G：profile = DEVICE_gemtek_xr1710g-ubi（OpenWrt U-Boot UBI 布局）
1710-factory.config            仅 XR1710G：profile = DEVICE_gemtek_xr1710g（原版 U-Boot 分区）
2010.config            上游遗留（XG2010G），本仓库不构建
PATCH/daed-pkg/daed/   daed 包定义（版本、安装规则、prebuilt-data 装载）
PATCH/daed-web/        daed WebUI 旧覆盖层（已停用，不再参与构建；保留仅为可追溯）
scripts/               构建辅助：apply-feed-patches.sh、check-firmware-artifacts.sh、
                       check-gemtek-profile-isolation.sh、set-build-version.sh 等
target/linux/airoha/   设备树、内核与无线补丁、子目标内核片段（an7581）
```

工作流：

| 工作流 | 触发 | 功能 |
|--------|------|------|
| [build-firmware.yml](.github/workflows/build-firmware.yml) | 手动 | 装配插件 → 构建（UBI 布局） → 闸门校验 → 上传 Artifacts / 发布 Release |

> ℹ️ 上游同步（naoki66）为**手动**操作，不设自动化工作流。原 `sync-upstream.yml`
> 跟随的是 `immortalwrt/immortalwrt` 而非设备支持仓库 naoki66，且会在成功合并后
> 无条件 `git push origin master`；上游作者本人该工作流在 2026-09-28 之后连续三次失败
> （`#58`/`#59`/`#60`），说明这类合并必须人工解决冲突。为避免自动化把 master 推离设备
> 支持基线，已于 2026-10-09 移除。

Release 约定：Tag 形如 `YYYYMMDD-<short-hash>`，名称含构建日期与短 hash；构建时会通过
[scripts/set-build-version.sh](scripts/set-build-version.sh) 写入 LuCI 可见的构建日期与 commit。

---

<a id="credits"></a>
## 🤝 致谢

本仓库的设备移植、设备树、内核与无线补丁来自 [@naoki66](https://github.com/naoki66) 的
[ImmortalWrt-for-Gemtek-brightspeed](https://github.com/naoki66/ImmortalWrt-for-Gemtek-brightspeed)；
固件基于 [ImmortalWrt](https://github.com/immortalwrt/immortalwrt) 与 OpenWrt 生态；
`kixdns` 来自 [JohnsonRan/luci-app-kixdns](https://github.com/JohnsonRan/luci-app-kixdns)。

感谢以上作者与上游社区的公开工作。

许可证：[GPL-2.0-only](https://spdx.org/licenses/GPL-2.0-only.html)（继承 ImmortalWrt）。
