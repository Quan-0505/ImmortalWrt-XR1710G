# XR1710G 启用 kixdns —— 部署记录与实测

**日期**：2026-10-09
**需求**：用户给出 `kixdns.json`（源文件来自 OPNsense `192.168.3.1`），要求"参考这份文件，帮我用上"。

**状态**：✅ 已部署、已实测、已持久化。

---

## 一、结论速览

| 项目 | 结果 |
|---|---|
| kixdns 版本 | 0.2.0-r2（`/usr/bin/kixdns`，8,065,257 B） |
| 监听 | `0.0.0.0:5335`（UDP×4 worker + TCP） |
| 接入方式 | **作为 dnsmasq 的上游**（不是 nft hijack） |
| 服务管理 | procd 托管，`START=95`，respawn，开机自启 |
| 抗污染效果 | **`www.google.com` 从污染 IP `174.132.167.252` 变为真实 IP `142.251.157.119`** |
| 冷查询延迟 | 平均 461 ms（**瓶颈是上游电信 DNS 本身 506 ms**，kixdns 反而更快） |
| 热缓存延迟 | 4 ms |
| 自愈 | `kill -9` 后 **6 秒自动重启**（procd respawn） |

---

## 二、★ 配置来源：不是用户给的那份，而是 OPNsense 上**正在运行**的那份

用户提供的 `kixdns.json`（sha256 `85fe2cdb…723276`）与 OPNsense 上 `/tmp/kixdns-config.bak/kixdns.json` **SHA256 完全一致** ——
但那是 OPNsense 插件 UI 保存的**源配置**，**不是 kixdns 实际加载的文件**。

实际加载的是 `/usr/local/etc/kixdns/pipeline.json`（2951 B），由插件转换生成。diff 显示用户后来改过两处关键内容：

| 项 | 用户给的（UI 旧版） | OPNsense **实际生效**版 |
|---|---|---|
| 上游2 | `202.96.134.133:53` (udp) | `202.96.128.166:53` (udp) |
| 兜底上游 | `8.8.4.4 / 8.8.8.8 / 1.1.1.1 / 9.9.9.9` (tcp) | `https://dns.alidns.com/dns-query` + `https://doh.pub/dns-query` (**DoH**) |
| 规则2 `response_matchers` | `response_upstream_ip{cidr:四个境外DNS}` | `[]`（清空） |

**⇒ 采用 OPNsense 生效版**（把兜底从境外明文 DNS 换成国内 DoH —— 国内可直连、加密、不被投毒，是明显更好的设计）。

**唯一改动：`bind_udp`/`bind_tcp` 从 `0.0.0.0:53` → `0.0.0.0:5335`。**原因见下。

---

## 三、为什么端口是 5335（而不是 53 或 5353）

| 端口 | 冲突情况 |
|---|---|
| `53` | ❌ dnsmasq 占用（10 个 socket），kixdns 直接起不来 |
| `5353` | ❌ **umdns（mDNS）占用**。两者同绑 `0.0.0.0:5353`，内核按 SO_REUSEPORT 哈希分发 UDP 包 ⇒ DNS 查询有概率被 umdns 吃掉，表现为**随机超时**（实测解析三个域名全空，就是这个原因） |
| `5335` | ✅ 无冲突 |

**⇒ init 脚本的 hijack 会自动从 `pipeline.json` 的 `bind_udp` 读端口**（`jsonfilter ... '@.settings.bind_udp'` 后取 `##*:`），所以改端口不需要改脚本。

---

## 四、★ 接入方式：为什么用「dnsmasq 上游」而不是 nft hijack

init 脚本提供 `hijack` 开关，用 nft 把 LAN 侧 dport 53 重定向到 kixdns：

```sh
nft add table inet kixdns
chain dstnat { type nat hook prerouting priority -105;
  iifname "$lan_device" udp dport 53 counter redirect to :$udp_port
  iifname "$lan_device" tcp dport 53 counter redirect to :$tcp_port }
```

