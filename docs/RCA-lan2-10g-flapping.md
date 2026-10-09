# XR1710G lan2 万兆抖动 —— 根因结论与修复

生成时间：2026-10-08
最后更新：2026-10-09（**已在本机完成"修复后复现验证"**，见文末「修复后验证」）
结论级别：**已实机验证** —— 根因、修复、修复后零抖动，三级证据齐全

## 一句话结论

`target/linux/airoha/dts/an7581-xr1710g.dts` 第 **363 行**的 `reset-before-id-read;`
只写在 `phy5`（= lan2）上，是全设备**唯一**的 lan2/wan 配置差异；
**删掉这一行**即为修复。

⚠️ **两份 DTS 都要删**（2026-10-09 仓库侧补充）：同一行也存在于
`target/linux/airoha/dts/an7581-gemtek-xr1710g-ubi.dts` 第 **389 行**。
设备实际刷的是 **`-ubi` 布局镜像**（board `gemtek_xr1710g-ubi`），它嵌的是 UBI 那份 DTS
—— **只删 `an7581-xr1710g.dts` 会让刷进去的实验镜像里该属性原封不动**，
实验会"看起来做了改动"却测到原状态。
旁证：两份镜像内嵌 DTB 的节点数为 **200 / 199**，可证明确由两份不同 DTS 生成。

## 证据链（全部来自原文，非推断）

1. **设备实跑 DTB 与仓库源码一致**
   从设备 `/sys/firmware/fdt` 取出的 DTB，用自写 FDT 解析器解出 202 个节点，
   `//soc/switch@1fb58000/mdio/ethernet-phy@5` 有 `reset-before-id-read`，
   `ethernet-phy@8` 没有。仓库 master 的 DTS 第 359-378 行逐字相同。

2. **该属性确实被内核执行**（这是之前被误判为"不存在"的一环）
   `target/linux/generic/hack-6.18/705-net-phy-reset-PHY-before-reading-its-ID-when-requested.patch`
   （ImmortalWrt，Tianling Shen）在 `drivers/net/mdio/fwnode_mdio.c` 里：
       if (!fwnode_property_read_bool(fwnode, "reset-before-id-read")) return 1;
   并用 `reset-assert-us` / `reset-deassert-us` 各 200000 us 打出 400 ms 复位脉冲，
   随后 `phy->mdio.reset_state = 0` 抑制常规复位。
   ⚠️ 它**不在 mainline 内核、也不在 realtek.ko 里** —— 用这两者去否定它必然得出错误结论。

3. **该动作的已知后果，由补丁作者亲自写明**
   `743-net-phy-realtek-restore-optional-RTK-SerDes-patch.patch`：
     "A second reset ... was found to clear firmware-programmed SDS 6.0x0d, 6.0x0e,
      and 6.0x1d bits. The PHY then reached Base-R block lock while the AN7581
      received no USXGMII partner word."
   `744-net-phy-realtek-reapply-RTK-SerDes-after-aneg.patch`：
     "The PHY can then report a completed copper link while the connected AN7581
      USXGMII PCS receives no partner word or carrier."
   ⇒ 这就是"链路抖动"的电气本质：**铜口 up，MAC/PCS 侧没有 carrier。**

4. **对照实验（同板同型号同速率同交换机，唯一变量就是这一行）**
   | 口 | PHY | reset-before-id-read | 10G 表现 |
   |---|---|---|---|
   | lan2 | RTL8261BE @ mt7530-0:05 | **有** | ❌ 抖动 |
   | wan  | RTL8261BE @ mt7530-0:08 | 无 | ✅ 15.9 GB 实测零错误零事件 |
   ⚠️ 附注（2026-10-09）：该行那个"10G 档位"**存疑** —— 当时对面交换机的铜口实测只宣称到
   `2500baseT/Full`，所以那次 15.9 GB 很可能跑在 **2.5G 而非 10G**。
   这**不影响对照的有效性**（两口同速率、同交换机，唯一变量仍是那一行），
   但**不要把「wan 在 10G 下也稳」当作已证事实**。

5. **卖家稳定版固件的 DTB（FDT 解析，187 节点）**
   `phy@5` 与 `phy@8` **两个属性都没有**：既无 `reset-before-id-read`，
   也无 `realtek,patch-rtk-serdes`。⇒ 两条会破坏 SDS 的路径都不存在。

## 为什么删掉是安全的

