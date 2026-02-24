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

    choice_start = b"\x00\x01\x0F\x02"
    choice_end_1 = b"\x00\x00\x00\x0B"
    choice_end_2 = b"\x00\x00\x00\x0C"

    text_start = ("char" + "\x00").encode("utf-16le")
    text_end = "%K".encode("utf-16le")
    lf = "%LF".encode("utf-16le")

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

                text = data[str_start:str_end].decode("utf-16le", errors="ignore").replace("\\n", "\n")
                name = None
                pos_name = data.rfind(opcode_name, 0, i)
                if pos_name != -1:
                    lf_start = pos_name + 4
                    if data[lf_start:lf_start+len(lf)] == lf:
                        name_start = lf_start + len(lf)
                        name = data[name_start:i].decode("utf-16le", errors="ignore")

                entry = {"index": index}
                if name:
                    entry["name"] = name
                entry["text"] = text

                results.append(entry)

                i = str_end + len(text_end)
                continue

        if data[i:i+4] == choice_start:
            j = i + 4
            choice_dict = {}
            count = 1

            while j < size:
                if data[j:j+2] in (b"\x4B\x00", b"\x4C\x00"):
                    str_start = j + 2
                    end1 = data.find(choice_end_1, str_start)
                    end2 = data.find(choice_end_2, str_start)
                    candidates = [x for x in (end1, end2) if x != -1]

                    if not candidates:
                        break

                    str_end = min(candidates)
                    text = data[str_start:str_end].decode("utf-16le", errors="ignore")
                    choice_dict[f"choice {count}"] = text
                    count += 1

                    if str_end == end1:
                        j = str_end + len(choice_end_1)
                    else:
                        j = str_end + len(choice_end_2)
                    continue

                j += 1

            if choice_dict:
                results.append(choice_dict)

            i = j
            continue

        i += 1
    return results

def imWS2(original_path, json_path):
    with open(original_path, "rb") as f:
        data = bytearray(f.read())
    with open(json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    opcode_text = struct.pack(">I", 0x14)
    opcode_name = struct.pack(">I", 0x15)
    choice_start = b"\x00\x01\x0F\x02"

    choice_end_1 = b"\x00\x00\x00\x0B"
    choice_end_2 = b"\x00\x00\x00\x0C"

    text_start = ("char" + "\x00").encode("utf-16le")
    text_end = "%K".encode("utf-16le")
    lf = "%LF".encode("utf-16le")

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
    name_pointer = 0
    choice_entries = [
        e for e in entries
        if isinstance(e, dict) and "choice 1" in e
    ]
    choice_pointer = 0
    i = 0
    size = len(data)

    while i < size - 40:
        if data[i:i+4] == opcode_name and name_pointer < len(name_list):
            lf_start = i + 4
            if data[lf_start:lf_start+len(lf)] == lf:
                name_start = lf_start + len(lf)
                next_text = data.find(opcode_text, name_start)
                
                if next_text != -1:
                    name_end = next_text
                    new_bytes = name_list[name_pointer].encode("utf-16le")
                    data[name_start:name_end] = new_bytes
                    name_pointer += 1
                    i = name_start + len(new_bytes)
                    continue

        if data[i:i+4] == opcode_text:
            index = struct.unpack_from("<I", data, i + 4)[0]
            if index in index_map:
                entry = index_map[index]
                start = i + 8

                if data[start:start+len(text_start)] == text_start:
                    str_start = start + len(text_start)
                    str_end = data.find(text_end, str_start)
                    if str_end != -1 and "text" in entry:
                        new_bytes = entry["text"].replace("\n", "\\n").encode("utf-16le")
                        data[str_start:str_end] = new_bytes
                        i = str_start + len(new_bytes) + len(text_end)
                        continue

        if data[i:i+4] == choice_start and choice_pointer < len(choice_entries):
            j = i + 4
            entry = choice_entries[choice_pointer]
            count = 1

            while j < size:
                if data[j:j+2] in (b"\x4B\x00", b"\x4C\x00"):
                    key = f"choice {count}"
                    if key not in entry:
                        break

                    str_start = j + 2
                    end1 = data.find(choice_end_1, str_start)
                    end2 = data.find(choice_end_2, str_start)
                    candidates = [x for x in (end1, end2) if x != -1]

                    if not candidates:
                        break

                    str_end = min(candidates)
                    new_bytes = entry[key].encode("utf-16le")
                    data[str_start:str_end] = new_bytes

                    if str_end == end1:
                        j = str_start + len(new_bytes) + len(choice_end_1)
                    else:
                        j = str_start + len(new_bytes) + len(choice_end_2)

                    count += 1
                    continue

                j += 1

            choice_pointer += 1
            i = j
            continue

        i += 1

    output_path = original_path + ".new"
    with open(output_path, "wb") as f:
        f.write(data)
    print(f"Created: {output_path}")

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
        print(f"Extracted: {output_path}")
        
    elif mode == "-i" and len(sys.argv) == 4:
        original_path = sys.argv[2]
        json_path = sys.argv[3]
        imWS2(original_path, json_path)
    else:
        sys.exit(1)