**没采用，理由**：dnsmasq 配置里有 `local='/lan/'`、`domain='lan'`、`expandhosts='1'` —— 它在做**本地域名解析**（`XR1710G.lan` 等）。
hijack 会让客户端绕过 dnsmasq，**丢失 `.lan` 本地解析能力**。

**采用的方案**：
```sh
uci set dhcp.@dnsmasq[0].server='127.0.0.1#5335'
uci set dhcp.@dnsmasq[0].noresolv='1'
uci set dhcp.@dnsmasq[0].strictorder='1'
```
⇒ 客户端无感，`.lan` 保留（实测 `192.168.5.1` 反解得 `XR1710G.lan` ✓），回滚只需删一条配置。

---

## 五、★★ 实测发现：DoH 兜底是**死代码**，规则2 从未执行

开启 `--debug` 观察 google.com 的完整决策链：

```
rule matched    rule="污染命中" phase=Request decision=Forward
decision made   detail=Forward { upstream: "udp://202.96.128.166:53,udp://202.96.128.86:53" }
upstream result upstream="202.96.128.86:53" outcome=Success rcode=No Error
rule evaluated  rule="污染命中" phase=Response matched=false     ← 污染检测没命中
request finished status=Completed

DoH 调用次数: 0        ← ★ 阿里/DNSPub DoH 一次没被调用
rule_1 出现次数: 0     ← ★ 规则2 从未执行
```

### 真实工作模式

```
所有查询 → 广东电信 DNS（202.96.128.86/166，双路并发取最快，UDP）
         → 污染检测（只匹配 127.0.0.0/8, 0.0.0.0/8, 169.254.0.0/16,
                      198.18.0.0/15, 224.0.0.0/4, 240.0.0.0/4 六个保留段）
         → 六段几乎永不命中 → on_miss: allow
```

**⇒ 即「电信 DNS + 缓存 + 多上游并发」。DoH 规则是**配了但永不执行的保险**。**

### 为什么结果还是对的

因为**广东电信官方 DNS 本身就返回真实 IP**：
```
dnsmasq 原来的上游     → www.google.com = 174.132.167.252   （污染）
202.96.128.86/166     → www.google.com = 142.251.157.119   （真实）
```
**⇒ 这才是这套配置「能用」的真正原因，不是兜底起了作用。**

### 保留的风险判断

那六个 CIDR 全是**结构性异常地址**（回环/无效/链路本地/保留/组播），而 **GFW 投毒返回的是真实境外 IP**（如 `174.132.167.252`，属 Softlayer）—— **一个都匹配不上**。
⇒ 若哪天电信 DNS 行为改变开始投毒，这份配置会**静默失效**，且兜底（规则2）因判据问题**永远不会接管**。

**修法（未实施，需决策）**：需 GeoIP 数据 + `response_answer_ip_geoip_country{country_codes:"CN"}`，
把 `on_miss` 从 `allow` 改为 `continue` ⇒ 非中国 IP 的应答交给 DoH 复核。
**代价**：大量正常境外站点（github/bing 等）也会走 DoH 复核，可能整体变慢。设备上 `/etc/kixdns/geoip.dat` **当前不存在**，
init 脚本有 `geoip_download_url` 选项可下载。

---

## 六、★ 实测延迟：瓶颈是上游，不是 kixdns

计时方法用 `/proc/uptime`（busybox 的 `date` **不支持 `%N`**，用它会得到恒为 0 的假数据 —— 本次先踩了一次）。

```
冷查询（15 个随机子域绕缓存）：
  110 / 90 / 90 / 100 / 1290 / 100 / 510 / 1360 / 100 / 100 / 100 / 1600 / 230 / 1070 / 70 ms
  ⇒ 平均 461 ms，最大 1600 ms，慢查询(>1s) 4/15

热缓存：4 ms

三方对比：
  直连电信 DNS 202.96.128.86 ：506 ms     ← ★ 上游本身就慢
  kixdns 经 dnsmasq          ：461 ms     ← 比直连上游还快 45ms
  阿里 DNS 223.5.5.5         ： 92 ms     ← 快 5 倍
```

