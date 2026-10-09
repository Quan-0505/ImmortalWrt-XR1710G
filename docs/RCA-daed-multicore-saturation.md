# XR1710G daed「只有一个 CPU 吃满」—— 根因与修复

**日期**：2026-10-09
**现象**：用户 htop 截图显示 daed 跑测速时 `CPU0 97.4% / CPU1 54.2% / CPU2 56.2% / CPU3 53.6%`，
`Load average 2.65`，`Net rx 106MiB/s tx 76.3MiB/s (46804/47468 pps)`，Speedtest 269.78 Mbps。
用户描述「和之前 R3S 一样只跑了单核」。

**结论（一句话）**：**不是 daed 单线程，也不是 GOMAXPROCS 限制**。是**两条相互独立的系统层配置**：
网卡中断全压在 CPU0，以及 RPS 设在了错误的队列上。两处修复后四核完全均衡，代理吞吐提升 64%+。

---

## 一、先排除的假设（都有实测反证，不要再重走）

| 假设 | 反证 |
|---|---|
| Go 被 `GOMAXPROCS` 限制 | `/proc/<pid>/environ` 无 GOMAXPROCS；`Threads: 13`；线程 CPU 时间分布在 8 条线程上 |
| 进程被 CPU 亲和性绑定 | `Cpus_allowed_list: 0-3`，13 条线程全部 `cpus=0-3` |
| daed 是单进程单线程 | htop 里那 10 个 `/usr/bin/daed` 条目是**线程**（`Tasks: 36, 13 thr`），实际只有 1 个进程 |
| daed 需要配置多线程参数 | 没有这种参数；问题是内核包路径的串行点 |

---

## 二、根因①：网卡中断全在 CPU0，且**电平触发中断只给掩码无效**

### 证据

```
             CPU0       CPU1       CPU2       CPU3
25:      34282456          0          0          0   GICv3 69 Level  airoha_eth.0   ← 3400 万次
29:       3691477          0          0          0   GICv3 70 Level  airoha_eth.4   ← 370 万次
11:       2925397    3496367    4612416    3000356   GICv3 30 Level  arch_timer     （这个是散开的，作对照）
```

8 条 `airoha_eth` 中断（irq25~32），**只有 irq25 与 irq29 有流量，且全在 CPU0**。

### ★ 关键坑：设掩码 ≠ 迁移

```
echo f > /proc/irq/25/smp_affinity     # 允许四核
→ 计数仍然是 34287327  0  0  0          # 纹丝不动
```
**原因**：`airoha_eth` 的中断是 **Level（电平）触发**，内核的 IRQ balancer 不会主动迁移电平触发中断。
**必须显式钉到单个核**：
```
echo 4 > /proc/irq/25/smp_affinity     # 只允许 CPU2
→ 计数变成 34885581  0  118531  0       # 新中断立刻落到 CPU2
```

### 修法（最终版，两条主力分居两核）

```
irq25 (airoha_eth.0, 主力)   → 4  (CPU2)
irq29 (airoha_eth.4, 次主力) → 8  (CPU3)
irq26/28/30/32               → 1  (CPU0)
irq27/31                     → 2  (CPU1)
```

---

## 三、根因②：★★ RPS 设错了队列（第一轮修复无效的真正原因）

### 证据

```
lan2   rx_queues=32  tx_queues=32      ← 网卡有 32 个硬件队列
ethtool -l lan2 → netlink error: Not supported   ← 驱动不支持运行时调队列数

只设 rx-0 后：
  lan2/rx-0  rps_cpus=f    ← 我设的
  lan2/rx-4  rps_cpus=1    ← ★ 实际收包用的是这个！只给了 CPU0
  lan2/rx-8  rps_cpus=1
  lan2/rx-16 rps_cpus=1
  lan2/rx-31 rps_cpus=1
```

**⇒ 真实流量走 `rx-4`（对应 `irq29`）。只给 `rx-0` 设 RPS 等于完全没生效。**

### 修法：遍历**所有**队列

