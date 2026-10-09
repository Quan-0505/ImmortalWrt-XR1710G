# 仓库两项修复完成 + 三条此前结论的纠正（2026-10-09）

**提交**：`d4c72a3`（本地 master，**未推送** —— 当前领先 `origin/master` 共 23 个提交）
**改动**：`.github/workflows/build-firmware.yml`（+105/-1）、`PATCH/daed-pkg/daed/Makefile`（+20）
**仓库路径**：`C:\Users\quan\Desktop\NetProxy-optimized-config-share\404-OpenWrt\ImmortalWrt-XR1710G`
（★ 注意不是同目录下的 `ImmortalWrt\`，那是 `Quan-0505/immortalwrt` 主仓库的 fork）

---

## 一、修复 1：daed 缺 `tc` 依赖（坑2b）—— 已加 `DEPENDS:=+tc`

### 位置
`PATCH/daed-pkg/daed/Makefile` 的 `define Package/daed` 块内，新增一行：
```make
  DEPENDS:=+tc
```
说明性注释全部放在 `define` **之外**（更规范；不过实测 `define` 块内的 `#` 注释也是安全的 ——
同文件的 `Package/daed/install` 块里本来就有两行中文 `#` 注释，而该文件已成功构建出固件）。

### 为什么这个依赖是必要的（本轮新增取证）
之前只知道"缺 tc 会静默失败"，但**不知道是哪一代 daed 需要它**。这次用 `strings` 计数做了对比：

| 二进制 | `"tc qdisc"` | `"tc filter"` | `"required host tool"` | `netlink` | `strings` 总行数 |
|---|---|---|---|---|---|
| `/rom/usr/bin/daed`（v3.1.3，Go） | **1** | 0 | **1** | 19 | 67,293 |
| `/usr/bin/daed`（daed-kdae，Rust 重写） | **0** | 0 | **0** | **894** | 229,647 |

**⇒ 结论：**
- **v3.1.3 确实调用外部 `tc`**（qdisc/clsact 走 `tc`，filter 走 netlink）⇒ **仓库构建的正是 v3.1.3**（`PKG_VERSION:=3.1.3`，载荷取自 `rust-daed` release v3.1.3）⇒ **这个依赖必须加**。
- **daed-kdae 不调用 `tc`**（Rust/Aya BPF loader 直接装程序 + Go netlink 直接建 clsact/filter）。它的启动日志自证：
  ```json
  {"default_object_source":"rust-aya-loader","kernel_ebpf_program_rewrite":"true",
   "object_source":"rust-aya-loader","message":"Rust/Aya BPF loader ..."}
  {"map_count":"14","program_count":"6","message":"Loaded eBPF programs and maps"}
  ```
- **那个 `required host tool is missing` 报错只存在于 v3.1.3**（kdae 里计数为 0）—— 所以旧结论对 v3.1.3 成立，对 kdae 不成立。将来若把载荷换成 kdae，本依赖可以去掉。

### 为什么 `+tc` 解析到 `tc-tiny` 就够（权威依据）
ImmortalWrt master 的 `package/network/utils/iproute2/Makefile`：
```make
define Package/tc-tiny
  VARIANT:=tctiny
  DEFAULT_VARIANT:=1              ← +tc 会解析到它
  PROVIDES:=tc
  DEPENDS:=+kmod-sched-core
endef
define Package/tc-bpf
  VARIANT:=tcbpf
  PROVIDES:=tc
  DEPENDS:=+kmod-sched-core +libbpf
endef
ifeq ($(BUILD_VARIANT),tctiny)
  LIBBPF_FORCE:=off
endif
```
设备实测（`tc-tiny-6.18.0-r2`）：
```
tc filter add dev br-lan ingress bpf help
  eBPF use case:
    object-file FILE [ section CLS_NAME ] [ verbose ] [ direct-action ] [ skip_hw | skip_sw ]
    object-pinned FILE [ direct-action ] [ skip_hw | skip_sw ]
```
（`ldd /usr/libexec/tc-tiny` 无 libbpf/libelf；`LIBBPF_FORCE=off` 只影响是否强制依赖
libbpf **包**，并不裁剪 eBPF 代码路径 —— 以设备实测为准。）

**⇒ 真实能力测试**：`tc qdisc add dev lo clsact`（无报错、`show` 确认存在）；
`tc filter add dev lo ingress bpf object-pinned /nonexistent direct-action` 报的是
「`Couldn't retrieve pinned program ... No such file or directory`」而**不是**
「Unknown filter kind」—— 证明 eBPF 解析路径确实编进了二进制。

---

## 二、修复 2：自定义 feed 的包"装不回去"（坑4）—— 新增发布步骤

