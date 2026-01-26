HLOG = 14
HSIZE = 1 << HLOG
MAX_LIT = 32
MAX_OFF = 1 << 13
MAX_REF = (1 << 8) + (1 << 3)

HashTable = [0] * HSIZE

def u32(x):
    return x & 0xFFFFFFFF

def hash_index(hval: int) -> int:
    x = u32(hval ^ u32(hval << 5))
    shift = u32(24 - HLOG - u32(hval * 5)) & 31
    return (x >> shift) & (HSIZE - 1)

def lzf_compress(input_bytes: bytes, output: bytearray) -> int:
    length = len(input_bytes)
    out_len = len(output)

    for i in range(HSIZE):
        HashTable[i] = 0

    ip = 0
    op = 0
    lit = 0

    if length >= 2:
        hval = u32((input_bytes[0] << 8) | input_bytes[1])
    else:
        hval = 0

    while True:
        if ip < length - 2:
            hval = u32((hval << 8) | input_bytes[ip + 2])
            hslot = hash_index(hval)

            ref = HashTable[hslot]
            HashTable[hslot] = ip

            off = ip - ref - 1

            if (
                ref > 0
                and off < MAX_OFF
                and ip + 4 < length
                and input_bytes[ref] == input_bytes[ip]
                and input_bytes[ref + 1] == input_bytes[ip + 1]
                and input_bytes[ref + 2] == input_bytes[ip + 2]
            ):
                max_len = min(MAX_REF, length - ip - 2)

                if op + lit + 1 + 3 >= out_len:
                    return 0

                l = 2
                while l < max_len and input_bytes[ref + l] == input_bytes[ip + l]:
                    l += 1

                if lit:
                    output[op] = lit - 1
                    op += 1
                    for i in range(lit):
                        output[op] = input_bytes[ip - lit + i]
                        op += 1
                    lit = 0

                l -= 2
                ip += 1

                if l < 7:
                    output[op] = ((off >> 8) + (l << 5)) & 0xFF
                    op += 1
                else:
                    output[op] = ((off >> 8) + 0xE0) & 0xFF
                    op += 1
                    output[op] = (l - 7) & 0xFF
                    op += 1

                output[op] = off & 0xFF
                op += 1

                ip += l - 1

                hval = u32((input_bytes[ip] << 8) | input_bytes[ip + 1])
                hval = u32((hval << 8) | input_bytes[ip + 2])
                HashTable[hash_index(hval)] = ip
                ip += 1

                hval = u32((hval << 8) | input_bytes[ip + 2])
                HashTable[hash_index(hval)] = ip
                ip += 1
                continue

        elif ip == length:
            break

        lit += 1
        ip += 1

        if lit == MAX_LIT:
            if op + 1 + MAX_LIT >= out_len:
                return 0

            output[op] = MAX_LIT - 1
            op += 1
            for i in range(MAX_LIT):
                output[op] = input_bytes[ip - MAX_LIT + i]
                op += 1
            lit = 0

    if lit:
        if op + 1 + lit >= out_len:
            return 0

        output[op] = lit - 1
        op += 1
        for i in range(lit):
            output[op] = input_bytes[ip - lit + i]
            op += 1

    return op

def lzf_decompress(input_bytes: bytes, output: bytearray) -> int:
    in_len = len(input_bytes)
    out_len = len(output)

    ip = 0
    op = 0

    while True:
        ctrl = input_bytes[ip]
        ip += 1

        if ctrl < MAX_LIT:
            ctrl += 1
            if op + ctrl > out_len:
                return 0

            for _ in range(ctrl):
                output[op] = input_bytes[ip]
                ip += 1
                op += 1
        else:
            length = ctrl >> 5
            ref = op - ((ctrl & 31) << 8) - 1

            if length == 7:
                length += input_bytes[ip]
                ip += 1

            ref -= input_bytes[ip]
            ip += 1

            if op + length + 2 > out_len:
                return 0
            if ref < 0:
                return 0

            output[op] = output[ref]
            op += 1
            ref += 1

            output[op] = output[ref]
            op += 1
            ref += 1

            while length:
                output[op] = output[ref]
                op += 1
                ref += 1
                length -= 1

        if ip >= in_len:
            return op

def compress(data: bytes) -> bytes:
    size = len(data) * 2
    while True:
        out = bytearray(size)
        n = lzf_compress(data, out)
        if n != 0:
            return bytes(out[:n])
        size *= 2

def decompress(data: bytes) -> bytes:
    size = len(data) * 2
    while True:
        out = bytearray(size)
        n = lzf_decompress(data, out)
        if n != 0:
            return bytes(out[:n])
        size *= 2
