# XR1710G NPU / 加解密能力实测报告（2026-10-09）

**问题**：「NPU 的加解密性能咋样」

**一句话结论**：**NPU 根本不具备加解密能力**（它只是转发卸载引擎）；SoC 里**另有一个**硬件加密引擎 EIP93 但**固件没编驱动、完全没用上**；CPU 也**没有** ARMv8 Crypto Extensions；因此本机 AES 只能软件跑（单核 283 Mbps）。**但实际代理流量全部协商到了 ChaCha20-Poly1305（单核 1740 Mbps，快 6.1 倍），加密开销约 0.08 核 —— 加密不是瓶颈。**

---

## 一、三层硬件事实

### 第 1 层：NPU（PPE）不做加解密

PPE = Packet Processing Engine，是**纯转发卸载**：流表匹配 + L2/L3/L4 改写 + 转发，**没有密码学单元**。
- 直连流量走 NPU：实测 960 Mbps 仅耗 0.25 核
- 代理流量必须经用户态做协议处理 ⇒ **物理上无法卸载**（架构决定，不是配置问题）

### 第 2 层：SoC 里有一个硬件加密引擎，但没用上

```
设备树：
  /sys/firmware/devicetree/base/soc/crypto@1fb70000/compatible
    → inside-secure,safexcel-eip93ies
```

**EIP93 是 Inside Secure（SafeXcel）的 IPsec/加密加速器**，典型用途是 IPsec ESP 卸载（AES-CBC/GCM、DES/3DES、SHA/HMAC）。

**但它完全没被启用**：
- `/proc/crypto` 有 38 条算法，driver 全是软件实现：`aes-generic` / `ctr(aes-generic)` / `ccm_base(...)` / `ghash-generic` / `sha256-lib` / `md5-lib` …，**没有任何 `safexcel` / `eip93` / `inside-secure`**
- `modules.builtin` / `modules.dep` 里没有对应驱动
- `openssl engine -t -c` 只有一个 `(dynamic) Dynamic engine loading support [ unavailable ]`

⇒ **芯片里有硬件，固件里没驱动。**

### 第 3 层：CPU 也没有 ARMv8 Crypto Extensions

```
/proc/cpuinfo Features: fp asimd evtstrm crc32 cpuid
  aes    ✗      pmull  ✗      sha1  ✗      sha2  ✗
  crc32  ✓      asimd  ✓      fp    ✓
```
（判定方法已做正/负向对照：必然存在的 `asimd` 判定=有，必然不存在的 `zzznotreal` 判定=无）

⇒ **AES 只能软件实现**（查表法）。这也解释了为什么 ChaCha20 反而比 AES 快得多 —— ChaCha20 本来就是为软件实现设计的（ARX 运算，无查表、无缓存时序侧信道）。

---

## 二、实测加解密性能

### 测量方法与单位验证

`openssl speed` 的输出单位是 **1000s of bytes per second**（即 `k` = 1000 B/s，不是 1024）。
**这个解读做过正向对照**：`openssl enc -aes-128-cbc` 加密 40 MB 实测 47.1 MB/s，而 `openssl speed` 同算法报 60044.02k ⇒ 按 k=1000 解读为 57.8 MB/s（enc 含文件 IO 开销故偏低）⇒ 吻合。

> ⚠️ 第一次尝试用 `openssl enc -aes-128-gcm` 做对照是**无效的** —— `enc` 子命令不支持 GCM，命令静默失败、文件未生成，却仍报出「0.020 秒 ⇒ 2000 MB/s」的假数据。**改用 CBC 才成立。**

### 单核吞吐（Mbps）

| 算法 | 16B | 64B | 256B | 1KB | 8KB | 16KB |
|---|---|---|---|---|---|---|
| AES-128-GCM | 50 | 123 | 216 | 264 | 282 | **283** |
| AES-256-GCM | 43 | 109 | 183 | 223 | 238 | **239** |
| **ChaCha20-Poly1305** | 310 | 643 | 1280 | 1614 | 1742 | **1740** |
| AES-128-CBC | 324 | 434 | 466 | 483 | 483 | **480** |
| SHA-256 | 59 | 174 | 394 | 582 | 675 | **681** |

### 四核并行（关键：验证能否线性分摊）

4 个独立进程同时跑，每个进程**仍保持单核满速**：

