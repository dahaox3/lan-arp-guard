#!/usr/bin/env python3
"""Reproducible OpenWrt 24.10 script-only IPKs; no cross compiler needed."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('lan-arp-guard', 'luci-app-lan-arp-guard')


def archive(files, epoch):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.GNU_FORMAT) as tar:
        dirs = {p.as_posix() for name in files for p in PurePosixPath(name).parents if str(p) != '.'}
        for name in sorted(dirs):
            item = tarfile.TarInfo('./' + name)
            item.type, item.mode, item.mtime = tarfile.DIRTYPE, 0o755, epoch
            tar.addfile(item)
        for name, (data, mode) in sorted(files.items()):
            assert not name.startswith('/') and '..' not in PurePosixPath(name).parts
            item = tarfile.TarInfo('./' + name)
            item.size, item.mode, item.mtime = len(data), mode, epoch
            tar.addfile(item, io.BytesIO(data))
    return gzip.compress(stream.getvalue(), compresslevel=9, mtime=epoch)


def package(name, epoch):
    directory = ROOT / 'package' / name
    makefile = (directory / 'Makefile').read_text(encoding='utf-8')
    version = re.search(r'^PKG_VERSION:=(.+)$', makefile, re.M)[1]
    version += '-r' + re.search(r'^PKG_RELEASE:=(.+)$', makefile, re.M)[1]
    backend = name == PACKAGES[0]
    trees = [(directory / 'files', '')] if backend else [(directory / 'root', ''), (directory / 'htdocs', 'www/')]
    files = {}
    for source, prefix in trees:
        for path in sorted(source.rglob('*')):
            if path.is_file():
                target = prefix + path.relative_to(source).as_posix()
                mode = 0o755 if target.startswith(('etc/init.d/', 'etc/hotplug.d/', 'usr/sbin/', 'usr/libexec/')) else 0o644
                files[target] = (path.read_bytes().replace(b'\r\n', b'\n'), mode)
    files[f'usr/share/licenses/{name}/LICENSE'] = ((ROOT / 'LICENSE').read_bytes().replace(b'\r\n', b'\n'), 0o644)
    dependencies = 'nftables-json, kmod-nft-bridge, ubus, jsonfilter, jshn, flock, rpcd' if backend else 'lan-arp-guard (>= 1.0.0), luci-base'
    description = 'Kernel LAN gateway ARP protection' if backend else 'LuCI interface for LAN gateway ARP protection'
    control = f'Package: {name}\nVersion: {version}\nArchitecture: all\nMaintainer: dahaox3\nSection: {"net" if backend else "luci"}\nPriority: optional\nLicense: MIT\nDepends: {dependencies}\nDescription: {description}\n'
    controls = {'control': (control.encode(), 0o644)}
    if backend:
        controls['conffiles'] = (b'/etc/config/lan-arp-guard\n', 0o644)
    post = '''#!/bin/sh
[ -n "$IPKG_INSTROOT" ] || {
 . /lib/functions.sh
 default_postinst "$0" "$@"
 /etc/init.d/rpcd reload
'''
    if backend:
        post += ' /etc/init.d/lan-arp-guard enable\n /etc/init.d/lan-arp-guard reload || true\n'
    post += '}\nexit 0\n'
    controls['postinst'] = (post.encode(), 0o755)
    controls['prerm'] = (b'#!/bin/sh\n[ -n "$IPKG_INSTROOT" ] || {\n . /lib/functions.sh\n default_prerm "$0" "$@"\n}\n', 0o755)
    blob = archive({'debian-binary': (b'2.0\n', 0o644), 'control.tar.gz': (archive(controls, epoch), 0o644), 'data.tar.gz': (archive(files, epoch), 0o644)}, epoch)
    path = ROOT / 'dist' / f'{name}_{version}_all.ipk'
    path.write_bytes(blob)
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-dirty', action='store_true')
    args = parser.parse_args()
    git = lambda *a: subprocess.check_output(['git', *a], cwd=ROOT, text=True).strip()
    dirty = bool(git('status', '--porcelain'))
    if dirty and not args.allow_dirty:
        parser.error('Commit source first (or use --allow-dirty for local development).')
    commit, epoch = git('rev-parse', 'HEAD'), int(git('show', '-s', '--format=%ct', 'HEAD'))
    (ROOT / 'dist').mkdir(exist_ok=True)
    paths = [package(name, epoch) for name in PACKAGES]
    sums = ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in paths)
    (ROOT / 'dist' / 'SHA256SUMS').write_text(sums, encoding='utf-8', newline='\n')
    (ROOT / 'dist' / 'BUILDINFO.json').write_text(json.dumps({'source_commit': commit, 'source_date_epoch': epoch, 'dirty': dirty, 'architecture': 'all', 'format': 'OpenWrt gzip/tar IPK', 'python': sys.version.split()[0], 'zlib': zlib.ZLIB_RUNTIME_VERSION, 'packages': [p.name for p in paths]}, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(sums, end='')


if __name__ == '__main__':
    main()
