"""Assert the installed firmware tree contains the pinned Go program and LuCI entry."""
import argparse
import hashlib
import json
import pathlib
import stat
import subprocess


def verify(root, rootfs=None):
    spec = json.loads((root / 'PATCH/daed-pkg/payload.json').read_text())
    if rootfs is None:
        hits = [p for p in (root / 'build_dir').glob('target-*/root-airoha')
                if (p / 'etc/openwrt_release').is_file()]
        if len(hits) != 1:
            raise ValueError(f'Expected one firmware root-airoha with openwrt_release; found {len(hits)}')
        rootfs = hits[0]
    control = rootfs / 'etc/openwrt_release'
    if not control.is_file() or not control.read_text().strip():
        raise ValueError('Firmware root positive control openwrt_release missing')
    binary = rootfs / 'usr/bin/daed'
    if hashlib.sha256(binary.read_bytes()).hexdigest() != spec['binary_sha256']:
        raise ValueError('Installed Go binary differs from verified release')
    for name in ['usr/bin/daed', 'etc/init.d/daed']:
        if not (rootfs / name).stat().st_mode & stat.S_IXUSR:
            raise ValueError(f'Installed file is not executable: {name}')
    for name in ['etc/init.d/daed', 'lib/upgrade/keep.d/daed']:
        if (rootfs / name).read_bytes() != (root / 'PATCH/daed-pkg/daed/files' / name).read_bytes():
            raise ValueError('Installed Go integration file differs: ' + name)
    seed = (root / '.config').read_text()
    if 'CONFIG_PACKAGE_luci-app-daed=y' in seed.splitlines():
        menu = json.loads((rootfs / 'usr/share/luci/menu.d/luci-app-daed.json').read_text())
        if menu['admin/services/daed']['action']['path'] != 'daed/open':
            raise ValueError('LuCI daed service action differs')
        view = rootfs / 'www/luci-static/resources/view/daed/open.js'
        # luci.mk may minify JS. Test the installed view's URL behavior instead
        # of comparing whitespace/comments against the source file.
        subprocess.run(['node', str(root / 'scripts/check-daed-launcher.cjs'), str(view)],
                       cwd=root, check=True)
        json.loads((rootfs / 'usr/share/rpcd/acl.d/luci-app-daed.json').read_text())
    if (rootfs / 'usr/share/daed/web').exists():
        raise ValueError('Unexpected legacy on-disk UI overlay')
    print(f'PASS: checked_file={control} positive_control=openwrt_release; rootfs={rootfs}; pinned Go binary SHA256, executable service, backup paths, selected LuCI menu/view/ACL, no legacy web overlay.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=pathlib.Path, default=pathlib.Path.cwd())
    parser.add_argument('--rootfs', type=pathlib.Path)
    args = parser.parse_args()
    verify(args.root.resolve(), args.rootfs)
