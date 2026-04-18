import struct
import sys
import json
import re
import os
from collections import deque

def u16_at(data, off): return struct.unpack_from('<H', data, off)[0]
def s32_at(data, off): return struct.unpack_from('<i', data, off)[0]
def u8_at(data, off): return data[off]

def find_null(data, off, maxlen=0x2000):
    for i in range(maxlen):
        if data[off + i] == 0:
            return off + i + 1
    raise ValueError

def nlt_entrypoints(nlt_path, sss_size):
    if not os.path.exists(nlt_path):
        return []
    with open(nlt_path, 'rb') as f:
        nlt_data = f.read()
    table_start = table_end = None
    for i in range(len(nlt_data) - 4, 0, -4):
        v = struct.unpack_from('<I', nlt_data, i)[0]
        if v != 0:
            table_end = i + 4
            break
    if table_end:
        for i in range(table_end - 4, 0, -4):
            v = struct.unpack_from('<I', nlt_data, i)[0]
            if v == 0:
                table_start = i + 4
                break
    if not table_start or not table_end:
        return []
    entries = []
    for i in range(table_start, table_end, 4):
        v = struct.unpack_from('<I', nlt_data, i)[0]
        if 0 < v < sss_size:
            entries.append(v)
    return entries

def parse_bytecode(data, extra_entry_points=None):
    abs_offset_positions = []
    instructions = {}
    visited = set()
    queue = deque([0])
    if extra_entry_points:
        queue.extend(extra_entry_points)

    while queue:
        off = queue.popleft()
        if off in visited or off < 0 or off >= len(data) - 1:
            continue
        visited.add(off)

        opcode = u16_at(data, off)
        pos = off + 2
        abs_offs = []
        is_terminal = False

        try:
            if opcode == 0x0002:
                pos = find_null(data, pos)
                pos = find_null(data, pos)
            elif opcode == 0x0100:
                pos += 2
                pos = find_null(data, pos)
            elif opcode == 0x0102:
                pos += 22
            elif opcode in (0x0104, 0x0105):
                pos += 12
            elif opcode == 0x0106:
                pos += 2
            elif opcode == 0x010a:
                pos += 3
            elif opcode == 0x010d:
                flag = u8_at(data, pos + 2)
                pos += 3
                if flag != 0:
                    val = u8_at(data, pos)
                    pos += 1
                    if val in (2, 3):
                        abs_offs.append(pos)
                        pos += 4
            elif opcode in (0x010e, 0x010f):
                pos += 22
            elif opcode in (0x0120, 0x0121):
                pos += 20
            elif opcode == 0x0122:
                pos += 2
            elif opcode in (0x0200,0x0201,0x0202,0x0203,0x0204,0x0205):
                pos += 9
            elif opcode == 0x0209:
                pos += 4
                pos = find_null(data, pos)
            elif opcode in (0x020a,):
                pos += 4
            elif opcode in (0x020b,0x020d,0x020e):
                pos += 8
            elif opcode == 0x020c:
                pos += 9
            elif opcode == 0x020f:
                pos += 14
            elif opcode == 0x0303:
                pos += 16
            elif opcode == 0x0304:
                pos = find_null(data, pos)
            elif opcode == 0x0305:
                pos += 6
            elif opcode == 0x0307:
                count = u16_at(data, pos)
                pos += 2
                for _ in range(count):
                    pos = find_null(data, pos)
                pos += 4
                pos = find_null(data, pos)
                pos += 1
            elif opcode == 0x030a:
                pass
            elif opcode == 0x0401:
                flag1 = u8_at(data, pos); pos += 1
                pos += 4
                pos += 1
                flag3 = u8_at(data, pos); pos += 1
                if flag3 != 0:
                    pos += 4
                else:
                    if flag1 == 0:
                        pos += 4
                    else:
                        pos = find_null(data, pos)
                abs_offs.append(pos)
                pos += 4
            elif opcode == 0x0402:
                pos += 8
                count = u8_at(data, pos); pos += 1
                for _ in range(count):
                    pos = find_null(data, pos)
            elif opcode == 0x0501:
                pos += 1
                pos = find_null(data, pos)
            elif opcode in (0x0502,0x0504,0x0507):
                pos += 1
            elif opcode == 0x0503:
                pos += 1
                pos = find_null(data, pos)
                pos += 1
            elif opcode == 0x0506:
                pos += 1
                pos = find_null(data, pos)
            elif opcode == 0x0605:
                pos += 17
            elif opcode == 0x0701:
                abs_offs.append(pos)
                target = s32_at(data, pos)
                pos += 4
                is_terminal = True
                queue.append(target)
            elif opcode == 0x0702:
                abs_offs.append(pos)
                target = s32_at(data, pos)
                pos += 4
                queue.append(target)
            elif opcode == 0x0703:
                is_terminal = True
            elif opcode == 0x0705:
                pos += 1
            elif opcode == 0x0801:
                pos = find_null(data, pos)
                pos += 1
                pos = find_null(data, pos)
            elif opcode == 0x0901:
                pos += 2
            elif opcode in (0x0902,0x0903):
                is_terminal = True
            elif opcode in (0x0904,0x0905,0x0a01,0x0a02,0x0a03,0x090a):
                pass
            elif opcode == 0x0906:
                pos = find_null(data, pos)
            elif opcode == 0x090b:
                pos += 3
            elif opcode == 0x0a04:
                pos += 2
            else:
                continue
        except:
            continue

        size = pos - off
        instructions[off] = (opcode, size)
        abs_offset_positions.extend(abs_offs)

        if opcode == 0x0401:
            target = s32_at(data, off + size - 4)
            queue.append(target)

        if not is_terminal:
            queue.append(pos)

    return sorted(set(abs_offset_positions)), instructions

