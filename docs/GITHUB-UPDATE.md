# XR1710G 固件修复 brief

> **核对时间**：2026-10-07 晚
> **核对方式**：逐项拉取 GitHub `master` 分支上的实际文件内容比对，非依据记忆或推断
> **一句话结论**：**缺陷 1 与缺陷 2 已在仓库中修复完毕，不要再动**；真正待处理的是 **`DEPENDS:=+tc`（缺陷 2b）** 与 **自定义 feed 发布（缺陷 4）**。

---

## 一、✅ 已修复 —— 请勿重复处理

### 1.1 DTB 的 CPU 配置（曾导致每次启动 4 次内核 oops）

**核对结果**（`target/linux/airoha/dts/an7581-xr1710g.dts`，446 行）：

```
&cpufreq {                                    ← L282
	reg = <0x0 0x1fa20000 0x0 0x2c0
	       0x0 0x1efbe000 0x0 0x800>;
	reg-names = "chip-scu", "mcucfg";
};                                            ← L286，已无 airoha,force-direct-pll

opp-1300000000 {                              ← L294，最高档就是 1300MHz
	opp-hz = /bits/ 64 <1300000000>;
```

- `airoha,force-direct-pll` → **已移除** ✅
- `opp-1350000000` / `opp-1400000000` → **已删除** ✅

**核对结果**（`.../base-files/etc/uci-defaults/11-xr1710g-cpufreq-defaults`）：

```
uci -q set cpufreq.cpufreq.maxfreq0='1300000'    ← 已从 1400000 改过来 ✅
```

**实测效果**：内核 oops 从 **4 次/启动 → 0 次**，负载 0.05~0.15，`scaling_available_frequencies`
最高 1300000。

---

### 1.2 daed 包的可执行位丢失

**核对结果**（`PATCH/daed-pkg/daed/Makefile`，51 行）：

```makefile
L34  define Package/daed/install
L35  	$(INSTALL_DIR) $(1)
L36  	$(CP) $(CURDIR)/prebuilt-data/. $(1)/
L37  	# $(CP) 只搬运、不保证可执行位：解包/artifact/打包任一环节丢掉都会静默继承到 apk。
L38  	# 设备上 /etc/init.d/daed 是 644 时 procd 直接 Permission denied，服务连实例都建不出来。
L39  	chmod 0755 $(1)/usr/bin/daed $(1)/etc/init.d/daed
L40  endef
```

**✅ 位置正确、手段正确** —— 在 install 阶段显式 chmod，能兜住上游任何环节的权限丢失。
**这比在解包处修更稳健**（见 §2.3 的可选加固说明）。

> **为什么设备上现在仍是 644**：当前运行的固件**构建于这个修复之前**。
> 设备侧已手工 `chmod 755` 止血（写在 `/overlay`，重启保留，但不抗重刷）。
> **重新构建并刷入新固件即自动生效，无需再改代码。**

---

## 二、❌ 待处理

### 2.1 【P0】daed 缺 `DEPENDS:=+tc` —— 数据面无法启动

**位置：`PATCH/daed-pkg/daed/Makefile` L17-22**（**注意：不是 `rust-daed` 仓库的
`repack-apk-v3.yml`** —— 固件构建时用的是本仓库的这份 Makefile，见 `build-firmware.yml`
L108-109 `rm -rf feeds/packages/net/daed` + `cp -rf PATCH/daed-pkg/daed feeds/packages/net/daed`）

```makefile
define Package/daed
	SECTION:=net
	CATEGORY:=Network
	TITLE:=daed (DaedNext Rust-native) transparent proxy v3.1.3
	URL:=https://github.com/Quan-0505/rust-daed
	DEPENDS:=+tc                     # ← 补这一行
endef
```

**现象**：daed 进程正常运行、WebUI 能打开、`/health` 返回 `{"healthCheck":1}`，但界面报

```
resident candidate preflight failed before current runtime teardown:
required host tool is missing
```

**根因**：daed 是静态 musl 二进制（不链接 iproute2），**但运行时靠外部 `tc` 命令挂载 eBPF**
（`tc qdisc add dev X clsact` + `tc filter add ... bpf object-file ...`）。包定义中没有声明该依赖，
设备上根本没装 `tc`。**报错信息完全没提 `tc`，排查代价极高。**

**设备实测**（安装 `tc` 前后）：

```
tc        MISSING     ← ★ 缺的就是它 ★
bpftool   MISSING
ip        /usr/bin/ip          ✓
nft       /usr/sbin/nft        ✓
/sys/kernel/btf/vmlinux  3,855,973 字节   ✓ BTF 完整
/sys/kernel/btf/{act_gact,act_mirred,act_skbedit,
                 cls_basic,cls_flow,cls_fw,cls_matchall,cls_u32}  ✓ tc 所需模块全在
bpffs on /sys/fs/bpf (rw)                  ✓ 已挂载
```

**内核侧一切就绪，唯独用户态缺 `tc`。**

> **实测 `tc-tiny` 就够用**（不必 `tc-full`）：它的 `tc filter add ... bpf help` 明确列出
> `eBPF use case: object-file FILE [ section CLS_NAME ] ... [ direct-action ]`，
> 正是 dae/daed 所需的全部能力。**因此 `+tc`（默认拉 `tc-tiny`）即可，能省不少空间。**

**验证成功的三个特征**（缺一不可）：

```sh
tc qdisc show dev br-lan          # 应出现: qdisc clsact ffff: parent ffff:fff1
ls /sys/fs/bpf/                   # 应出现: dae-native-runtime-<pid>-0
curl http://127.0.0.1:2023/health # 应返回: {"healthCheck":1}
```

**本机实测：三者全部出现，报错消失**，日志推进到
`resident datapath group tg selector failed for tcp4: no alive dialer`
—— **这证明数据面已挂载、流量已被接管**（那是节点未配置，与打包无关）。

---

### 2.2 【P1】7 个自定义 feed 从未发布，apk 索引全部 404

**现象**：设备上每次 `apk update` / `apk add` 都刷出一片警告：

```
ERROR: wget: exited with error 8
WARNING: updating and opening .../app_airoha/packages.adb: unexpected end of file
（easytier / glass / luci_app_bandix / openwrt_bandix / pon_drivers 同样各报一条）
```

**镜像上实际存在的 feed**（逐个探测）：

```
[OK  ] base  200:117505    packages 200:826128    luci 200:414343
[OK  ] routing 200:3839    telephony 200:111713
[OK  ] targets/airoha/an7581/packages  200:16000
────────────────────────────────────────────────────
[MISS] app_airoha / pon_drivers / pon_userspace
       easytier / glass / openwrt_bandix / luci_app_bandix  → 全部 404
```

**分界线极干净：标准的全在，自定义的全没** —— 不是网络故障，是**从未发布**。

**根因**：`build-firmware.yml` 里没有任何发布包索引的步骤：