**⇒ 可选优化（未实施，属网络策略选择）**：把 `223.5.5.5` / `119.29.29.29` 加进规则1 的 `actions`，
与电信 DNS **并列**（kixdns 并发查询取最快）。代价是 CDN 就近行为可能变化。

---

## 七、解析正确性实测（全部真实 IP）

```
www.google.com  → 142.251.157.119 / .152 / .155 / .154 / .150 / .151 / .156 / .153  + 8 个 IPv6   ✓
www.youtube.com → 142.251.157.4   / .152 / .153 / .155 / .150 / .154 / .156 / .151  + 8 个 IPv6   ✓
www.bing.com    → 23.37.92.147 … .143（9 个）                                                     ✓
github.com      → 20.27.177.113                                                                   ✓
twitter.com     → 162.159.140.229                                                                 ✓
www.baidu.com   → 183.2.172.177 + IPv6                                                            ✓
www.qq.com      → 121.14.77.221 / .201 + IPv6                                                     ✓
```

---

## 八、关于 `upstream call failed ... TCP response timeout` 警告（已定位，非缺陷）

```
upstream call failed, waiting for others  upstream=udp:202.96.128.86:53
  error=TCP response timeout from upstream 202.96.128.86:53 (remaining: 1199ms)
  elapsed_ns=2806604779        ← 2.81 秒
```

**两点看似矛盾，实为正常：**
1. 配的是 `transport: udp`，却报 TCP —— 因为 `enable_tcp_fallback: true`，**UDP 超时后自动用 TCP 重试**，两跳都超时才报此错。
   实测 kixdns 持有 **8 条 TCP 连接**到两个电信 DNS 的 53 端口（`tcp_pool_size: 128`）。
2. 2.81 秒 > `upstream_timeout_ms: 1200` —— 是 UDP + TCP 两段超时的累计。

**⇒ 且已停止增长**：日志时间戳集中在 `05:04:36 / 05:04:58 / 05:05:42`（正是测试期间查询随机不存在域名的时候），
15 秒增量实测为 **0**。上游直连测试两个都正常（返回 `121.14.77.221`）。

---

## 九、★ 单点故障与自愈

**实测：停掉 kixdns 的瞬间，全屋 DNS 完全瘫痪**（`www.qq.com`、`www.bing.com` 均返回空）。

**且不能简单加备用上游** —— dnsmasq 默认**并发查询所有 server 取最快**，加运营商 DNS 作备用等于每次都有一半概率拿到**污染结果**，前功尽弃。

**⇒ 正确做法：保持单一上游，依靠 procd respawn 自愈。**
```
实测 kill -9 kixdns → 第 6 秒自动重启（新 PID）→ 监听 5335 恢复 → 解析正常
procd 参数：respawn 3600 5 5，limits nofile=65536
```

---

## 十、持久化状态

### ★ 关键发现：`/etc/kixdns/pipeline.json` **不在任何 keep 规则里**

```
/lib/upgrade/keep.d/base-files  →  /etc/config/          ✅（所以 uci 改动自动保留）
/lib/upgrade/keep.d/kixdns      →  /etc/kixdns/stats.db  ❌ 只有这一个！
```
**⇒ 若不处理，重刷后 `pipeline.json` 会丢失并退回出厂示例。**

**已修**：把整个 `/etc/kixdns/` 目录加入 `/etc/sysupgrade.conf`（比只加单文件更好，未来加 `geoip.dat` 也自动带上）。

### 当前状态

