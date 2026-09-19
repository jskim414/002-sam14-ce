"""Read-only CE DLC wrapper, measured on installed build 24966116.

The outer byte transform precedes the ordinary SN14/LWC container. It is
independent of locale. No game executable or native dependency is required.
"""
import re
from .lwc import FormatError

SIGNATURE=b'SN14SCEXVER0001\0'

def unwrap(raw: bytes, filename: str, steam_app_id: int | None = None) -> tuple[bytes,str]:
    if len(raw)>16*1024*1024:raise FormatError('Container exceeds configured limit')
    if len(raw)>=20 and raw[4:20]==SIGNATURE:return raw,'PLAIN'
    match=re.fullmatch(r'scedaexce(\d+)\.s14',filename)
    if not match or not isinstance(steam_app_id,int) or isinstance(steam_app_id,bool) or not 0<steam_app_id<2**31:
        raise FormatError('UNRECOGNIZED_OUTER_HEADER: no measured DLC profile')
    if len(raw)<20:raise FormatError('Truncated DLC container')
    state=(int(match[1])+steam_app_id)&0xffffffff
    output=bytearray(len(raw))
    for i,byte in enumerate(raw):
        state=(state*0x6c078965+0x3039)&0xffffffff
        output[i]=byte^(((state>>16)^(state>>24))&255)
    if output[4:20]!=SIGNATURE:raise FormatError('DLC profile does not decode the expected signature')
    return bytes(output),'DLC_LCG_XOR_V1'
