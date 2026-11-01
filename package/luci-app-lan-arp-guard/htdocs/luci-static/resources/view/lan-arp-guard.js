'use strict';
'require view';
'require form';
'require rpc';
'require poll';
'require uci';

var status = rpc.declare({ object: 'lan-arp-guard', method: 'status', expect: {} });
var events = rpc.declare({ object: 'lan-arp-guard', method: 'events', expect: {} });

function describe(data) {
	var errors = {
		invalid_interface: '逻辑接口名称无效', interface_unavailable: '逻辑接口尚未就绪',
		not_a_bridge: '接口不是可用的 Linux 网桥', invalid_ipv4: '保护地址无效',
		too_many_addresses: '保护地址超过 32 个', no_ipv4: '接口尚无 IPv4 地址',
		validation_failed: '规则校验失败', apply_failed: '规则应用失败', remove_failed: '规则删除失败'
	};
	var text = data.active ? '保护规则已加载' : '保护规则未加载';
	if (!data.enabled) text += '；配置已停用';
	if (data.error) text += '；' + (errors[data.error] || '上次应用失败') + '，请查看系统日志';
	return text;
}

return view.extend({
	load: function() { return uci.load('lan-arp-guard'); },
	render: function() {
		var m = new form.Map('lan-arp-guard', 'LAN 网关保护',
			'拦截从 LAN 客户端进入、冒用网关 IPv4 地址的 ARP 报文。也可防范虚拟网卡地址冲突引发的错误声明；不判断设备是否恶意。');
		var s = m.section(form.NamedSection, 'main', 'guard', '设置');
		s.anonymous = true;
		var o = s.option(form.Flag, 'enabled', '启用保护');
		o.rmempty = false;
		o = s.option(form.Value, 'interface', 'LAN 逻辑接口');
		o.datatype = 'uciname'; o.rmempty = false; o.placeholder = 'lan';
		o.description = '填写 lan 等逻辑接口名；实际设备必须是网桥。不要填写 WAN。';
		o = s.option(form.DynamicList, 'protected_ip', '手动保护 IPv4 地址');
		o.datatype = 'ip4addr("nomask")';
		o.description = '通常留空，自动保护该网桥当前全部 IPv4 地址。手动列表最多 32 个地址。';
		o = s.option(form.Flag, 'logging', '记录拦截日志');
		o.rmempty = false;
		o.description = '每分钟最多 2 条、突发 2 条；所有被拦截报文仍计数。';
		var state = E('p', {}, '正在读取…');
		var counters = E('p');
		var logs = E('pre', { style: 'max-height:18em;overflow:auto;white-space:pre-wrap' });
		return m.render().then(function(formNode) {
			var node = E('div', {}, [formNode,
				E('h3', {}, '运行状态'), state, counters,
				E('p', {}, '计数自最近一次规则加载起累计，重载或重启会清零。自动每 10 秒刷新；没有记录不代表已经保护所有类型的 ARP 欺骗。'),
				E('h3', {}, '最近 20 条网关声明拦截记录'), logs]);
			poll.add(function() {
				return Promise.all([status(), events()]).then(function(results) {
					var data = results[0];
					state.textContent = describe(data);
					counters.textContent = '网桥：' + (data.device || '—') + '；保护地址：' +
						(data.addresses || []).join('、') + '；拦截：' + (data.packets || '0') +
						' 包 / ' + (data.bytes || '0') + ' 字节';
					logs.textContent = results[1].log || '当前系统日志中没有记录。';
				}).catch(function() {
					state.textContent = '读取失败，请确认后端、rpcd 和登录状态正常。';
				});
			}, 10);
			return node;
		});
	}
});