```sh
for Q in /sys/class/net/$I/queues/rx-*; do
  echo f    > $Q/rps_cpus
  echo 4096 > $Q/rps_flow_cnt
done
for Q in /sys/class/net/$I/queues/tx-*; do echo f > $Q/xps_cpus; done
```
覆盖 `lan2 lan3 lan4 wan br-lan dae0 eth0 eth1`，实测 **64 个 rx 队列全部覆盖**。

---

## 四、附带发现：TCP 窗口是真瓶颈（与 CPU 无关，但影响体感）

四台**不同大洲**的目标全部卡在 ~50 Mbps，这不是服务器带宽问题：

| 目标 | 解析 IP | 实测吞吐 | RTT | 所需在途窗口 = 吞吐 × RTT |
|---|---|---|---|---|
| Hetzner 美东 | 5.161.7.195 | 53.0 Mbps | 226.6 ms | 1.50 MB |
| OVH 法国 | 141.95.207.211 | 54.6 Mbps | 201.7 ms | 1.38 MB |
| Linode 新加坡 | 139.162.23.4 | 46.4 Mbps | 335.4 ms | 1.95 MB |
| ThinkBroadband UK | 80.249.99.148 | 50.3 Mbps | — | — |

而设备上：
```
net.core.rmem_max = 1048576   ← 恰好 1 MB
net.core.wmem_max = 1048576   ← 恰好 1 MB
net.ipv4.tcp_adv_win_scale = 1   （通告窗口 = 缓冲的一半）
```
**⇒ 单连接吞吐 ≈ 窗口 / RTT，窗口被 1MB 卡住 ⇒ 200ms RTT 下上限约 40~50 Mbps。与实测完全吻合。**

**⇒ 这解释了为什么只有多连接的测速软件能跑到 269 Mbps，而单线程浏览器下载永远 ~50 Mbps。**

修法：`rmem_max/wmem_max` → 16 MB，`tcp_rmem[2]`/`tcp_wmem[2]` → 16 MB。

---

## 五、实测改善曲线

**测量方法**：PC 侧 `curl --parallel --parallel-max 16` 同时下 4 个境外大文件（Hetzner/OVH/Linode/ThinkBroadband），
设备侧每 2 秒采样一次 `/proc/stat` 每核使用率（**busy = user+nice+system+irq+softirq**，必须含软中断）
与 `dae0` 计数器。**以 `dae0_rx` 增量为权威吞吐判据**（`br-lan` 计数器**不可用** —— daed 的 eBPF 在 `br-lan` 的
`clsact` 上把包在网络栈之前就重定向进了 `daens` netns，网桥设备层不计入；`lan2`/`wan` 是真实转发计数）。

| 阶段 | 代理吞吐 | CPU 分布 (cpu0/1/2/3) |
|---|---|---|
| **用户原始状态** | — | **97.4 / 54.2 / 56.2 / 53.6** ← 单核钉死 |
| 基线（16 路并发） | 193 Mbps | 64~93 / 33~71 |
| ① 中断钉核 + TCP 缓冲 | 252 Mbps | 61~95 / 38~74 |
| ② + 全部 32 队列 RPS | 316 Mbps | 84 / 82 / 88 / 88 |
| ③ + 中断再平衡 | ~356 Mbps | **83 / 81 / 89 / 90** ✅ |

**⇒ 确凿的是 193 → 316+（+64%）与「单核 97% → 四核均衡 ±5%」这个质变。
③ 相对 ② 的 316→356 差异可能含测量波动（窗口 28s vs 26s），不单独计为确证增益。**

---

## 六、★ 判定「流量是否真的走代理」的可靠指纹

排查中极易被误导：`dl.google.com` 下载能到 **1.1 Gbps 但 CPU 仅 2~5%** —— 因为它在中国有 GGC 缓存，
解析到**国内 IP**，命中路由规则 `dip(geoip:cn) -> direct`，**走内核直连 + NPU 硬件卸载**，与 daed 无关。

