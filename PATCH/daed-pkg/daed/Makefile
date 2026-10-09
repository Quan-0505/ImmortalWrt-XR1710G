# daed (DaedNext, Rust-native) v3.1.3 - prebuilt package for this fork.
# Payload (usr/, etc/) is unpacked at build time by the firmware workflow from
# the rust-daed release .apk (Quan-0505/rust-daed, tag v3.1.3) into
# prebuilt-data/. No compilation happens here.

include $(TOPDIR)/rules.mk

PKG_NAME:=daed
PKG_VERSION:=3.1.3
PKG_RELEASE:=1

PKG_LICENSE:=AGPL-3.0-only
PKG_MAINTAINER:=Quan-0505

include $(INCLUDE_DIR)/package.mk

# --- 为什么必须有 DEPENDS:=+tc (v3.1.3 的静默失败根因) ---------------------
# v3.1.3 是 Go 实现：eBPF 的 qdisc(clsact) 靠【外部 tc 命令】挂载，只有 filter
# 部分走 netlink。设备上缺 tc 时，它的报错是
#     resident candidate preflight failed before current runtime teardown:
#     required host tool is missing
# —— 完全没提要装什么，是典型静默失败，请勿删除本依赖。
#
# 取证 (strings 计数)：/rom/usr/bin/daed (v3.1.3) 含 "tc qdisc" 1 处、
# "required host tool" 1 处；而 Rust 重写版 daed-kdae 两者皆为 0
# (它用 Rust/Aya loader + Go netlink，全程不 exec tc)。故本依赖只对
# v3.1.3 必要 —— 将来若把载荷换成 kdae，可以去掉。
#
# tc 是虚拟包，由 iproute2 提供三个变体 tc-tiny / tc-bpf / tc-full。
# tc-tiny 带 DEFAULT_VARIANT:=1，故 +tc 解析为 tc-tiny，实测够用：
# 它支持 `tc qdisc add dev X clsact`，以及
# `tc filter add ... bpf object-file FILE ... direct-action`。
# (iproute2 的 LIBBPF_FORCE=off 只影响是否强制依赖 libbpf 包，
#  并不裁剪 eBPF 代码路径 —— 设备上实测确证。)
# ---------------------------------------------------------------------------
define Package/daed
  SECTION:=net
  CATEGORY:=Network
  TITLE:=daed (DaedNext Rust-native) transparent proxy v3.1.3
  URL:=https://github.com/Quan-0505/rust-daed
  DEPENDS:=+tc
endef

define Package/daed/description
  Rust-native dae/daed product daemon (eBPF transparent proxy, embedded
  WebUI on :2023, sticky-ip build). Static musl binary; WebUI and geo
  data bundled. Requires a BTF-enabled kernel.
endef

define Package/daed/conffiles
/etc/config/daed
endef

define Package/daed/install
	$(INSTALL_DIR) $(1)
	$(CP) $(CURDIR)/prebuilt-data/. $(1)/
	# $(CP) 只搬运、不保证可执行位：解包/artifact/打包任一环节丢掉都会静默继承到 apk。
	# 设备上 /etc/init.d/daed 是 644 时 procd 直接 Permission denied，服务连实例都建不出来。
	chmod 0755 $(1)/usr/bin/daed $(1)/etc/init.d/daed
endef

# binary-only package: nothing to prepare, configure or compile
define Build/Prepare
endef
define Build/Configure
endef
define Build/Compile
endef

$(eval $(call BuildPackage,daed))
