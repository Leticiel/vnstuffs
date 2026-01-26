import os
import struct
import sys

MAGIC = b"\x44\x4C\x31\x2E\x30\x1A\x00\x00"  #"DL1.0 1A 00 00"

def lzss_decompress(data: bytes, output_size=None) -> bytes:
    FRAME_SIZE = 0x1000
    FRAME_FILL = 0x00
    FRAME_INIT_POS = 0xFEE
    frame = bytearray([FRAME_FILL] * FRAME_SIZE)
    frame_pos = FRAME_INIT_POS
    frame_mask = FRAME_SIZE - 1

    out = bytearray()
    i = 0
    size = len(data)

    while i < size:
        ctl = data[i]
        i += 1

        bit = 1
        while bit != 0x100 and i < size:
            if output_size is not None and len(out) >= output_size:
                return bytes(out)

            if ctl & bit:
                b = data[i]
                i += 1
                frame[frame_pos] = b
                frame_pos = (frame_pos + 1) & frame_mask
                out.append(b)
            else:
                if i + 1 > size:
                    break

                lo = data[i]
                hi = data[i + 1]
                i += 2
                offset = ((hi & 0xF0) << 4) | lo
                count = 3 + (hi & 0x0F)

                for _ in range(count):
                    if output_size is not None and len(out) >= output_size:
                        return bytes(out)

                    v = frame[offset]
                    offset = (offset + 1) & frame_mask
                    frame[frame_pos] = v
                    frame_pos = (frame_pos + 1) & frame_mask
                    out.append(v)

            bit <<= 1

    return bytes(out)

def exDL1(path):
    with open(path, "rb") as f:
        data = f.read()

    if data[:8] != MAGIC:
        print("Not a DL1 archive")
        return

    entry_count = struct.unpack_from("<H", data, 8)[0]
    index_offset = struct.unpack_from("<I", data, 10)[0]

    entries = []
    pos = index_offset

    for i in range(entry_count):
        name_raw = data[pos:pos + 12]
        size = struct.unpack_from("<I", data, pos + 12)[0]
        pos += 16

        name = name_raw.split(b"\x00", 1)[0].decode("ascii", errors="ignore")
        if not name:
            name = f"file_{i:04d}.bin"

        entries.append((name, size))

    base = os.path.splitext(os.path.basename(path))[0]
    out_dir = base
    os.makedirs(out_dir, exist_ok=True)
    data_pos = 0x10

    for name, size in entries:
        file_data = data[data_pos:data_pos + size]
        data_pos += size

        if file_data.startswith(b"LZ") and len(file_data) >= 10:
            unpacked_size = struct.unpack_from("<I", file_data, 6)[0]
            comp_stream = file_data[10:]
            try:
                file_data = lzss_decompress(comp_stream, unpacked_size)
                print(f"{name}  (LZSS)")
            except:
                print(f"{name}  (LZSS failed)")
        else:
            print(name)

        out_path = os.path.join(out_dir, name)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        with open(out_path, "wb") as out_f:
            out_f.write(file_data)

def packDL1(folder):
    files = []

    for root, _, filenames in os.walk(folder):
        for fn in filenames:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, folder).replace("\\", "/")
            files.append((rel, full))

    files.sort()

    entry_count = len(files)
    header = bytearray()
    header += MAGIC
    header += struct.pack("<H", entry_count)
    header += b"\x00\x00\x00\x00"
    header += b"\x00" * 2

    data_blob = bytearray()
    index = bytearray()

    for rel, full in files:
        name = os.path.basename(rel).encode("ascii", errors="ignore")[:12]
        name = name.ljust(12, b"\x00")

        with open(full, "rb") as f:
            raw = f.read()

        size = len(raw)

        index += name
        index += struct.pack("<I", size)

        data_blob += raw

    index_offset = 0x10 + len(data_blob)

    struct.pack_into("<I", header, 10, index_offset)

    out_path = folder.rstrip("/\\") + ".dl1"

    with open(out_path, "wb") as f:
        f.write(header)
        f.write(data_blob)
        f.write(index)

    print(f"Created {out_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage:")
        print("  dl1.py -e <input.dl1>")
        print("  dl1.py -p <input_folder>")
        sys.exit(0)

    mode = sys.argv[1]
    target = sys.argv[2]

    if mode == "-e":
        exDL1(target)
    elif mode == "-p":
        packDL1(target)
    else:
        sys.exit(0)
