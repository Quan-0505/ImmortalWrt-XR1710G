# XR1710G 刷机指南 —— release `20261009-bcdc0b3e`

> 交接会话构建的镜像，已由我逐项验证。**关键结论：分区布局与设备实跑 DTB 逐字一致，可以 sysupgrade 直刷。**
> 生成于 2026-10-08 23:45

---

## ⚠️ 第一件事：**用哪个文件，别选错**

| 用 | 文件名 | 为什么 |
|---|---|---|
| ✅ **用这个** | `immortalwrt-airoha-an7581-gemtek_xr1710g-squashfs-sysupgrade.itb` | 分区表 = `vendor 0x0/0x600000` + `chainloader 0x600000/0x100000` + `ubi 0x700000/0x1b700000`，**与设备实跑 DTB 逐字一致** |
| ❌ **绝对不要刷这个** | `immortalwrt-airoha-an7581-gemtek_xr1710g-ubi-squashfs-sysupgrade.itb` | 分区表是 `bl2 0x0/0x20000` + `ubi 0x20000/0x0`（整片 flash 做 UBI，U-Boot 自己住在 UBI 里）—— **与本机完全不兼容** |

> ★ **陷阱**：名字里带 `-ubi-` 的那个看起来"更像本机"（本机 board 名确实是 `gemtek_xr1710g-ubi`），**但它的分区表与实机完全不符**。**以分区表为准，不以文件名直觉为准。**

**镜像校验值（已与 GitHub 官方 digest 逐位比对一致）：**

```
文件   : immortalwrt-airoha-an7581-gemtek_xr1710g-squashfs-sysupgrade.itb
字节   : 60698908
SHA256 : a03948fa00ce3f7ff2f455080b39becdf7e23c6ce05d5a0e392a86b85ec4b6ce
```

---

## 已完成的镜像验证（刷之前就已经验过，不用再担心）

| 验证项 | 结果 |
|---|---|
| **① 分区布局** | `vendor 0x0/0x600000` / `chainloader 0x600000/0x100000` / `ubi 0x700000/0x1b700000` —— **与设备实跑 DTB 逐字一致 ✅** |
| **② `reset-before-id-read`（本次修复目标）** | `ethernet-phy@5`(lan2) **已删除 ✅** |
| **③ `realtek,patch-rtk-serdes`（防回归）** | `phy@5` 与 `phy@8` **两口都在 ✅** |
| **④ `airoha,force-direct-pll`（旧坑1）** | **已移除 ✅**（没把修好的坑改回来） |
| **⑤ CPU OPP** | 17 档，最高 `opp-1300000000` = **1300 MHz ✅**（1350/1400 两档已删） |
| **⑥ 镜像完整性** | SHA256 与 GitHub digest 一致 ✅ |

---

## 步骤 0 —— 恢复管理网卡（**必须你来，需要管理员权限**）

PC 上的 `以太网 15`（Realtek PCIe 5GbE，接路由器 lan3）当前是 **Disabled**。
**任选一种方式启用：**

- **图形界面**：开始菜单搜「网络连接」/ `ncpa.cpl` → 右键「以太网 15」→ **启用**
- **命令行（需管理员）**：Win+X → 「终端(管理员)」→
  ```powershell
  Enable-NetAdapter -Name '以太网 15'
  ```

**验证：**
```powershell
ping 192.168.2.1
Test-NetConnection 192.168.2.1 -Port 22
```
两条都通才继续。**不通就不要往下走** —— 先查线是不是插在 lan3/lan4 上（lan2 那个万兆口现在没插东西）。

---

## 步骤 1 —— 把镜像传到路由器并校验

```powershell
# 在 PC 上（把 <镜像路径> 换成上面那个文件）
scp "C:\Users\quan\Desktop\NetProxy-optimized-config-share\XR1710G\immortalwrt-airoha-an7581-gemtek_xr1710g-squashfs-sysupgrade.itb" root@192.168.2.1:/tmp/fw.itb
```

> 密码 `liquansen`。若 scp 因为 Windows 端引号/转义出问题，改用 base64 分块传，或直接在 LuCI 里上传（见步骤 2 备选）。

