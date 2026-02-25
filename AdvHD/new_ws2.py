#by Leticiel
import sys
import os
import struct
import json

def exWS2(path):
    with open(path, "rb") as f:
        data = f.read()

    results = []
    size = len(data)
    i = 0

    opcode_text = struct.pack(">I", 0x14)
    opcode_name = struct.pack(">I", 0x15)

    text_start = ("char" + "\x00").encode("utf-16le")
    text_end = "%K".encode("utf-16le")
    name_marker = "%L".encode("utf-16le")

    choice_block_start = b"\x00\x0E\x0B\x00"

    while i < size - 40:

        if data[i:i+4] == opcode_text:

            index = struct.unpack_from("<I", data, i + 4)[0]
            start = i + 8

            if data[start:start+len(text_start)] == text_start:

                str_start = start + len(text_start)
                str_end = data.find(text_end, str_start)

                if str_end == -1:
                    i += 1
                    continue

                text = data[str_start:str_end].decode(
                    "utf-16le", errors="ignore"
                ).replace("\\n", "\n")

                name = None

                pos_name = data.rfind(opcode_name, 0, i)
                if pos_name != -1:
                    lf_start = pos_name + 4
                    if data[lf_start:lf_start+4] == name_marker:
                        name_start = lf_start + 6
                        name = data[name_start:i].decode(
                            "utf-16le", errors="ignore"
                        )

                entry = {"index": index}
                if name:
                    entry["name"] = name
                entry["text"] = text

                results.append(entry)
                i = str_end + len(text_end)
                continue

        if data[i:i+4] == choice_block_start:

            ptr = i + 4
            choice_count = struct.unpack_from("<H", data, ptr)[0]
            ptr += 2

            linked = False

            if data[ptr:ptr+2] == b"\x01\x0F":
                ptr += 2
                ptr += 1

            elif data[ptr:ptr+2] == b"\x01\x01":
                linked = True
                ptr += 2
                ptr += 1
                ptr += 10
                ptr += 4
                ptr += 4
            else:
                i += 1
                continue

            choice_dict = {"_linked": linked}

            for c in range(choice_count):

                if not (linked and c == 0):
                    ptr += 2

                end_marker = struct.pack(">I", 0x0B + c)
                str_end = data.find(end_marker, ptr)

                if str_end == -1:
                    break

                raw = data[ptr:str_end]
                text = raw.decode("utf-16le", errors="ignore")

                choice_dict[f"choice {c+1}"] = text
                choice_dict[f"_size_{c+1}"] = len(raw)

                ptr = str_end + 4

                while ptr + 1 < size:
                    if data[ptr:ptr+2] == b"\x00\x00":
                        ptr += 2
                        break
                    ptr += 2

            if len(choice_dict) > 1:
                results.append(choice_dict)

            i = ptr
            continue

        i += 1

    i = 0
    while i < size - 6:
        if data[i] == 0x3F and data[i+1:i+6] == b"\x16\x00\x00\x64\x00":
            results.append({
                "jump": i + 1
            })
            i += 6
        else:
            i += 1

    return results

