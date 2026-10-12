# Footstrap 中文包索引缓存导致构建校验失败

2026-10-13 检查 run #30（38264005592）的 plugin-check.log：NETKIT、BTF/BPF/veth/clsact 均通过，Go daed 2.2.4 APK 已生成，但 luci-i18n-footstrap-zh-cn APK 数量为 0。最终 .config 只有 footstrap 的 es/ru 翻译选项，缺少 zh-cn，说明中文包未进入元数据，并非编译翻译文件时报错。

工作流先安装 LuCI feed 并生成元数据，随后添加主题 po/zh_Hans；仅增加 po 文件不会改变主题 Makefile 的时间戳，已缓存的包信息未发现新增语言。修复在补入翻译后触碰主题 Makefile，刷新 LuCI feed 索引、断言新增中文包并重新安装主题链接、清除主题旧包索引。在 make defconfig 后立即检查中文包仍被选中，避免几小时构建后才发现配置被丢弃。

本地验证：工作流 YAML 可解析，修改步骤的 bash -n 通过，git diff --check 通过。实际包生成与镜像 manifest 仍由重新运行的 CI 验证；在此之前不刷写失败构建产物。
