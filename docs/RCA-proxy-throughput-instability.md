# XR1710G 代理吞吐「速度上不去 / 上去后掉下来」—— 根因：内核 `netdev_budget` 默认值为 1

**日期**：2026-10-09
**现象**（用户原话）：「我手动测试了一下，它确实每个核心都负载均衡了。但是它速度上去了，占用不能持续稳定，会掉下来。」
**背景**：CPU 单核吃满问题（见 `RCA-daed-multicore-saturation.md`）修复后，四核已均衡，暴露出新的故障面。

**结论（一句话）**：本内核（6.18.52 airoha）编译默认 `net.core.netdev_budget = 1`（Linux 标准默认 **300**），
导致 NAPI 软中断**每处理 1 个包就必须让出 CPU 并重走一遍调度**。实测使 `time_squeeze`
空闲时每 12 秒累积 **3,673** 次、代理负载下每 4 秒高达 **7,022** 次。改为 300 后归零，
代理吞吐波动由 ±30%（含两次崩塌到 296/783 KB/s）收窄至 ±13% 且崩塌消失。

---

## 一、发现过程

### 1. 基线体检排除掉大部分嫌疑

| 项目 | 实测 | 结论 |
|---|---|---|
| 温度 | `thermal_zone0` 54.8°C；trip point 95°C(hot)/120°C(critical) | **热降频排除** |
| 降频设备 | `cooling_device0-2` 全是 `mt7996_phy0.*`（WiFi），**CPU 未绑定任何降频设备** | **热降频排除** |
| 调频器 | `performance`，1300MHz；`time_in_state` 显示 99.93% 时间在最高档 | **未发生降频** |
| conntrack | 796 / 65536 = **1.2%** | 排除 |
| 内存 | 可用 1,382 MB；`allocstall_*` 全 0、`compact_stall` 0 | 排除 |
| fq_codel | wan 下 32 个子队列 `Sent 0 bytes 0 pkt (dropped 0)` —— **全空** | **AQM 丢包排除**（代理流量走 `dae0`，不经 wan 的 fq_codel） |
| br-lan clsact | `dropped 344 / 3845 万包` | 排除（daed 的 eBPF 没在丢包） |

### 2. 两处异常浮出

```
① net.core.netdev_budget = 1        ← Linux 标准默认是 300
② softnet_stat 的 time_squeeze 偏高：
     cpu1 = 20.7%   cpu2 = 22.3%   cpu3 = 19.2%   (squeeze / processed)
```

### 3. ★ 逐处确认 `netdev_budget=1` 的来源 —— 是内核编译默认值，无人设置

```
/etc/sysctl.conf          → 无
/etc/sysctl.d/*（6 个文件）→ 无
grep -rl 整个 /etc/       → 无任何文件提及
内核 cmdline              → 无
uci                       → 无
/etc/fs-net-tune.sh       → 只设了 netdev_max_backlog，未碰 budget
/proc 条目的 mtime         → 等于开机时刻 ⇒ 开机后无人写过它
```

---

## 二、机制

`net.core.netdev_budget` = **每轮 NAPI 软中断允许处理的总包数**（跨所有 netdev）。
配套的 `netdev_budget_usecs = 20000`（20ms）是时间预算，两者**取先到者**。

设为 1 时：**每处理 1 个包就触发一次「预算用尽」**，内核记一次 `time_squeeze`
并让出 CPU、重新走一遍软中断调度。

**⇒ 后果**：
1. 纯浪费的调度开销（空闲时每 12 秒 3,673 次）
2. 高包速率下 NAPI 被反复打断 ⇒ 丢包 / 延迟抖动 ⇒ TCP 超时重传 ⇒ 拥塞窗口崩塌

**⇒ 这解释了「速度上去后掉下来」：不是 CPU 不够，而是包处理被反复打断导致连接降速。**

---

## 三、★★ 一个必须记住的推理陷阱（本次踩到并已修正）

**错误推理**：观察到「崩塌时 `daed` CPU 只有 8.8%、四核 busy 只有 5-7%」，
就判断「设备是闲的 ⇒ 瓶颈在上游，设备无辜」。

**为什么错**：这混淆了因果方向。

```
budget=1 → NAPI 反复被打断 → 丢包/延迟抖动 → TCP 重传、拥塞窗口崩塌
         → 上游停止供数 → 【此时】设备才变闲
```

**「崩塌时设备空闲」是设备先出问题的【结果】，不是设备无辜的【证据】。**

**判据怎么写才对**：不能用「出问题时 CPU 是否忙」来判定瓶颈在哪 —— 因为
**一旦上游断流，任何设备都会显示空闲**。要区分「处理不动」与「没数据可处理」，
必须看**修复前后的稳定性对比**，而不是看故障瞬间的瞬时占用。

---

## 四、A/B 实测数据