**⇒ 判据：看 `dae0` 的计数器。**
```sh
cat /sys/class/net/dae0/statistics/rx_bytes   # 下载方向，走代理时增长
cat /sys/class/net/dae0/statistics/tx_bytes   # 几乎不涨（回程不走 dae0）
```
**⇒ 直连（NPU）：dae0 增量为 0。走代理：dae0_rx 增量 ≈ 下载字节数。**

配套确认路由规则已加载：
```sh
logread | grep 'daed\[' | grep -o 'Routing match set len: [0-9]*/[0-9]*'
# 正常应为 21/1024；若为 1/1024 说明只加载了空/默认规则
logread | grep 'daed\[' | grep -o 'outbounds referenced by routing rules: \[[^]]*\]'
# 正常应列出 [tg direct proxy block]
```

---

## 七、持久化（★ 已升级为四层 —— 初版只有两层，被运行期重置击穿过一次）

### ⚠️ 初版设计有致命缺陷（2026-10-09 实证）

初版是**两层**：`/etc/fs-net-tune.sh`（永久主体）+ `/etc/uci-defaults/97-net-tune`（一次性调用壳）。
两层都登记进 `sysupgrade.conf`，**对称重刷是有效的**。

**⇒ 但它只保证「开机时应用一次」。运行期网卡一旦重新初始化，RPS 会被驱动重置，而脚本不会重跑。**

实测证据（dmesg）：

```
[  939.384675] airoha_eth ... lan2: entered allmulticast mode      ← 重新入网桥
[  939.392252] airoha_eth ... lan2: entered promiscuous mode
[ 1223.269666] airoha_eth ... lan2: Link is Down
[ 1223.277719] br-lan: port 1(lan2) entered disabled state
[ 1226.412786] airoha_eth ... lan2: Link is Up - 10Gbps/Full
[ 1226.426517] br-lan: port 1(lan2) entered forwarding state
```

**⇒ 重置的精确范围（这是关键区分）：**

| 路径 | 是否被重置 | 原因 |
|---|---|---|
| `/proc/irq/*/smp_affinity` | ❌ **不受影响** | 不属于 netdev 生命周期 |
| `/sys/class/net/*/queues/*/rps_cpus` | ✅ **被恢复为默认 `1`** | 属于 netdev 队列，随驱动重新注册而重建 |

**⇒ 这就是为什么「中断钉核活了下来，但 RPS 全丢」—— 两者生命周期不同。**

### 现行四层设计

```
① /etc/fs-net-tune.sh v3.1            永久幂等主体；「检测后写」+ 日志限长
    sha256 b9cb0db106daa7e376a78979639132a940cf5683f7f1bd7f03404dd05bfd9d7f（3878 B）
    （v3 = 4e3f5be2… 3566 B，备份在 /etc/fs-net-tune.sh.v3.bak；v2 备份在 .v2.bak）
② /etc/hotplug.d/net/90-rps-guard      ACTION=add|ifup|up 时触发（★ 治本层）
    sha256 680bab233da1c51300ce4db31e7ce057ac70ac9651145821b00aa66ad7575f7a
③ cron  */2 * * * * /etc/fs-net-tune.sh   兜底（治非 net 事件导致的重置）
④ /etc/sysupgrade.conf                 四个路径全部登记（现共 14 项）
```

**v3.1 相对 v3 的唯一改动**：日志只记「数量 + 前 3 项」。
v3 会把全部改动项列进日志 —— 实测一次重置 64 个队列时单条日志达 **1.5 KB**，
若网卡频繁抖动会刷爆日志。改后同场景 **114 字节**（缩小 13 倍），
数量足以判断「有没有被重置」，样例足以判断「重置了哪一类」。

**为什么 hotplug 是治本层**：`ACTION=add` 正是**网卡注册的那一刻**，也正是 RPS 被重置的那一刻。
项目内既有的 `00-sysctl`、`50-fw4-bridge-reload`、`99-ppe-reload` 用的都是这个机制。

