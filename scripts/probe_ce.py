"""Decode CE snapshots and describe binary record candidates, without promotion."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extractors.lwc import decode, FormatError
from common import ROOT, output_path, sha256, write_json

def string_at(data: bytes, offset: int, size: int) -> str:
    return data[offset:offset+size].decode('utf-16le', errors='strict').split('\0')[0]

def probe(path: Path) -> tuple[dict, bytes | None]:
    raw = path.read_bytes()
    report = {'file_name': path.name, 'size_bytes': len(raw), 'sha256': sha256(path)}
    if raw[4:20] != b'SN14SCEXVER0001\0':
        report.update(status='FAILED', reason='UNRECOGNIZED_OUTER_HEADER')
        return report, None
    offset = raw.find(b'LWC\x1a')
    if offset < 20:
        report.update(status='FAILED', reason='MISSING_LWC_STREAM')
        return report, None
    report.update(header_version=struct.unpack_from('<I',raw)[0], lwc_offset=offset)
    # Only short title metadata is exported; narrative/help text stays private.
    header_text = raw[20:offset-offset%2].decode('utf-16le', errors='replace')
    parts = [s for s in header_text.split('\0') if s]
    report['title_candidate'] = next((s for s in parts[1:] if len(s)<40), None)
    try:
        data = decode(raw[offset:])
    except FormatError as error:
        report.update(status='FAILED', reason=str(error))
        return report, None
    report.update(status='DECOMPRESSED', decoded_size=len(data),
                  decoded_sha256=hashlib.sha256(data).hexdigest())
    return report, data

def officer_records(data: bytes) -> tuple[dict, list[dict]]:
    """Recognize CE's counted 316-byte record block with its invalid sentinel.

    Layout is a measured candidate until independent field verification passes.
    Offsets are decompressed-byte offsets, not original-file offsets.
    """
    sentinel = '\ubb34\ud6a8'.encode('utf-16le') + bytes(10)
    starts = []
    for match in re.finditer(re.escape(sentinel), data):
        p = match.start()
        if p < 4 or p+316>len(data): continue
        count = struct.unpack_from('<I',data,p-4)[0]
        if not 1000 <= count <= 10000 or p+count*316>len(data): continue
        if data[p+14:p+28] == sentinel and struct.unpack_from('<H',data,p+316+150)[0] == 1:
            starts.append((p,count))
    if len(starts)!=1:
        raise FormatError(f'Expected one officer record block, found {len(starts)}')
    start, count = starts[0]
    rows=[]
    for index in range(count):
        off=start+index*316; record=data[off:off+316]
        surname=string_at(record,0,14); given=string_at(record,14,14)
        if not surname and not given: continue
        rows.append({'record_index':index, 'record_offset':off,
                     'source_id':struct.unpack_from('<H',record,150)[0],
                     'name':surname+given,'courtesy_name':string_at(record,28,6),
                     'stats_candidate':list(record[166:171]),
                     'raw_tail_hex':record[144:].hex(),
                     'record_sha256':hashlib.sha256(record).hexdigest()})
    return {'offset':start,'count':count,'record_size':316,'named_records':len(rows)},rows

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); out=output_path(a.output)
    if not out.is_relative_to((ROOT/'.artifacts').resolve()):
        raise ValueError('Probe results must remain private')
    out.mkdir(parents=True)
    inventory=json.loads((a.snapshot/'inventory.json').read_text('utf-8'))
    reports=[]
    for row in inventory['files']:
        rel=Path(row['relative_path'])
        if '0010_KO' not in rel.parts or 'exce' not in rel.name or rel.suffix!='.s14':continue
        path=a.snapshot/'game'/rel
        if sha256(path)!=row['sha256']:raise FormatError('Source snapshot hash mismatch')
        report,data=probe(path);report['relative_path']=rel.as_posix()
        if data is not None:
            name=rel.as_posix().replace('/','_')
            (out/(name+'.decoded.bin')).write_bytes(data)
            if path.name.startswith('sceda'):
                try:
                    block,officers=officer_records(data)
                    report['officer_block']=block
                    write_json(out/(name+'.officers.json'),{'block':block,'officers':officers})
                except FormatError as e:report['officer_error']=str(e)
        reports.append(report)
    write_json(out/'probe-report.json',{'steam_build_id':inventory['steam_build_id'],
               'inventory_sha256':sha256(a.snapshot/'inventory.json'),'files':reports})
    for row in reports:
        print(row['file_name'],row['status'],row.get('title_candidate'),row.get('officer_block',{}).get('named_records'),row.get('reason',''))

if __name__=='__main__':main()
