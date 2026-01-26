import struct
import sys
import os
import json

def read_u32(f):
    b = f.read(4)
    if len(b) < 4:
        raise EOFError
    return struct.unpack("<I", b)[0]

def write_u32(f, v):
    f.write(struct.pack("<I", v))

def read_7bit_length(f):
    result = 0
    shift = 0
    for _ in range(5):
        b = f.read(1)
        if not b:
            raise EOFError("Unexpected EOF while reading length")
        b = b[0]
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return result
        shift += 7
    raise ValueError("Invalid length")

def write_7bit_length(buf, value):
    v = value
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            buf.append(b | 0x80)
        else:
            buf.append(b)
            break

def parse_cmp(infile):
    with open(infile, "rb") as f:
        magic = f.read(4)
        label_count = read_u32(f)
        jump_table_size = read_u32(f)
        string_count = read_u32(f)
        header_blob = magic + struct.pack("<III", label_count, jump_table_size, string_count)
        label_blob = bytearray()
        for _ in range(label_count):
            pos0 = f.tell()
            length = read_7bit_length(f)
            pos1 = f.tell()
            f.seek(pos0)
            raw = f.read(pos1 - pos0 + length + 4)
            label_blob += raw

        jump_blob = f.read(jump_table_size)
        strings = []
        for _ in range(string_count):
            length = read_7bit_length(f)
            data = f.read(length)
            s = data.decode("utf-8", errors="replace")
            strings.append(s)
    return header_blob, label_blob, jump_blob, strings

def extract_cmp(infile):
    header_blob, label_blob, jump_blob, strings = parse_cmp(infile)
    text_ids = []
    size = len(jump_blob)
    i = 0
    string_count = len(strings)

    while i + 4 <= size:
        b0 = jump_blob[i]
        b1 = jump_blob[i + 1]

        if b0 == 0x2C and b1 == 0x00:
            sid = jump_blob[i + 2] | (jump_blob[i + 3] << 8)
            if sid < string_count:
                text_ids.append(sid)
            i += 4
            continue

        if b0 == 0x1A and b1 == 0x00:
            sid = jump_blob[i + 2] | (jump_blob[i + 3] << 8)
            if sid < string_count:
                text_ids.append(sid)
            i += 4
            continue

        i += 1

    seen = set()
    filtered_ids = []
    for sid in text_ids:
        if sid not in seen:
            seen.add(sid)
            filtered_ids.append(sid)

    out_list = []
    for sid in filtered_ids:
        out_list.append({
            "id": sid,
            "original": strings[sid],
            "translate": ""
        })

    outfile = infile + ".json"
    with open(outfile, "w", encoding="utf-8") as out:
        json.dump(out_list, out, ensure_ascii=False, indent=2)

    print(f"Extracted {len(out_list)} strings -> {outfile}")

def import_cmp(infile, json_file):
    header_blob, label_blob, jump_blob, strings = parse_cmp(infile)

    with open(json_file, "r", encoding="utf-8") as jf:
        data = json.load(jf)

    replaced = 0
    for e in data:
        sid = e.get("id")
        tr = e.get("translate", "")
        orig = e.get("original", "")

        if not tr:
            continue

        if 0 <= sid < len(strings):
            if orig and strings[sid] != orig:
                continue

            strings[sid] = tr
            replaced += 1

    new_string_blob = bytearray()
    for s in strings:
        b = s.encode("utf-8")
        write_7bit_length(new_string_blob, len(b))
        new_string_blob += b

    outfile = infile + ".new"
    with open(outfile, "wb") as out:
        out.write(header_blob)
        out.write(label_blob)
        out.write(jump_blob)
        out.write(new_string_blob)

    print(f"Imported {replaced} strings")
    print(f"Created {outfile}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:")
        print("  cmp.py -e <input.cmp>")
        print("  cmp.py -i <input.cmp> <input.json>")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "-e" and len(sys.argv) == 3:
        extract_cmp(sys.argv[2])

    elif mode == "-i" and len(sys.argv) == 4:
        import_cmp(sys.argv[2], sys.argv[3])

    else:
        sys.exit(1)