### 4.1 空闲基线（squeeze 增量）

| | cpu0 | cpu1 | cpu2 | cpu3 | 合计 /12s |
|---|---|---|---|---|---|
| `budget=1` | 1056 | 750 | 1050 | 817 | **3,673** |
| `budget=300` | **0** | **0** | **0** | **0** | **0** |

### 4.2 代理负载时间序列（16 路并行，间隔 4 秒）

| 指标 | `budget=1` | `budget=300` |
|---|---|---|
| squeeze /4s | 473 ~ 7,022 | **0（全部 24 个采样点）** |
| 吞吐 | 8,000-10,500 KB/s，**±30%** | 7,581-9,760 KB/s，**±13%** |
| 崩塌 | **t=112 → 296 KB/s；t=116 → 783 KB/s** | **无** |
| daed CPU | 8% ~ 65% 剧烈摆动 | 22% ~ 31% 稳定 |
| 四核 busy | 5% ~ 33% | 8% ~ 25% |

### 4.3 对照组：直连 vs 代理（同一次实验内）

```
直连腾讯云镜像（dae0≈0，走 NPU 卸载不经协议栈）：
  wan 47,000-51,000 KB/s (≈370-400 Mbps)   波动 ±4%    busy 1-4%
  squeeze/4s: 130-407                        daed 0.5-2%

走代理 OVH：
  wan 8,000-10,500 KB/s (≈65-84 Mbps)      波动 ±30%   busy 5-33%
  squeeze/4s: 473-7,022                      daed 8-65%
```

**⇒ 反直觉但可解释**：代理吞吐低 5 倍，squeeze 却高 10 倍。
因为直连走 NPU 硬件卸载、包根本不进协议栈；代理走用户态长路径
（eBPF 重定向进 `daens` netns + daed 处理），包进协议栈且路径复杂。
**⇒ `budget=1` 专门惩罚这种「包进协议栈」的路径 —— 也就是代理路径。**

---

## 五、修复（四层，接进既有的网络调优守护）

```
① /etc/fs-net-tune.sh                     4768 B  sha256 ca01b638fc62a128e04edeb5dbe5d45770c2fde214d3f36455e084420c15c7e9
   在 SYSCTLS 段新增 net.core.netdev_budget=300（含完整来龙去脉注释）
   备份：/etc/fs-net-tune.sh.v31.bak
② /etc/sysctl.d/13-netdev-budget.conf     1148 B  sha256 26ce8662df57ceec06ab7469dd1e4a5469bcfa28294a4e62329f8565137a1a08
   ★ 纯 ASCII（非 ASCII 字节数实测 = 0）
   动机：fs-net-tune.sh 靠 uci-defaults/hotplug/cron 触发，开机后最长约 2 分钟空窗；
        sysctl.d 在开机极早期加载，两者互补，堵住空窗
   备份：/etc/sysctl.d/13-netdev-budget.conf.bak-zh（中文注释初版，520 B）
③ /etc/sysupgrade.conf                     15 项（新增第 ② 项）
④ hotplug /etc/hotplug.d/net/90-rps-guard + cron */2 照旧作用于 ①
```

### 验证

| 项目 | 结果 |
|---|---|
| `sh -n`（fs-net-tune.sh） | SYNTAX-OK |
| **三个源文件 本地==设备 逐字节比对** | ✅ `ca01b638…` / `26ce8662…` / `680bab23…` 全部一致 |
| `sysctl -p /etc/sysctl.d/13-netdev-budget.conf` | 先人为改回 1 再加载 → `net.core.netdev_budget = 300` ✓（确认文件本身有效） |
| 纯 ASCII 检查 | 非 ASCII 字节数 = **0** |
| 幂等性 | 连跑两次，net-tune 日志 26 → 26 ✓ |
| squeeze 终态 | 12 秒增量 **0 / 0 / 0 / 0** ✓ |
| RPS 终态 | lan2 32/32 · wan 32/32 · br-lan 1/1 · dae0 1/1 ✓ |
| 中断亲和性 | irq25=4 · irq29=8 ✓ |
| 连通性 | 外网 204 ✓  DNS `183.2.172.177` ✓  代理出口 ✓ |
| 生效值 | `cat /proc/sys/net/core/netdev_budget` = 300 ✓ |

### ★ 为什么 sysctl.d 那份改成英文注释

初次写入时用了中文注释。设备侧一切正常（sha256 一致、`sysctl -p` 能加载），
但用 PowerShell `Get-Content` 读出来是乱码 —— 文件是 UTF-8，而 PowerShell 默认按系统 ANSI(GBK) 解码。

**⇒ 文件本身没坏，问题在于：任何用非 UTF-8 工具读它的人（包括未来的我）都会看到乱码，
可能误判为「文件损坏」而去"修"它。**

