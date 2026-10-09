# 交接：XR1710G lan2 万兆抖动修复（一行 DTS 改动 + 重编 + 重刷）

> 本文自包含。接手方无需阅读其它对话即可执行。
> 生成于 2026-10-08，由「刷入ImmortalWrt固件到路由器」会话（`session-ab450929-9af0-4bf3-be21-20a6b6dbf4c9`）交接。
> 配套文件：`FIX-lan2-10g-reset-before-id-read.patch`（可直接 `git apply`）、`RCA-lan2-10g-flapping.md`（完整证据链）。

---

## 0. 任务一句话

在 `Quan-0505/ImmortalWrt-XR1710G` 仓库里**删掉一行设备树属性**，重编固件并刷入，验证 lan2 的万兆链路抖动是否消失。

```bash
# 在仓库根目录
sed -i '/reset-before-id-read;/d' target/linux/airoha/dts/an7581-xr1710g.dts
git diff --stat          # 应当只有这一处、-1 行
```

**只改这一处。不要顺手改别的。** 理由见 §3「一次只动一个变量」。

---

## 1. ⚠️ 刷机前必读：UBI 布局错配（最容易变砖的一步）

**本机 chainloader 是 UBI 1.5 布局，而仓库构建出的镜像内嵌 UBI 2.0 布局的设备树。直接刷 release 镜像会因 DTB 描述与 chainloader 边界不符而无法启动。**

| | 分区布局 | 来源 |
|---|---|---|
| **本机实际** | `mtd0 vendor 0x0/0x600000`、`mtd1 chainloader 0x600000/0x100000`、`mtd2 ubi 0x700000/0x1d9c0000`、`mtd3 reserved_bmt 0x1e0c0000/0x01f40000` | 设备实况 |
| 仓库两套 DTS + naoki66 / YYH2913 / orangeyoo 全部镜像 | `ubi 0x700000/0x1b700000`、`reserved_bmt 0x1be00000/0x04200000` | 仓库源码 |

**本次正确的做法（与上一轮成功刷入时相同）**：把镜像内嵌 DTB 的分区节点**改回 UBI 1.5 布局**（同长度改名 + 重算 fdt hash），再刷 `*-sysupgrade.itb`。

**上游正解**（`DEVICE_COMPAT_MESSAGE` 明示）：先用 http-uboot 装新布局 chainloader，再进恢复模式重建 UBI。**带配置的普通 sysupgrade 不安全。**

**恢复安全网**（万一刷坏）：
- http-uboot：`192.168.255.1:80`，界面选 **UBI 1.5**；只写 chainloader 槽 `0x600000`（≤1 MiB），不触碰原厂一级 bootloader
- `bootcmd=run boot_ubi || http_recovery` —— UBI 启动失败会自动掉进 Web 恢复
- 也可开机按住 reset（GPIO0 低有效）
- **界面布局选择必须与镜像内嵌 FDT 一致**，否则 `not enough PEBs` → `Waiting for root device /dev/fit0`

---

## 2. 精确改动位置

文件：`target/linux/airoha/dts/an7581-xr1710g.dts`（master 分支，446 行）

```dts
   357 | 	pinctrl-0 = <&mdio_pins>;
   358 | 	mdio {
   359 | 		phy5: ethernet-phy@5 {                          /* ← lan2 */
   360 | 			compatible = "ethernet-phy-ieee802.3-c45";
   361 | 			reg = <5>;
   362 | 			reset-gpios = <&en7581_pinctrl 46 GPIO_ACTIVE_LOW>;
   363 | 			reset-before-id-read;                   /* ★★ 删掉这一行 ★★ */
   364 | 			reset-assert-us = <200000>;
   365 | 			reset-deassert-us = <200000>;
   366 | 			tx-polarity = <PHY_POL_INVERT>;
   367 | 			rx-polarity = <PHY_POL_INVERT>;
   368 | 			realtek,patch-rtk-serdes;
   369 | 		};
   370 | 		phy8: ethernet-phy@8 {                          /* ← wan，本来就没有，不要动 */
   371 | 			compatible = "ethernet-phy-ieee802.3-c45";
   372 | 			reg = <8>;
   373 | 			reset-gpios = <&en7581_pinctrl 31 GPIO_ACTIVE_LOW>;
   374 | 			reset-assert-us = <200000>;
   375 | 			reset-deassert-us = <200000>;
   376 | 			tx-polarity = <PHY_POL_INVERT>;
   377 | 			rx-polarity = <PHY_POL_INVERT>;
   378 | 			realtek,patch-rtk-serdes;
   379 | 		};
```

