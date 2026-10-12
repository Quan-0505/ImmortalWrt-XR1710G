#!/bin/sh
# footstrap 吸顶导航修复 —— 幂等，可重复执行
#
# 【装到哪】/etc/fs-fix-nav.sh，权限 755，并登记进 /etc/sysupgrade.conf
#
# 【为什么必须单独存在一个"永久主体"】
# /etc/uci-defaults/ 下的脚本**执行成功后会被系统自动删除**。因此如果只把
# 本逻辑放在 /etc/uci-defaults/ 里，重刷时它已不存在 → 备份机制"登记了但文件
# 不存在"→ 不会被备份 → 重刷后修复彻底丢失。这个坑真实发生过。
# 正确做法是两层：本文件为永久主体（永不删除、始终可备份），
# /etc/uci-defaults/98-fix-footstrap-header 只做一层调用壳。
#
# 【缺陷背景】
# footstrap 的 cascade.css（141KB）整个文件包在一个 CSS 层叠层内
# （第 12 行第 1 列即 @layer，末尾有配对的孤立 }，1057 对花括号平衡）。
# 按层叠层规则，层外规则永远优先于层内规则 —— 所以追加到文件末尾即可生效。
# ★ 但仅仅提高 z-index 无效 ★
# nav.fs-sidebar 与 main.fs-main 在 DOM 里是兄弟节点，然而只要有任一方的祖先
# 建立了独立的层叠上下文，两者的 z-index 就不在同一维度上比较，此时数值改成
# 9999 也无用。必须用 isolation:isolate 把二者拉回同一层叠上下文，z-index 才生效。
#
# 【失败过的做法，勿重试】
#   ① 给 `header` 加规则 —— 页面上根本没有 header 元素
#   ② 层外只加 nav.fs-sidebar{z-index:500} —— 无效
#   ③ 怀疑视图 status.js 注入 CSS —— 已排除，其中无 position:sticky、无 z-index
#
# 【验证方法】把页面往下滚足够深（浅滚时标题尚未与导航栏相遇，会误判为正常），
# 标题应被导航栏盖住而不是压在导航栏上面。
#
# 【回滚】cp /www/luci-static/footstrap/cascade.css.bak-preclean \
#            /www/luci-static/footstrap/cascade.css

CSS=/www/luci-static/footstrap/cascade.css
MARK=fs-fix-nav-overlap-v3

[ -f "$CSS" ] || exit 0
grep -q "$MARK" "$CSS" && exit 0

# 只在首次（尚无任何历史补丁标记）时留一份原始备份，避免覆盖真正的原版
grep -q 'fs-fix-sticky-header\|fs-fix-nav-overlap:' "$CSS" || cp "$CSS" "$CSS.bak-preclean" 2>/dev/null

{
  printf '\n/* %s: 让吸顶导航在层叠上无条件压住内容 */\n' "$MARK"
  printf '.fs-shell{isolation:isolate}\n'
  printf 'nav.fs-sidebar{position:sticky !important;top:0 !important;z-index:9999 !important;background:var(--fs-bar-bg) !important}\n'
} >> "$CSS"

# LuCI asset URLs use the package database mtime as their cache key.
# Change only the timestamp so cached pre-fix CSS is fetched again.
for xr_status in /lib/apk/db/installed /usr/lib/opkg/status; do
  [ -f "$xr_status" ] && touch "$xr_status"
done

exit 0