```
L432  - name: Upload artifacts     # 只上传 bin/targets/airoha/an7581/*.itb 等固件产物
L448        bin/targets/airoha/an7581/feeds.buildinfo   # 这只是 feed 版本清单，不是包
L484        # release 里只放镜像；buildinfo 与 sha256sums 随 Actions 产物提供
```

**影响（不只是噪音）**：`luci-app-airoha-npu` 来自 `app_airoha` feed。该 feed 404 意味着
**这个包永远无法升级或重装**——设备上唯一能装的就是镜像里预装的那份。
**即使把它的权限缺陷修好并重新编译，产物也没有途径发布和安装。**

> 核实过：GitHub Release 里也确实只有 2 个 `.itb` 固件资产，零个包文件。

**建议（二选一）**：

- **补发布步骤**：CI 里把 `bin/packages/**/packages.adb` 及包文件上传到 `mirrors.vsean.net` 对应路径；
- **或清理无效 feed**：从 `/etc/apk/repositories.d/distfeeds.list` 移除（设备侧已实施，见 §三）。

---

### 2.3 【可选】Python 解包块补 chmod（防御性加固）

**位置**：`build-firmware.yml` 的 `Prepare daed payload` 步骤，L188-196。

```python
L187|  shutil.rmtree(dst, ignore_errors=True)          # 先整个删掉重建
L188|  for m in tf.getmembers():
L189|      if m.name.startswith('usr/') or m.name.startswith('etc/'):
L190|          p = os.path.join(dst, m.name)
L191|          if m.isdir():
L192|              os.makedirs(p, exist_ok=True)
L193|          elif m.isfile():
L194|              os.makedirs(os.path.dirname(p), exist_ok=True)
L195|              with open(p, 'wb') as f:                 # ← 默认权限 0666 & ~umask = 644
L196|                  f.write(tf.extractfile(m).read())
                  # 此处缺 os.chmod(p, m.mode)
```

**同文件内的对照实验**：L165-172 的 kixdns 解包块做同样的事，但它记得设权限：

```python
L170|  open(path, 'wb').write(blob)
L171|  os.chmod(path, 0o755)                            ✅
```

**这是权限丢失的源头**（`open(p,'wb')` → 644，且 L189 的 `startswith` 条件正好命中
`usr/bin/daed` 与 `etc/init.d/daed`，与实测权限一一对应）。

**⚠️ 但注意**：§1.2 的 Makefile `chmod 0755` **已经在 install 阶段兜住了这个问题**，
所以此项**不影响正确性**，属于纵深防御。若要修：

```python
            with open(p, 'wb') as f:
                f.write(tf.extractfile(m).read())
            os.chmod(p, m.mode)          # ← 保留 tar 中的原始模式
```

> 用 `m.mode` 而非写死 `0o755`，避免将来把 644 的配置文件误提权。

**另建议**把 L199-201 的"只打印不校验"升级为真正的失败门：

```python
for exe in ('usr/bin/daed', 'etc/init.d/daed'):
    fp = os.path.join(dst, exe)
    if not os.path.isfile(fp):
        raise SystemExit('daed payload is missing %s' % exe)
    if not os.access(fp, os.X_OK):
        raise SystemExit('%s lost its exec bit (mode=%o)' % (exe, os.stat(fp).st_mode & 0o777))
```

L394 的 `ls -lh ... prebuilt-data/usr/bin/daed ...` 同样只列文件不校验权限，可一并改造。

---

### 2.4 【P2】dropbear 绑定到陈旧地址

**现状**（设备实测）：`/etc/config/dropbear` 里 `option _direct '1'` + `option DirectInterface 'lan'`，
最终进程行为 `dropbear ... -l br-lan -p 22 -K 300 -T 3`。

**症状**：首次启动后 SSH 不通，但 `tcp22` 在设备内部确实在监听。

**原因**：`-l br-lan` 会在**启动那一刻**把接口名解析成具体 IP 并绑定。而 XR1710G 首启是两阶段的：

```
第 1 阶段：/bin/config_generate 生成默认配置 → LAN = 192.168.1.1
          → dropbear 绑定 192.168.1.1:22                    ✅
第 2 阶段：固件自己的 uci-defaults 落地最终配置 → LAN = 192.168.2.1 → 重启
          → 192.168.1.1 消失了
          → dropbear 仍死抱旧地址 → 在 192.168.2.1 上 connection refused  ❌
```

**临时修法**：`/etc/init.d/dropbear restart`（重新解析即恢复）。
**彻底修法**：让 dropbear 监听 `0.0.0.0`（去掉 `-l`），或在 LAN 配置变更后自动 reload。

> 影响面有限：只在首启那一刻出现，重启服务即恢复。

---

## 三、设备侧已完成的操作（供参考，请勿重复）

| 项目 | 内容 | 重启保留 | 抗重刷 |
|---|---|---|---|
| UBI 布局 | 从 `UBI 1.5` 重建为标准 **`UBI 2.0`**（439 MiB） | ✅ | ✅ |
| DTB | 已刷入修复版镜像（PLL 关闭 + OPP 上限 1300MHz） | ✅ | ✅ |
| 可执行位 | `chmod 755 /usr/bin/daed /etc/init.d/daed`<br>`chmod 755 /etc/init.d/airoha-npu /usr/libexec/airoha-ppe.awk` | ✅ | ❌ 重刷即失 |
| `tc` | `apk add tc`（装上 `tc-tiny`，已够用） | ✅ | ❌ 重刷即失 |
| daed | `enable` 自启，运行中，`:2023` 正常，数据面已挂载 | ✅ | ✅ |
| NPU | **保持 `disable`**（原因见下方警告） | ✅ | ✅ |
| feed 清理 | 移除 7 行 404；新增自愈脚本 + 登记 `sysupgrade.conf` | ✅ | ✅ |

### ⚠️ NPU 服务的定时炸弹

修好 `/etc/init.d/airoha-npu` 的可执行位后，**手动 `start` 它会导致命令挂起**（超过 3 分钟无返回）。

**这意味着：权限修好后，`/etc/rc.d/S89airoha-npu` 会在下次开机真的执行，可能导致开机卡死。**

> 原本"不可执行"反而是一种意外保护：脚本静默失败，开机不受影响。

**⇒ 在 NPU 服务的超时/阻塞问题查清之前，必须保持 `/etc/init.d/airoha-npu disable`。**

### 设备侧持久化的正确姿势（★ 曾经踩过坑，务必照做 ★）

**踩过的坑**：曾认为「把脚本路径写进 `/etc/sysupgrade.conf` 就会被保留」。

**这是错的。** `/etc/uci-defaults/` 下的脚本**执行成功后会被系统自动删除**（这是 uci-defaults 的标准机制）。
于是到 sysupgrade 时它已不存在，而备份机制**只备份实际存在的文件** —— 结果是既没被保留、
也没被恢复，修复静默丢失。实测确认：设备上 `/etc/uci-defaults/99-remove-dead-feeds` 当时确实已缺失。

**正确做法是两层 + 产物入册：**