**只删第 363 行。`realtek,patch-rtk-serdes`（368 / 378 行）必须保留** —— 它是社区专门为 XR1710G 加的 SerDes 修复，去掉会退回已知有问题的状态。详见 §6「不要做的事」。

---

## 3. 为什么是这一行（证据链）

### 3.1 它是两个万兆口唯一的配置差异

同一个设备、同一颗 PHY 型号（Realtek RTL8261BE）、同为 10G、接同一台交换机：

| 口 | MDIO 地址 | `reset-before-id-read` | 实测 10G 表现 |
|---|---|---|---|
| **lan2** | `mt7530-0:05` (PHYAD 5) | **有** | ❌ 反复抖动（曾录得 down=8 / up=8） |
| **wan** | `mt7530-0:08` (PHYAD 8) | 无 | ✅ 15.9 GB 实测零错误、零链路事件 |

对设备实跑 DTB（`/sys/firmware/fdt`，自写 FDT 解析器解出 202 节点）与仓库源码做了逐属性差分，**两个 PHY 节点除这一行外全部相同**（`tx/rx-polarity`、`reset-gpios`、`reset-assert/deassert-us`、`realtek,patch-rtk-serdes` 全部一致；`reset-gpios` 仅 phandle 编号因重编译而不同，GPIO 号 46/31 一致）。

### 3.2 该属性真实存在且被执行（这一条最容易被误判）

实现方**不在 mainline 内核、也不在 `realtek.ko` 里**，而在：

```
target/linux/generic/hack-6.18/705-net-phy-reset-PHY-before-reading-its-ID-when-requested.patch
（ImmortalWrt，作者 Tianling Shen <cnsztl@immortalwrt.org>）
```

补丁在 `drivers/net/mdio/fwnode_mdio.c` 中：

```c
/* 第 44 行，逐字确认 */
if (!fwnode_property_read_bool(fwnode, "reset-before-id-read"))
        return 1;

reset_gpio = fwnode_gpiod_get_index(fwnode, "reset", 0, GPIOD_OUT_HIGH, "PHY pre-ID reset");
...
fwnode_property_read_u32(fwnode, "reset-assert-us",   &assert_us);
fwnode_property_read_u32(fwnode, "reset-deassert-us", &deassert_us);
if (assert_us)   fsleep(assert_us);          /* 本板 200000 us */
gpiod_set_value_cansleep(reset_gpio, 0);
if (deassert_us) fsleep(deassert_us);        /* 本板 200000 us */
```

⇒ 它让 lan2 的 PHY 在**读 ID 之前**先被硬复位 **400 ms**（200 拉低 + 200 放开），随后置 `phy->mdio.reset_state = 0`、抑制常规复位。
⇒ **wan 完全没有这个动作。**

> ⚠️ **接手方注意**：如果你用「mainline 源码里搜不到」来否定这个属性，会得出错误结论。它只存在于本仓库的 `target/linux/generic/hack-*` 里。

### 3.3 该动作的已知后果，由本仓库的补丁作者亲自写明

`743-net-phy-realtek-restore-optional-RTK-SerDes-patch.patch` 原文：

