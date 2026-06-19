def gmult(a: int, b: int) -> int:
    p = 0
    a &= 0xFF
    b &= 0xFF
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p & 0xFF


def rcon(index: int) -> bytes:
    if index == 0:
        return b"\x00\x00\x00\x00"
    value = 1
    for _ in range(index - 1):
        value = gmult(value, 2)
    return bytes((value, 0, 0, 0))


def rot_word(word: bytes) -> bytes:
    return word[1:] + word[:1]


def sub_word(word: bytes, sbox: bytes) -> bytes:
    return bytes(sbox[b] for b in word)


def expand_ust_aes_key(seed: bytes, sbox: bytes) -> bytes:
    words = [bytearray(seed[index : index + 4]) for index in range(0, 32, 4)]
    nk = 8
    nb = 4
    nr = 14

    for index in range(nk, nb * (nr + 1)):
        temp = bytes(words[index - 1])
        if index % nk == 0:
            temp = bytes(
                a ^ b
                for a, b in zip(
                    sub_word(rot_word(temp), sbox), rcon(index // nk)
                )
            )
        elif index % nk == 4:
            temp = sub_word(temp, sbox)
        next_word = bytes(a ^ b for a, b in zip(words[index - nk], temp))
        words.append(bytearray(next_word))

    expanded = b"".join(bytes(word) for word in words)
    return expanded[8:40]