```
/etc/sysupgrade.conf         14 项（新增 /etc/kixdns/）
/etc/config/kixdns           enabled=1, hijack=0, listener_label=default
/etc/config/dhcp             server=127.0.0.1#5335, noresolv=1, strictorder=1
/etc/kixdns/pipeline.json    2437 B  sha256 0455eee9e692f2fdee713375cd8a33c9899cfe7b3eb8e416c03559399ba33e00
/etc/kixdns/pipeline.json.bak-orig   571 B（固件自带的 5353 示例，保留）
/etc/config/dhcp.bak-before-kixdns   改前备份
/etc/sysupgrade.conf.bak-before-kixdns  改前备份
工作区副本：XR1710G/kixdns-1710.json（= 设备上生效的配置）
```

**逐项存在性验证**：14 项中 2 项 ⚠️（`/etc/uci-defaults/99-remove-dead-feeds`、`/etc/uci-defaults/98-fix-footstrap-header`）
—— 这两个是**一次性调用壳**，执行后被系统自动消耗，**属预期行为**，非缺陷（永久主体 `/etc/fs-fix-feeds.sh`、`/etc/fs-fix-nav.sh` 都在）。

---

## 十一、回滚方法

```sh
# 1. dnsmasq 恢复默认上游
cp -a /etc/config/dhcp.bak-before-kixdns /etc/config/dhcp
/etc/init.d/dnsmasq restart

# 2. 停用 kixdns
uci set kixdns.main.enabled='0'; uci commit kixdns
/etc/init.d/kixdns stop; /etc/init.d/kixdns disable

# 3. 恢复 sysupgrade.conf
cp -a /etc/sysupgrade.conf.bak-before-kixdns /etc/sysupgrade.conf
```

---

## 十二、kixdns 能力清单（从 LuCI 配置编辑器 `config_editor.html` 提取，权威）

**实测确认的完整 schema**（注意：`strings` + `grep -x` **不可用** —— Rust 二进制里短字符串不带分隔符粘连，
必须用 `grep -o`；本次先踩了这个坑，靠阳性对照才发现）：

```
matcher 类型：
  any, listener_label, client_ip{cidr}, domain_suffix{value}, domain_regex{value},
  qclass{value}, qtype{value}, edns_present{expect},
  geo_site{value}, geo_site_not{value}, geoip_country{country_codes}, geoip_private{expect},
  upstream_equals{value},
  request_domain_suffix{value}, request_domain_regex{value},
  response_type{value}, response_rcode{value}, response_qclass{value},
  response_edns_present{expect}, response_upstream_ip{cidr}, response_answer_ip{cidr},
  response_answer_ip_geoip_country{country_codes}, response_answer_ip_geoip_private{expect},
  response_request_domain_geosite{value}, response_request_domain_geosite_not{value},
  response_txt_content{mode,value}

action 类型：
  forward{upstream,transport,ecs_mode,ecs_prefix_v4,ecs_ip}, allow, continue, log,
  jump_to_pipeline, static_ip_response, static_txt_response, replace_txt_response, static_response

forward 的 upstream 支持协议前缀：
  tcp://  udp://  doh://  dot://  doq://  https://  tls://  quic://   以及逗号分隔多上游

ECS 注入：ecs_mode = clear | from_client_ip | static

其他已确认支持的 settings：
  min_ttl, bind_udp, bind_tcp, bind_doh, doh_path, doh_tls_cert, doh_tls_key, doh_pool_size,
  dot_pool_size, doq_pool_size, doq_enable_0rtt, doq_keepalive_interval_ms,
  default_upstream, upstream_timeout_ms, request_timeout_ms, response_jump_limit,
  udp_pool_size, tcp_pool_size, tcp_connection_max_age_seconds,
  tcp_connection_idle_timeout_seconds, tcp_health_check_error_threshold,
  cache_capacity, cache_max_ttl, dashmap_shards,
  cache_background_refresh, cache_refresh_threshold_percent, cache_refresh_min_ttl,
  flow_control_enabled, flow_control_initial_permits, flow_control_min_permits,
  flow_control_max_permits, flow_control_latency_threshold_ms, flow_control_adjustment_interval_secs,
  serve_stale, serve_stale_ttl, serve_stale_expire_ttl, serve_stale_ttl_reset, serve_stale_client_timeout_ms,
  enable_tcp_fallback, geoip_dat_path, geoip_db_path, geoip_auto_convert,
  geosite_enabled, geosite_data_paths, geoip_filter_countries, country_codes
```
**⇒ 支持 `geosite:cn` / `geoip:CN` 这种 call syntax（编辑器里有 `parseCallSyntax`）—— 具备做域名分类分流的能力，只是当前无数据文件。**

