'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../package/luci-app-lan-arp-guard/htdocs/luci-static/resources/view/lan-arp-guard.js'), 'utf8');
let poller, declarations = [], nodes = [];
function E(tag, attrs, children) {
    const node = { tag, attrs, children, textContent: '' };
    nodes.push(node);
    return node;
}
class Map {
    section() { return { option() { return {}; } }; }
    render() { return Promise.resolve(E('form')); }
}
let active = true;
const env = {
    E, Promise,
    view: { extend: x => x },
    uci: { load: () => Promise.resolve() },
    form: { Map },
    poll: { add: fn => { poller = fn; } },
    rpc: { declare: declaration => {
        declarations.push(declaration);
        return () => Promise.resolve(declaration.method === 'status'
            ? { active, enabled: true, device: 'br-test', addresses: ['192.0.2.1'], packets: '11', bytes: '308', error: active ? '' : 'not_a_bridge' }
            : { log: '<img src=x onerror=alert(1)>' });
    } }
};
(async () => {
    const result = vm.runInNewContext('(function(){' + source + '\n})()', env);
    await result.load();
    await result.render();
    await poller();
    assert.deepEqual(declarations.map(x => x.method), ['status', 'events']);
    assert.ok(nodes.some(x => x.textContent.includes('11 包')));
    assert.ok(nodes.some(x => x.textContent === '<img src=x onerror=alert(1)>'));
    assert.ok(!source.includes('innerHTML'), 'logs must remain plain text');
    active = false;
    await poller();
    assert.ok(nodes.some(x => x.textContent.includes('接口不是可用的 Linux 网桥')));
    console.log('PASS: form/render, status/counter polling, apply errors, log text safety');
})().catch(error => { console.error(error); process.exitCode = 1; });
