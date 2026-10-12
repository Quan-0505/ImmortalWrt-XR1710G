# 2026-10-12 构建验证失败与修复

run #27（UBI，38241676891）和 #28（plain，38241680875）在提交 fa92d882 上完成编译、上传产物后，均于 Verify plugin integration 阶段失败。plugin-check.log 的最后断言为 kernel is missing CONFIG_NETKIT=y，发布任务正确跳过。

根因一：工作流在目标内核片段追加 CONFIG_NETKIT=y，但两份种子保留 # CONFIG_KERNEL_NETKIT is not set。include/kernel-defaults.mk 会把顶层 CONFIG_KERNEL_* 映射追加到内核 .config.target，覆盖前面的目标片段。实际产物 .config 和两份日志均确认 NETKIT 被关闭。

修复：1710.config、1710-factory.config 都启用 CONFIG_KERNEL_NETKIT=y。保留构建后实际内核 CONFIG_NETKIT=y 断言；增加 defconfig 后立即检查，避免耗时编译后才发现冲突。

根因二：产物 .config 与 manifest 都缺少新加入的 luci-app-daed。其 Makefile 仅包含 luci.mk，没有 include/scan.mk 用于发现包的 call BuildPackage 扫描签名，导致 feeds 索引漏包；feeds install 对找不到包只警告且可退出0。

修复：加入 LuCI 包的标准扫描注释；feed 索引立即断言 Package: luci-app-daed，XR1710G 两份种子在 defconfig 后立即断言 CONFIG_PACKAGE_luci-app-daed=y。保留最终 manifest 和安装树验证。

本地验证：使用仓库实际 scripts/kconfig.pl 重放配置合并，两份旧种子都关闭 NETKIT、修复后的种子都启用；实际扫描正则对旧 Makefile 阴性、修复后阳性。Go procd 和 LuCI URL 行为检查通过。完整交叉编译与最终安装树需由修复后的 Actions 验证，旧失败产物不能作为已验收固件发布。

失败记录：
- https://github.com/Quan-0505/ImmortalWrt-XR1710G/actions/runs/38241676891
- https://github.com/Quan-0505/ImmortalWrt-XR1710G/actions/runs/38241680875