> **A second reset** at the end of the table was found to **clear firmware-programmed SDS 6.0x0d, 6.0x0e, and 6.0x1d bits.** The PHY then reached Base-R block lock while the **AN7581 received no USXGMII partner word**.

`744-net-phy-realtek-reapply-RTK-SerDes-after-aneg.patch` 原文：

> The PHY can then **report a completed copper link while the connected AN7581 USXGMII PCS receives no partner word or carrier**.

⇒ 即：**铜口链路 up，但 MAC/PCS 侧拿不到 carrier** —— 这正是「链路抖动」的电气本质。

### 3.4 历史背景（说明为什么不能简单照抄卖家固件）

从 GitHub 提交历史看：

```
2026-08-31  63ab99a67c  net: phy: realtek: stabilize XR1710G host SerDes
                        （把适配过的 RTL826x flow_s 操作恢复、让两个 XR1710G PHY 启用、
                          并在铜口自协商后重新施加这些值）
2026-09-06  d3a0fa1b7e  添加Realtek PHY的SerDes补丁支持
```

⇒ **这两个补丁是社区专门为 XR1710G 的主机侧 SerDes 不稳而写的修复**，不是随内核来的。
⇒ 卖家稳定固件的 DTB（`r39859-fd28cb248b`，内核 6.18.35，187 节点）**两个属性都没有**：既无 `reset-before-id-read`，也无 `realtek,patch-rtk-serdes`。
⇒ **所以不能简单等于"照抄卖家 DTS"** —— 正确做法是**保留 SerDes 补丁、只去掉那个会破坏 SDS 的多余复位**。

### 3.5 为什么删掉是安全的

`phy@8`（wan）**本身就是反证**：同型号 PHY、同一条 MDIO 总线、同一版固件，**它没有这个属性，照样被正确识别并稳定工作**。
该属性存在的理由是「某些 PHY 在硬复位前不响应 ID 读」（705 号补丁 L4-6 原文），而这两颗 RTL8261BE 明显不属于那一类。⇒ 对 lan2 而言它是**纯冗余 + 副作用**。

---

## 4. 刷入后的验证步骤

### 4.1 基线判据（刷前刷后各取一次）

```sh
# 两个口必须分开数！两个口日志前缀只差 PHY 地址
logread | grep -c 'lan2: Link is Down'          # lan2 在 mt7530-0:05
logread | grep -c 'wan: Link is Down'           # wan  在 mt7530-0:08
logread | grep 'mt7530-0:05' | grep -c 'pulsed RTK'      # 仅 lan2
logread | grep 'mt7530-0:08' | grep -c 'pulsed RTK'      # 仅 wan
logread | grep -c 'carrier lost with copper link up'
```

**判读要点：**

- `pulsed RTK SerDes ... after copper AN` + `carrier recovered after 1 flow_s pulse(s)` —— **2.5G / 5G / 10G 每一次 link-up 都会恰好出现一次，属正常握手，不是故障信号。** 不要把它当病灶计数。
- 真正要看的是 **`lan2: Link is Down` 在稳定挂载期间的增量**。刷前在「lan2 + 交换机 + 全屋」组合下曾录得 down=8 / up=8。

### 4.2 复现测试（必须在同一启动周期内做）

1. 把下游交换机的网线接到 **lan2**（本机 lan2 与 lan3/lan4 是**两条独立硬件通路**：lan2 走外置 RTL8261BE `airoha_eth 1fb50000.ethernet`，lan3/lan4 走 SoC 内置交换机 `mt7530-mmio 1fb58000.switch`）。
2. 加负载：让 PC 对 lan2 侧发满流量，同时让路由器向外发（**发送方向尤其重要** —— 历次"稳定"的观测里路由器几乎只收不发，这是唯一没测透的维度）。
3. 持续观察 **≥30 分钟**：

```sh
/etc/10g-monitor.sh status      # 设备上已部署的监测器 v2（按端口分离计数）
/etc/10g-monitor.sh report
tail -n 20 /overlay/10g-test.log
```