```
实例1 = 35576.07k    实例2 = 35491.68k
实例3 = 35498.67k    实例4 = 35304.74k
线性度 = 1.00  ✅ 零衰减
```

| 算法 | 单核 | 四核合计 |
|---|---|---|
| AES-128-GCM | 283 Mbps | **1136 Mbps** |
| ChaCha20-Poly1305 | 1740 Mbps | **6945 Mbps** |

---

## 三、代理实际用的是哪一个 —— 抓包实测

### 节点清单（`daed.db` / `wing.db` 明文）

```
1  vless  @jp.proxy.suli.ng:8000  security=tls  sni=www.tesla.com      flow=xtls-rprx-vision
2  trojan @jp.proxy.suli.ng:8001  security=tls  sni=jp.proxy.suli.ng
3  anytls @jp.proxy.suli.ng:8003  security=tls  sni=jp.proxy.suli.ng
4  vless  @64.186.245.6:443       security=tls  sni=office.mitsuha.me  flow=xtls-rprx-vision   [US]Dmit
5  vless  @104.224.154.132:443    security=tls  sni=office.mitsuha.me  flow=xtls-rprx-vision   [US]Bandwagonhost
节点 RTT ≈ 163–166 ms
```

**全部 `security=tls` ⇒ 加密由 Go 的 `crypto/tls` 决定。**

### 结果

```
ClientHello × 12（全部完整解析）
  首选 0xCCA9 ECDHE_ECDSA_CHACHA20_POLY1305
  次选 0xCCA8 ECDHE_RSA_CHACHA20_POLY1305
  TLS1.3 段内：0x1303(CHACHA20) 第 11 位 → 0x1301(AES128) 第 12 → 0x1302(AES256) 第 13
  ⇒ ChaCha20 在两个协议版本里都排在 AES 之前

ServerHello × 24
  24/24 = TLS_CHACHA20_POLY1305_SHA256
```

**⇒ 本机代理流量 100% 走 ChaCha20-Poly1305。加密 567 Mbps 仅需约 `567/6945 ≈ 0.08` 核。**

### 为什么 Go 这么选

Go 的 `crypto/tls` 在 arm64 上通过 `cpu.ARM64.HasAES` 判断 AES-GCM 硬件支持；**本机该标志为 false** ⇒ Go 把 ChaCha20 提到首位。这与观测完全一致。

---

## 四、★ 推翻我自己的一个推测

我曾推算：「代理 395 Mbps ÷ 单核软件 AES-GCM 283 Mbps ≈ **1.4 核**，而实测 daed 正好占用 **1.40 核**」—— 并据此认为加密就是 daed 的主要成本。

**这是错的，纯属巧合。** 实际用的是 ChaCha20（比 AES-GCM 快 6.1 倍），加密只占约 0.08 核。daed 那 1.40 核花在**协议处理与网络栈**上，不在加密。

**教训：两个数字碰巧接近不构成因果。我当时没有验证「用的是哪个算法」这个前提，就把它当成了结论的支撑。**

---

## 五、★ 一个意外发现（标注为「证据指向」，非定论）

`/etc/daed/runtime/generated.dae` 里写着：
```
tls_implementation:'tls'      utls_imitate:'chrome_auto'
```

但实测抓到的 ClientHello **不是 Chrome 的指纹**：
- Chrome 会把 TLS1.3 三件套放在最前，且首位是 `TLS_AES_128_GCM_SHA256`
- 实测列表首位是 `ECDHE_ECDSA_CHACHA20_POLY1305`，TLS1.3 三件套落在第 11–13 位
- 这是 **Go `crypto/tls` 的默认布局**

⇒ **证据指向 uTLS 指纹未生效**（可能被 `tls_implementation:'tls'` 覆盖，或该版本 daed 未接入 uTLS）。
**未进一步验证**，因为需要读 daed 源码或做对照实验才能定论。若 uTLS 确实没生效，则「抗 TLS 指纹识别」这一层的实际强度低于配置所暗示的。

---

## 六、待排除项

`generated.dae` 里有：
```
bandwidth_max_tx:'200 mbps'      bandwidth_max_rx:'1 gbps'
```
**实测峰值 567 Mbps 已超过 200 Mbps，且下载方向对应 rx(1 gbps)，故判断它不是瓶颈。**
但**没有直接验证它是否真在限速**（需要改配置做 A/B，会影响全屋上网，未做）。

