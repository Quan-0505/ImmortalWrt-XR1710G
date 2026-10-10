# 上游同步与 CI 验证记录（2026-10-10）

## 已验证的构建

[Build Firmware #24](https://github.com/Quan-0505/ImmortalWrt-XR1710G/actions/runs/38057021110)
在 `diag/npu-symbol` 的 `e2b29fd2d4` 上成功完成。其固件配置为 `1710.config`，
只产出 OpenWrt U-Boot UBI 布局；不能据此宣称原厂布局已经通过。

正式同步分支中的 `df0b16605e` 保留了完全相同的两段验证修复，去除了临时
NPU 取证步骤及 `diag-npu.log` 上传路径。`diag` 分支不合入正式分支。

## 错误定位与阳性对照

旧 `find ... -path '*/linux-*/.config' -print -quit` 的候选有两个：
mac80211 backports 配置与 `linux-6.18.54/.config`。前者排在前面时，检测会错误
报告缺少内核符号。新模式限制 `-maxdepth 2`，本次记录中的候选数为 1。

`plugin-check.log` 明确打印实际检查路径为内核源码树的 `.config`，并打印
`CONFIG_DEBUG_INFO_BTF`、`CONFIG_BPF_SYSCALL`、`CONFIG_VETH`、
`CONFIG_NET_CLS_ACT`、`CONFIG_NET_CLS_BPF`、`CONFIG_NET_SCH_INGRESS` 均为 `y`。
两段验证步骤在 run#24 均实际执行并成功。完整内核 `.config` 未随 artifact 上传，
以上符号取证来自该次 CI 的实际 trace。

## 下载产物验证

- UBI 镜像 SHA256：`d7426d63bf224263bc75db4516bd83936797fd7bc94bc5a0e4dd66c19cf07cd3`。
- `sha256sums` 中已上传的 5 个文件全匹配。`profiles.json` 不在 artifact 上传列表。
- FIT 内 kernel、DTB、rootfs 的 CRC32/SHA1 共 6 项全部匹配。
- DTB 共 199 节点，compatible 为 `gemtek,xr1710g-ubi`；分区为 `bl2` 与 `ubi`。
- phy5 的 `realtek,patch-rtk-serdes` 阳性属性存在，`reset-before-id-read` 不存在。
- 四个 CPU 的 OPP 范围为 500MHz–1.3GHz；NPU 节点状态为 `okay`。
- manifest 共 357 包，含 `tc-tiny 6.18.0-r2`、`daed 3.1.3-r1`、kixdns、NPU 与 Wi-Fi 包。
- 自定义 feed 压缩包含 14 个非空 APK，包括 `luci-app-airoha-npu-2.0.0-r5.apk`。

`d4c72a3bc3` 的 `+tc` 依赖和 feed 发布修复已经是 master 与 sync 的祖先，
旧文档里的“未推送 / 未修复”属于历史状态，不能作为重复修改的依据。

## 正式发布要求

正式 master 上分别使用 `1710.config` 与 `1710-factory.config` 构建两种布局。
每次构建在发布前断言每个 ITB 在 `sha256sums` 中恰好有一条记录，并实算校验。
任一校验失败就停止发布；release tag 指向该次构建的确切 `github.sha`。
同日同提交的两次构建使用同一个 release，已存在资产不覆盖，只补缺失资产。
发布正文附带该次源提交的 first-parent 历史。
两布局构建可并行，独立发布 job 按日期与源提交串行，下载 artifact 后再次核对
镜像校验，避免同名 feed 资产并发上传的 422。协调两次派发时传入同一个
`build_date`（YYYYMMDD），避免跨午夜后生成不同的 tag。

本记录证明构建产物内容，不代替新内核的设备侧刷机、无线与长期稳定性测试。

## 本地静态验证范围

四个 config seed 的设备隔离检查通过；完整 tracked Python 树 27 个文件的
`py_compile` 通过。Ruff `F,E9` 剩余 10 项与 naoki66 上游完全一致，属于既有
通用脚本问题，没有为本次同步修改这些无关文件。