| 层 | 文件 | 作用 | 会被删除吗 |
|---|---|---|---|
| 主体 | `/etc/fs-fix-feeds.sh`、`/etc/fs-fix-nav.sh` | 幂等的真正逻辑，作为**永久锚点** | ❌ 永不删除 |
| 调用壳 | `/etc/uci-defaults/99-remove-dead-feeds`、`98-fix-footstrap-header` | 首启时调用主体 | ✅ 执行后被系统消耗（正常） |
| 产物 | `/etc/apk/repositories.d/distfeeds.list` | 清理结果本身也入册，作为第二道保险 | — |

**⇒ 凡是用 uci-defaults 一次性脚本做的设备侧修改，产物本身也必须写进 `sysupgrade.conf`。**

当前 `/etc/sysupgrade.conf` 全量内容（7 项，都已验证实际存在）：

```
/etc/crontabs/
/etc/config/wireless
/etc/uci-defaults/99-remove-dead-feeds
/etc/uci-defaults/98-fix-footstrap-header
/etc/fs-fix-nav.sh
/etc/fs-fix-feeds.sh
/etc/apk/repositories.d/distfeeds.list
```

### feed 清理（设备侧）

原版 `distfeeds.list` 14 行，其中 6 行指向从未发布的 feed。清理后 8 行、0 残留。

**效果**：`apk update` 从满屏 `wget: exited with error 8` 变为完全干净，可装包数量 **10644 个一个不少**。
若上游修好 feed 发布，删掉主体脚本与调用壳即可恢复默认行为。

**已做端到端演练**（在 `/tmp` 副本上做，不碰线上文件）：原始 14 行 / 6 个死 feed → 执行后 8 行 / 0 残留。

### footstrap 吸顶导航重叠（设备侧，已修复）

**现象**：LuCI 页面下滚后，页面标题（如「Airoha SoC状态」）压在吸顶导航栏（logo `XR1710G`）上面。

> ⚠️ **极易误判**：滚动位置浅时标题尚未与导航栏相遇，页面看起来完全正常。
> 本轮就因此误判过一次「已修复」。**判断时必须往下滚足够深。**

**根因**：主题 `cascade.css`（141 KB）整个文件包在一个 CSS 层叠层内 —— 第 12 行第 1 列即 `@layer`，
末尾有配对的孤立 `}`。层外规则优先，所以追加到文件末尾即生效；**但仅提高 `z-index` 无效**：
`nav.fs-sidebar` 与 `main.fs-main` 虽为兄弟节点，只要任一方的祖先建立了独立层叠上下文，
两者的 `z-index` 就不在同一维度比较，此时改成 9999 也无用。

**生效修法**（追加到 `cascade.css` 末尾，层外）：

```css
.fs-shell{isolation:isolate}
nav.fs-sidebar{position:sticky !important;top:0 !important;z-index:9999 !important;background:var(--fs-bar-bg) !important}
```

`isolation:isolate` 把二者拉回同一层叠上下文后 `z-index` 才真正生效。

**失败过的做法（勿重试）**：① 给 `header` 加规则 —— 页面上根本没有 `header` 元素；
② 层外只加 `nav.fs-sidebar{z-index:500}` —— 无效；③ 怀疑视图 `status.js` 注入 CSS —— 已排除。

**回滚**：`cp /www/luci-static/footstrap/cascade.css.bak-preclean /www/luci-static/footstrap/cascade.css`

**持久化**：主体 `/etc/fs-fix-nav.sh` + 调用壳 `/etc/uci-defaults/98-fix-footstrap-header`，
源码见工作区同名文件。

### 3.5 lan2 万兆口链路抖动

> # 🛑 本节结论已被 2026-10-09 实机验证的结果取代 —— 阅读前必看
>
> **本节记录的是一条**走错的诊断路线**。它的最终结论「问题在链路对端设备，不在固件」是**错误的**。**
> 正确的根因与修复见 → **`XR1710G/RCA-lan2-10g-flapping.md`**（根因 / 修复 / 修复后零抖动，三级证据齐全）。
>
> **一句话真相**：根因是 `target/linux/airoha/dts/an7581-xr1710g.dts` 第 363 行的 `reset-before-id-read;`
> （**只**写在 lan2 的 `phy5` 上，是全设备 lan2/wan 唯一的配置差异）。
> **删掉 → 重编 → 重刷**，之后 lan2 在真 10G 下**零抖动、零物理层错误、TCP 零重传**。
>
> ⚠️ **仓库侧补充（2026-10-09）**：这一行在**两份 DTS**里都有 ——
> `an7581-xr1710g.dts` 第 **363** 行、`an7581-gemtek-xr1710g-ubi.dts` 第 **389** 行。
> 设备刷的是 **`-ubi` 镜像**（board `gemtek_xr1710g-ubi`），**只删 plain 那份等于没改** ——
> 实验镜像里该属性仍会原封不动，实验会"看起来做了改动"却测到原状态。
> 已在 `bcdc0b3` 里两份都删，发布为 release **`20261009-bcdc0b3e`**（两种布局各一份 `.itb`）；
> 产物 DTB 的比对（改前 `True` → 改后 `False`、`rtk-serdes` 保留）与**无需刷机**的重放方法
> 见 `RCA-lan2-10g-flapping.md` §修复。
>
> **★ 本节有三处会主动误导你的断言，已就地标注更正：**
> 1. 「`reset-before-id-read` 是**死属性**、内核根本不解析它」→ **错**。
>    真正实现它的补丁**不在 mainline、不在 `realtek.ko` 里**，所以拿这两个参照系去搜必然搜不到：
>    `target/linux/generic/hack-6.18/705-net-phy-reset-PHY-before-reading-its-ID-when-requested.patch`
>    （在 `drivers/net/mdio/fwnode_mdio.c` 中读该属性，用 `reset-assert-us`/`reset-deassert-us` 打出 400ms 复位脉冲）
> 2. 「问题在链路对端设备」→ **错**。对端的差异只是**速率上限**（有的铜口只有 2.5G），
>    那是另一件事，当时把「速率上不去」和「链路抖动」混为一谈了。
> 3. 「wan@10G 跑 15.8 GB 零抖动」→ 该「10G 档位」**存疑**：
>    同一台交换机的部分铜口实测**只宣称到 `2500baseT/Full`**，那次很可能跑在 2.5G。
>
> **★★ 教训（本项目已第三次栽在同一件事上）：把「我的搜索方法看不见」当成了「它不存在」。**
> 下否定结论前，必须先证明搜索方法能看见一个**已知存在**的东西。

**现象**：网线插 `lan2`（2.5G/5G/10G，外置 Realtek RTL8261BE PHY）时链路反复掉线，
下游 AP 及其后数十台设备间歇性断网，表象酷似「DHCP 故障」。
**换插 `lan3`（1G，SoC 内置交换机）后完全正常** —— 33 台设备 9 秒内集体上线，0 掉线。

#### ★ 决定性判据（这一条最难反驳，也是本次诊断的核心）

```sh
logread | grep -c 'netdev carrier lost with copper link up'
# → 0
logread | grep -c 'restarting RTK SerDes'
# → 0
```

