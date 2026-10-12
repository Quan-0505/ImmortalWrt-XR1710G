"""Fetch only the pinned public Go binary and geodata; never import device state."""
import argparse
import hashlib
import io
import json
import pathlib
import struct
import tarfile
import urllib.request


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
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive_file:
        payload = {}
        for name in required:
            hits = [m for m in archive_file.getmembers() if m.name == name and m.isfile()]
            if len(hits) != 1:
                raise ValueError(f'Expected one regular {name}, found {len(hits)}')
            payload[name] = archive_file.extractfile(hits[0]).read()
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
    if b'v2.2.4-kdae' not in binary:
        raise ValueError('Go release version marker missing')
    dst = root / 'feeds/packages/net/daed/prebuilt-data'
    if dst.exists() and any(p.is_file() for p in dst.rglob('*')):
        raise ValueError('Payload destination is not empty; refusing mixed Go/Rust files')
    for name, data in payload.items():
        p = dst / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        p.chmod(0o755 if name == 'usr/bin/daed' else 0o644)
    print('PASS: pinned archive and binary SHA256; static AArch64 ELF/PT_LOAD control; v2.2.4-kdae; only binary + public geodata extracted.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=pathlib.Path, default=pathlib.Path.cwd())
    parser.add_argument('--archive', type=pathlib.Path)
    args = parser.parse_args()
    prepare(args.root.resolve(), args.archive)