---

## 十三、工具经验（本轮踩到的，全部可复用）

| 坑 | 现象 | 正解 |
|---|---|---|
| ★ `grep -x` 测 Rust 二进制字符串 | 明明存在的 `bind_udp` 返回 0 命中 | 短字符串在二进制里**粘连**，必须用 `grep -o`。**先做阳性对照**再下否定结论 |
| ★ busybox `date` 无 `%N` | 延迟测量恒返回 `0 ms` | 用 `awk '{printf "%d",$1*1000}' /proc/uptime` 计时；**先自检计时器**（`sleep 1` 应得 ~1000ms） |
| busybox 无 `nl` | `nl: not found` | 用 `awk '{print NR"  "$0}'` |
| busybox `grep` 不支持 `{n,m}` | `bad regex ... Invalid contents of {}` | 用 `sed -n` 按行号取区间 |
| 5353 被 umdns 占用 | DNS 查询随机无响应 | 换 5335；或停 umdns |
| `strings` 判字段存在性 | 大批字段误报不存在 | 改用 LuCI 的 `config_editor.html`（135786 B，含完整 schema 与字段映射表） |
| Windows OpenSSH 转义 | 脚本被破坏 | 整段 base64：`echo <b64> \| base64 -d > /tmp/x.sh && sh /tmp/x.sh` |
| `nslookup` 不支持指定端口 | 无法直测 5353/5335 | 用 `socat UDP4-LISTEN:53,bind=127.0.0.2,fork UDP4:127.0.0.1:5335` 搭中继 |
| `/lib/upgrade/keep.d/` 覆盖不全 | 配置文件重刷后丢失 | **做任何设备侧改动前先查 keep.d 与 sysupgrade.conf 的实际覆盖面** |

---

## 十四、GeoIP 改造路径（**已验证可行，用户决定暂不实施**）

### 决策记录

用户选择「先不做，保持现状」。理由成立：当前解析正确、延迟正常，改造只对抗**尚未发生的**风险（电信 DNS 未来若开始投毒），
却会让 github/bing 等大量境外站点多走一次 DoH 复核。**已下载的 CN-only MMDB 存于 `XR1710G/kixdns-geoip-cn.mmdb`（226,640 B），随时可用，不必重下。**

### ★ 实测验证过的完整路径

```
① 下载 V2Ray geoip.dat（15.81 MB）
   https://cdn.jsdelivr.net/gh/Loyalsoldier/v2ray-rules-dat@release/geoip.dat
   实测从设备直连 HTTP=200，1.25s；raw.githubusercontent.com 也可达（HTTP=200，1.33s）
   —— ★ 后者在 PC 上曾是 DNS 解析失败，kixdns 修好污染后变为可达，属本次部署的附带收益
   头部魔数 `0a bc 29 0a 02 41 44`（protobuf，"AD" = 首个国家码）

② ★ kixdns 自带转换器（kixdns 读 MMDB，不读 V2Ray .dat）
   /usr/bin/kixdns convert-geo-ip -i geoip.dat -o out.mmdb [-f CN]
   全量：260 国 / 560,662 IPv4 段 + 498,841 IPv6 段 → 8,412,959 B (8.02 MB)
   CN-only：6,163 IPv4 段 + 3,446 IPv6 段 → 226,640 B (221 KB)   ← ★ 推荐用这个
   二进制佐证：含 "could not find MaxMind DB metadata in file"

③ 配置（三步，缺一不可）
   · 放文件：/etc/kixdns/geoip-cn.mmdb（221 KB）
   · pipeline.json 加： "geoip_db_path": "/etc/kixdns/geoip-cn.mmdb"
   · 换判据：
       { "type": "response_answer_ip_geoip_country", "country_codes": "CN", "operator": "and" }
       response_actions_on_match → allow       国内 IP，采用
       response_actions_on_miss  → continue    非中国 IP，交给 DoH 规则复核  ← ★ 关键
```