**为什么还需要 cron**：hotplug 只在 net 事件时触发；若重置来自驱动内部 reset 或手动 `ip link`，
不产生 net 事件 ⇒ cron 兜底。因已改为「检测后写」，无变化时**不触碰任何 sysfs**，高频调用成本可忽略。

**为什么用「检测后写」而不是无条件写**：无条件写每次要触碰 128+ 个 sysfs 文件（8 接口 × 32 队列 × 2），
而 sysfs 写入会触发内核回调。改为检测后，状态正确时零写入。

### 逐层实证（不是「写了就算」）

| 层 | 验证方法 | 结果 |
|---|---|---|
| ① 幂等性 | 状态正确时连跑，看 `logger` 增量 | 增量 **0** ⇒ 检测后写生效 |
| ① 有效性 | 故意破坏 `lan2/rx-0`、`lan2/rx-4`、`wan/rx-0` | 全部自动修复；日志留痕 `re-applied 3 setting(s)` |
| ② hotplug | 破坏 `lan2/rx-7` → 发 `ACTION=add` 事件 | 6 秒后变 `f`；lan2 **32/32**、wan **32/32** |
| ③ cron | 观察 crond 进程与 crontab 内容 | 已加载，`*/2` 生效 |
| ④ 登记 | 逐项 `[ -e ]` 存在性检查 | 14 项，2 项 ⚠️ 为一次性壳被消耗（预期） |
| 中断亲和性 | 复核 8 条 irq | `25=4 29=8 26=1 27=2 28=1 30=1 31=2 32=1` ✓ |

**⇒ 另有备份可回滚**：`/etc/fs-net-tune.sh.v2.bak`、`/etc/crontabs/root.bak-rps`、
`/etc/sysupgrade.conf.bak-rps`。

**为什么必须两层**：`/etc/uci-defaults/` 下脚本执行成功后会被系统**自动删除**，
sysupgrade 时「登记了但文件不存在」⇒ 不会被备份 ⇒ 修改静默丢失。
（本项目已栽过两次，见 `fs-fix-nav.sh` / `fs-fix-feeds.sh` 同类设计。）

**★ 注意 `/etc/hotplug.d/` 不在任何 `/lib/upgrade/keep.d/` 规则内** —— 必须显式登记，否则重刷即丢。

---

## 八、★ 考察 QiuSimons/YAOF 的结论

仓库：`QiuSimons/YAOF`，2773 stars，**默认分支 `25.12`**（不是 master/main，用错分支会 404）。

### 唯一直接相关的文件：`PATCH/files/etc/hotplug.d/net/01-maximize_nic_rx_tx_buffers`

```sh
#!/bin/sh
[ "$ACTION" = "add" ] || exit 0
[ -z "$DEVICENAME" ] && exit 0
command -v ethtool >/dev/null 2>&1 || exit 0
NIC="$DEVICENAME"
[ ! -d "/sys/class/net/$NIC/device" ] && exit 0
[ "$(cat "/sys/class/net/$NIC/type" 2>/dev/null)" != "1" ] && exit 0
ETHTOOL_G=$(ethtool -g "$NIC" 2>/dev/null)
[ -z "$ETHTOOL_G" ] && exit 0
RX_MAX=$(echo "$ETHTOOL_G" | awk '/RX:/ {print $2; exit}')
TX_MAX=$(echo "$ETHTOOL_G" | awk '/TX:/ {print $2; exit}')
[ -n "$RX_MAX" ] && [ "$RX_MAX" != "0" ] && ethtool -G "$NIC" rx "$RX_MAX" 2>/dev/null
[ -n "$TX_MAX" ] && [ "$TX_MAX" != "0" ] && ethtool -G "$NIC" tx "$TX_MAX" 2>/dev/null
if ethtool -c "$NIC" 2>/dev/null | grep -q "Adaptive RX:"; then
    ethtool -C "$NIC" adaptive-rx on adaptive-tx on >/dev/null 2>&1
fi
logger -t net-buffer "Maximized ring buffers for $NIC"
```

