# by Leticiel
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
    opcode_names = (b"\x00\x15", b"\x01\x15")

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
                pos_name = -1
                
                for op in opcode_names:
                    p = data.rfind(op, 0, i)
                    if p > pos_name:
                        pos_name = p

                if pos_name != -1:
                    lf_start = pos_name + 2
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
                ptr += 3

            elif data[ptr:ptr+2] == b"\x01\x01":
                linked = True
                ptr += 21
            else:
                i += 1
                continue

            choice_dict = {}

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

    return results

def imWS2(original_path, json_path):
    with open(original_path, "rb") as f:
        original = f.read()
    with open(json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    opcode_text = struct.pack(">I", 0x14)
    opcode_names = (b"\x00\x15", b"\x01\x15")

    text_start = ("char" + "\x00").encode("utf-16le")
    text_end = "%K".encode("utf-16le")
    name_marker = "%L".encode("utf-16le")

    choice_block_start = b"\x00\x0E\x0B\x00"

    size = len(original)
    patches = []

    index_map = {
        e["index"]: e
        for e in entries
        if isinstance(e, dict) and "index" in e
    }

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

    i = 0

    while i < size - 40:
        if original[i:i+4] == opcode_text:

            index = struct.unpack_from("<I", original, i + 4)[0]
            entry = index_map.get(index)

            if entry:

                start = i + 8

                if original[start:start+len(text_start)] == text_start:

                    str_start = start + len(text_start)
                    str_end = original.find(text_end, str_start)

                    if str_end != -1:

                        new_bytes = entry["text"].replace(
                            "\n", "\\n"
                        ).encode("utf-16le")

                        patches.append({
                            "start": str_start,
                            "end": str_end,
                            "new": new_bytes
                        })

                        i = str_end
                        continue

        if original[i:i+2] in opcode_names:

            if name_index >= len(name_list):
                i += 1
                continue

            start = i + 2

            if original[start:start+4] != name_marker:
                i += 1
                continue

            name_start = start + 6
            next_text = original.find(opcode_text, name_start)

            if next_text == -1:
                i += 1
                continue

            new_bytes = name_list[name_index].encode("utf-16le")

            patches.append({
                "start": name_start,
                "end": next_text,
                "new": new_bytes
            })

            name_index += 1
            i = next_text
            continue

        if (
            original[i:i+4] == choice_block_start
            and choice_index < len(choice_entries)
        ):

            entry = choice_entries[choice_index]

            ptr = i + 4
            choice_count = struct.unpack_from("<H", original, ptr)[0]
            ptr += 2

            linked = False

            if original[ptr:ptr+2] == b"\x01\x0F":
                ptr += 3

            elif original[ptr:ptr+2] == b"\x01\x01":
                linked = True
                ptr += 21
            else:
                i += 1
                continue

            for c in range(choice_count):

                key = f"choice {c+1}"
                if key not in entry:
                    break

                if not (linked and c == 0):
                    ptr += 2

                end_marker = struct.pack(">I", 0x0B + c)
                str_end = original.find(end_marker, ptr)

                if str_end == -1:
                    break

                new_bytes = entry[key].encode("utf-16le")

                patches.append({
                    "start": ptr,
                    "end": str_end,
                    "new": new_bytes
                })

                ptr = str_end + 4

                while original[ptr:ptr+2] != b"\x00\x00":
                    ptr += 2
                ptr += 2

            choice_index += 1
            i = ptr
            continue

        i += 1

    patches.sort(key=lambda x: x["start"])

    new_data = bytearray()
    cursor = 0

    for p in patches:
        new_data += original[cursor:p["start"]]
        new_data += p["new"]
        cursor = p["end"]

    new_data += original[cursor:]

    def map_offset(old_offset):

        shift = 0

        for p in patches:
            if p["start"] < old_offset:
                shift += len(p["new"]) - (p["end"] - p["start"])
            else:
                break

        return old_offset + shift

    getmsgskip_sig = (
        b"\x1C" +
        "GetMsgSkip".encode("utf-16le") +
        b"\x00\x00\x00\x00"
    )

    i = 0
    size = len(new_data)

    while True:

        pos = new_data.find(getmsgskip_sig, i)
        if pos == -1:
            break

        ptr = pos + len(getmsgskip_sig)
        ptr += 7

        if new_data[ptr:ptr+4] != b"\x00\x00\x80\x3F":
            i = pos + 1
            continue

        ptr += 4

        pointer1_pos = ptr
        old_pointer1 = struct.unpack_from("<I", new_data, ptr)[0]
        ptr += 4

        pointer2_pos = ptr
        old_pointer2 = struct.unpack_from("<I", new_data, ptr)[0]
        ptr += 20

        if new_data[ptr:ptr+2] != b"\x00\x02":
            i = pos + 1
            continue

        ptr += 2
        pointer2_dup_pos = ptr

        new_pointer1 = map_offset(old_pointer1)
        new_pointer2 = map_offset(old_pointer2)

        struct.pack_into("<I", new_data, pointer1_pos, new_pointer1)
        struct.pack_into("<I", new_data, pointer2_pos, new_pointer2)
        struct.pack_into("<I", new_data, pointer2_dup_pos, new_pointer2)

        i = pos + 1

    movie_sig = b"\x46" + "movie".encode("utf-16le")
    movie2_sig = b"\x3A" + "movie".encode("utf-16le")

    i = 0

    while True:

        pos = new_data.find(movie_sig, i)
        if pos == -1:
            break

        ptr = pos + len(movie_sig)
        ptr += 20

        if new_data[ptr:ptr+3] != b"\x00\x01\x02":
            i = pos + 1
            continue

        ptr += 5

        if new_data[ptr:ptr+4] != b"\x00\x00\x80\x3F":
            i = pos + 1
            continue

        ptr += 4

        pointer1_pos = ptr
        old_pointer1 = struct.unpack_from("<I", new_data, ptr)[0]
        ptr += 4

        pointer2_pos = ptr
        old_pointer2 = struct.unpack_from("<I", new_data, ptr)[0]
        ptr += 4

        if new_data[ptr:ptr+len(movie2_sig)] != movie2_sig:
            i = pos + 1
            continue

        ptr += len(movie2_sig)

        if new_data[ptr:ptr+5] != b"\x00\x00\x00\x02\x02":
            i = pos + 1
            continue

        ptr += 5

        pointer2_dup_pos = ptr

        new_pointer1 = map_offset(old_pointer1)
        new_pointer2 = map_offset(old_pointer2)

        struct.pack_into("<I", new_data, pointer1_pos, new_pointer1)
        struct.pack_into("<I", new_data, pointer2_pos, new_pointer2)
        struct.pack_into("<I", new_data, pointer2_dup_pos, new_pointer2)

        i = pos + 1

    evret_sig = b"\x07" + "EVRET".encode("utf-16le")

    i = 0

    while True:

        pos = new_data.find(evret_sig, i)
        if pos == -1:
            break

        pointer2_dup_pos = pos - 4
        old_pointer = struct.unpack_from("<I", new_data, pointer2_dup_pos)[0]

        ptr = pointer2_dup_pos - 4

        if new_data[ptr:ptr+4] != b"\x00\x00\x00\x00":
            i = pos + 1
            continue

        ptr -= 4
        if new_data[ptr:ptr+4] != b"\x00\x00\x80\x3F":
            i = pos + 1
            continue

        ptr -= 4
        if new_data[ptr:ptr+4] != b"\x01\x82\x6E\x00":
            i = pos + 1
            continue

        pointer1_pos = ptr - 4
        old_pointer1 = struct.unpack_from("<I", new_data, pointer1_pos)[0]

        new_pointer = map_offset(old_pointer1)

        struct.pack_into("<I", new_data, pointer1_pos, new_pointer)
        struct.pack_into("<I", new_data, pointer2_dup_pos, new_pointer)

        i = pos + 1

    output_path = original_path + ".new"

    with open(output_path, "wb") as f:
        f.write(new_data)

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