补丁 744 的 SerDes 重试状态机有两条路径：

| 路径 | 含义 | 实测 |
|---|---|---|
| `netdev carrier lost with copper link up` → restart | **PHY 说铜口 up、MAC 侧丢 carrier** —— 这才是 SerDes/in-band 参数不匹配的症状 | **0 次** |
| `pulsed ... after copper AN` → recovered | **铜口自己重新协商** —— 真实物理链路重建 | 11 次 |

**⇒ 第一条路径从未触发 ⇒ PHY 始终如实报告铜缆真的断了，不是 SoC 误判。**

#### 完整证据链

| # | 事实 | 证据 |
|---|---|---|
| 1 | PHY 如实报告铜缆真断 | `carrier lost with copper link up` = **0** |
| 2 | 每次掉线都伴随真实的铜口重协商 | 11 次 pulse 全部带 `after copper AN` |
| 3 | 链路裕量在临界线上 | 协商速率每次不同：`5G → 2.5G → 2.5G → 2.5G → 10G`；10G 只撑了 96 秒 |
| 4 | 驱动/PHY/workaround 组合本身没问题 | **wan 口同款 PHY、同款驱动、同款 workaround，3 次脉冲后彻底稳定，此后 0 掉线** |
| 5 | 同一根线在 1G 下完全健康 | 插 lan3 后 33 台设备零掉线、47 台 ARP 可达 |
| 6 | 卖家的"稳定版"走另一条 PHY 初始化路径 | 其 DTB 里**没有** `realtek,patch-rtk-serdes` |

#### 与卖家固件的设备树对比（逐属性，用 FDT 解析器做的）

卖家固件：`immortalwrt-airoha-an7581-gemtek_xr1710g-ubi-squashfs-sysupgrade(9).itb`
→ `ImmortalWrt r39859-fd28cb248b`，**内核 6.18.35**，board `gemtek_xr1710g-ubi`，DTB 位于文件偏移 `0x56A000`（22,977 B）

```
设备实时 DTB（6.18.52）  /soc/switch@1fb58000/mdio/ethernet-phy@5   ← lan2 万兆 PHY
      compatible                = "ethernet-phy-ieee802.3-c45"
      reg                       = <0x5>
      reset-gpios / reset-*-us  / tx-polarity / rx-polarity   ← 两边一致
    ✅ realtek,patch-rtk-serdes  = <>          ← 有
    ✅ reset-before-id-read      = <>          ← 有
    ❌ realtek,sds-mode                        ← 不存在

卖家固件 DTB（6.18.35）  同一节点
      （前述属性全部一致）
    ❌ realtek,patch-rtk-serdes  ← ★ 完全没有 ★
    ❌ reset-before-id-read      ← ★ 完全没有 ★
    ❌ realtek,sds-mode
```

**⇒ 排除 phandle 编号变化、LED 节点改名、`interrupts` 尾部条目这些非实质差异后，
两份 DTB 真正影响功能的差异只有这两项。** 连 bootargs 都只差一个 `ubi.fm_autoconvert=1`。

#### 结论与失效条件（❌ 2026-10-09 已作废 —— 见本节顶部横幅）

**~~判断：问题在链路对端设备，不在路由器、不在线材、不在固件。~~**

**⇒ 该判断是错的。根因在**固件 DTS**（`reset-before-id-read;`），删除后已实机验证修复有效。**
**⇒ 当时那组「单变量对照」的漏洞在于：对端从交换机换成 PC 的同时，
协商速率也从 10G 掉到了 5G**（PC 那块 Realtek 是 **5GbE**）——
**所以它只证明了「5G 有余量」，不能为固件开脱。** 10G 才是暴露问题的档位。

> ⚠️ 本节更早的结论「物理层 —— 这根线只能跑 1G」同样已被推翻，勿采信。

**变量对照（同一台路由器、同一个 lan2 口、同一版固件 6.18.52、同一套 `realtek,patch-rtk-serdes`）：**

| 变量 | 抖动期 | 稳定期 |
|---|---|---|
| **线材** | 同一根 | **同一根** ← 用户确认只是把插头从交换机移到电脑 |
| **对端设备** | **下游交换机** | **PC（Realtek PCIe 5GbE）** |
| 协商速率 | 5G / 2.5G / 10G 都到过 | **稳定 5000Mbps** |
| 结果 | **8 次掉线、11 次脉冲** | **0 次掉线** |

**⇒ 稳定期实测数据（同一启动周期内）：**

- ICMP 混流 **70 MB**（含 60008 B 分片包 × 300，RTT `1.202/1.402/6.021 ms`，**0% 丢包**）
- **TCP 线速灌流 2.12 GB / 15 秒**（1.09 Gbps —— 受 `socat` 默认 8 KB 块限制**未压满链路**，不是链路上限）
- `rx_errors = 0`、`tx_errors = 0`，`rx_dropped`/`tx_dropped` **全程零增长**
- 协商速率**一次未变**；lan2 的 SerDes 脉冲**仅 1 次**，发生在插上线那一刻，2 秒后恢复

**⇒ 原判据依然成立且更强：**

```sh
logread | grep -c 'netdev carrier lost with copper link up'   # → 0
```

补丁 744 那条「PHY 说铜口 up、MAC 侧却丢 carrier」的异常路径**从未触发** ——
每次掉线都是**真实的铜口事件**，即对端真的把链路丢了。这一点在换了对端之后依然成立。

**⚠️ 仍未排除的混杂变量：**抖动期那台设备已运行很久，而稳定期是刚重启的。
**必须把交换机插回来、在同一启动周期内做 A/B，才能关闭「设备运行时长」这个缺口。**

**⚠️ 仍未验证的能力：lan2 的 10G 模式至今没有被验证过。**

| 候选对端 | 能力上限 | 能否测 10G |
|---|---|---|
| PC（`以太网 15`） | **Realtek PCIe 5GbE**，可选速率止于 5.0 Gbps | ❌ |
| wan 口的上联设备 | 只广告 10/100/1000/2500 | ❌ |
| **下游交换机** | **到过 10G** | ✅ **唯一候选** |

> **失效条件（falsifier）**：若把交换机插回 lan2（**同一根线、同一启动周期**）后**不再复现抖动**，
> 则「对端设备是元凶」这一判断错误，应转向固件侧做 `realtek,sds-mode` 与 `patch-rtk-serdes` 的 A/B（见下方第四档）。

#### ⚠️ 监测陷阱一：脉冲计数会把两个口混在一起（本项目真实误判过一次）

`grep -c 'pulsed RTK'` **同时匹配 lan2 与 wan** —— 两个口都是 RTL8261BE，日志前缀只差 PHY 地址：

| 端口 | 日志标识 |
|---|---|
| **lan2**（10G 电口） | `RTL8261BE 10Gbps PHY mt7530-0:05` |
| **wan**（10G 电口） | `RTL8261BE 10Gbps PHY mt7530-0:08` |

