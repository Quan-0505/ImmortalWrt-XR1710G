#!/bin/sh
. /lib/functions/system.sh

case "$(board_name)" in
gemtek,xr1710g|gemtek,xr1710g-ubi) ;;
*) exit 0 ;;
esac

[ -d /www/luci-static/vantage ] || exit 1
uci -q set luci.themes.Vantage='/luci-static/vantage' &&
uci -q set luci.main.mediaurlbase='/luci-static/vantage' &&
uci -q commit luci