### 真实问题（与之前的说法不同）
```
设备 /etc/apk/repositories.d/distfeeds.list（原始 = .bak-preclean，8 行）:
  # This file is auto-generated...
  # Add your custom feeds to /etc/apk/repositories.d/customfeeds.list
  https://mirrors.vsean.net/openwrt/snapshots/targets/airoha/an7581/packages/packages.adb
  https://mirrors.vsean.net/openwrt/snapshots/packages/aarch64_cortex-a53/base/packages.adb
  https://mirrors.vsean.net/openwrt/snapshots/packages/aarch64_cortex-a53/luci/packages.adb
  https://mirrors.vsean.net/openwrt/snapshots/packages/aarch64_cortex-a53/packages/packages.adb
  https://mirrors.vsean.net/openwrt/snapshots/packages/aarch64_cortex-a53/routing/packages.adb
  https://mirrors.vsean.net/openwrt/snapshots/packages/aarch64_cortex-a53/telephony/packages.adb
```
**⇒ 那 7 个自定义 feed 从来不在这里。** 它们的包被**编译进镜像**（`feeds.conf.default` 从 GitHub 拉源码，
构建期可用），但运行时**没有任何仓库提供它们**：

```
luci-app-airoha-npu-2.0.0-r5   {feeds/app_airoha/feeds/app_airoha/luci-app-airoha-npu}  [installed]
luci-i18n-airoha-npu-zh-cn-... {feeds/app_airoha/...}                                   [installed]
luci-theme-glass-1.1.6-r1      {feeds/luci-theme-glass/feeds/luci-theme-glass}          [installed]
```

镜像可达性实测（**跟随重定向 `curl -L`**，索引文件名用 apk 的 `packages.adb`）：
```
官方 base/luci  → 302 → https://mirrors.pku.edu.cn/immortalwrt/... → 200, 117,505 bytes   ✅
app_airoha / pon_drivers / pon_userspace / easytier / glass /
openwrt_bandix / luci_app_bandix                          → 404, 597 bytes（错误页）   ❌ 7/7
```

**⇒ 后果：`luci-app-airoha-npu`（NPU 的 LuCI 界面）一旦损坏或被误删，无法重装；也无法升级。**

### 实现
`.github/workflows/build-firmware.yml` 新增步骤 `Publish custom feed packages`（位于
`Check build status` 与 `Upload artifacts` 之间，`if: always()`）：

1. 遍历 `bin/packages/aarch64_cortex-a53/<feed>/`，收集 8 个候选目录的 `*.apk`：
   `app_airoha pon_drivers pon_userspace easytier glass luci-theme-glass openwrt_bandix luci_app_bandix`
   **★ `glass` 与 `luci-theme-glass` 两个名字都收** —— 因为 `feeds.conf.default` 里 `glass` 用了
   `--directory=luci-theme-glass`，实际目录名是后者（已装包的来源路径证实）。
2. 尝试 `apk index -o packages.adb .`（优先 `staging_dir/host/bin/apk`，回退系统 `apk`）；
   **失败不中断**，退化为"直接装 .apk"。
3. 附 `README.txt`（安装方法、`--allow-untrusted` 的必要性、作为本地仓库的用法）。
4. 打包成 `dist/custom-feeds-aarch64_cortex-a53.tar.gz`。
5. 加入 Actions 产物路径 **与 release 的 `files:`**（原先 release 只放 `.itb`）。

### 验证（三层）
| 层次 | 方法 | 结果 |
|---|---|---|
| 语法 | 设备 BusyBox `sh -n`（**先做正/负向对照**：正常脚本 exit 0、故意写坏的 exit 2） | `exit=0` ✅ |
| 结构 | heredoc `EOF` 顶格且出现 1 次；`for/do/done` = 3/3/3；`if/fi` = 3/3 ✅ |
| 行为 | 在设备 `/tmp` 造假 `bin/packages`（放 2 个自定义 feed 包 + 1 个 `base/` 官方包）真跑一遍 | 2 个正确收集、**官方 feed 的包被正确排除**、`tar.gz` 正常生成 ✅ |

YAML 解析：`yaml.safe_load` 通过，job `build` 共 20 步，新步骤为第 17 步。

---

## 三、三条必须纠正的此前结论

### ❌ 纠正 1：「这 7 个 feed 在 distfeeds.list 里，导致 `apk update` 刷屏报错，需移除」
**错。** 它们**根本不在** `distfeeds.list` 里。
- 原始文件（`.bak-preclean`）实测 8 行，只有官方 6 条 + 2 行注释。
- 清理后也是 8 行，**逐字节相同**。
- `apk update` 输出全程干净：`OK: 10644 distinct packages available`。

