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

define Package/daed
  SECTION:=net
  CATEGORY:=Network
  TITLE:=daed (DaedNext Rust-native) transparent proxy v3.1.3
  URL:=https://github.com/Quan-0505/rust-daed
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