**⇒ 这个文件在**开机极早期由 sysctl 服务解析**，属于启动关键路径，不该带任何非 ASCII 变量。
中文注释在这里零收益、有维护成本 ⇒ 改为纯 ASCII。**
`fs-net-tune.sh` 的中文注释保留（它是 shell 脚本，`#` 之后由 sh 跳过，风险更低，
且中文可读性对用户有价值）。

---

## 六、遗留与验证缺口

1. **★ 终验判据：用户重跑测速，看速度是否还会中途掉下来。** 未回收。
2. **只做了一轮 A/B**，两次测量不在同一时刻，上游条件可能有变化。
   `/proc/net/softnet_stat` 的**累计** squeeze 比例仍显示 18-19%，
   因为分母含修复前的大段时间 —— **要看增量（时间序列里的 0），不要看累计比例**。
3. 未做长时间浸泡（本次只跑了 96 秒 + 12 秒 ×2）。
4. **代理吞吐上限 65-84 Mbps vs 直连 370-400 Mbps 的差距**未追查 ——
   可能是代理节点（Tokyo AS400618）带宽限制，也可能是海缆/晚高峰。
   本次修复证明的是**稳定性**改善，**不是上限提升**（上限几乎没变：10.5 → 9.8 MB/s）。
5. 若用户重跑测速后仍掉速，下一步排查方向（按嫌疑排序）：
   ① 代理节点侧带宽/质量（换节点对比）；
   ② ISP 对代理协议的特征识别与限速（换端口/协议对比）；
   ③ daed 的节点选择与健康检查逻辑（看 `/etc/daed/logs/current.jsonl`）。

---

## 七、可复用的诊断工具

### 时间序列采样器 `/tmp/ts.sh <总时长> <间隔>`

每行输出：瞬时吞吐（wan/lan2/dae0）、四核 busy、四核 squeeze 增量、
丢包、温度、mq requeues、daed CPU%。

**⇒ 用途：把「掉速」的时刻与所有候选指标对齐，一眼看出谁在同时变化。**

**⇒ 实现要点（都是本项目踩过的坑）**：
- **不用 `paste`**（BusyBox 没有）—— 把每个值写成独立一行，用 `sed -n "${N}p"` 取，
  或把两列合成一个文件后单次 `awk` 双文件对比
- **不用 `awk` 三元在 printf 参数位**（BusyBox awk 报 syntax error）—— 改用 `if/else` 先赋值
- **`strtonum("0x"$1)` 解析 softnet_stat 的十六进制可用**，但 `("0x"$1)+0` 返回 0 不可用
- 整个脚本 base64 传输（PowerShell 会把 `$(` 当子表达式在本地求值）

### 关键判据速查

```sh
# 内核默认值缺陷确认
cat /proc/sys/net/core/netdev_budget          # 应为 300，本机出厂是 1

# NAPI 是否被反复打断（要测【增量】不要看累计）
awk '{print strtonum("0x"$3)}' /proc/net/softnet_stat

# 代理流量指纹（为 0 说明走直连/NPU 卸载）
cat /sys/class/net/dae0/statistics/rx_bytes

# 是否走 NPU 卸载（直连的特征：高吞吐 + 极低 CPU）
```

---

## 八、工具陷阱（本会话新增，均已付出代价）

- **JavaScript `String.replace()` 的替换串里 `$'` 是特殊模式**（还有 `$$` `$&` `` $` `` `$n`），
  `$'` = 匹配子串**右侧**的文本。我用它改脚本时 `grep -v '^$'` 里的 `$'` 被替换成 `\n\nexit 0\n`，
  把脚本炸成语法错误，而设备上 cron 每 2 分钟就在跑它。
  ⇒ **铁律：替换串可能含 `$` 时必须用函数式替换 `content.replace(old, () => newText)`。**
  ⇒ 认知教训：`writeFileSync`（逐字节直写，安全）与 `replace`（过 `$` 解析，危险）是
    **两条不同的风险路径**，我把「写文件验证过了」错误推广成了「改文件也安全」。
- **PowerShell 会把 `$(...)` 当子表达式在本地求值** —— 经 SSH 下发含 `$(cat ...)` 的命令时
  它在本机执行并报 `CommandNotFoundException`。
  **⇒ 任何含 `$(` 或 `<` 的 shell 一律整段 base64 传输，绝不行内联。**
- **BusyBox 没有 `paste`**（本项目第三次踩到）。
- **BusyBox awk 的 `? :` 三元不能用在 printf 参数位**（报 `syntax error`）。
- **`awk` 里 `$ (i+4)` 带空格是语法错误**（`$` 与 `(` 必须紧贴）。
- **改设备脚本的安全流程**：部署前留 `.bak` → 本地逐字节自检（片段完整性、if/fi 配对、唯一 exit）
  → sha256 比对 → 上设备 `sh -n` → 实际执行 → 幂等复验。