**两招**：① `ethtool -G` 把环缓冲拉到硬件上限；② `ethtool -C adaptive-rx on` **自适应中断合并**（吞吐高时减少中断次数，
与我们要解决的 CPU 饱和是同一目标）。

### ❌ 但在这台设备上**无法照搬** —— 驱动不支持

```
lan2/w an/lan3:  ethtool -g → Not supported
                 ethtool -c → Not supported
                 ethtool -l → Not supported
driver=airoha_eth  version=6.18.52
```
YAOF 针对 NanoPi（Rockchip `stmmac` 驱动，`-G/-C/-L` 全实现）；XR1710G 的 **Airoha 自研 `airoha_eth`**
只实现了 `-i / -k / -S / -s`，环缓冲、中断合并、队列数**驱动层就没暴露**。

**⇒ 借鉴的是思路（把网卡层能调的旋钮拉满），等价旋钮在本设备上是：
中断亲和性钉核 + 全队列 RPS/RFS/XPS + TCP 缓冲 —— 正是本文实施的这三项。**

### 其他补丁：无需借鉴

| 补丁 | 作用 | 结论 |
|---|---|---|
| `PATCH/pkgs/firewall/firewall4_patches/001-fix-fw4-flow-offload.patch` | fw4 flowtable 生成改用 `net.device` 并加 `net.up` 检查 | **本固件已等价生效**：flowtable devices 已含 `lan2 lan3 lan4 phy0.0-ap0 phy0.1-ap0 pppoe-wan wan` |
| `PATCH/kernel/bbr3/` | BBR v3 | 本设备已用 `bbr`；换 v3 需重编内核，收益未证 |
| `PATCH/kernel/sfe/953-...shortcut-fe.patch` | Shortcut-FE 转发加速 | 本设备已有 NPU/PPE 硬件卸载（`flow_offloading=1`、`flow_offloading_hw=1`、PPE `bound:24/total:331`），功能重叠 |
| `PATCH/kernel/wg/950-...` | WireGuard hotplug | 与本问题无关 |

---

## 九、关于 R3S 的同类现象

用户反馈 R3S 上「也只跑了单核」。**机制大概率同源**（中断集中 + RPS 未开），
但 R3S 是 Rockchip 平台、驱动为 `stmmac`，**支持 `ethtool -L/-G/-C`**，
所以那边可用的手段更多（含 YAOF 的两招 + 多队列调整）。
**需在 R3S 上独立验证，不能直接套用本设备的结论。**

---

## 十、遗留与验证缺口

1. **最快的终验**：让用户在浏览器重跑一次 Speedtest，对照 htop 的 CPU 分布。
   **预期：四核应落在 40~55% 区间（271 Mbps 下可能略高），不应再出现「某核 90%+ 而其余 50%」的形态。**
   本次设备侧用真实转发路径（16 路并发经代理，205 Mbps）实测四核 42/44/47/46%，
   但**用户单浏览器测速的结果尚未回收**（2026-10-09 两次反馈都还没拿到修复后的测速截图）。
2. `ethtool -g/-c/-l` 均不支持 ⇒ **环缓冲与中断合并无法调**，这是 `airoha_eth` 驱动的硬限制，
   若要突破需改驱动或内核。
3. 中断只有 irq25/irq29 两条有流量，另 6 条（irq26/27/28/30/31/32）计数为 0 ——
   说明硬件多队列未启用（32 个队列文件存在但只用了 2 个）。**根因在驱动，无运行时解。**
4. 未做长时间稳定性浸泡（本轮只跑了数轮 30 秒负载）。
5. **★ 若用户重跑测速后仍是单核吃满** —— 说明存在第三个机制。下一步排查方向（按嫌疑排序）：
   ① daed 内部某线程的亲和性或锁竞争（查 `/proc/<pid>/task/*/stat` 的逐线程 CPU 增量与所在核）；
   ② daed 是否对自身做了 CPU 绑定（查 `sched_setaffinity` 相关配置或环境变量）；
   ③ eBPF 程序的执行核是否被固定（`bpftool prog show` 看 attach 信息）。