**传完后在路由器上校验（关键，别跳过）：**
```sh
# 先确认 RAM 够（镜像 57.9 MB，/tmp 是内存盘）
free | head -2
df -h /tmp

# 校验 SHA256 —— 必须与上面那个值逐位一致
sha256sum /tmp/fw.itb

# 再验一次镜像内容没传坏：确认里面是"普通版"布局
grep -c "gemtek_xr1710g-ubi" /tmp/fw.itb   # 只是文件名字符串，不代表布局
```

**判据：`sha256sum` 输出 = `a03948fa00ce3f7ff2f455080b39becdf7e23c6ce05d5a0e392a86b85ec4b6ce`。不一致就重传，不要刷。**

---

## 步骤 1.5 —— 先做镜像试运行（不写 flash）

本版 `sysupgrade` **支持 `-T`（试运行）**，刷之前先验一次：

```sh
sysupgrade -T /tmp/fw.itb ; echo "退出码=$?"
```

**判据：退出码 = 0。** 即使校验失败也只是**中止且不写 flash**（安全失败）。

> ⚠️ 实测 `-T -v` **不打印任何输出**，只有退出码可依据。所以"compat 版本通过"这个结论**只能由退出码支持**，没有文字确认。

---

## 步骤 2 —— 刷写

```sh
sysupgrade /tmp/fw.itb
```

**★ 不要加 `-k`。** 本版 `sysupgrade --help` 里 `-k` 的含义是
*"include in backup a list of current installed packages at `/etc/backup/installed_packages.txt`"*，
**不是"保留配置"**。（本指南早期版本写成 `sysupgrade -k` 是**错的**，已更正。）

**OpenWrt 的 `sysupgrade` 默认就保留配置** —— 当前配置里 LAN 是 `192.168.2.1`，默认行为即可保住它，同时保住 daed 配置、feed 清理、footstrap 修复、以及 `sysupgrade.conf` 里登记的全部 9 项。**要放弃配置才需要显式加 `-n`。**

本版相关选项（摘自设备上的 `sysupgrade --help`）：

| 选项 | 含义 |
|---|---|
| （不加） | **默认保留配置** |
| `-n` | **不**保留配置 |
| `-c` | 保留 `/etc/` 下**所有**被改过的文件 |
| `-u` | 备份时跳过与 `/rom` 中相同的文件 |
| `-T` | 只校验、不刷写 |
| `-F` | 校验失败也强行刷（危险） |
| `-p` | 不尝试恢复分区表 |

- 路由器会**自动重启**，全程约 **2–4 分钟**
- SSH/网页会断开 —— **这是正常的**
- **不要断电、不要拔线**

> **备选（网页方式）**：浏览器打开 `http://192.168.2.1` → 系统 → 备份/刷写固件 → 「刷写新固件」→ 选文件 → **保留勾选「保留配置」** → 刷写。

**⚠️ 刷写期间可以放心的理由**：按当前拓扑，全屋设备（`192.168.5.x`）在 OPNsense 后面，1710 只是挂在 OPNsense 局域网上的一个客户端（走 wan 口）。**刷 1710 不会断全屋的网**，只影响它自己的 LAN/Wi-Fi。

---

## 步骤 3 —— 刷完立刻验证修复是否真的生效

**等 3–4 分钟，然后：**

```sh
# ① 管理通路
ping 192.168.2.1
ssh root@192.168.2.1
```

```sh
# ② ★ 最关键的验证 —— 直接从运行中的设备树里读，确认属性真的没了
ls /sys/firmware/devicetree/base/soc/switch@1fb58000/mdio/ethernet-phy@5/
#    期待：看不到 reset-before-id-read
#    仍应看到：reset-gpios / reset-assert-us / reset-deassert-us / realtek,patch-rtk-serdes

# 对照（wan 本来就没有）
ls /sys/firmware/devicetree/base/soc/switch@1fb58000/mdio/ethernet-phy@8/
```

> **这一条是整个流程里最硬的证据** —— 它读的是**内核实际使用的设备树**，不是仓库源码、也不是镜像文件。看到 `reset-before-id-read` 消失，就说明修复真的进了运行时。