**通过判据**：稳定期内 `lan2: Link is Down` 增量为 **0**，且协商速率稳定在 **10000Mb/s**（不出现 5000→2500 的降级）。

### 4.3 建议同时记录的一组对照

| 组合 | 目的 |
|---|---|
| lan2 + 交换机 + 满负载 | 主验证 |
| lan2 + PC 网卡（Realtek 5GbE）| 已知稳定，作为"未回归"检查 |
| wan + 全屋（现状，2.5G）| 已知稳定，作为"未回归"检查 |

---

## 5. 如果没修好（否证条件与下一嫌疑）

**这条结论的否证条件**：删掉该行、重编重刷后，lan2 在「交换机 + 负载」下**仍然抖动**。

此时按顺序排查（**仍然一次只动一个变量**）：

1. **`airoha,tx-fir`** —— 由 `629-net-pcs-airoha-add-optional-USXGMII-TX-FIR-override.patch` 引入，是 10G **发送**侧唯一还没被排除的调优旋钮，**当前 DTS 两个口都没有设置**。补丁作者自述"无元组通过可复现测试"，属未验证钩子 —— 需要试值，不是照抄。
2. **`744` 的脉冲时长** —— 原文里 `10–12 ms` 是作者**在某一台机器上实测**得出的值，换板可能不适用。可作为参数扫描对象。
3. **`628` 的 RX 校准 crossing search** —— 已随固件包含，但参数是否适配本板未知。
4. **补丁 622 被静默删除的那条线索**（naoki66 线）：原文说 *"This is needed on the Gemtek XR1710G LAN2 path. Its vendor U-Boot writes **SDS page 6 register 3 to 0x88c6**, while the common Linux initialization sequence currently leaves that board setting out."* 该属性与驱动支持在 commit `45bd3239`(2026-09-28) 被删除且无解释。
   ⚠️ **光加 DTS 无效**：实测 `strings /lib/modules/6.18.52/realtek.ko` 中**既无** `realtek,sds-mode` **也无** `configured SDS mode`。**驱动端 `RTL826X_SDS_HOST_MODE_PAGE 6 / REG 3` 与 `rtk826x_config_sds_mode()` 需一并恢复。**

---

## 6. 不要做的事

| ✗ 不要 | 原因 |
|---|---|
| **不要删 `realtek,patch-rtk-serdes`** | 它是社区专门为 XR1710G 主机侧 SerDes 不稳写的修复，去掉等于退回已知有问题的状态。本任务的判断是"保留补丁、只去掉破坏 SDS 的多余复位"。 |
| **不要一次改多个变量** | 删 `reset-before-id-read` 与调 `tx-fir` 若同批刷入，无论结果好坏都无法归因。本次只删一行。 |
| **不要照抄卖家 DTB** | 卖家那份是两个属性都没有（它构建时该特性可能还没引入），直接照抄会连 SerDes 修复一起丢掉。 |
| **不要用「加重置重训」治抖动** | 743 号补丁明写：表尾再叠一次 DTE XS / PCS / TXPLL reset 会清掉固件写入的 SDS 位，方向是反的。 |
| **不要移除 lan2 的网桥成员** | `uci` 里 `network.@device[0].ports='lan2' 'lan3' 'lan4'` 是正确且有益的，lan2 无链路时无害，插回即可用。 |
| **不要动 CPU OPP / `airoha,force-direct-pll`** | 那组问题（每次启动 4 次内核 oops）**已在当前 master 修完并实测 oops 4→0**。重复修改会造成回归。 |
| **不要指望运行时开关** | 该属性在 PHY probe 时读取。已实测确认无运行时开关：`modinfo realtek` 无参数、`/sys/module/realtek/parameters/` 不存在、`ethtool --show-priv-flags` 不支持、debugfs 下无相关节点。**只能重编重刷。** |