`phy@8`（wan）本身就是反证：**同型号 PHY、同一条 MDIO 总线，不靠这个属性照样被正确识别**。
该属性存在的理由是"某些 PHY 在硬复位前不响应 ID 读"（705 号补丁 L4-6），
而这两颗 RTL8261BE 明显不属于那一类。

## 修复

    sed -i '/reset-before-id-read;/d' \
        target/linux/airoha/dts/an7581-xr1710g.dts \
        target/linux/airoha/dts/an7581-gemtek-xr1710g-ubi.dts

即 `FIX-lan2-10g-reset-before-id-read.patch`（**该补丁只覆盖 plain 那一份**，`-ubi` 那份需同改）。
改完需重编 + 重刷（该属性在 PHY probe 时读取，无运行时开关）。

### 仓库侧实施与发布记录（2026-10-09）

| 项 | 值 |
|---|---|
| commit | `bcdc0b3`（两份 DTS 各删 1 行、0 行新增） |
| release | **`20261009-bcdc0b3e`**（两种布局各一份 `.itb`） |
| 镜像 buildinfo | `2026-10-8-035afe00fa-bcdc0b3e56`（与设备 REVISION 一致；tag 用发布日、buildinfo 用构建日，差一天属正常） |
| 保留项 | `realtek,patch-rtk-serdes` 两份**都保留**（那是下一步的变量，本次不动） |

### 仓库侧可重放的验证（无需刷机）

    原理：.itb 本身就是 FIT（外层 FDT，13 个节点；子镜像用 data-position / data-size 外置存储），
    其中 `fdt-1` 就是板级 DTB（comp=none）。解析时节点名与属性值都要按 4 字节对齐
    （见本文「现场方法学备忘」最后一条）。

    工具：工作区 `404-OpenWrt\yaof-upstream\_xr_dtbcheck.py`（自写 FDT 解析器，无第三方依赖）

        python _xr_dtbcheck.py <immortalwrt-*-squashfs-sysupgrade.itb>

    | 镜像 | phy@5 `reset-before-id-read` | phy@5 `rtk-serdes` | phy@8 `reset-before-id-read` |
    |---|---|---|---|
    | `20261008-03f343a7`（改前） | **True** | True | False |
    | `20261009-bcdc0b3e`（改后，**两份镜像都测**） | **False** | True | False |

    改前那行 `True` 是**阴性对照** —— 它证明这把尺子确实能看见该属性（呼应本文教训：
    「未找到」≠「不存在」）。改后 `False` = 修复确实进了产物；`rtk-serdes` 仍为 `True`
    = 没有误删下一步要用的变量。

## 否证条件（若此结论错，应往哪查）

1. 删掉并重刷后 lan2 仍抖 ⇒ 根因不是它。下一个嫌疑：
   - `629-net-pcs-airoha-add-optional-USXGMII-TX-FIR-override.patch` 引入的 `airoha,tx-fir`，
     **当前 DTS 完全没有设置它**（两个口都没有）—— 这是唯一还没被排除的 10G TX 侧调优旋钮。
   - `744` 的 10–12 ms 脉冲时长是**在作者那一台机器上实测**得出的，换板可能不适用。
   - `628` 的 RX 校准 crossing search。
2. ~~若修复后 lan2 变稳但速率掉到 5G/2.5G ⇒ 说明 SerDes 仍未建立 10G，属同一族问题的不同表现。~~
   ⇒ **【2026-10-09 实测作废 · 这条否证条件本身是个陷阱，别再照着查】**
   实测 lan2 一度只跑到 **2500Mb/s**，但原因**不是 SerDes 没建立 10G**，而是
   **对端交换机那个铜口物理上只支持 2.5GBASE-T** —— `ethtool lan2` 的
   `Link partner advertised link modes` 里**根本没有** `10000baseT/Full`，也没有 `5000baseT/Full`。
   把同一根线换到该交换机一个支持 10G 的口上，lan2 **立刻** `Link is Up - 10Gbps/Full`。

   ⇒ **判据：先看对端宣称了什么速率，再怀疑固件。**
   ```sh
   ethtool lan2 | sed -n '/Link partner advertised link modes/,/Link partner advertised auto/p'
   ```
   对端不宣称 10G 时协商到 2.5G 是**完全正确的行为**，不是故障。
   ⇒ 不要再把「速率不是 10G」当作 SerDes 失败的证据。