def imWS2(original_path, json_path):
    with open(original_path, "rb") as f:
        data = bytearray(f.read())
    with open(json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    opcode_text = struct.pack(">I", 0x14)
    opcode_name = struct.pack(">I", 0x15)

    text_start = ("char" + "\x00").encode("utf-16le")
    text_end = "%K".encode("utf-16le")
    name_marker = "%L".encode("utf-16le")

    choice_block_start = b"\x00\x0E\x0B\x00"

    name_list = [
        e["name"]
        for e in entries
        if isinstance(e, dict) and "name" in e
    ]
    name_index = 0

    choice_entries = [
        e for e in entries
        if isinstance(e, dict) and "choice 1" in e
    ]
    choice_index = 0

    jump_positions = [
        e["jump"]
        for e in entries
        if isinstance(e, dict) and "jump" in e
    ]

    delta_events = []

    i = 0

    while i < len(data) - 40:
        if data[i:i+4] == opcode_text:

            index = struct.unpack_from("<I", data, i + 4)[0]

            entry = next(
                (e for e in entries
                 if isinstance(e, dict)
                 and e.get("index") == index),
                None
            )

            if not entry:
                i += 1
                continue

            start = i + 8
            if data[start:start+len(text_start)] != text_start:
                i += 1
                continue

            str_start = start + len(text_start)
            str_end = data.find(text_end, str_start)
            if str_end == -1:
                i += 1
                continue

            old_len = str_end - str_start
            new_bytes = entry["text"].replace("\n", "\\n").encode("utf-16le")

            delta = len(new_bytes) - old_len
            data[str_start:str_start+old_len] = new_bytes

            if delta != 0:
                delta_events.append((str_start, delta))

            i = str_start + len(new_bytes)
            continue

        if data[i:i+4] == opcode_name:

            if name_index >= len(name_list):
                i += 1
                continue

            start = i + 4
            if data[start:start+4] != name_marker:
                i += 1
                continue

            name_start = start + 6
            next_text = data.find(opcode_text, name_start)
            if next_text == -1:
                i += 1
                continue

            old_len = next_text - name_start
            new_bytes = name_list[name_index].encode("utf-16le")

            delta = len(new_bytes) - old_len
            data[name_start:name_start+old_len] = new_bytes

            if delta != 0:
                delta_events.append((name_start, delta))

            name_index += 1
            i = name_start + len(new_bytes)
            continue

        if (
            data[i:i+4] == choice_block_start
            and choice_index < len(choice_entries)
        ):

            entry = choice_entries[choice_index]
            ptr = i + 4

            choice_count = struct.unpack_from("<H", data, ptr)[0]
            ptr += 2

            if data[ptr:ptr+2] == b"\x01\x0F":

                ptr += 2
                ptr += 1

                for c in range(choice_count):

                    key = f"choice {c+1}"
                    if key not in entry:
                        break

                    ptr += 2

                    end_marker = struct.pack(">I", 0x0B + c)
                    str_end = data.find(end_marker, ptr)
                    if str_end == -1:
                        break

                    old_len = str_end - ptr
                    new_bytes = entry[key].encode("utf-16le")

                    delta = len(new_bytes) - old_len
                    data[ptr:ptr+old_len] = new_bytes

                    if delta != 0:
                        delta_events.append((ptr, delta))

                    ptr += len(new_bytes)
                    ptr += 4

                    while data[ptr:ptr+2] != b"\x00\x00":
                        ptr += 2
                    ptr += 2

                i = ptr
                choice_index += 1
                continue

            elif data[ptr:ptr+2] == b"\x01\x01":

                ptr += 2
                ptr += 1
                ptr += 10

                pointer_pos = ptr
                old_block2 = struct.unpack_from("<I", data, ptr)[0]
                ptr += 4
                ptr += 4

                for c in range(choice_count):

                    key = f"choice {c+1}"
                    if key not in entry:
                        break

                    if c != 0:
                        ptr += 2

                    end_marker = struct.pack(">I", 0x0B + c)
                    str_end = data.find(end_marker, ptr)
                    if str_end == -1:
                        break

                    old_len = str_end - ptr
                    new_bytes = entry[key].encode("utf-16le")

                    delta = len(new_bytes) - old_len
                    data[ptr:ptr+old_len] = new_bytes

                    if delta != 0:
                        delta_events.append((ptr, delta))

                    ptr += len(new_bytes)
                    ptr += 4

                    while data[ptr:ptr+2] != b"\x00\x00":
                        ptr += 2
                    ptr += 2

                shift = sum(d for pos, d in delta_events if pos < pointer_pos)
                new_block2 = old_block2 + shift
                struct.pack_into("<I", data, pointer_pos, new_block2)

                i = ptr
                choice_index += 1
                continue

        i += 1

    sorted_deltas = sorted(delta_events)

    for jump in jump_positions:

        cumulative = 0
        for pos, d in sorted_deltas:
            if pos < jump:
                cumulative += d
            else:
                break

        new_jump = jump + cumulative

        old_bytes = struct.pack("<I", jump)
        new_bytes = struct.pack("<I", new_jump)

        found = False
        pos = 0
        while True:
            pos = data.find(old_bytes, pos)
            if pos == -1:
                break
            data[pos:pos+4] = new_bytes
            pos += 4
            found = True
        if not found:
            print("Error: Use original ws2 to import")
            sys.exit(1)

    output_path = original_path + ".new"

    with open(output_path, "wb") as f:
        f.write(data)

    print("Created:", output_path)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:")
        print("  Extract: -e <input.ws2>")
        print("  Import : -i <original.ws2> <modified.json>")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "-e" and len(sys.argv) == 3:
        input_path = sys.argv[2]
        output_path = os.path.splitext(input_path)[0] + ".json"
        data = exWS2(input_path)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Extracted:", output_path)

    elif mode == "-i" and len(sys.argv) == 4:
        original_path = sys.argv[2]
        json_path = sys.argv[3]
        imWS2(original_path, json_path)

    else:
        sys.exit(1)
