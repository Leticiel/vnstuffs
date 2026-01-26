import os
import struct
import sys
from lzf import compress, decompress

ENTRY_SIZE = 80
MAGIC = b"SHA_"
VERSION = 1

def read_u32(f):
    return struct.unpack("<I", f.read(4))[0]

def write_u32(f, v):
    f.write(struct.pack("<I", v))

def extract_pac(archive_path):
    base = os.path.splitext(os.path.basename(archive_path))[0]
    out_dir = base
    os.makedirs(out_dir, exist_ok=True)

    with open(archive_path, "rb") as f:
        magic = f.read(4)
        if magic != MAGIC:
            return

        version = read_u32(f)
        entry_count = read_u32(f)
        entries = []
        for _ in range(entry_count):
            raw = f.read(ENTRY_SIZE)
            name_len = raw[0]
            name_bytes = raw[1:64][:name_len]
            name = name_bytes.decode("utf-8", errors="replace")
            offset = struct.unpack("<I", raw[64:68])[0]
            size = struct.unpack("<I", raw[68:72])[0]
            entries.append((name, offset, size))

        for name, offset, size in entries:
            f.seek(offset)
            data = f.read(size)

            if name.lower().endswith((".txt", ".cmp")):
                try:
                    data = decompress(data)
                    print(f"Decompressed: {name}")
                except Exception as e:
                    print(f"Decompress failed")

            out_path = os.path.join(out_dir, name)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as out_f:
                out_f.write(data)

            print(f"Extracted: {name} ({len(data)})")
            
def pack_pac(folder):
    folder = os.path.normpath(folder)
    base = os.path.basename(folder)
    out_path = base + ".pac"

    files = []
    for root, _, filenames in os.walk(folder):
        for fn in filenames:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, folder).replace("\\", "/")
            files.append((rel, full))

    if not files:
        return

    files.sort(key=lambda x: x[0])

    entry_count = len(files)
    entries = []
    data_blobs = []
    offset = 4 + 4 + 4 + ENTRY_SIZE * entry_count

    for rel, full in files:
        with open(full, "rb") as f_in:
            data = f_in.read()

        if rel.lower().endswith((".txt", ".cmp")):
            try:
                data = compress(data)
                print(f"Compressed: {rel}")
            except Exception as e:
                pass

        size = len(data)
        entries.append((rel, offset, size))
        data_blobs.append(data)
        offset += size

    with open(out_path, "wb") as f:
        f.write(MAGIC)
        write_u32(f, VERSION)
        write_u32(f, entry_count)

        for name, off, size in entries:
            name_bytes = name.encode("cp932")
            if len(name_bytes) > 63:
                raise ValueError(f"Filename too long: {name}")

            raw = bytearray(ENTRY_SIZE)
            raw[0] = len(name_bytes)
            raw[1:1 + len(name_bytes)] = name_bytes
            raw[64:68] = struct.pack("<I", off)
            raw[68:72] = struct.pack("<I", size)
            f.write(raw)

        for data in data_blobs:
            f.write(data)

    print(f"Created: {out_path} ({entry_count} files)")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage:")
        print("  pac.py -e input.pac")
        print("  pac.py -p folder")
        sys.exit(1)

    mode = sys.argv[1]
    path = sys.argv[2]

    if mode == "-e":
        extract_pac(path)
    elif mode == "-p":
        pack_pac(path)
    else:
        sys.exit(1)