---

## 7. 当前设备实况（接手方需要的现场事实）

### 7.1 拓扑

- XR1710G = **二级路由**，LAN `192.168.2.1/24`（br-lan），**WAN 为 DHCP 客户端**
- 主路由 = **OPNsense `192.168.5.1`**
- **管理通路走 lan3**（PC 的 `以太网 15` = `192.168.2.182` → lan3 → `192.168.2.1`）。SSH 地址 `192.168.2.1`，账号 `root`。
  ⚠️ **WAN 侧 22/80/443 被 WAN 区防火墙 REJECT**，无法从 OPNsense 侧管理。
- PC 网卡（已实测枚举）：
  | 名称 | 芯片 | 速率 | 地址 |
  |---|---|---|---|
  | `以太网 15` | Realtek PCIe 5GbE #2 | 1G（接 lan3） | 192.168.2.182 |
  | `以太网 6` | **Mellanox ConnectX-4 Lx** | **10G（光口）** | 192.168.5.130 |
  | `以太网 12` | **Mellanox ConnectX-4 Lx #2** | **25G（光口，直连 NAS）** | 192.168.6.88 |

  ⇒ **注意**：PC 有 10G/25G 光口 Mellanox，**但都是光口，物理上无法接路由器的 RJ45 铜口**。此前"PC 网卡最高 5G"的说法是错的，但"无法直连测试 10G"这个结论仍然成立。

### 7.2 交接时的即时状态

```
lan2   carrier=0   operstate=down     ← 自环线已拔，无链路
wan    carrier=1   speed=2500Mb/s     ← ★ 现在挂在全屋局域网上
br-lan 成员: lan3 lan4 phy0.0-ap0 phy0.1-ap0
br-lan 地址: 192.168.2.1/24
lan3   carrier=1   speed=1000
内核 oops: 0    段错误: 0    CPU 1300000 kHz / governor=performance
监测器 /etc/10g-monitor.sh v2 运行中（PID 20413），日志 /overlay/10g-test.log
```

**⇒ `wan` 已接入全屋 LAN（2.5G），抓包可见 `192.168.5.0/24` 的真实流量**：ARP（192.168.5.194 → .112/.247）、DHCP（192.168.5.201）、IPv6 MLD、以及来自 `1c:2a:a3:2c:26:65`（= `192.168.5.5`）的 **RSTP BPDU，bridge-id `8000.1c:2a:a3:2c:26:65.8011`（VLAN 11）**
**⇒ 结论：那台下游交换机是**可网管的**、在跑 RSTP、使用 VLAN 11。** 若后续怀疑交换机侧行为，可从这一点入手。

### 7.3 服务健康（接手前刚复核，均为可靠查法）

```
daed: 2 个进程（/usr/bin/daed run -c /etc/daed/ --state /etc/daed/daed.db，PID 3310）
      :2023 LISTEN 正常
      /sys/fs/bpf/dae-native-runtime-3310-0 存在
      br-lan 有 qdisc clsact ffff: parent ffff:fff1
      /etc/init.d/daed enabled=yes
```

> ⚠️ **查进程不要用 `pgrep -c`** —— 本机 BusyBox v1.38.0 的 `pgrep` **不支持 `-c`**（`unrecognized option: c`）。用 `ps w | grep -c '[d]aed'`。用错方法会得出 "daed 0 进程" 的假结论。

---

## 8. 已正式排除的假设（不要重走）