**必须按 `mt7530-0:0X` 分开过滤。** 本项目曾因此把 wan 的脉冲误记到 lan2 头上，
并据此得出「加压测试触发了负载相关病灶」的错误结论，实际 lan2 全程零 SerDes 事件。
`/etc/10g-monitor.sh` v2 已按端口分离计数。

#### ⚠️ 监测陷阱二：设备没有 RTC，墙钟时间戳不可信

XR1710G **无 RTC**，启动后靠 NTP 校时。**WAN 未通时时钟是错的** —— 实测出现过监测器心跳
从 `[12:34:24]` 直接跳到 `[21:32:08]`（WAN 改 DHCP 拿到网络后 NTP 才生效）。

**⇒ 判读日志一律用内核的 `[  1126.674669]` 这类开机秒数，不要用墙钟时间戳。**

#### ★ 2026-10-08 第二轮：wan 口跑通 10G + 两个新假设（**均未定论**）

**背景变更：** 1710 已改回**二级路由**（LAN `192.168.2.1`），**WAN 改 DHCP**，主路由为 **OPNsense（`192.168.5.1`）**。

**★ 新观测 1：wan 口（PHYAD 8）对同一台交换机跑到 `10000Mb/s` 且稳定**

```
ethtool wan:
  Link partner advertised: 1000baseT/Full 10000baseT/Full 2500baseT/Full 5000baseT/Full
  Speed: 10000Mb/s   Link detected: yes
```

- 交换机插到 wan 后：`Link is Down` → 一次 SerDes 脉冲 → `Link is Up - 10Gbps/Full`，**2 秒恢复**
- 持续 **9 分钟以上零掉线、零新脉冲**；`rx_errors=0 tx_errors=0 rx_crc_errors=0 collisions=0`
- 同时 lan2 对 PC 跑 5000Mbps，两口并存互不影响
- ⇒ **这是本设备 10G 模式第一次被证明能稳定工作**

**★ 新观测 2：那台交换机是 10G 交换机，且挂在 OPNsense 的 LAN 上**

- `ethtool` 读到对端广告 **1G / 2.5G / 5G / 10G**
- 交换机插 wan 后，wan **透过它**从 OPNsense 拿到租约：`udhcpc: lease of 192.168.5.197 obtained from 192.168.5.1`
- ⇒ ⚠️ **把该交换机接进 br-lan 会让 `192.168.2.0/24` 与 OPNsense 的 `192.168.5.0/24` 在二层合并、出现双 DHCP 服务器。实验前必须先处理，否则会搅乱全屋。**

**★ 设备树逐属性对比（本机固件 vs 卖家稳定版固件）**

| 属性 | 本机 phy@5 (lan2) | 本机 phy@8 (wan) | 卖家 phy@5 | 卖家 phy@8 |
|---|---|---|---|---|
| `reset-before-id-read` | **有** | 无 | 无 | 无 |
| `realtek,patch-rtk-serdes` | 有 | 有 | 无 | 无 |
| `realtek,sds-mode` | 无 | 无 | 无 | 无 |
| `reset-gpios` | GPIO **46** | GPIO **31** | GPIO 46 | GPIO 31 |
| `reset-assert-us` / `reset-deassert-us` | 200000 / 200000 | 同 | 同 | 同 |
| `rx-polarity` / `tx-polarity` | invert / invert | 同 | 同 | 同 |

⚠️ `reset-gpios` 的 phandle 数值不同（本机 `0x28` vs 卖家 `0x20`）**不是差异** —— 那只是 DTB 重编译导致的节点编号漂移，**GPIO 号完全相同**。曾误判过一次。

**⇒ 这两个属性构成本节最重要的差异。**
**★ `reset-before-id-read` 只写在 lan2 的 `phy5` 上 —— 这是全设备 lan2/wan 唯一的配置差异，
也正是根因（已实机验证）。**

**★ 假设 A（✅ 2026-10-09 恢复为有效结论 · 曾于 2026-10-08 被误判作废）：
`reset-before-id-read` 使 lan2 的 PHY 在探测时被硬复位，冲掉厂商 U-Boot 写入的 SDS 位**

- 支撑：补丁 622 原文明确点名 **LAN2 路径**与 U-Boot 写的 `SDS page 6 register 3 = 0x88c6`
- **★ 它确实被执行（这才是关键）**：
  `target/linux/generic/hack-6.18/705-net-phy-reset-PHY-before-reading-its-ID-when-requested.patch`
  （ImmortalWrt，Tianling Shen）在 `drivers/net/mdio/fwnode_mdio.c` 中：
  `if (!fwnode_property_read_bool(fwnode, "reset-before-id-read")) return 1;`，
  随后用 `reset-assert-us` / `reset-deassert-us`（本板各 200000us）打出 **400ms 复位脉冲**，
  再置 `phy->mdio.reset_state = 0` 抑制常规复位。
- 该动作的后果由补丁作者亲自写明：
  **743 号** —— 多一次复位会清掉固件写入的 SDS `6.0x0d` / `6.0x0e` / `6.0x1d` 位，
  PHY 随之锁上 Base-R，而 AN7581 收不到 USXGMII 对端字；
  **744 号** —— "The PHY can then report a completed copper link while the connected AN7581
  USXGMII PCS receives no partner word or carrier."
  ⇒ **这就是「抖动」的电气本质：铜口 up、MAC/PCS 侧没有 carrier。**
- **❌ 此前"作废"它的理由错得很有代表性：**
  那时在**主线** `phy_device.c` / `mdio_device.c` / `fwnode_mdio.c` / `of_mdio.c` / `phy-core.c`、
  v6.17/v6.18、主线 `airoha_eth.c` / `mt7530.c` / realtek PHY、本仓库**全部 184 个** airoha 补丁、
  以及设备实跑的 `realtek.ko` 里搜这个字符串，全都搜不到，于是判定「内核根本不解析它」。
  **但它根本不在这些地方 —— 它在 `target/linux/generic/hack-*` 里。**
- ★★ **教训：下"不存在"的结论前，必须先证明你的搜索方法能看见一个已知存在的东西。**
  当时若拿**确凿生效**的 `reset-gpios` / `reset-assert-us` 做阳性对照，就会发现自己同样扫不到 ——
  那样就不会得出"不存在"。**这已是本项目第三次栽在同一个坑里。**

**★ 假设 B：交换机侧的端口保护 / 环路检测在关端口**

- 支撑：`carrier lost with copper link up` = **0** ⇒ 每次掉线都是**真实铜口事件**，即对端主动把链路丢了；环路检测正是「周期探测 → 关端口 → 超时 → 重开」的行为，与「多次掉线且能自动恢复」「只有交换机当代价时才发作、PC 当代价时不发作」吻合
- ⚠️ **但「与速率无关」这条支撑已不可用** —— 见下方「监测陷阱补充」，该记录的正则本身是错的
- ⚠️ **且第三轮实测对其不利**：wan 挂同一台交换机跑 15.8 GB 零抖动（见第三轮）
  ⚠️ **2026-10-09 附注**：那次记录的"@10G"**存疑** —— 同一台交换机的部分铜口实测
  `Link partner advertised` **只到 `2500baseT/Full`**，所以那次很可能跑在 2.5G。
  **这不影响"该假设不成立"的结论**（真正根因已由 DTS 属性差异 + 实机验证独立锁定）。