---

## 七、结论与建议

| 问题 | 答案 |
|---|---|
| NPU 能做加解密吗 | **不能**。PPE 只做转发卸载，没有密码学单元 |
| 代理能用 NPU 加速吗 | **不能**。必须经用户态协议处理（架构决定） |
| SoC 有硬件加密引擎吗 | **有**，EIP93（`safexcel-eip93ies`），设备树里声明了 |
| 用上了吗 | **没有**。无内核驱动，`/proc/crypto` 全是软件实现 |
| CPU 有 AES 指令吗 | **没有**。`aes`/`pmull`/`sha1`/`sha2` 全缺 |
| 那 AES 有多快 | 单核 283 Mbps / 四核 1136 Mbps（软件） |
| 实际用 AES 吗 | **不用**。24/24 全协商到 ChaCha20-Poly1305 |
| 加密是瓶颈吗 | **不是**。567 Mbps 仅需约 0.08 核 |
| 该不该挖 EIP93 | **不建议**。要写内核驱动 + 让用户态走 AF_ALG/cryptodev，而 ChaCha20 已远超实际需求（6945 Mbps vs 567 Mbps） |

**⇒ 代理吞吐的上限问题不在加解密。** 见 `RCA-proxy-1000M-ceiling.md`（4 核 CPU 预算限制）与 `RCA-daed-multicore-saturation.md`。

---

## 八、本轮方法错误记录（三个，全是自伤）

抓包解析连错三次，每次都差点得出错误结论：

1. **假设链路层是以太网** —— 实际 `pppoe-wan` 上 tcpdump 用 `LINKTYPE_LINUX_SLL`（16 字节头，不是 14）。
   症状：解析出 0 个握手（400 个包里）。
2. **只处理 IPv4** —— 实际这些包是 **IPv6**（`86 dd`）。我的过滤器 `eth_type != 0x0800: continue` 直接全跳过。
3. **`snaplen` 设成 200 字节 + 解析器 `if i+5+rl > len(pl): break`** ——
   ServerHello 约 120 字节能装下，而 ClientHello 有 500+ 字节，被截断后**整个包被丢弃**。症状：ServerHello 24 个 / ClientHello 0 个。

**⇒ 通用教训（这是本项目第四次同类错误）：解析器本身就是被测对象的一部分。在用它下「不存在」的结论前，必须先证明它能看见一个已知存在的东西。** 本次是靠「payload 首字节分布」统计发现 `0x16` 里其实有 12 个 handshake 子类型 1（ClientHello），从而定位到解析器 bug —— 而不是继续相信「ClientHello = 0」。

**其他工具坑（本轮）**：
- `tcpdump ... &` 之后用裸 `wait` 会等它永不返回 ⇒ 脚本挂死。必须用定时 `sleep` + 显式 `kill`。
- `openssl s_client | grep 'Cipher is'` 在 TLS1.3 下常报 `Cipher is (NONE)` —— 是 s_client 在 ChangeCipherSpec 前就退出，**不是握手失败**。
- `openssl enc` 不支持 GCM（`-aes-128-gcm`），做单位对照必须换 CBC。
- 用 `-ciphersuites` 指定顺序去测「节点偏好」是**测错了对象** —— 那测的是我自己的偏好。

---

## 九、取证命令速查

```sh
# CPU 是否有 AES 指令
grep -m1 '^Features' /proc/cpuinfo | tr ' ' '\n' | grep -E '^(aes|pmull|sha1|sha2)$'

# 内核注册的 crypto 算法与驱动（generic = 软件）
grep '^driver' /proc/crypto | sort | uniq -c | sort -rn

# 设备树里有没有 crypto 引擎
ls /sys/firmware/devicetree/base/soc/ | grep -i crypto
tr '\0' '\n' < /sys/firmware/devicetree/base/soc/crypto@*/compatible

# 单核加解密吞吐（注意单位是 1000 B/s）
openssl speed -evp chacha20-poly1305 -seconds 3

# 抓真实协商结果（snaplen 必须够大，且 pppoe-wan 是 LINUX_SLL 且常为 IPv6）
tcpdump -i pppoe-wan -n -s 1500 -c 600 -w /tmp/hs.pcap 'tcp port 443'
```