| 假设 | 排除依据 |
|---|---|
| 网线问题 | 用户确认**同一根线**，仅换插口结果即不同 |
| 交换机侧端口保护 / 环路检测 | 用自环线实测：两个口 15 秒内**外部源 MAC 数量 = 0**，只有路由器自己发的 DHCP 广播 |
| EEE / 节能以太网 | `ethtool --show-eee lan2` 与 `wan` 均返回 `netlink error: Not supported`，驱动不实现 |
| `rx-polarity` / `tx-polarity` 不对称 | **错**：两个口、两个固件里全部相同，都是 `<0x1>` |
| `pulsed RTK SerDes` 是故障信号 | **错**：2.5G/5G/10G 每次 link-up 都恰好出现一次，是正常握手，pulse 数量不携带额外信息 |
| PC 网卡只到 5G | **错**：PC 有双口 Mellanox ConnectX-4 Lx（10G + 25G），但均为光口 |
| wan 可作 lan2 的对照组 | **部分错**：两口走不同 PCS 实例（`pcs@1fa08000` = an7581-pcs-**pon** / `pcs@1fa09000` = an7581-pcs-**eth**，resets 也不同）。**但 PHY 节点层面的对照仍然成立**（§3.1 的差分是 PHY 节点内的）。 |
| 缺少 625 / 628 / 629 / 747 等补丁 | 这些补丁最后修改时间均**早于**本固件构建提交`d0c702152b`(2026-10-07T03:26:07Z)，已包含在固件内 |
| Mellanox 的 RoCE / PFC | 用户明确要求排除；且其为光口，物理上不接路由器 RJ45 铜口 |

---

## 9. 可复用的现场方法（本轮踩出来的，省得再踩）

- **强制路由器从指定口真发包**：`ip neigh add <ip> lladdr <mac> nud permanent dev <if>` 绕开 ARP，再把流量指向该 IP，包就会真的从那个口出网线。
  ⚠️ **直接给两个本机地址互 ping 是没用的** —— 内核 `local` 路由会内部回环，网口计数器纹丝不动（曾据此得出虚假的 2.95 Gbps）。
- **`ping -i 0` 在本机 BusyBox 上不会洪泛**（实测 10 秒只发出 1 个包）。
- **`socat` / `nc` 在本机发 UDP 实测为 0 字节**，需保留 stderr 才能看到原因。
- **端口连通性判据**：`tcpdump -i <if> -n -e` 看源 MAC。交换机不会把帧从入端口发回，所以"本口发出的帧出现在另一个口" ⇒ 两口直连。**本设备有 `tcpdump`**（此前以为没有）。
- **FDT 解析**：节点名与属性值都按 **4 字节对齐**，按 1 字节跳会导致结构块错位、报 `bad token`。
- **"搜不到" ≠ "不存在"**：必须先证明搜索方法能看见已知存在的东西。本项目里 `reset-before-id-read` 就不在 mainline、不在模块里，而在 `target/linux/generic/hack-*`。同类错误本轮犯了三次（另两次：`grep` 截断当成"对端只有 100M"、字节搜压缩 ITB 当成"卖家内核没这段代码"）。
- **设备无 RTC**，启动后靠 NTP 校时；WAN 未通时时钟是错的。**判读日志一律用内核的 `[  1126.674669]` 开机秒数，不要用墙钟时间戳。**
- **经 SSH 传含引号/管道/`$`/括号的命令时，Windows OpenSSH 会剥双引号并破坏转义** ⇒ 一律 base64 传送：`echo <b64> | base64 -d > /tmp/x.sh && sh /tmp/x.sh`。
- **`/sys/class/net/<if>/master` 在本内核读不出内容**，判断网桥成员要用 `ls /sys/class/net/br-lan/brif/`。

---

## 10. 交付清单

| 文件 | 说明 |
|---|---|
| `HANDOFF-lan2-10g-fix.md` | 本文 |
| `FIX-lan2-10g-reset-before-id-read.patch` | 一行补丁，可 `git apply` |
| `RCA-lan2-10g-flapping.md` | 完整根因报告（更详细的证据链、否定条件、排除清单） |
| `GITHUB-UPDATE.md` | 项目长期 brief（注意：其中关于 `pulsed RTK SerDes` 是故障信号的旧判断**已作废**，见 §8） |
