"""Fetch only the pinned public Go binary and geodata; never import device state."""
import argparse
import hashlib
import io
import json
import pathlib
import struct
import tarfile
import urllib.request


def _members(archive_file):
    """把 apk/ipk 统一成 {相对路径: 成员}。

    两种打包格式都要支持：
      * 旧 ipk 结构：外层 tar 里放 ./data.tar.gz，真正的文件在里层；
      * 新 apk(v3) 结构：外层 tar 成员直接是 .PKGINFO / usr/bin/daed 等，没有 data.tar.gz。
    """
    top = {m.name.lstrip('./'): m for m in archive_file.getmembers() if m.isfile()}
    inner = next((m for n, m in top.items() if n.endswith('data.tar.gz')), None)
    if inner is None:
        return archive_file, top
    with tarfile.open(fileobj=io.BytesIO(archive_file.extractfile(inner).read()), mode='r:gz') as nested:
        return nested, {m.name.lstrip('./'): m for m in nested.getmembers() if m.isfile()}


def prepare(root, archive=None):
    spec = json.loads((root / 'PATCH/daed-pkg/payload.json').read_text())
    url = f"https://github.com/{spec['repository']}/releases/download/{spec['tag']}/{spec['asset']}"
    if archive:
        raw = archive.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=600) as response:
            raw = response.read()
    if hashlib.sha256(raw).hexdigest() != spec['archive_sha256']:
        raise ValueError('Pinned public archive SHA256 mismatch')
    required = ('usr/bin/daed', 'usr/share/daed/geoip.dat', 'usr/share/daed/geosite.dat')
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:*') as archive_file:
        handle, members = _members(archive_file)
        payload = {}
        for name in required:
            hits = [m for n, m in members.items() if n == name]
            if len(hits) != 1:
                raise ValueError(f'Expected one regular {name}, found {len(hits)}')
            payload[name] = handle.extractfile(hits[0]).read()
    # Keep the public geodata archive, but pin the tested DNS handoff binary.
    if spec.get('binary_url'):
        with urllib.request.urlopen(spec['binary_url'], timeout=600) as response:
            payload['usr/bin/daed'] = response.read()
    binary = payload['usr/bin/daed']
    if hashlib.sha256(binary).hexdigest() != spec['binary_sha256']:
        raise ValueError('Go binary SHA256 mismatch')
    if binary[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', binary, 18)[0] != 183:
        raise ValueError('Expected little-endian ELF64 AArch64')
    phoff = struct.unpack_from('<Q', binary, 32)[0]
    entry_size, count = struct.unpack_from('<HH', binary, 54)
    types = [struct.unpack_from('<I', binary, phoff + i * entry_size)[0] for i in range(count)]
    if 1 not in types or 3 in types:
        raise ValueError('Expected static ELF with PT_LOAD and no PT_INTERP')
    if spec.get('binary_version', spec['tag']).encode() not in binary:
        raise ValueError('Go release version marker missing')
    dst = root / 'feeds/packages/net/daed/prebuilt-data'
    if dst.exists() and any(p.is_file() for p in dst.rglob('*')):
        raise ValueError('Payload destination is not empty; refusing mixed Go/Rust files')
    for name, data in payload.items():
        p = dst / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        p.chmod(0o755 if name == 'usr/bin/daed' else 0o644)
    print('PASS: pinned archive and binary SHA256; static AArch64 ELF/PT_LOAD control; version marker; only binary + public geodata extracted.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=pathlib.Path, default=pathlib.Path.cwd())
    parser.add_argument('--archive', type=pathlib.Path)
    args = parser.parse_args()
    prepare(args.root.resolve(), args.archive)
