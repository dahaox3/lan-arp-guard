include $(TOPDIR)/rules.mk

PKG_NAME:=lan-arp-guard
PKG_VERSION:=1.0.0
PKG_RELEASE:=1
PKG_LICENSE:=MIT
PKG_MAINTAINER:=dahaox3

include $(INCLUDE_DIR)/package.mk

define Package/lan-arp-guard
  SECTION:=net
  CATEGORY:=Network
  TITLE:=LAN gateway ARP protection
  PKGARCH:=all
  DEPENDS:=+nftables-json +kmod-nft-bridge +ubus +jsonfilter +jshn +flock +rpcd
endef

define Package/lan-arp-guard/description
  Block LAN bridge clients claiming the gateway IPv4 address.
  Kernel nftables filtering, no userspace daemon.
endef

define Build/Compile
endef

define Package/lan-arp-guard/conffiles
/etc/config/lan-arp-guard
endef

define Package/lan-arp-guard/install
	$(CP) ./files/* $(1)/
	chmod 0755 $(1)/etc/init.d/lan-arp-guard $(1)/etc/hotplug.d/iface/90-lan-arp-guard
	chmod 0755 $(1)/usr/sbin/lan-arp-guard $(1)/usr/libexec/rpcd/lan-arp-guard
endef

define Package/lan-arp-guard/postinst
#!/bin/sh
[ -n "$$IPKG_INSTROOT" ] || {
	/etc/init.d/rpcd reload
	/etc/init.d/lan-arp-guard enable
	/etc/init.d/lan-arp-guard reload || true
}
exit 0
endef

$(eval $(call BuildPackage,lan-arp-guard))