## 已排除的假设（不要再走回头路）

| 假设 | 排除依据 |
|---|---|
| 网线问题 | 用户确认同一根线，换口即变 |
| 交换机侧端口保护/环路检测 | 自环线实测：两端口仅见路由器自身 DHCP 广播，外部帧为 0 |
| PC 网卡只到 5G | **错**：PC 有双口 Mellanox ConnectX-4 Lx（10G + 25G） |
| EEE / 节能以太网 | `ethtool --show-eee` 两口均 `Not supported`，驱动不实现 |
| `rx-polarity` 不对称 | **错**：两个口、两个固件里 rx/tx-polarity 全部相同（均为 0x1） |
| `pulsed RTK SerDes` 是故障信号 | **错**：2.5G/5G/10G 每次 link-up 都会出现一次，是正常握手 |
| wan 可作 lan2 的对照组 | **错**：两口走不同 PCS 实例（`pcs@1fa08000` pon vs `pcs@1fa09000` eth），但**PHY 节点本身的对照仍然成立** |
| 缺少 625/628/629/747 等补丁 | 补丁最后修改时间均早于固件构建提交，已包含 |
| Mellanox RoCE/PFC | 用户明确要求排除；且其为光口，物理上不接路由器 RJ45 |

## 现场方法学备忘（低成本、可复用）

- **强制路由器从指定口真发包**：`ip neigh add <ip> lladdr <mac> nud permanent dev <if>` 绕开 ARP，
  再 `ping`/`socat` 指向该 IP，包就会真的从那个口出网线。
  （直接给两个本机地址互 ping 是**没用的**——内核 local 路由会内部回环，计数器不会动。）
- **`ping -i 0` 在本机 BusyBox 上不会洪泛**（实测 10 秒只发出 1 个包）。
- **端口连通性判据**：`tcpdump -i <if> -n -e` 看源 MAC；交换机不会把帧从入端口发回，
  所以"自己发的帧出现在另一个口" ⇒ 两个口是直连的。
- **FDT 解析**：节点名与属性值都按 **4 字节对齐**，按 1 字节跳会导致结构块错位。
- **"未找到"不等于"不存在"**：本项目里 `reset-before-id-read` 就不在 mainline、不在模块里，
  而在 `target/linux/generic/hack-*`。搜不到时先证明搜索方法能看见已知存在的东西。

---

# ✅ 修复后验证（2026-10-09 实机）

**验证方式：重编 → 实刷 → 在真实拓扑下压测。**

## 1. 修复真的进了固件（读实跑设备树，不是看源码）

固件 REVISION `2026-10-8-035afe00fa-bcdc0b3e56`，内核 6.18.52。刷后用普通
`sysupgrade`（默认保留配置）刷入，掉线 59 秒后自动恢复。

    ls /sys/firmware/devicetree/base/soc/switch@1fb58000/mdio/ethernet-phy@5/
    → compatible name phandle realtek,patch-rtk-serdes reg reset-assert-us
      reset-deassert-us reset-gpios rx-polarity tx-polarity
      ↑ reset-before-id-read 已消失（刷前该属性存在）

    ethernet-phy@8/ 内容相同，且从来就没有该属性 ⇒ 无回归
    realtek,patch-rtk-serdes 仍在 ⇒ 744 号的 SerDes 重打逻辑没有被误删

## 2. 抖动消失（真实拓扑 + 真实全屋流量）

拓扑：1710 = **主路由**（br-lan `192.168.5.1/24`，WAN = PPPoE），全屋交换机接 **lan2**。

| 指标 | 修复前 | 修复后 |
|---|---|---|
| lan2 `Link is Down` | **8 次** | **0 次**（累计的 2 次全部是人工换插口造成） |
| lan2 速率 | 5000 → 自降到 2500 | **稳定 10000** |
| 内核 oops | 4 次/启动 | **0** |

## 3. 高负载下依然零抖动

用 PC 的万兆口（Mellanox ConnectX-4 Lx，`192.168.5.124`）经交换机对路由器打 iperf3：

| 项目 | 结果 |
|---|---|
| 下行 4 流 | 1.79 Gbits/sec（30 秒 / 6.24 GB） |
| 上行 4 流（`-R`） | 2.72 Gbits/sec（30 秒 / 9.49 GB） |
| TCP 重传 | **Retr = 0** |
| 通过 lan2 的总量 | 约 **31 GB** |
| 压测期间 lan2 抖动 | **0** |
| `tx_errors` | **0** |
| `rx_crc_errors` / `rx_frame_errors` / `rx_fifo_errors` / `rx_missed_errors` | **全部 0** |

