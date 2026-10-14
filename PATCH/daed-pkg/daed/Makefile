# Pinned Go daed-kdae v2.2.4 DNS reload hotfix, with the new console embedded in the binary.
include $(TOPDIR)/rules.mk

PKG_NAME:=daed
PKG_VERSION:=2.2.4
PKG_RELEASE:=2
PKG_LICENSE:=AGPL-3.0-only
PKG_MAINTAINER:=Quan-0505

include $(INCLUDE_DIR)/package.mk

# Preserve the exact, already-stripped Go release binary.
RSTRIP:=:

define Package/daed
  SECTION:=net
  CATEGORY:=Network
  TITLE:=daed Go KDAE network console
  URL:=https://github.com/Quan-0505/daed-kdae
  DEPENDS:=+tc +ip-full
endef

define Package/daed/description
  Static Go dae-wing/kdae daemon with embedded console, live logs,
  scheduled geodata updates and group editors. Requires BTF/TC eBPF.
endef

define Package/daed/conffiles
/etc/config/daed
endef

define Package/daed/install
	$(INSTALL_DIR) $(1)
	$(CP) $(CURDIR)/prebuilt-data/. $(1)/
	$(CP) $(CURDIR)/files/. $(1)/
	chmod 0755 $(1)/usr/bin/daed $(1)/etc/init.d/daed $(1)/etc/uci-defaults/99-daed-go-enable
endef

define Build/Prepare
endef
define Build/Configure
endef
define Build/Compile
endef

$(eval $(call BuildPackage,daed))
