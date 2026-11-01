#!/usr/bin/env python3
"""Privileged Linux packet test on a disposable bridge (no real LAN traffic)."""
import json
from pathlib import Path
import socket
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
TABLE = 'lag_test'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs).stdout


def count():
    data = json.loads(run('nft', '-j', 'list', 'counter', 'bridge', TABLE, 'blocked'))
    return next(x['counter']['packets'] for x in data['nftables'] if 'counter' in x)


def frame(sender_ip, source_mac=b'\x02\x00\x00\x00\x00\x22', opcode=2):
    # Ethernet broadcast, ARP sender claim, broadcast gratuitous target.
    eth = b'\xff' * 6 + source_mac + b'\x08\x06'
    arp = struct.pack('!HHBBH', 1, 0x0800, 6, 4, opcode)
    arp += source_mac + socket.inet_aton(sender_ip) + b'\x00' * 6 + socket.inet_aton('192.0.2.1')
    return eth + arp


def send(dev, payload):
    with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3)) as sock:
        sock.bind((dev, 0))
        sock.send(payload)
    time.sleep(0.12)


def main():
    try:
        run('ip', 'link', 'add', 'br-lagtest', 'type', 'bridge')
        run('ip', 'link', 'add', 'lag-port', 'type', 'veth', 'peer', 'name', 'lag-client')
        run('ip', 'link', 'set', 'lag-port', 'master', 'br-lagtest')
        for dev in ('br-lagtest', 'lag-port', 'lag-client'):
            run('ip', 'link', 'set', dev, 'up')
        time.sleep(0.4)
        helper = ROOT / 'package/lan-arp-guard/files/usr/sbin/lan-arp-guard'
        # Load the real renderer without its CLI. OpenWrt provides ash, jshn, functions.
        script = helper.read_text().split('# CLI entry point.')[0]
        script += '\nIPS="192.0.2.1 198.51.100.1"; DEVICE=br-lagtest; LOGGING=1; render_rules\n'
        rules = run('sh', input=script).replace('lan_arp_guard', TABLE)
        run('nft', '-c', '-f', '-', input=rules)
        run('nft', '-f', '-', input=rules)
        assert count() == 0
        send('lag-client', frame('192.0.2.1'))
        assert count() == 1, 'forged gateway reply was not blocked'
        send('lag-client', frame('192.0.2.1', opcode=1))
        assert count() == 2, 'forged gateway request was not blocked'
        send('lag-client', frame('198.51.100.1'))
        assert count() == 3, 'second protected address was not blocked'
        send('lag-client', frame('192.0.2.22'))
        assert count() == 3, 'ordinary client ARP was blocked'
        # Router-originated gateway ARP uses bridge output, not client ingress.
        send('br-lagtest', frame('192.0.2.1'))
        assert count() == 3, 'router gateway announcement was blocked'
        # Logging rate limit MUST NOT become a rate limit on dropping.
        for _ in range(8):
            send('lag-client', frame('192.0.2.1'))
        assert count() == 11, 'drop stopped after logging limit was exhausted'
        # Invalid atomic replacement must leave the old table and counter intact.
        bad = rules.replace('priority -300', 'priority invalid_priority')
        failed = subprocess.run(['nft', '-f', '-'], input=bad, text=True, capture_output=True)
        assert failed.returncode != 0
        assert count() == 11, 'invalid replacement removed working protection'
        # Successful reload is gap-free, starts a fresh counter, and remains effective.
        run('nft', '-f', '-', input=rules)
        assert count() == 0
        send('lag-client', frame('192.0.2.1'))
        assert count() == 1
        # Disabling logs still drops packets.
        rules = '\n'.join(x for x in rules.splitlines() if ' log prefix ' not in x) + '\n'
        run('nft', '-f', '-', input=rules)
        send('lag-client', frame('192.0.2.1'))
        assert count() == 1
        print('PASS: forged reply/request, alias, legitimate client/router ARP, log flood, atomic failure/reload, logging off')
    finally:
        subprocess.run(['nft', 'delete', 'table', 'bridge', TABLE], capture_output=True)
        subprocess.run(['ip', 'link', 'del', 'lag-client'], capture_output=True)
        subprocess.run(['ip', 'link', 'del', 'br-lagtest'], capture_output=True)


if __name__ == '__main__':
    main()
