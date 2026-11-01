# LAN 网关保护 / LAN ARP Guard

用于 OpenWrt / ImmortalWrt 24.10（fw4/nftables）的独立轻量插件。
在 LAN 网桥入口拦截客户端冒用网关 IPv4 地址的 ARP 报文，适用于误设虚拟网卡地址、地址冲突及部分网关 ARP 欺骗场景。

**不增加常驻守护进程**：内核处理报文，shell 只在启动、配置或接口变化时执行。
LuCI 页面打开时每 10 秒读取一次状态；页面关闭后无轮询。
不依赖 UA-Mask、UA3F 或校园网认证服务。

## 安装

从 [Releases](https://github.com/dahaox3/lan-arp-guard/releases) 下载两个 `*_all.ipk`，先核对 `SHA256SUMS`。

```sh
opkg update
opkg install /tmp/lan-arp-guard_1.0.0-r1_all.ipk
opkg install /tmp/luci-app-lan-arp-guard_1.0.0-r1_all.ipk
```

入口：**网络 → LAN 网关保护**。默认启用，读取逻辑接口 `lan` 的实际网桥和全部 IPv4 地址。
保存并应用后重新加载规则；网桥暂未就绪时保留原规则，在后续接口 ifup/ifupdate 时重试。
IPK 为脚本和前端文件，`Architecture: all`，可用于 A53；`kmod-nft-bridge` 必须由当前固件的匹配软件源安装。
不要强制安装其他内核版本的模块。

已经手工部署过同名 `/etc/init.d/lan-arp-guard` 的用户，应先备份它及旧 `.nft` 文件。
安装后由新服务接管同名 `bridge lan_arp_guard` 表；旧 `/etc/lan-arp-guard.nft` 不再读取。
不要让另一套自定义脚本同时管理这张表。

## 工作范围

- 丢弃从受保护网桥端口进入、ARP sender IPv4 属于保护地址集的报文；请求和回复都检查。
- 路由器自己发送的正常网关 ARP 不走该入口链，不按此规则丢弃。
- 普通客户端使用自身地址的 ARP 不受影响，不封禁整个设备。
- 可选限速日志：`LAN-GW-ARP`，每分钟 2 条、突发 2 条；超出日志额度仍拦截、计数。
- 显示内核拦截包数、字节数和系统环形日志中最近 20 条记录。
- 原子替换规则，校验或应用失败不会先清空已有保护。
- 仅管理自有 bridge 表，不重启网络、不修改 WAN MAC、DNS、Wi-Fi、代理或全局防火墙配置。

这不是完整的动态 ARP 检测系统，不做 DHCP snooping、全网 IP/MAC 绑定、IPv6 NDP/RA 防护，
也无法修复无线驱动或内存故障。客户端间报文若走硬件/无线快速通道，未经过 Linux bridge hook，
规则不保证能过滤那条路径；需要通过实际抓包/计数验证，不能仅凭界面“已加载”宣称所有路径受保护。
不适合未经调整就用于 VRRP、代理 ARP、存在合法备用网关或特殊桥接拓扑的网络。
配置中的手动地址是完整覆盖列表，留空才自动发现。

## 配置与命令

```uci
config guard 'main'
    option enabled '1'
    option interface 'lan'
    option logging '1'
    # list protected_ip '192.0.2.1'  # 可选，通常留空
```

```sh
/usr/sbin/lan-arp-guard status      # 只读 JSON；读取实际内核规则
/usr/sbin/lan-arp-guard events      # 只读 JSON；最近的限速日志
/usr/sbin/lan-arp-guard check       # 解析配置并 nft --check，不应用
/etc/init.d/lan-arp-guard reload
```

状态字段：`enabled` 表示 UCI 开关；`active` 表示内核表存在，二者不等价。
`error` 是上次应用的错误；失败时可能仍保留旧网桥/地址的规则，界面显示的是实际已加载对象。
计数是自**最近一次规则重载**起累计，重载/重启清零；不承诺永久计数。
日志使用现有 logd，不创建自己的持久日志文件；是否跨重启保存取决于系统日志配置。
外部执行 `nft flush ruleset` 会删除规则，需要手动重载服务；不添加无限循环监视器。

停用：在界面取消启用并保存应用。卸载：

```sh
opkg remove luci-app-lan-arp-guard lan-arp-guard
```

卸载只删除本插件的保护表；配置作为 conffile 按 opkg 规则保留。
若要恢复此前手工脚本，请在卸载后恢复备份并重新启动旧服务。

## 构建与验证

```sh
python3 scripts/build_ipk.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
node tests/test_view.js
# OpenWrt / ImmortalWrt 上（不修改现有网桥与防火墙）：
sh tests/test_guard.sh
```

CI 在 OpenWrt 24.10.6 rootfs 中测试 ash/jshn/jsonfilter，另用临时 bridge/veth 和原始 ARP 帧验证：
伪造请求/回复被丢弃、普通客户端及路由器自身 ARP 放行、日志限速不影响拦截、
无效事务保留旧规则、重载及关闭日志后的拦截行为。
报文测试只应在隔离且有 CAP_NET_ADMIN/CAP_NET_RAW 的测试环境执行。
两次构建校验可复现，产物包含源码提交和 SHA256；发布包不含实际设备名单、校园网账号或诊断日志。

也可把 `package/` 下两个目录加入 OpenWrt feeds/构建树，按对应 Makefile 编译。

设计参考：[nftables bridge filtering](https://wiki.nftables.org/wiki-nftables/index.php/Bridge_filtering)。
MIT License。