```sh
# ③ 基础健康
printf 'oops=%s  segfault=%s\n' "$(logread | grep -c 'Oops')" "$(logread | grep -ci segfault)"
printf 'board=%s  内核=%s\n' "$(cat /tmp/sysinfo/board_name)" "$(uname -r)"
cat /etc/openwrt_release | grep -E 'RELEASE|REVISION'

# ④ 网桥与管理口没被刷丢
ls /sys/class/net/br-lan/brif/
ip -4 -o addr show br-lan

# ⑤ daed（应仍为 2 进程 / :2023 LISTEN / clsact）
ps w | grep -c '[d]aed'
netstat -lntp 2>/dev/null | grep 2023
tc qdisc show dev br-lan
```

**若 ② 里 `reset-before-id-read` 仍然存在** ⇒ 说明刷进去的还是旧镜像，停下来查（可能刷错文件、或 sysupgrade 校验失败）。

---

## 步骤 4 —— 10G 抖动测试

**前置**：把下游交换机的网线从 wan 挪到 **lan2**（万兆口）。lan3/lan4 保持不动（那是管理通路）。

```sh
# 启动监测器（设备上已部署 v2，按端口分离计数）
/etc/10g-monitor.sh start
/etc/10g-monitor.sh status
```

**基线对照（刷之前的记录）：**
| 组合 | 结果 |
|---|---|
| lan2 + 交换机 + 全屋 | ❌ down=8 / up=8（主要症状） |
| lan2 + PC 5GbE | ✅ 零掉线（**但只跑到 5G，没到 10G**） |
| wan + 全屋 2.5G | ✅ 稳定 |

**加负载**（关键是**发送方向** —— 历次"稳定"的观测中路由器几乎只收不发，这是唯一从没测透的维度）：
- 让 PC 从 lan2 侧灌流量进来
- 同时让路由器往外发（可用 `ip neigh add ... nud permanent` 绕开 ARP 强制走 lan2）

**通过判据：**
```sh
# 稳定挂载 ≥30 分钟后，这个增量必须是 0
logread | grep -c 'lan2: Link is Down'
# 协商速率应稳定在 10000Mb/s，不出现 5000→2500 降级
cat /sys/class/net/lan2/speed
```

> **注意**：`pulsed RTK SerDes ... after copper AN` 在 2.5G/5G/10G **每次** link-up 都会出现一次，**是正常握手，不是故障信号**，不要拿它计数。
> 两个口的日志前缀只差 PHY 地址：**lan2 = `mt7530-0:05`**、**wan = `mt7530-0:08`**，**必须分开过滤**，否则会把 wan 的事件误记到 lan2 头上。

---

## 万一刷坏了 —— 恢复手段

1. **http-uboot**：`192.168.255.1:80`，界面选对应的布局版本。**只写 chainloader 槽 `0x600000`（≤1 MiB），不触碰原厂一级 bootloader。**
2. **自动兜底**：`bootcmd=run boot_ubi || http_recovery` —— UBI 启动失败会自动掉进 Web 恢复
3. **备用入口**：开机按住 reset（GPIO0 低有效）
4. **纯固件问题**：只需重刷 `*-sysupgrade.itb`，不必重建 UBI

**⚠️ 恢复时界面的布局选择必须与镜像内嵌 FDT 一致**，否则 `not enough PEBs` → `Waiting for root device /dev/fit0`。

---

## 如果刷完仍然抖动（否证条件）

按顺序、**一次只改一个变量**：

1. **`airoha,tx-fir`** —— 补丁 629 引入的 10G **发送**侧唯一未排除旋钮，当前两个口都没设。作者自述"无元组通过可复现测试"，属未验证钩子，需要试值。
2. **`744` 的脉冲时长（10–12 ms）** —— 那是作者**在某一台机器上实测**得出的值，换板可能不适用。
3. **`628` 的 RX 校准 crossing search** —— 已随固件包含，参数是否适配本板未知。
4. **补丁 622 的 `realtek,sds-mode = <0x88c6>`** —— naoki66 线原文说 U-Boot 会给 SDS page 6 reg 3 写 `0x88c6`，而通用 Linux 初始化漏了这项。⚠️ **光加 DTS 无效**，驱动端 `rtk826x_config_sds_mode()` 需一并恢复。

---

## 一句话总结