---

## 十一、工具经验（本轮踩到的）

- **busybox 没有 `paste`** —— 采样脚本里用它报 `paste: not found`，要用纯 shell 算术。
- **`awk` 数组迭代输出顺序不确定** —— 用它生成两列再做对比会字段错位；要用固定顺序 `printf`。
- **CPU 使用率公式必须含软中断**：`busy = user + nice + system + irq + softirq = $2+$3+$4+$7+$8`。
  只用 `$2+$4`（user+system）会**严重低估网络负载**（网络处理跑在 softirq 里）——
  我曾据此报出「2~11%」的错误数字。
- **`br-lan` 计数器不能用来测代理转发量** —— daed 的 eBPF 在网桥层之前就把包重定向走了。
  用 `dae0`（判是否走代理）或 `lan2`/`wan`（测真实转发）。
- **PowerShell 解析 curl 输出会碰到 Unicode 数字**（`۳`、`߉3`）导致
  `InvalidCastFromStringToDoubleOrSingle` —— 汇总吞吐不要用 curl 的 `-w` 输出，改用设备侧 `dae0` 增量。
- **`chmod +x` 别忘了**（本轮忘记一次，`nohup` 报 `Permission denied`）。

---

## 十二、★ 复发与再验证（2026-10-09 同日，用户第二次反馈「cpu 还是没有负载均衡」）

### 现象

用户 htop 截图：`CPU0 93.4% / CPU1 47.6% / CPU2 50.4% / CPU3 52.4%`，`Net rx 102MiB/s tx 72.9MiB/s
(46771/52427 pps)`，Speedtest 271.34 Mbps，8 个 daed 线程合计 117.8%。

**⇒ 形态与初版几乎一致 ⇒ 说明修复被某种机制回退了。**

### 定位过程（三步，每步都有独立证据）

**① 先查中断亲和性 —— 完好，排除**

```
irq25 aff=4 (CPU2) ✓    irq29 aff=8 (CPU3) ✓
⇒ 中断钉核全部存活，不是它
```

**② 查软中断分布 —— 锁定异常**

```
                  CPU0       CPU1       CPU2       CPU3
NET_RX:       5,332,885    428,741    429,901    456,453     ← CPU0 占 79.4%
/proc/stat:  cpu0 softirq=137400 | cpu1=4118 cpu2=5718 cpu3=4756   ← CPU0 是其他核的 24~33 倍
```

**③ 查 RPS —— 找到真凶**

```
lan2  rx队列=32  已设f=0   未设=32     ← ★ 全部被打回默认值 1
wan   rx队列=32  已设f=0   未设=32     ← ★ 同上
br-lan/dae0（各 1 队列）已设f=1 ✓       ← 单队列的幸免于难
```

**⇒ 与 dmesg 的网卡重新入网桥事件对上了（见第七节）。**

**⇒ 双层机制的解释**：中断亲和性决定「谁收包」，RPS 决定「谁处理包」。
中断层活了，处理层死了 ⇒ 包收进 CPU2/CPU3 后仍全部堆到 CPU0 走协议栈。

### ★★ 用真实转发路径做的终局验证（16 路并行下载经 daed 代理，33 秒，205 Mbps）

```
每核 busy（busy = user+nice+sys+irq+softirq）：
    cpu0 = 42%   cpu1 = 44%   cpu2 = 47%   cpu3 = 46%     ← 四核差距仅 5 个百分点

每核处理的包数（/proc/net/softnet_stat 第 1 列 processed）：
    cpu0 = 291,721 (25%)   cpu1 = 287,519 (24%)
    cpu2 = 300,061 (25%)   cpu3 = 280,295 (24%)           ← 完美均分

daed 全部线程 CPU 增量：
    3,226 jiffies / 33 秒 = 97.76% of one core（4 核的 24.44%）

代理流量指纹：dae0_rx 增量 886,831,685 字节 = 845.7 MB ⇒ 25.63 MB/s
```

