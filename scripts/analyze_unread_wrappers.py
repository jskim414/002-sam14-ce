"""Bounded, read-only triage of the two unread CE DLC wrappers."""
import argparse
from collections import Counter
import math
from pathlib import Path
import zlib
from common import sha256,write_json

def analyze(snapshot):
    results=[]
    for code in (32,33):
        rel=f'DLC/0010_KO/scedaexce{code}.s14';path=snapshot/'game'/rel;data=path.read_bytes()
        signatures={k:data.find(v) for k,v in {'SN14':b'SN14','LWC':b'LWC','ZIP':b'PK\x03\x04','GZIP':b'\x1f\x8b','XZ':b'\xfd7zXZ\x00'}.items()}
        candidates=[]
        for offset in range(min(1024,len(data)-2)):
            # Only valid zlib CMF/FLG signatures; enforce an output bound.
            a,b=data[offset:offset+2]
            if a&15!=8 or a>>4>7 or (a*256+b)%31:continue
            try:
                decoder=zlib.decompressobj();output=decoder.decompress(data[offset:],16*1024*1024)
                if decoder.eof:candidates.append({'offset':offset,'output_bytes':len(output)})
            except zlib.error:pass
        xor_headers=[]
        for offset in (0,4,16,32):
            for key in range(256):
                head=bytes(x^key for x in data[offset:offset+4])
                if head==b'SN14' or head.startswith(b'LWC'):xor_headers.append({'offset':offset,'key':key})
        entropy=-sum((n/len(data))*math.log2(n/len(data)) for n in Counter(data).values())
        results.append({'relative_path':rel,'sha256':sha256(path),'bytes':len(data),'entropy_bits_per_byte':round(entropy,6),'signature_offsets':signatures,'bounded_zlib_streams':candidates,'single_byte_xor_header_matches':xor_headers,'status':'UNRESOLVED_WRAPPER','interpretation':'No supported wrapper established; entropy alone does not prove encryption. No keys, bodies, scenario dates or officer rows inferred.'})
    return {'read_only':True,'files':results,'scope':'Signatures across full file, valid zlib headers in first 1024 bytes with 16 MiB output limit, single-byte XOR header candidates at offsets 0/4/16/32. Not exhaustive cryptanalysis.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    result=analyze(a.snapshot);write_json(a.report,result);print('Two wrapper triage records written; unresolved content remains excluded.')
