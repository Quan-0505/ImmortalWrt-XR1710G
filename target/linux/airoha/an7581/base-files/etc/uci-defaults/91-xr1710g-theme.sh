#!/bin/sh
#
# XR1710G：默认 LuCI 主题 = footstrap（luci-theme-footstrap）。
#
# 为什么要有这个脚本：主题包自带的 uci-defaults（通常叫 30_luci-theme-*）只在
# luci.main.mediaurlbase 尚未设置时才写入，而镜像里的基础 luci 配置默认是
# /luci-static/bootstrap（或 argon），所以必须显式覆盖一次。
# 编号 91 保证排在主题包自身的脚本之后；脚本以 exit 0 结束，符合 uci-defaults
# 语义（成功后由 /lib/functions.sh 自动删除，不会每次启动都改配置）。

. /lib/functions/system.sh

case "$(board_name)" in
gemtek,xr1710g|gemtek,xr1710g-ubi) ;;
*) exit 0 ;;
esac

uci -q set luci.main.mediaurlbase='/luci-static/footstrap'
uci -q commit luci

exit 0