- **失效条件**：若确认该交换机未启用任何环路 / 端口保护功能 ⇒ 假设 B 作废

**⇒ 决定性实验：把交换机接回 lan2，看是否在**同一启动周期**内复现抖动。**
**⇒ ⚠️ 实验前必须先解决二层合并问题（见「新观测 2」）；解法见第三轮「运行时脱桥」。**

**★ 监测陷阱补充：`grep -o '[0-9]*Gbps/Full'` 会吃掉小数点**

```sh
"2.5Gbps/Full"   →   该正则匹配出 "5Gbps/Full"      # 2.5G 与 5G 无法区分！
正确写法: grep -oE '[0-9]+(\.[0-9]+)?Gbps/Full'
```

⇒ 本项目曾据此记录过「交换机在 5G 上也掉过线」。**该记录的可靠性存疑**，不能再当作「速率无关」的证据。

**★ 运行时不改固件读写万兆 PHY 寄存器的通道：全部不存在（已逐一验证）**

| 通道 | 结果 |
|---|---|
| `phytool` / `mdio` / `mdio-read` / `mdio-write` / `mii-tool` | ✗ 不存在，apk 索引里也没有 |
| `ethtool -d lan2` | ✗ `Cannot get register dump: Not supported` |
| `/sys/kernel/debug/phy/` | ✗ 只有内部 PHY（`phy-1fae0000.*`），**无 RTL8261BE 节点** |
| `mdio-netlink` 内核支持 | ✗ `modules.builtin` 中只有 `mdio-bus` / `mdio_devres` / `fwnode_mdio` / `of_mdio` |
| `/sys/module/realtek/parameters/` | ✗ 不存在；`realtek,patch-rtk-serdes` 无任何运行时开关 |

⇒ **A/B 只能靠重新构建 + 重刷。**

**★ 顺带从 `realtek.ko` 里捞到的两条有用字符串（说明修复路子还在）**

```
SerDes link did not come up                    ← 驱动里有「SerDes 起不来」的失败路径（我们日志里从未出现）
rtl826x_phy_patch_sds_get / _set, sds_page, sds_reg, sds_retries
                                               ← ★ SDS 读写底层函数仍在，只是 realtek,sds-mode 入口被删
```

⇒ **将来恢复补丁 622 时，驱动的 SDS 读写机制无需重写，只需把属性解析与调用加回去。**

---

#### ★ 2026-10-08 第三轮：wan@10G **负载下**通过 + 两个口走**不同的 PCS**（推翻「wan 可作对照组」）

**★ 结论 1：`wan@10G` 在**负载下**通过 —— 15.1 GB，零错误、零链路事件**

用「**丢包也照样过链路**」的灌流法加压（包只要经过链路就算数 —— 防火墙是在**收包之后**才丢的）：

```
[PC 以太网6 → 路由器 wan]  UDP 1400B：11001676 包 / 14688.8 MB / 50s = 2350 Mbps
路由器 wan:  rx +15,844,136,856 字节  ⇒ 合计 15111.5 MB / 56s，平均 2264 Mbps
施压后:  speed=10000 carrier=1 up；rx_errors=0 tx_errors=0 rx_crc_errors=0
         down=2 up=3 pulse=3 carrier_lost=0   ← 与施压前逐字节相同，一次未动
         lan2 down=0 pulse=1（不受影响）
```

⇒ **这条 10G 通路（PHY + MAC + 这台交换机）在负载下是健康的。**
⚠️ 诚实说明：① 反方向 `socat -u OPEN:/dev/zero UDP-DATAGRAM:...,blocksize=1400` **只送出 1.4 MB**（它带 UDP 时几乎不推流），本次是**单向主导**测试；② ICMP 灌流（`ping -s 60000 -i 0`）**完全无效** —— 60 秒只发出 138 个包，大分片 ICMP 回不来、`-i 0` 也没进洪泛模式。

**★ 结论 2：wan 与 lan2 的 PCS 是**两套不同实例**，不可互作对照**

```
wan  (ethernet@2) → pcs@1fa08000   compatible = "airoha,an7581-pcs-pon"
lan2 (ethernet@4) → pcs@1fa09000   compatible = "airoha,an7581-pcs-eth"
     resets:  wan <0x21 0x34 0x21 0x0>   lan2 <0x21 0x6 0x21 0x7>
```

⇒ 驱动是同一个（`drivers/net/pcs/airoha/pcs-airoha.c`）的两份 match_data，但 **compatible 不同、reset 线不同**。
⇒ **此前「wan 是同型号 PHY / 同驱动 / 同 workaround，所以是一份免费对照组」的推论作废** —— 那只在 PHY 层成立，PCS/SerDes 层不同。

**★ 结论 3：假设 A 作废**（见上文修正块）；625/628/629 三个 PCS 补丁**确在运行固件内**：

```
设备固件构建提交 d0c702152b = 2026-10-07T03:26:07Z
625 (USXGMII 速率自适应)  最近改动 2026-09-27T16:34:19Z  ✅ 早于构建
628 (RX 校准 SDK 搜索)    最近改动 2026-09-27T16:44:57Z  ✅
629 (USXGMII TX FIR)      最近改动 2026-09-27T16:56:21Z  ✅
747 (RTL8261 USXGMII)     最近改动 2026-09-27T15:14:30Z  ✅
```
⇒ 假设「PCS 修复缺失」同样作废。

**★ 排查工具：运行时把某口从网桥摘出（不改 uci、不 reload、可一键还原）**

```sh
ip link set lan3 nomaster          # 摘出
ip link set lan3 master br-lan     # 还原
```

已在空闲的 lan3 上预演通过。**判据以 `ls /sys/class/net/br-lan/brif/` 为准**（`/sys/class/net/<口>/master` 在本内核上读不出来，不要用它判断）。
用途：**把挂在 OPNsense LAN 上的交换机接进 lan2 做实验时，先摘出 lan2，即可避免 `192.168.2.0/24` 与 `192.168.5.0/24` 二层合并、双 DHCP 打架** —— 摘出后 lan2 是无 IP 的孤立二层口，全屋设备网关仍是 OPNsense，不受影响。
若需给 lan2 一个 L3 存在以便加压：`ip addr add 192.168.5.250/24 dev lan2`（运行时）。**安全**：dnsmasq 的 `dhcp-range` 绑定 br-lan，不会因加地址而开始发租约。

**★ 至此的变量对比表**

| 组合 | 结果 |
|---|---|
| **wan** @10G + **同一台交换机** + 15.8 GB 负载 | ✅ 完全健康 |
| **lan2** @5G + **PC** + 2.12 GB 负载 | ✅ 完全健康 |
| **lan2** @10G + **同一台交换机** | ❌ 上次 8 次掉线 / 11 次脉冲（**本轮从未复现**） |