**⇒ 账算得平**：daed 约 1 核（97.76%）+ 网络软中断约 0.8 核 = 1.79 核 ÷ 4 = 每核约 45%，
与实测 42/44/47/46% 完全吻合。

### 对照表

| 场景 | cpu0 | cpu1 | cpu2 | cpu3 | 合计 |
|---|---|---|---|---|---|
| 用户截图（复发态） | **93.4%** | 47.6% | 50.4% | 52.4% | 243.8% |
| 空闲基线 | 2% | 2% | 3% | 2% | 9% |
| **修复后实测（205 Mbps 代理）** | **42%** | **44%** | **47%** | **46%** | 179% |

### ★★★ 三个必须记住的认知修正

**修正 1：`rps_cpus=1` **并不会**把包全赶到 CPU0。**

A/B 对照实测（iperf3 8 路并行 30 秒，LAN 侧本机终结）：

```
A 组 (RPS=f):  processed cpu0=31% cpu1=39% cpu2=28% cpu3= 0%
B 组 (RPS=1):  processed cpu0=34% cpu1= 3% cpu2=32% cpu3=29%
```

**⇒ 因为硬件中断已钉在 CPU2(irq25)/CPU3(irq29)；当 RPS 掩码不允许这些核时，
内核就在**当前中断核**上就地处理，而不是硬塞给 CPU0。**
**⇒ 所以「设了 rps_cpus=1 就等于单核」是错的。**

**修正 2：那个「不处理网络包」的核，`busy` 反而最高。**

```
A 组: cpu3 processed=0%   busy=88%
B 组: cpu1 processed=3%   busy=83%
```
**⇒ 它忙的不是网络软中断，而是 daed 的线程。**
**⇒ 代理进程本身才是最大的 CPU 消费者（约 1 核），只是它被调度到了不同核上。**

**修正 3：判据要选对 —— `/proc/softirqs` 不是好判据。**

`/proc/softirqs` 的 `NET_RX` 统计的是**软中断向量被执行了多少次**，
受 NAPI 批处理大小、GRO 合并、执行时机影响极大，**不能当作「处理了多少包」**。
初版我用它得出了自相矛盾的分布（RPS=1 时 cpu0 只占 3%）。

**⇒ 正确判据是 `/proc/net/softnet_stat`：**
```
第 1 列 processed      = 该核实际处理的包数   ← 权威判据
第 2 列 dropped
第 3 列 time_squeeze
第 10 列 received_rps  = 被 RPS 转移到本核的包数  ← RPS 是否生效的直接证据
格式为十六进制，BusyBox awk 需用 strtonum("0x"$1)（实测可用；隐式 ("0x"$1)+0 返回 0，不可用）
```

### ★ 诚实说明：无法严格分离各修复项的贡献

**能确定的**：当前状态下四核均衡（实测 42/44/47/46，包处理 25/24/25/24）。

**不能确定的**：RPS 恢复与中断亲和性各自的独立贡献。
A/B 测试显示在本机终结场景下 RPS 开关对分布影响不大，
但**本机终结 ≠ 代理转发**（转发要经 eBPF 重定向进 `daens` netns，绕过 RFS 的 socket 匹配），
所以 A/B 的结论不能外推到真实场景。

**⇒ 这正是建三层守护的理由：不依赖对贡献的精确归因，直接保证状态不被回退。**

### 本轮清理的遗留

- 我此前调试留下的 `socat UDP4-LISTEN:53,bind=127.0.0.2,fork UDP4:127.0.0.1:5353`
  残留进程 3 个（PID 393/396/409）—— 已全部 `kill -9`。
- 我自己脚本里的 jiffies→秒 换算 bug：`4 jiffies / 3秒` 曾误报成 `133% of one core`，
  正确是 `1.33%`（jiffies 为 100/秒，需除以 100）。已修正为 `x/d` 与 `x/(d*4)`。

### 本轮新增工具经验

- **BusyBox 没有 `paste`** —— 用它做两文件列对齐会报 `paste: not found`（第二次踩到）。
  替代：把每个值写成独立一行，用 `sed -n "${N}p"` 取行 + shell 算术。