**速率上限说明（重要，别误判成链路问题）**：1.8～2.7 Gbps 是**路由器 CPU 的天花板**
（1.3 GHz Cortex-A53；单流 1.41 Gbps ≈ 一个核跑满），不是链路问题。
本地生成的流量**用不上 NPU 卸载** —— 8 路并行 socat 与单路同为 ~1.2 Gbps、CPU 仅 17% 忙，
说明瓶颈是每包开销（约 10 万 pps）。
⇒ **要压满 10G 必须由外部设备产生、且走转发路径（可被 PPE 卸载）。**
本机唯一另一个 10G 口是 `wan`，其对端调制解调器只有 2.5G，
**所以在这套拓扑下"10G 饱和"物理上做不到** —— 不要把它当成未完成的验证项。

## 4. `rx_errors` 增长是假警报（勿再误判）

实测 `rx_errors` 与 `rx_dropped` **1:1 同步增长**（279→293 与 296→311），
而具名物理层计数器 `rx_crc_errors`、`rx_frame_errors`、`rx_fifo_errors`、`rx_missed_errors` **全为 0**。
⇒ 该驱动把"未能交付到 socket 的包"也计入 `rx_errors`，**与物理层无关**。

⚠️ 注意 `ethtool -S lan2` 返回 `no stats available`（该驱动不暴露具名统计），
查具名计数器要看 `/sys/class/net/lan2/statistics/`。

## 5. 30 分钟高压浸泡测试（最终判定）

用 PC 的万兆口做 iperf3 循环（每轮 20 秒下行 + 20 秒上行，持续 30 分钟，共 42 轮），
全程与浸泡前基线逐项对比：

| 指标 | 基线 | 30 分钟后 | 增量 |
|---|---|---|---|
| **lan2 `Link is Down`** | 2 | 2 | **0** ✅ |
| **lan2 `Link is Up`** | 3 | 3 | **0** ✅ |
| SerDes `pulsed`（mt7530-0:05） | 3 | 3 | **0** ✅ |
| `carrier lost with copper link up` | 0 | 0 | **0** ✅ |
| `tx_errors` | 0 | 0 | **0** ✅ |
| `tx_dropped` | 5 | 5 | **0** ✅ |
| 速率 | 10000 | **10000** | — ✅ |
| `rx_crc/frame/fifo/missed_errors` | 0 | **全部 0** | **0** ✅ |
| 内核 oops / segfault | 0 | **0 / 0** | **0** ✅ |

**承载量：**

| 项目 | 数值 |
|---|---|
| 覆盖时长 | **1822 秒**（30.4 分钟） |
| 通过 lan2 的总流量 | **395,258 MB ≈ 385 GB** |
| 收包 | **+117,402,216**（1.17 亿） |
| 发包 | **+174,619,904**（1.75 亿） |
| **总包数** | **约 2.92 亿个** |
| 单轮下行 | 1.25 ~ 1.76 Gbps |
| 单轮上行 | 2.20 ~ 2.51 Gbps |

**监测器 29 次心跳连续 30 分钟读数完全不变**（`l2down=2 l2up=3 l2pulse=3 l2rec=3 clost=0`）。

**同期全屋状态**：DHCP 租约 **17 → 38 条**（整栋房子正常上线）、外网通、DNS 正常。
> 这正是原故障的核心表象 —— 修复前「下面 AP 和客户端获取不到 IP」。

## 6. 仍未覆盖的部分（结论的边界）

- **10G 满速转发未验证**（受拓扑限制，见第 3 节）：本机唯一另一个 10G 口是 `wan`，
  其上联调制解调器只有 2.5G。**这是物理限制，不是未完成的验证项。**
- **长期（数天～数周）观察**：30 分钟高压已足以证伪"负载相关抖动"，
  但若数月后重现，应先看 `/overlay/10g-test.log` 的时间分布，
  再按本文「否证条件」一节往下查（首查嫌疑仍是 `airoha,tx-fir`）。
- **换板/换固件版本后的可移植性未知**：本结论建立在
  REVISION `2026-10-8-035afe00fa-bcdc0b3e56` / 内核 6.18.52 上。
