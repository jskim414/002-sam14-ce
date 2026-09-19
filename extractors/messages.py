"""Bounded readers for the measured CE zp1 container and message string table."""
import struct
import zlib
from .lwc import FormatError

MAX_OUTPUT = 16 * 1024 * 1024


def decode_zp1(raw: bytes) -> bytes:
    if len(raw) < 0x800 or len(raw)>MAX_OUTPUT*2 or raw[:4] != b'zp1\0':
        raise FormatError('Unsupported zp1 container')
    total, block_size, count = struct.unpack_from('<III', raw, 4)
    if not 0 < total <= MAX_OUTPUT or block_size != 0x40000 or count != (total + block_size - 1) // block_size:
        raise FormatError('Invalid zp1 output bounds')
    if 16 + 4 * count > 0x800:
        raise FormatError('Invalid zp1 directory')
    lengths = struct.unpack_from('<' + 'I' * count, raw, 16)
    pos = 0x800
    output = bytearray()
    for length in lengths:
        if length <= 4 or pos + length > len(raw) or struct.unpack_from('<I', raw, pos)[0] != length - 4:
            raise FormatError('Invalid zp1 block bounds')
        decoder = zlib.decompressobj()
        expected = min(block_size, total - len(output))
        try:
            block = decoder.decompress(raw[pos + 4:pos + length], expected + 1)
        except zlib.error as exc:
            raise FormatError('Invalid zp1 compressed block') from exc
        if len(block) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise FormatError('Invalid zp1 block output')
        output.extend(block)
        end=pos+length
        pos = (end + 127) & ~127
        if any(raw[end:pos]):raise FormatError('Unexpected zp1 alignment bytes')
    if any(raw[pos:]):
        raise FormatError('Unexpected zp1 trailing data')
    return bytes(output)


def string_table(data: bytes) -> list[dict]:
    if len(data) < 76 or struct.unpack_from('<II', data) != (1, 12):
        raise FormatError('Unsupported message directory')
    if struct.unpack_from('<I', data, 8)[0] != len(data) - 12:
        raise FormatError('Message file length mismatch')
    count = struct.unpack_from('<I', data, 12)[0]
    if count != 4:
        raise FormatError('Unsupported message section count')
    sections = [struct.unpack_from('<II', data, 16 + i * 8) for i in range(count)]
    if any(offset < 36 or 12 + offset + length > len(data) for offset, length in sections):
        raise FormatError('Message section outside file')
    start, size = sections[0]
    start += 12
    table = start + 24
    first = struct.unpack_from('<I', data, table)[0]
    if first < 4 or first % 4 or first > size - 24:
        raise FormatError('Invalid message string directory')
    offsets = list(struct.unpack_from('<' + 'I' * (first // 4), data, table))
    offsets.append(start + size - table)
    if any(a % 2 or b <= a or b > size - 24 for a, b in zip(offsets, offsets[1:])):
        raise FormatError('Invalid message string bounds')
    result = []
    for index, (a, b) in enumerate(zip(offsets, offsets[1:])):
        text = data[table + a:table + b]
        if not text.endswith(b'\0\0'):
            raise FormatError('Unterminated message string')
        try:
            value = text.decode('utf-16le').rstrip('\0')
        except UnicodeError as exc:
            raise FormatError('Invalid message UTF-16') from exc
        result.append({'id': index, 'text': value, 'record_offset': table + a})
    return result


STATE_CODES = {0: 'DISABLED', 1: 'ACTIVE_FORCE', 2: 'ACTIVE_FORCE', 3: 'ACTIVE_FORCE',
               4: 'ACTIVE_FORCE', 5: 'FREE', 6: 'PRISONER', 7: 'UNAPPEARED',
               8: 'UNDISCOVERED', 9: 'DEAD'}
STATE_SOURCE_LABELS = ['무효', '군주', '도독', '태수', '일반', '재야', '포로', '미등장', '미발견', '사망']


def validate_enums(messages: list[dict]) -> None:
    if [x['text'] for x in messages[249:259]] != STATE_SOURCE_LABELS:
        raise FormatError('Officer state message enum changed')
    if [x['text'] for x in messages[4:9]] != ['무효', '일반', '튜토리얼', '체험판', '전기제패']:
        raise FormatError('Scenario mode message enum changed')