### ⚠️ 不要用 LuCI 的 `GeoIP 下载 URL` 输入框

```
它做的是：before each service start → curl 下载 15.81 MB 到 /etc/kixdns/geoip.dat
curl 参数：--connect-timeout 30 --max-time 300，不走代理，失败时 || true 不阻塞启动
```
三个问题：① 每次重启 kixdns 都重下 15.81 MB；② 失败时最坏拖 30 秒；③ 下的是 `.dat`，仍需转换。
**⇒ 手动放一次文件、URL 留空更好**；且 `/etc/kixdns/` 已在 sysupgrade.conf 内 ⇒ 重刷保留。

### LuCI 各项设置的建议（逐项实测依据）

| 设置 | 建议 | 依据 |
|---|---|---|
| 启用 | ✅ 开 | — |
| DNS 劫持 | ⛔ 关 | 与「dnsmasq 上游」方案二选一；开了客户端会绕过 dnsmasq 丢掉 `.lan` |
| 监听器标签 `default` | ✅ 保持 | `pipeline_select` 里写的就是它 |
| UDP 工作线程数（空=自动） | ✅ 保持空 | 自动 = CPU 核心数 4；DNS 负载极轻 |
| GeoIP 下载 URL | ⚠️ 留空 | 见上 |
| 配置文件下载 URL | ⛔ 留空 | 填了配置可被远程覆盖，LuCI 会多出「更新配置」按钮 |
| 日志过滤器 | ✅ 保持「查询日志（推荐）」 | 这就是 `overview.js` 里的 `o.default`，官方推荐值 |
| 调试日志 | ✅ 保持关 | 排查时临时开（`--debug`） |
| 日志大小限制 1024 KB | ✅ 保持 | 超限自动清空 |
| **TypeSafe API 密钥** | ⛔ **留空** | ★ **二进制里根本没有 `typesafe_api_key` 这个字段，init 脚本也不读** ⇒ UI 僵尸选项，填了不产生任何行为 |

### ★ LuCI 源码里的权威依据（`/www/luci-static/resources/view/kixdns/overview.js`，10808 B）

```javascript
// L211-297，全部 option 定义
form.Flag  : enabled, hijack, debug
form.Value : listener_label, udp_workers, geoip_download_url, config_download_url,
             rust_log, log_size, typesafe_api_key
form.Button: _update_config

// rust_log 的下拉预设（form.Value + o.value() = 可编辑下拉，不是纯文本！）
o.default = 'warn,kixdns::engine::matcher_adapter=info,kixdns::engine::phases=info';
o.value(o.default, 'Query logs (recommended)');   // ← 截图里的「查询日志（推荐）」
o.value('warn',  'Warnings and errors only');
o.value('error', 'Errors only');
o.value('info',  'Info');
o.value('debug', 'Debug');

// TypeSafe（只存在于 UI，后端无实现）
o = s.option(form.Value, 'typesafe_api_key', _('TypeSafe API key'), ...);
o.password = true; o.rmempty = true;   // ← rmempty ⇒ 留空时不写入 uci，故配置文件里看不到
```
**⇒ 教训：判断一个 UI 选项是否真实生效，要**三处交叉验证** —— uci 里有没有这个键、init 脚本读不读它、二进制认不认识它。
本次 `typesafe_api_key` 三处全无（仅 UI 有）⇒ 僵尸选项。若只看 UI 会误判为"可用功能"。