- **BusyBox awk 的 `? :` 三元不能用在 `printf` 参数位** —— 报 `syntax error`。
  要改用 `if/else` 赋值给变量后再 `printf`。
- **`awk` 里 `$ (i+4)` 这种带空格的字段引用是语法错误**（`$` 与 `(` 必须紧贴）。
- **PowerShell 会把 `$(...)` 当子表达式在本地求值** —— 经 SSH 下发含 `$(cat ...)` 的命令时，
  它会在**本机**执行并报 `CommandNotFoundException`。
  **⇒ 铁律：任何含 `$(` 的 shell 一律整段 base64 后传输，绝不行内联。**
  同理 `<` 会被当成重定向符导致解析失败。
- **`strtonum` 在 BusyBox awk 上可用**（本固件实测），但**必须先用阳性对照验证**：
  `awk 'BEGIN{printf "%d\n", strtonum("0x1f")}'` 应输出 31。
  这是本项目第四次栽在「没有阳性对照就下否定结论」上。
- **经 SSH 传文件时 stdin 不可靠** —— PowerShell 管道会引入 CRLF/BOM，导致 `base64: invalid input`。
  可靠做法是 `echo '<b64>' | base64 -d > 目标`（b64 字符集不含特殊字符，可安全内联）。

### ★★★ 本轮最贵的一个坑：JavaScript `String.replace()` 的 `$'` 特殊模式

**事故经过**：我用 `cur.replace(oldBlock, newBlock)` 改脚本，`newBlock` 里含 shell 的
`grep -v '^$'`。写入后文件变成：

```
SAMPLE=$(echo "$DETAIL" | tr ' ' '\n' | grep -v '^
                                                    ← '^$' 只剩 '^
exit 0                                              ← 被塞进来的"匹配右侧文本"
 | head -3 | tr '\n' ' ')
```

`sh -n` 报 `unterminated quoted string`。**而设备上 cron 每 2 分钟就在跑这个坏脚本。**

**根因**：JS `String.replace(search, replacement)` 在 replacement 是**字符串**时，
会解析这些特殊模式：

```
$$  → 一个 $              $&  → 匹配到的子串
$`  → 匹配子串【左侧】的文本
$'  → 匹配子串【右侧】的文本     ← ★★★★ 就是它
$n  → 第 n 个捕获组
```

`oldBlock` 以 `fi` 结尾、其右侧正好是 `\n\nexit 0\n` ⇒ `'^$'` 里的 `$'`
被替换成了这段文本。**与实测的 L78-L81 逐字节吻合。**

**⇒ 铁律：`String.replace()` 的替换串若可能含 `$`，必须用函数式替换。**

```js
// ✗ 危险：replacement 里的 $' / $& / $` / $n 会被解析
content.replace(old, newText);
// ✓ 安全：函数返回值不做任何 $ 解析
content.replace(old, () => newText);
```

**⇒ 并且本次的补救流程值得复用**（这才是把事故变成资产的部分）：
1. **先回滚到已知可用版本**（部署前我留了 `.v3.bak`，`cp` 回来即恢复）
2. **最小复现定位根因**（三种写法直写文件全部正常 ⇒ 排除写文件环节，锁定 `replace`）
3. **重做后本地逐字节自检，再上设备** —— 7 项断言：
   `含完整的 grep -v '^$'`、`含 head -3`、`含 SAMPLE=`、`不含裸 exit 0 夹在命令替换里`、
   `行数合理`、`恰好一个 exit 0 在末尾`、`if/fi 配对` ⇒ 全绿才部署
4. **上设备后再验一次**（sha256 + `sh -n` + 实际执行 + 幂等）

**⇒ 关键认知**：原来「`fs.writeFileSync` 写文件」和「`replace` 改文件」是**两条不同的风险路径** —
前者是逐字节直写（安全），后者要过 `$` 解析（危险）。
**我把「写文件验证过了」错误地推广成了「改文件也安全」。**
