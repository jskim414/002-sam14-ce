"""Bounded LWC decoder implemented from the documented stream grammar.

Format reference: https://github.com/tenshoukijp/nobu_src_koeilw
No third-party DLL is loaded. This module never writes game files.
"""
import struct

class FormatError(ValueError):
    pass

class Bits:
    def __init__(self, data: bytes):
        self.data, self.position = data, 0

    def take(self, count: int) -> int:
        if count < 0 or self.position + count > len(self.data) * 8:
            raise FormatError('Truncated LWC bitstream')
        result = 0
        for _ in range(count):
            result = (result << 1) | ((self.data[self.position // 8] >> (7 - self.position % 8)) & 1)
            self.position += 1
        return result

    def integer(self) -> int:
        # n one-bits and a terminating zero select a width of n+1.
        width = 1
        while self.take(1):
            width += 1
            if width > 24:
                raise FormatError('LWC code exceeds supported size bound')
        return (1 << width) - 2 + self.take(width)

def decode(data: bytes, *, max_output: int = 16 * 1024 * 1024) -> bytes:
    if len(data) < 268 or data[:4] != b'LWC\x1a':
        raise FormatError('Missing LWC header')
    size, payload_size = struct.unpack_from('<II', data, 4)
    if size > max_output:
        raise FormatError('LWC output exceeds configured limit')
    if payload_size + 268 != len(data):
        raise FormatError('LWC payload length mismatch')
    literals = data[12:268]
    if len(set(literals)) != 256:
        raise FormatError('LWC literal table is not a permutation')
    bits = Bits(data[268:])
    out = bytearray()
    while len(out) < size:
        token = bits.integer()
        if token < 256:
            out.append(literals[token])
        else:
            distance = token - 256
            length = bits.integer() + 3
            if not 1 <= distance <= len(out) or len(out) + length > size:
                raise FormatError('Invalid LWC back-reference')
            for _ in range(length):
                out.append(out[-distance])
    # Writers may emit padding in the last byte; no further data bytes allowed.
    if (bits.position + 7) // 8 != payload_size:
        raise FormatError('Unconsumed LWC payload bytes')
    return bytes(out)
