import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackageTest(unittest.TestCase):
    def test_archives_and_permissions(self):
        packages = sorted((ROOT / 'dist').glob('*.ipk'))
        self.assertEqual(len(packages), 2)
        for path in packages:
            with self.subTest(package=path.name), tarfile.open(path, 'r:gz') as outer:
                self.assertEqual({m.name.removeprefix('./') for m in outer if m.isfile()}, {'debian-binary', 'control.tar.gz', 'data.tar.gz'})
                self.assertEqual(outer.extractfile('./debian-binary').read(), b'2.0\n')
                with tarfile.open(fileobj=io.BytesIO(outer.extractfile('./control.tar.gz').read()), mode='r:gz') as control:
                    text = control.extractfile('./control').read().decode()
                    self.assertIn('Architecture: all\n', text)
                    self.assertIn('Version: 1.0.0-r1\n', text)
                    if path.name.startswith('lan-arp-guard_'):
                        self.assertIn('kmod-nft-bridge', text)
                        self.assertEqual(control.extractfile('./conffiles').read(), b'/etc/config/lan-arp-guard\n')
                with tarfile.open(fileobj=io.BytesIO(outer.extractfile('./data.tar.gz').read()), mode='r:gz') as data:
                    for member in data:
                        self.assertNotIn('..', PurePosixPath(member.name).parts)
                        self.assertFalse(member.name.startswith('/'))
                        self.assertEqual((member.uid, member.gid), (0, 0))
                        if member.isfile():
                            content = data.extractfile(member).read()
                            self.assertNotIn(b'\r\n', content)
                            target = member.name.removeprefix('./')
                            if target.startswith(('etc/init.d/', 'etc/hotplug.d/', 'usr/sbin/', 'usr/libexec/')):
                                self.assertEqual(member.mode, 0o755)
                            if target.endswith('.json'):
                                json.loads(content)

    def test_read_only_rpc_acl(self):
        path = ROOT / 'package/luci-app-lan-arp-guard/root/usr/share/rpcd/acl.d/luci-app-lan-arp-guard.json'
        acl = json.loads(path.read_text())['luci-app-lan-arp-guard']
        self.assertEqual(acl['write'], {'uci': ['lan-arp-guard']})
        self.assertEqual(acl['read']['ubus'], {'lan-arp-guard': ['status', 'events']})

    def test_no_private_config_defaults(self):
        config = (ROOT / 'package/lan-arp-guard/files/etc/config/lan-arp-guard').read_text()
        self.assertNotIn('192.168.', config)
        self.assertNotIn('mac', config.lower())
        self.assertIn("option interface 'lan'", config)


if __name__ == '__main__':
    unittest.main()
