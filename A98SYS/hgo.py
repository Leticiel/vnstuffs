import sys, os, json

MES_STARTS     = [b'\x00\x03\x01', b'\x02\x03\x01']
MES_ENDS       = [b'\x00\x03\x02', b'\x00\x03\x03', b'\x00\x03\x04']
CHOICE_STARTS = [b'\x04\x81']
CHOICE_ENDS   = [b'\x00\x01\x01']
SEQUENCE      = b'\x7C\x00\x03\x02\x03\x01'
REPLACEMENT   = b'\x20'

def decode_raw(raw):
    for enc in ("ascii", "shift_jis"):
        try:
            return raw.decode(enc)
        except:
            pass
    return None

def extract_blocks(data, starts, ends, out):
    for s in starts:
        i = 0
        while True:
            i = data.find(s, i)
            if i == -1:
                break

            epos = -1
            esel = None
            for e in ends:
                p = data.find(e, i + len(s))
                if p != -1:
                    epos, esel = p, e
                    break

            if epos == -1:
                i += 1
                continue

            raw = data[i + len(s):epos]
            txt = decode_raw(raw)
            if txt:
                out.append({"Original": txt, "Translate": ""})

            i = epos + len(esel)

def extract_hgo(input_hgo, output_json):
    data = open(input_hgo, "rb").read().replace(SEQUENCE, REPLACEMENT)
    out = []

    extract_blocks(data, MES_STARTS, MES_ENDS, out)
    extract_blocks(data, CHOICE_STARTS, CHOICE_ENDS, out)

    json.dump(out, open(output_json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"[+] Extracted {len(out)} strings -> {output_json}")

def read_json(path):
    d = {}
    for e in json.load(open(path, "r", encoding="utf-8")):
        o, t = e.get("Original"), e.get("Translate")
        if o and t:
            d[o] = t
    return d

def replace_strings(data, starts, ends, trans):
    out = bytearray()
    i, n = 0, len(data)

    while i < n:
        pos, seq = -1, None
        for s in starts:
            p = data.find(s, i)
            if p != -1 and (pos == -1 or p < pos):
                pos, seq = p, s

        if pos == -1:
            out.extend(data[i:])
            break

        epos, esel = -1, None
        for e in ends:
            p = data.find(e, pos + len(seq))
            if p != -1:
                epos, esel = p, e
                break

        if epos == -1:
            out.extend(data[i:])
            break

        out.extend(data[i:pos + len(seq)])
        raw = data[pos + len(seq):epos]

        try:
            o = raw.decode("shift_jis")
            out.extend(trans.get(o, o).encode("shift_jis"))
        except:
            out.extend(raw)

        out.extend(esel)
        i = epos + len(esel)

    return bytes(out)

def import_hgo(input_hgo, input_json, output_hgo):
    data = open(input_hgo, "rb").read().replace(SEQUENCE, REPLACEMENT)
    trans = read_json(input_json)

    data = replace_strings(data, MES_STARTS, MES_ENDS, trans)
    data = replace_strings(data, CHOICE_STARTS, CHOICE_ENDS, trans)

    open(output_hgo, "wb").write(data)
    print(f"[+] Imported -> {output_hgo}")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("-e", "-i"):
        print("Usage:")
        print("  hgo.py -e <input.hgo>")
        print("  hgo.py -i <input.json>")
        sys.exit(1)

    mode, path = sys.argv[1], sys.argv[2]

    if mode == "-e":
        if not os.path.isfile(path):
            print("File not found:", path)
            sys.exit(1)
        extract_hgo(path, os.path.splitext(path)[0] + ".json")

    else:
        if not os.path.isfile(path):
            print("File not found:", path)
            sys.exit(1)

        base = os.path.splitext(os.path.basename(path))[0]
        input_hgo = os.path.join(os.path.dirname(path), base + ".hgo")
        if not os.path.isfile(input_hgo):
            print("Not found:", input_hgo)
            sys.exit(1)

        outdir = os.path.join(os.path.dirname(input_hgo), "new")
        os.makedirs(outdir, exist_ok=True)

        import_hgo(input_hgo, path,
                   os.path.join(outdir, os.path.basename(input_hgo)))

if __name__ == "__main__":
    main()
