import os
import struct
import sys

MAGIC = b"PACK"
ENTRY_SIZE = 136
NAME_SIZE = 128
XOR_KEY = 0xC5


def xor_bytes(data):
    return bytes(b ^ XOR_KEY for b in data)

def extract_archive(path):
    base = os.path.splitext(os.path.basename(path))[0]
    out_dir = os.path.join(os.path.dirname(path), base)
    os.makedirs(out_dir, exist_ok=True)

    list_path = os.path.join(out_dir, "list.txt")
    order = []

    with open(path, "rb") as f:
        if f.read(4) != MAGIC:
            raise Exception("Invalid magic")

        count = struct.unpack("<I", f.read(4))[0]
        index = xor_bytes(f.read(count * ENTRY_SIZE))

        entries = []
        for i in range(count):
            e = index[i * ENTRY_SIZE:(i + 1) * ENTRY_SIZE]
            name = e[:NAME_SIZE].split(b"\x00", 1)[0].decode("utf-8", "ignore")
            size = struct.unpack("<I", e[NAME_SIZE:NAME_SIZE + 4])[0]
            offset = struct.unpack("<I", e[NAME_SIZE + 4:NAME_SIZE + 8])[0]
            entries.append((name, size, offset))
            order.append(name)

        for name, size, offset in entries:
            f.seek(offset)
            data = xor_bytes(f.read(size))
            out = os.path.join(out_dir, name)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as o:
                o.write(data)
            print(f"[+] {name}")

    with open(list_path, "w", encoding="utf-8") as lf:
        for n in order:
            lf.write(n + "\n")

    print("Extracted:", out_dir)

def pack_folder(folder):
    folder = os.path.abspath(folder)
    base = os.path.basename(folder.rstrip("/\\"))
    out_path = os.path.join(os.path.dirname(folder), base + ".pkd")
    list_path = os.path.join(folder, "list.txt")
    files = []

    if os.path.isfile(list_path):
        with open(list_path, "r", encoding="utf-8") as lf:
            for line in lf:
                rel = line.strip()
                if not rel:
                    continue
                full = os.path.join(folder, rel)
                if not os.path.isfile(full):
                    raise Exception(f"Missing file listed in list.txt: {rel}")
                files.append((rel, full))
    else:
        for root, _, names in os.walk(folder):
            for n in names:
                if n.lower() == "list.txt":
                    continue
                full = os.path.join(root, n)
                rel = os.path.relpath(full, folder).replace("\\", "/")
                files.append((rel, full))
        files.sort()

    count = len(files)
    index = bytearray()
    data = bytearray()
    offset = 8 + count * ENTRY_SIZE

    for rel, full in files:
        with open(full, "rb") as rf:
            raw = rf.read()

        name = rel.encode("utf-8")[:NAME_SIZE]
        name += b"\x00" * (NAME_SIZE - len(name))
        index += name
        index += struct.pack("<I", len(raw))
        index += struct.pack("<I", offset)
        index += b"\x00" * (ENTRY_SIZE - len(name) - 8)

        data += xor_bytes(raw)
        offset += len(raw)

        print(f"[+] {rel}")

    with open(out_path, "wb") as o:
        o.write(MAGIC)
        o.write(struct.pack("<I", count))
        o.write(xor_bytes(index))
        o.write(data)

    print("Done:", out_path)

def main():
    if len(sys.argv) != 3:
        print("Usage:")
        print("    pkd.py -e <input.pkd>")
        print("    pkd.py -p <folder>")
        return

    if sys.argv[1] == "-e":
        extract_archive(sys.argv[2])
    elif sys.argv[1] == "-p":
        pack_folder(sys.argv[2])
    else:
        print("    pkd.py -e <input.pkd>")
        print("    pkd.py -p <folder>")

if __name__ == "__main__":
    main()