def parse_text(data):
    entries = []
    pos = 0
    while pos < len(data) - 8:
        idx = data.find(b'\x07\x03', pos)
        if idx == -1:
            break
        p = idx + 2
        if p + 2 > len(data):
            pos = idx + 2; continue
        voice_flag = data[p]
        if data[p + 1] != 0x00:
            pos = idx + 2; continue
        p += 2
        voice_label = ""
        if voice_flag == 0x01:
            null_pos = data.find(b'\x00', p)
            if null_pos == -1 or null_pos - p > 50:
                pos = idx + 2; continue
            try:
                voice_label = data[p:null_pos].decode('ascii')
            except:
                pos = idx + 2; continue
            if not re.match(r'^[a-zA-Z0-9_]+$', voice_label):
                pos = idx + 2; continue
            p = null_pos + 1
        elif voice_flag != 0x00:
            pos = idx + 2; continue
        if p + 4 > len(data):
            pos = idx + 2; continue
        line_num = struct.unpack_from('<I', data, p)[0]
        if line_num > 0xFFFF:
            pos = idx + 2; continue
        p += 4
        text_start = p
        null_pos = data.find(b'\x00', p)
        if null_pos == -1:
            pos = idx + 2; continue
        text_bytes = data[text_start:null_pos]
        try:
            text = text_bytes.decode('shift-jis')
        except:
            text = text_bytes.decode('shift-jis', errors='replace')
        entries.append({
            'offset': idx,
            'voice_flag': voice_flag,
            'voice_label': voice_label,
            'line_num': line_num,
            'text_offset': text_start,
            'end_offset': null_pos + 1,
            'text': text
        })
        pos = null_pos + 1
    return entries

def extract(sss_path, json_path):
    with open(sss_path, 'rb') as f:
        data = f.read()
    entries = parse_text(data)
    out = []
    for i, e in enumerate(entries):
        out.append({
            'index': i,
            'offset': f"0x{e['offset']:06X}",
            'voice_flag': e['voice_flag'],
            'voice_label': e['voice_label'],
            'line_num': e['line_num'],
            'original_text': e['text'],
            'translated_text': ''
        })
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

def pack(original_sss_path, json_path, output_sss_path):
    with open(original_sss_path, 'rb') as f:
        original_data = f.read()

    nlt_path = os.path.join(os.path.dirname(original_sss_path) or '.', 'RSS.NLT')
    nlt_bak = nlt_path + '.bak'
    nlt_source = nlt_bak if os.path.exists(nlt_bak) else nlt_path
    nlt_entries = nlt_entrypoints(nlt_source, len(original_data))

    abs_offset_positions, _ = parse_bytecode(original_data, nlt_entries)
    entries = parse_text(original_data)

    with open(json_path, 'r', encoding='utf-8') as f:
        json_entries = json.load(f)

    translations = {i['index']: i['translated_text'].strip()
                    for i in json_entries if i.get('translated_text','').strip()}

    patches = []
    for idx, txt in translations.items():
        if idx >= len(entries):
            continue
        try:
            new_bytes = txt.encode('cp932')
        except:
            continue
        e = entries[idx]
        patches.append((e['text_offset'], e['end_offset']-1, new_bytes))

    patches.sort()

    shift_points = []
    for s, e, nb in patches:
        delta = len(nb) - (e - s)
        if delta:
            shift_points.append((s, delta))

    output = bytearray()
    prev = 0
    for s, e, nb in patches:
        output.extend(original_data[prev:s])
        output.extend(nb)
        prev = e
    output.extend(original_data[prev:])

    if shift_points:
        cum = []
        r = 0
        for s, d in shift_points:
            r += d
            cum.append((s, r))

        def get_shift(p):
            for i in range(len(cum)-1, -1, -1):
                if p >= cum[i][0]:
                    return cum[i][1]
            return 0

        for loc in abs_offset_positions:
            new_loc = loc + get_shift(loc)
            if new_loc + 4 > len(output):
                continue
            orig = struct.unpack_from('<I', original_data, loc)[0]
            new = orig + get_shift(orig)
            if new != orig:
                struct.pack_into('<I', output, new_loc, new)

    with open(output_sss_path, 'wb') as f:
        f.write(output)

def main():
    if len(sys.argv) < 2:
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd == 'extract':
        extract(sys.argv[2], sys.argv[3])
    elif cmd == 'pack':
        pack(sys.argv[2], sys.argv[3], sys.argv[4])

if __name__ == '__main__':
    main()
