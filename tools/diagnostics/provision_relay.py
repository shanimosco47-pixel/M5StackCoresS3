"""Prepare a private NVS patch; never flash or print credentials.

Requires a fresh 0x4000-byte NVS backup and the installed ESP-IDF parser.
Preserves every existing record except provider, appends two relay strings,
and checks all CRCs plus unchanged unrelated records before creating output.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
from urllib.parse import urlsplit
from zlib import crc32


def validate(partition):
    for page in partition.pages:
        if page.is_empty:
            continue
        if page.header['crc']['original'] != page.header['crc']['computed']:
            raise ValueError('invalid page CRC')
        for entry in page.entries:
            if entry.state != 'Written':
                continue
            crc = entry.metadata['crc']
            if crc['original'] != crc['computed']:
                raise ValueError('invalid entry CRC')
            if entry.children and crc['data_original'] != crc['data_computed']:
                raise ValueError('invalid data CRC')


def records(partition):
    result = {}
    for page in sorted(partition.pages, key=lambda p: p.header['page_index']):
        for entry in page.entries:
            if entry.state == 'Written':
                # Blob-data chunks and their index legitimately share a name.
                key = (entry.metadata['namespace'], entry.key, entry.raw[1], entry.raw[3])
                if key in result:
                    raise ValueError('ambiguous written entries')
                result[key] = bytes(entry.raw) + b''.join(bytes(c.raw) for c in entry.children)
    return result


def patch(data, url, token, parser):
    original = parser.NVS_Partition('private', bytearray(data))
    validate(original)
    namespaces = [entry.data['value'] for page in original.pages for entry in page.entries
                  if entry.state == 'Written' and entry.metadata['namespace'] == 0
                  and entry.key == 'stackchan_cfg']
    if len(namespaces) != 1:
        raise ValueError('missing or ambiguous settings namespace')
    namespace = namespaces[0]
    before = records(original)
    if any(key[0] == namespace and key[1] in ('relay_url', 'relay_token') for key in before):
        raise ValueError('relay settings already exist; use the device settings API')
    providers = [(page, entry) for page in original.pages for entry in page.entries
                 if entry.state == 'Written' and entry.metadata['namespace'] == namespace
                 and entry.key == 'provider' and entry.metadata['type'] == 'uint8_t']
    if len(providers) != 1:
        raise ValueError('missing provider entry')
    output = bytearray(data)
    page, entry = providers[0]
    provider_key = (namespace, 'provider', entry.raw[1], entry.raw[3])
    offset = page.start_address + 64 + entry.index * 32
    output[offset + 24] = 3  # Append-only Provider::Relay wire value.
    struct.pack_into('<I', output, offset + 4,
                     crc32(output[offset:offset + 4] + output[offset + 8:offset + 32], 0xFFFFFFFF))
    for key, value in (('relay_url', url), ('relay_token', token)):
        encoded = value.encode('utf-8') + b'\0'
        span = 1 + (len(encoded) + 31) // 32
        destination = None
        for page in original.pages:
            if page.header['status'] != 'Active':
                continue
            for index in range(127 - span):
                def empty(slot):
                    bitmap = output[page.start_address + 32 + slot // 4]
                    return (bitmap >> (2 * (slot % 4))) & 3 == 3
                if all(empty(slot) for slot in range(index, index + span)):
                    destination = page.start_address, index
                    break
            if destination is not None:
                break
        if destination is None:
            raise ValueError('no contiguous space; refusing compaction or destructive rewrite')
        page_offset, index = destination
        header = bytearray(b'\xff' * 32)
        header[:4] = bytes((namespace, 0x21, span, 0xFF))
        header[8:24] = key.encode('ascii').ljust(16, b'\0')
        struct.pack_into('<H', header, 24, len(encoded))
        struct.pack_into('<I', header, 28, crc32(encoded, 0xFFFFFFFF))
        struct.pack_into('<I', header, 4, crc32(header[:4] + header[8:], 0xFFFFFFFF))
        offset = page_offset + 64 + index * 32
        output[offset:offset + span * 32] = header + encoded.ljust((span - 1) * 32, b'\xff')
        for slot in range(index, index + span):
            output[page_offset + 32 + slot // 4] &= ~(1 << (2 * (slot % 4)))
    final = parser.NVS_Partition('private', output)
    validate(final)
    after = records(final)
    expected_new = {(namespace, key, 0x21, 0xFF) for key in ('relay_url', 'relay_token')}
    if set(after) != set(before) | expected_new:
        raise ValueError('unexpected record change')
    if any(after[key] != value for key, value in before.items() if key != provider_key):
        raise ValueError('unrelated record changed')
    for key, value in (('relay_url', url), ('relay_token', token)):
        raw = after[namespace, key, 0x21, 0xFF]
        length = struct.unpack_from('<H', raw, 24)[0]
        if raw[32:32 + length] != value.encode() + b'\0':
            raise ValueError('string verification failed')
    return bytes(output)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--input', required=True)
    cli.add_argument('--output', required=True)
    cli.add_argument('--url', required=True)
    cli.add_argument('--project', required=True)
    cli.add_argument('--idf-path', required=True)
    args = cli.parse_args()
    repository = Path(__file__).resolve().parents[2]
    output = Path(args.output).resolve()
    sdk = Path(args.idf_path).resolve()
    if output.exists() or output.is_relative_to(repository) or sdk.is_relative_to(repository):
        raise SystemExit('Use a new private output outside the repository and an installed SDK')
    target = urlsplit(args.url)
    if (target.scheme != 'https' or not target.hostname or not target.hostname.endswith('.run.app')
            or target.username or target.password or target.port not in (None, 443)
            or target.path not in ('', '/') or target.query or target.fragment):
        raise SystemExit('Expected the verified Cloud Run HTTPS base URL')
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', args.project):
        raise SystemExit('Invalid project')
    executable = shutil.which('gcloud')
    if not executable or Path(executable).resolve().is_relative_to(repository):
        raise SystemExit('Use the installed Google Cloud SDK')
    result = subprocess.run([executable, 'secrets', 'versions', 'access', '1',
                             '--secret=voice-relay-device-secret', '--project=' + args.project, '--quiet'],
                            capture_output=True, timeout=60)
    if result.returncode:
        raise SystemExit('Cannot read the device credential; value not displayed')
    token = result.stdout.decode().strip()
    if not 32 <= len(token) <= 256 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise SystemExit('Invalid device credential format')
    data = Path(args.input).read_bytes()
    if len(data) != 0x4000:
        raise SystemExit('Expected exactly the verified 0x4000-byte NVS partition')
    sys.path.insert(0, str(sdk / 'components/nvs_flash/nvs_partition_tool'))
    import nvs_parser
    prepared = patch(data, args.url.rstrip('/'), token, nvs_parser)
    with output.open('xb') as stream:
        stream.write(prepared)
    print(json.dumps({'bytes': len(prepared), 'sha256': hashlib.sha256(prepared).hexdigest(),
                      'changed_keys': ['provider', 'relay_url', 'relay_token'],
                      'unrelated_records_preserved': True, 'crc_verified': True}))


if __name__ == '__main__':
    main()