**刷 `..._xr1710g-squashfs-sysupgrade.itb`（不带 `-ubi-`），命令就是 `sysupgrade /tmp/fw.itb`（不加任何选项 = 保留配置），刷完用 `ls /sys/firmware/devicetree/base/soc/switch@1fb58000/mdio/ethernet-phy@5/` 确认 `reset-before-id-read` 消失，然后把交换机插到 lan2 跑监测器。**

---

## 附：刷前发现的持久化陷阱（**本次已修复，但设计本身要记住**）

刷前检查发现：`sysupgrade.conf` 里登记的这两个**调用壳已经不存在了**——

```
★ 登记了但不存在: /etc/uci-defaults/99-remove-dead-feeds
★ 登记了但不存在: /etc/uci-defaults/98-fix-footstrap-header
```

**原因**：`/etc/uci-defaults/` 下的脚本**执行成功后会被系统自动删除**（标准机制），而备份只备份**实际存在**的文件 ⇒ 既没被保留、也没被恢复，**全程没有任何报错**。

**后果**：`/www/luci-static/footstrap/cascade.css` 的 footstrap 修复改在**只读 squashfs** 里，重刷必然被原始版本覆盖；若调用壳缺失，就**没有任何脚本会再修它** ⇒ 吸顶导航重叠 bug 直接回归。

**已在刷前修复**：重建两个壳（内容一行、mode 755），并把 `/etc/10g-monitor.sh`、`/etc/10g-loadtest.sh` 也登记进 `sysupgrade.conf`。刷前终态——

```
sysupgrade.conf 共 9 项，逐项验证存在，缺失 0 项：
  /etc/crontabs/                              ✅
  /etc/config/wireless                        ✅
  /etc/uci-defaults/99-remove-dead-feeds      ✅（本次重建）
  /etc/uci-defaults/98-fix-footstrap-header   ✅（本次重建）
  /etc/fs-fix-nav.sh                          ✅
  /etc/fs-fix-feeds.sh                        ✅
  /etc/apk/repositories.d/distfeeds.list      ✅
  /etc/10g-monitor.sh                         ✅（本次新增）
  /etc/10g-loadtest.sh                        ✅（本次新增）
```

**⇒ ★ 本次刷机是这套三层持久化设计的第一次真实重刷检验**（此前只做过 `/tmp` 副本演练 + 存在性检查）。刷完应确认：两个壳被重新执行后又被消耗掉、`cascade.css` 里 `isolation` 与 `z-index:9999` 各为 1、`distfeeds.list` 行数仍为 8、`sysupgrade.conf` 仍为 9 项。

**⇒ 通用规律（做任何设备侧持久化前必读）**：三层缺一不可 ——
1. **永久主体**放在 `/etc/uci-defaults/` **之外**（如 `/etc/fs-fix-nav.sh`），永不删除；
2. **一次性调用壳**在 `/etc/uci-defaults/` 下，内容仅一行调用；
3. **被修改的目标文件本身**也写进 `sysupgrade.conf`（能写的话）作为第二道保险。

三者都要登记进 `sysupgrade.conf`。

---

## 刷前最终状态存档（可复现）

```
镜像    /tmp/fw.itb   60698908 字节
        SHA256 = a03948fa00ce3f7ff2f455080b39becdf7e23c6ce05d5a0e392a86b85ec4b6ce
        与 GitHub digest 逐位一致 ✅
试运行  sysupgrade -T /tmp/fw.itb  →  退出码 0 ✅
配置备份 /tmp/cfg-backup.tar.gz  19439 字节 / 73 项，已拉回 PC：
        XR1710G/cfg-backup-before-flash.tar.gz
刷前基线 lan2 PHY 节点含 reset-before-id-read：1 个（刷后应为 0）
        /sys/firmware/devicetree/base/soc/switch@1fb58000/mdio/ethernet-phy@5/
内存    total 1.78 GB / free 1.41 GB      /tmp(tmpfs) 909.3M 可用 850.7M
固件    内核 6.18.52   REVISION 2026-10-7-035afe00fa-d0c702152b   board gemtek,xr1710g
网络    br-lan 192.168.2.1/24，成员 lan3 lan4 phy0.0-ap0 phy0.1-ap0；lan2 carrier=0
服务    daed 1 进程、:2023 LISTEN、br-lan 有 qdisc clsact
```
