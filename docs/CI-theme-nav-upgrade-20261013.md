# XR1710G 主题导航修复在升级后自动恢复

实机升级到 20261013-268c236a 后，滚动 Airoha SoC 状态页会让页面标题覆盖吸顶导航。设备仍保留永久主体 /etc/fs-fix-nav.sh，但之前执行成功的一次性 uci-defaults 调用壳已删除，升级恢复包无法备份不存在的文件。新主题 CSS 因而缺少修复。

将永久主体及 98-fix-footstrap-header 调用壳纳入板级 base-files，使每次新固件都能重新应用层叠隔离和吸顶导航样式。补丁标记升级为 v3；应用 CSS 后仅更新已安装包数据库的时间戳（不改变内容），同步 LuCI pkgs_update_time 资源缓存键，避免浏览器继续使用缓存的旧 CSS。脚本对同一标记幂等。

验证：两份脚本 bash -n 通过，git diff --check 通过。实机执行后，浏览器样式计算结果 isolation=isolate、导航 z-index=9999；滚动至标题顶部落在导航范围内时，elementFromPoint 命中导航元素，实际截图确认标题不再压住品牌。此修复已直接应用到运行设备；仓库源码修复将在下次构建进入 ROM。