⇒ 唯一尚未被隔离的变量是**端口本身**。决定性实验：**把交换机从 wan 挪到 lan2，其余一切不变。**

---

#### 安全方案分档（严守「不断网、不危险」）

| 档 | 操作 | 风险 |
|---|---|---|
| 🟢 **一** | `ethtool -s lan2 autoneg on advertise 1000baseT/Full` —— 把 lan2 锁 1G | **零**。lan2 当前无链路，改它不影响运行中的网络；`ethtool` 是运行时设置，重启即失效 |
| 🟢 **二** | 拿一根 Cat6a 短跳线接**独立设备**到 lan2 测，主线继续留 lan3 | **零**。不动主线，全屋无感 |
| 🟡 **三** | 把主线从 lan3 移到 lan2 实测 | 需几十秒到几分钟断网，挑无人时段 |
| 🔴 **四** | 重新构建固件（见下） | **刷机操作，非必要不做** |

#### 第四档：重新构建时的三个候选（**本次均未执行**）

1. **恢复补丁 622 + DTS 补 `realtek,sds-mode = <0x88c6>`**
   上游原文：*"This is needed on the **Gemtek XR1710G LAN2 path**. Its **vendor U-Boot writes SDS page 6 register 3 to `0x88c6`**, while the common Linux initialization sequence currently leaves that board setting out."*
   **这是全场唯一一句明写「XR1710G LAN2 需要它」的寄存器级板级校准值。**
   ⚠️ **光加 DTS 无效** —— 驱动端 `#define RTL826X_SDS_HOST_MODE_PAGE 6 / REG 3` 与 `rtl826x_config_sds_mode()` 也一并被删，需同时恢复。
   **实测确认**：`strings /lib/modules/6.18.52/realtek.ko` 中既无 `realtek,sds-mode` 也无 `configured SDS mode`；`logread | grep -c 'configured SDS mode'` → **0**。
   该属性与补丁在 commit `45bd3239`（2026-09-28）被静默删除，**commit 正文无任何解释**。

2. **核对补丁 625（USXGMII 速率自适应）是否落地**
   原文：*"USXGMII uses in-band autonegotiation, so this code path is never reached on speed changes. **The RATE_UPDATE_MODE and FORCE_RATE_ADAPT_MODE registers remain configured for the previous speed.**"*
   ~~**这正是「5000M 降到 2500M」的机制。**~~

   ⚠️ **【2026-10-09 更正】这句话把两件不同的事混为一谈了。**
   实测「只跑到 2500Mb/s」的真因是：**对端交换机那个铜口物理上只支持 2.5GBASE-T** ——
   `ethtool lan2` 的 `Link partner advertised link modes` 里**根本没有** `10000baseT/Full`，
   也没有 `5000baseT/Full`。把同一根线换到该交换机一个支持 10G 的口上，lan2 **立刻**
   `Link is Up - 10Gbps/Full`。
   ⇒ **对端不宣称 10G 时协商到 2.5G 是正确行为，不是"自降故障"。**
   ⇒ **不要拿「观测到 2500M」当作补丁 625 生效的证据。**
   （补丁 625 仍是真实的潜在隐患，但**与本机观测到的 2500M 无关**。）

   **正确判据（先看对端，再怀疑固件）：**
   ```sh
   ethtool lan2 | sed -n '/Link partner advertised link modes/,/Link partner advertised auto/p'
   ```

3. **A/B：去掉 `realtek,patch-rtk-serdes`**
   **卖家那个稳定版就没有它 —— 这是唯一能在同一块板子上直接对标的参照物。**
   ⚠️ **无运行时开关**：`/sys/module/realtek/parameters/` 不存在、`ethtool --show-priv-flags` 不支持、
   debugfs 下无 rtk/sds/serdes 节点（`.ko` 里的 `sds_work_disabled` 等只是内部变量名）。**只能重新编译。**

#### ⚠️ 明确的「不要做」

**不要在固件补丁表之后再叠一次 DTE XS / PCS reset / TXPLL reset。**
补丁 743 作者用正-反-正三轮测试证明：表尾的第二次 reset 会清掉固件写入的 SDS `6.0x0d`/`6.0x0e`/`6.0x1d` 位，
导致「PHY 拿到 Base-R block lock 但 AN7581 收不到 USXGMII partner word」。**方向是反的。**

#### 上游参考（naoki66 线，本机血统已确认为该线）

| 补丁 | 作用 | 关键值 |
|---|---|---|
| 743 | 恢复板级 opt-in 的 RTK SerDes 调优 | 写 `SDS 7.0x10 = 0x80aa`、`SDS 6.0x12 = 0x5078` |
| 744 | 铜口 AN 之后重新应用上述值 | 中间脉冲 `0x8003` 保持 10~12 ms；宽限窗口 120 次 PCS 轮询 |
| 747 | RTL8261 USXGMII in-band 控制 | 配合 DTS 的 `managed = "in-band-status"` |
| 622 | **（已删）** 板级 SDS mode | **`SDS page 6 reg 3 = 0x88c6`** |
| 628 | RX 校准改用 SDK crossing search | IDAC 由 `0x580`（锁不住）改 `0x5a5`（命中 `0x9edf` 目标） |
| 629 | 可选 USXGMII TX-FIR 覆盖 | **钩子而已**，作者自述无元组通过可复现测试；本机 DTS 与仓库 DTS **均未设置** |

> 独立佐证：orangeyoo 社区版记录过同一硬件的 10G 实机数据 ——
> *"`wan` 协商 10Gbps Full，`lan1` 与测试 NAS 协商 5Gbps Full … 两端口最终 `rx/tx errors=0`；**无新增 Link Down**"*
> **⇒ 说明 10G 口不是天生必抖，属板级/单元级差异。**

#### 诊断工具（可复用）

```sh
# 1. 判据：是否 MAC 侧丢 carrier（0 = 物理层问题）
logread | grep -c 'carrier lost with copper link up'

# 2. 各口抖动统计
for p in lan2 lan3 lan4 wan; do
  printf '%s down=%s up=%s\n' "$p" \
    "$(logread | grep -c "$p: Link is Down")" \
    "$(logread | grep -c "$p: Link is Up")"
done

# 3. 协商速率变化（看是否每次不同 ⇒ 临界链路）
logread | grep 'Link is Up' | grep -o '[0-9]*Gbps/Full'

# 4. 各口实时状态
for p in lan2 lan3 lan4 wan; do
  printf '%s carrier=%s speed=%s operstate=%s\n' "$p" \
    "$(cat /sys/class/net/$p/carrier)" "$(cat /sys/class/net/$p/speed)" \
    "$(cat /sys/class/net/$p/operstate)"
done

# 5. 设备树里的 PHY 节点（重点看有无 sds-mode / patch-rtk-serdes）
ls /proc/device-tree/soc/switch@1fb58000/mdio/
for f in /proc/device-tree/soc/switch@1fb58000/mdio/ethernet-phy@5/*; do
  printf '%s = ' "$(basename $f)"; tr -d '\0' < "$f" | head -c 60; echo
done

# 6. 取回完整实时 DTB 做离线对比（只读）
base64 /sys/firmware/fdt
```

