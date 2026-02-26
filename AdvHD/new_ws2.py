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

    import struct
    import json

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

    delta_events = []

    i = 0
    size = len(data)

    while i < size - 40:
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

            size = len(data)
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
            size = len(data)
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

                ptr += 3

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

                size = len(data)
                i = ptr
                choice_index += 1
                continue

            elif data[ptr:ptr+2] == b"\x01\x01":

                ptr += 13

                pointer_pos = ptr
                old_block2 = struct.unpack_from("<I", data, ptr)[0]
                ptr += 8

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

                shift = sum(d for pos, d in delta_events if pos < old_block2)
                new_block2 = old_block2 + shift
                struct.pack_into("<I", data, pointer_pos, new_block2)

                size = len(data)
                i = ptr
                choice_index += 1
                continue

        i += 1

    getmsgskip_sig = (
        b"\x1C" +
        "GetMsgSkip".encode("utf-16le") +
        b"\x00\x00\x00\x00"
    )

    sorted_deltas = sorted(delta_events)

    def calc_shift(offset):
        s = 0
        for pos, delta in sorted_deltas:
            if pos < offset:
                s += delta
            else:
                break
        return s

    i = 0
    size = len(data)

    while True:

        pos = data.find(getmsgskip_sig, i)
        if pos == -1:
            break

        ptr = pos + len(getmsgskip_sig)
        ptr += 7

        if data[ptr:ptr+4] != b"\x00\x00\x80\x3F":
            i = pos + 1
            continue

        ptr += 4

        pointer1_pos = ptr
        old_pointer1 = struct.unpack_from("<I", data, ptr)[0]
        ptr += 4

        pointer2_pos = ptr
        old_pointer2 = struct.unpack_from("<I", data, ptr)[0]
        ptr += 20

        if data[ptr:ptr+2] != b"\x00\x02":
            i = pos + 1
            continue

        ptr += 2
        pointer2_dup_pos = ptr

        shift1 = calc_shift(old_pointer1)
        shift2 = calc_shift(old_pointer2)

        new_pointer1 = old_pointer1 + shift1
        new_pointer2 = old_pointer2 + shift2

        struct.pack_into("<I", data, pointer1_pos, new_pointer1)
        struct.pack_into("<I", data, pointer2_pos, new_pointer2)
        struct.pack_into("<I", data, pointer2_dup_pos, new_pointer2)

        i = pos + 1

    movie_sig = b"\x46" + "movie".encode("utf-16le")
    movie2_sig = b"\x3A" + "movie".encode("utf-16le")

    i = 0
    size = len(data)

    while True:

        pos = data.find(movie_sig, i)
        if pos == -1:
            break

        ptr = pos + len(movie_sig)

        ptr += 20

        if data[ptr:ptr+3] != b"\x00\x01\x02":
            i = pos + 1
            continue

        ptr += 5

        # check float 1.0
        if data[ptr:ptr+4] != b"\x00\x00\x80\x3F":
            i = pos + 1
            continue

        ptr += 4

        pointer1_pos = ptr
        old_pointer1 = struct.unpack_from("<I", data, ptr)[0]
        ptr += 4

        pointer2_pos = ptr
        old_pointer2 = struct.unpack_from("<I", data, ptr)[0]
        ptr += 4

        if data[ptr:ptr+len(movie2_sig)] != movie2_sig:
            i = pos + 1
            continue

        ptr += len(movie2_sig)

        if data[ptr:ptr+5] != b"\x00\x00\x00\x02\x02":
            i = pos + 1
            continue

        ptr += 5

        pointer2_dup_pos = ptr
        shift1 = calc_shift(old_pointer1)
        shift2 = calc_shift(old_pointer2)

        new_pointer1 = old_pointer1 + shift1
        new_pointer2 = old_pointer2 + shift2

        struct.pack_into("<I", data, pointer1_pos, new_pointer1)
        struct.pack_into("<I", data, pointer2_pos, new_pointer2)
        struct.pack_into("<I", data, pointer2_dup_pos, new_pointer2)

        i = pos + 1
        
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