**⇒ 设备上那个 `/etc/fs-fix-feeds.sh` 是个纯 no-op** —— 它的 `sed -i -e /app_airoha/d ...`
一行都没匹配到。它无害（幂等、不报错）、但也**什么都没修**。
**建议**：要么删除（连同 `/etc/uci-defaults/99-remove-dead-feeds` 与 `sysupgrade.conf` 里的登记），
要么改成对上面「修复 2」的说明。**未擅自改动**（涉及 3 处设备文件 + sysupgrade.conf）。

### ❌ 纠正 2：「用 `Packages.gz` 测 feed 可达性」
`Packages.gz` 是 **opkg** 时代的索引名；本机用 **apk**，索引名是 **`packages.adb`**。
我第一次就是拿 `Packages.gz` 去测的（返回 302，看不出真假）。
**⇒ 教训：测一个仓库是否可用，必须用它**当前包管理器**约定的索引文件名。**

### ❌ 纠正 3：「`define` 块内不能写 `#` 注释」
我把新注释从 `define` 内移到块外，理由是怕 `$(eval)` 处理不一致 —— **实测这个担心不成立**：
同文件 `Package/daed/install` 块内本来就有两行中文 `#` 注释，而该文件成功构建出固件多次。
放在块外只是**更规范**，不是因为块内会坏。

---

## 四、本轮的工具/方法教训（都是实际付过代价的）

1. **`C:\Users\quan\AppData\Local\Microsoft\WindowsApps\bash.exe` 是 WSL 启动器，本机未安装任何 WSL 发行版**
   ⇒ 本机**没有可用的 bash**。用它做 `bash -n` 会让**每一个**脚本都"失败"（实测 16/16 失败，
   含 `Checkout`、`Build Firmware` 等早已成功构建过的步骤）。
   **⇒ 替代方案：把脚本片段传到设备上用 BusyBox `sh -n` 检查。**

2. **★ 每次批量判定前必须先跑正/负向对照。**
   本轮两次靠它避免了错误结论：① 上面那个 bash；② `tc filter add help` 不含 eBPF 选项 ——
   若不做对照，会误判「tc-tiny 不支持 eBPF」。

3. **`tc filter add help` ≠ `tc filter add dev X ingress bpf help`。**
   前者只出通用用法，**不含各 filter kind 的选项**。查 eBPF 支持必须带 `bpf`。

4. **PowerShell 会把多行 `git commit -m` 拆成多个 pathspec 参数**（报一堆
   `pathspec 'xxx' did not match`）。**必须写进文件用 `git commit -F <file>`**，
   并用 `UTF8Encoding($false)` 写（无 BOM）+ LF 换行。

5. **经 SSH 传大块 base64 会撞命令行长度上限**（`The filename or extension is too long`）。
   51,200 字符一块传不过去。**只传需要验证的最小片段**（本轮改成只传改动的那一步，6,548 字符）。

6. **PowerShell 哈希表键大小写不敏感**（旧教训，本轮再次影响脚本设计）。

7. **`mirrors.vsean.net` 是活的重定向器**（根路径 200），302 跳到
   `mirrors.pku.edu.cn/immortalwrt/...`。**测可达性必须 `curl -L`**，否则 302 会被误读成异常。

---

## 五、仍未做 / 待用户决定

1. **推送这 23 个本地提交**（含本次 `d4c72a3`）—— 未做，属发布动作。
2. **`build-firmware.yml` 的 daed 解包循环仍缺 `os.chmod(p, m.mode)`**（约 L195-196）。
   已被 `Makefile` 的 `chmod 0755` 在 install 阶段兜住 ⇒ **降级为可选加固**，非缺陷。
3. **设备侧 `fs-fix-feeds.sh` 的清理**（见纠正 1）。
4. **`DEPENDS:=+tc` 的端到端验证需一次真实构建** —— 本地无法验证 OpenWrt 的依赖解析，
   只能等 CI。判据：构建产物 manifest 里出现 `tc-tiny`（或 `tc-bpf`/`tc-full`）。
5. **发布步骤的端到端验证需一次真实构建** —— 判据：release 里出现
   `custom-feeds-aarch64_cortex-a53.tar.gz`，且包内含 `luci-app-airoha-npu-*.apk`。

---

## 六、设备当前状态（本轮未改设备，仅只读 + 一次 `/tmp` 演练）

```
netdev_budget=300  dev_weight=64  dae0 GRO/GSO=off    （A/B 实验已全部回滚）
临时记录器 8 个全为 0；iperf3 已停；无监听端口残留
daed=1  kixdns=1  dnsmasq=2  crond=1   CPU 空闲 0.10 核
外网 204 ✓   DNS 142.251.214.110 ✓   代理出口 104.224.154.132 ✓
```
`/tmp` 里留了演练产物（`/tmp/pubtest`、`/tmp/step_pub.sh`、`/tmp/ok.sh`、`/tmp/bad.sh`、
`/tmp/wfsyn.b64`），**建议清理**（`/tmp` 是 tmpfs，占内存）。