**两份 DTB 的离线对比**：用工作区里的 FDT 解析器脚本（`run_code` + TypeScript，见本轮会话），
可逐节点、逐属性 diff，自动排除 phandle 编号噪音。

---

## 四、验证方法（可重放）

```sh
# 内核稳定性：应为 0
dmesg | grep -c Internal

# CPU 频率上限：应为 1300000
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq

# DTB 里 PLL 属性应已消失
ls /proc/device-tree/cpufreq/ | grep -i pll

# daed 数据面：clsact qdisc + bpfs 运行时目录
tc qdisc show dev br-lan
ls /sys/fs/bpf/

# daed 健康
curl http://127.0.0.1:2023/health      # {"healthCheck":1}

# tc 是否可用
command -v tc && tc -V

# feed 是否干净：应无任何 warning
apk update
```

---

## 五、优先级

| 优先级 | 项目 | 位置 | 理由 |
|---|---|---|---|
| **P0** | **§2.1 缺 `DEPENDS:=+tc`** | `PATCH/daed-pkg/daed/Makefile` L17-22 | daed 数据面完全起不来，且报错不提 `tc`，排查成本极高 |
| **P1** | **§2.2 feed 从未发布** | `build-firmware.yml` | 堵死自定义包的升级/重装路径 |
| **P2** | §2.3 Python 解包 chmod | `build-firmware.yml` L195 | 已被 Makefile chmod 兜住，属纵深防御 |
| **P2** | §2.4 dropbear 绑定 | dropbear 配置 | 仅首启一次性 |
| — | ~~§3.5 lan2 抖动（`reset-before-id-read`）~~ | 两份 DTS（plain 363 行 / ubi 389 行） | ✅ **已修复 + 已实机验证**（`bcdc0b3` / release `20261009-bcdc0b3e`） |
| — | ~~§1.1 DTB~~ | — | ✅ **已完成** |
| — | ~~§1.2 Makefile chmod~~ | — | ✅ **已完成** |

> **两个待办缺陷（§2.1 / §2.2）都是"静默失败"型**：一个报错不说缺什么，一个连报错都没有。
> 建议 CI 里加两道断言一次性覆盖：
> - **依赖完整性**：`apk info -R daed` 输出中必须含 `tc`
> - **发布完整性**：构建后校验 `bin/packages/**/packages.adb` 确实被推送到了镜像

---

## 六、刷机备忘

- **恢复模式**：取卡针按住 `Reset` 直至指示灯跑马灯，浏览器访问 **`192.168.255.1`**
  （该页面自带 DHCP，会自动给电脑发地址；本机曾获得 `192.168.255.2`）
- **务必选 `UBI 2.0 - 439 MiB`**，且必须与镜像内嵌的 device tree 一致
- 该固件 LuCI 里自带 **`System → U-Boot Recovery`** 页面，以后进恢复模式无需再抠孔
- `-ubi` profile 的镜像（compat `gemtek,xr1710g-ubi`）**不能**用 UBI 2.0 选择器刷
- http-uboot 只写 `chainloader` 槽（0x00600000，≤1 MiB），**`vendor` 分区只读、原厂一级 bootloader 不受影响**，
  `bootcmd=run boot_ubi || http_recovery` —— UBI 启动失败会自动掉进 Web 恢复

## 七、当前设备状态

```
固件        ImmortalWrt SNAPSHOT，内核 6.18.52，REVISION 2026-10-8-035afe00fa-bcdc0b3e56
主机名      XR1710G        型号 Gemtek XR1710G（Airoha AN7581GT）
★ 角色      主路由
★ LAN       br-lan 192.168.5.1/24   （成员：lan2 lan3 lan4 phy0.0-ap0 phy0.1-ap0）
★ WAN       PPPoE 拨号 → pppoe-wan 100.64.x.x（运营商 CGNAT），默认路由 via 100.64.0.1
★ LAN 接线  全屋交换机接在 lan2，lan2 协商 10000Mb/s/Full
PC 侧       以太网6 = Mellanox 10G / 192.168.5.124（从本机 DHCP）
            以太网12 = 25G / 192.168.6.88     以太网15（旧 192.168.2.182）已离线
内核 oops   0              内存可用 1.52 GB / 1.86 GB
daed        PID 运行中，:2023 正常
            ⚠️ 节点库 daed.db 在 2026-10-09 重刷时被清空，需重新导入订阅（软件本身健康）
tc          已安装（tc-tiny 6.18.0-r2）—— ⚠️ 每次重刷后都会丢，需 `apk add tc`
LuCI 主题   footstrap，吸顶导航重叠缺陷已修复（见 3.4 节），重刷后自动重放**已验证**
lan2 万兆口 ★ 抖动已解决（根因 = reset-before-id-read，见 RCA-lan2-10g-flapping.md）
            ★ 修复版 = `bcdc0b3`，release `20261009-bcdc0b3e`（**两份** DTS 都删了该行：plain 363 / ubi 389）
            ★ 真 10G + 全屋真实流量下压测约 31 GB：零抖动、tx_errors=0、TCP Retr=0
10G 模式    ★ 已验证可稳定工作。但 10G **满速转发**受拓扑限制做不到（wan 上联只有 2.5G）
sysupgrade.conf  10 项（含新增的 /etc/daed/，防止再次丢节点库）
长时间监测  /etc/10g-monitor.sh 运行中，日志 /overlay/10g-test.log
```

> ## ⚠️ 地址警告（最重要的一条，先读这个）
>
> **这台设备的 LAN 地址在 `192.168.2.1` 与 `192.168.5.1` 之间来回改过三次。**
> **不要相信任何文档或记忆里的地址 —— 先同时 ping 两个地址，再决定连哪个。**
>
> 最后一次核实：**2026-10-09 08:17**（内核 uptime 1528s）——
> **角色 = 主路由，LAN = `192.168.5.1`，WAN = PPPoE 拨号。**
>
> **历史（已作废，勿再据此操作）**：曾一度为**二级路由**，LAN = `192.168.2.1`、
> WAN = DHCP 客户端（从 OPNsense 取得 `192.168.5.197/24`），主路由为 OPNsense `192.168.5.1`。
> 该拓扑已于 2026-10-09 被用户改回「1710 当主路由」。
>
> ⚠️ **重刷后必查两项**（都实际踩过）：
> ① **`tc` 会丢** → `apk add tc`（daed 挂载 eBPF 依赖它；缺了会报 "required host tool is missing"）；
> ② **`/etc/daed/` 若不在 `sysupgrade.conf` 里就会被清空** —— 节点库已因此丢过一次（现已加入，共 10 项）。
>
> ⚠️ **`/etc/uci-defaults/` 下的脚本执行成功后会被系统自动删除**，是常态，不要"修复"它。
> 持久化必须用**三层设计**：永久主体（放 `/etc/uci-defaults/` 之外）+ 一次性调用壳 + **目标文件本身也写进 `sysupgrade.conf`**。
