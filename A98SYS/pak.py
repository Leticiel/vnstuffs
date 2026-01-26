import os, struct, sys

MAGIC = b"ADPACK32"
HEADER_SIZE = 16
ENTRY_SIZE = 32

def crc16_ccitt(data):
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) & 0xFFFF) ^ 0x1021 if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc & 0xFFFF

def ru32(f):
    b = f.read(4)
    return struct.unpack("<I", b)[0] if len(b) == 4 else 0

def wu32(f, v):
    f.write(struct.pack("<I", v))

def extract_adpack32(path):
    out_dir = os.path.splitext(os.path.basename(path))[0]

    try:
        f = open(path, "rb")
    except:
        return

    if f.read(8) != MAGIC:
        f.close()
        return

    f.read(4)
    n = ru32(f)

    ent = []
    for _ in range(n):
        name = f.read(26)
        f.read(2)
        off = ru32(f)
        nb = name.split(b"\x00", 1)[0]
        ent.append((nb.decode("utf-8", "ignore") or "..END", off))

    ent.sort(key=lambda x: x[1])

    f.seek(0, 2)
    end = f.tell()

    os.makedirs(out_dir, exist_ok=True)

    for i, (name, off) in enumerate(ent):
        if name == "..END":
            continue
        size = (ent[i + 1][1] if i + 1 < len(ent) else end) - off
        if size <= 0:
            continue

        out = os.path.join(out_dir, name)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        f.seek(off)
        open(out, "wb").write(f.read(size))

        print(name)

    f.close()

def pack_adpack32(input_dir):
    out_path = os.path.basename(os.path.normpath(input_dir)) + ".pak"

    files = []
    for r, _, fs in os.walk(input_dir):
        for fn in fs:
            rel = os.path.relpath(os.path.join(r, fn), input_dir).replace("\\", "/")
            if rel != "..END":
                files.append((rel, os.path.join(r, fn)))

    files.sort(key=lambda x: x[0].lower())

    off = HEADER_SIZE + (len(files) + 1) * ENTRY_SIZE
    ent = []

    for rel, full in files:
        nb = rel.encode("utf-8")
        if len(nb) > 26:
            continue
        size = os.path.getsize(full)
        ent.append((nb.ljust(26, b"\x00"), crc16_ccitt(nb), off, full))
        off += size

    ent.append((b"\x00" * 26, crc16_ccitt(b"..END"), off, None))

    try:
        f = open(out_path, "wb")
    except:
        return

    f.write(MAGIC + b"\x00\x00\x01\x00")
    wu32(f, len(ent))

    for name, crc, off, _ in ent:
        f.write(name)
        f.write(struct.pack("<H", crc))
        wu32(f, off)

    for _, _, _, p in ent:
        if p:
            with open(p, "rb") as g:
                while True:
                    c = g.read(1024 * 1024)
                    if not c:
                        break
                    f.write(c)

    f.close()
    print("Created", out_path)

if __name__ == "__main__":
    if len(sys.argv) == 3:
        if sys.argv[1] == "-e":
            extract_adpack32(sys.argv[2])
        elif sys.argv[1] == "-p":
            pack_adpack32(sys.argv[2])
