"""Minimal Word 97-2003 (.doc) text extractor - pure stdlib, no dependencies.

Parses the OLE/CFB container, reads the WordDocument stream's FIB, follows the
piece table in the table stream and decodes each piece. Good enough to recover
the prose of a normal report; not a full Word implementation.
"""

from __future__ import annotations

import struct
import sys

FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD
DIFSECT = 0xFFFFFFFC


class Ole:
    def __init__(self, blob: bytes) -> None:
        self.blob = blob
        if blob[:8] != bytes.fromhex("d0cf11e0a1b11ae1"):
            raise ValueError("not an OLE/CFB file")
        self.sector_shift = struct.unpack_from("<H", blob, 30)[0]
        self.mini_shift = struct.unpack_from("<H", blob, 32)[0]
        self.sector_size = 1 << self.sector_shift
        self.mini_size = 1 << self.mini_shift
        self.num_fat = struct.unpack_from("<I", blob, 44)[0]
        self.dir_start = struct.unpack_from("<I", blob, 48)[0]
        self.mini_cutoff = struct.unpack_from("<I", blob, 56)[0]
        self.mini_fat_start = struct.unpack_from("<I", blob, 60)[0]
        self.num_mini_fat = struct.unpack_from("<I", blob, 64)[0]
        self.difat_start = struct.unpack_from("<I", blob, 68)[0]
        self.num_difat = struct.unpack_from("<I", blob, 72)[0]
        self._build_fat()
        self._read_directory()
        self._build_mini_fat()

    def _sector(self, n: int) -> bytes:
        off = 512 + n * self.sector_size
        return self.blob[off : off + self.sector_size]

    def _chain(self, start: int, fat: list[int]) -> list[int]:
        out, cur, guard = [], start, 0
        while cur not in (ENDOFCHAIN, FREESECT) and cur < len(fat) and guard < 1_000_000:
            out.append(cur)
            cur = fat[cur]
            guard += 1
        return out

    def _build_fat(self) -> None:
        difat = list(struct.unpack_from("<109I", self.blob, 76))
        nxt = self.difat_start
        per = self.sector_size // 4 - 1
        for _ in range(self.num_difat):
            if nxt >= ENDOFCHAIN:
                break
            raw = self._sector(nxt)
            vals = list(struct.unpack_from(f"<{self.sector_size // 4}I", raw, 0))
            difat.extend(vals[:per])
            nxt = vals[per]
        fat: list[int] = []
        for s in difat[: self.num_fat]:
            if s >= ENDOFCHAIN:
                continue
            fat.extend(struct.unpack_from(f"<{self.sector_size // 4}I", self._sector(s), 0))
        self.fat = fat

    def _build_mini_fat(self) -> None:
        mfat: list[int] = []
        for s in self._chain(self.mini_fat_start, self.fat):
            mfat.extend(struct.unpack_from(f"<{self.sector_size // 4}I", self._sector(s), 0))
        self.mini_fat = mfat
        root = next(e for e in self.entries if e["type"] == 5)
        self.mini_stream = self._read_chain(root["start"], root["size"], self.fat)

    def _read_chain(self, start: int, size: int, fat: list[int]) -> bytes:
        buf = bytearray()
        for s in self._chain(start, fat):
            buf.extend(self._sector(s))
            if len(buf) >= size:
                break
        return bytes(buf[:size])

    def _read_mini(self, start: int, size: int) -> bytes:
        buf = bytearray()
        for s in self._chain(start, self.mini_fat):
            off = s * self.mini_size
            buf.extend(self.mini_stream[off : off + self.mini_size])
            if len(buf) >= size:
                break
        return bytes(buf[:size])

    def _read_directory(self) -> None:
        raw = self._read_chain(self.dir_start, 1 << 30, self.fat)
        self.entries = []
        for i in range(0, len(raw), 128):
            e = raw[i : i + 128]
            if len(e) < 128:
                break
            nlen = struct.unpack_from("<H", e, 64)[0]
            name = e[: max(0, nlen - 2)].decode("utf-16-le", "ignore")
            self.entries.append(
                {
                    "name": name,
                    "type": e[66],
                    "start": struct.unpack_from("<I", e, 116)[0],
                    "size": struct.unpack_from("<Q", e, 120)[0],
                }
            )

    def stream(self, name: str) -> bytes:
        for e in self.entries:
            if e["name"] == name and e["type"] == 2:
                if e["size"] < self.mini_cutoff:
                    return self._read_mini(e["start"], e["size"])
                return self._read_chain(e["start"], e["size"], self.fat)
        raise KeyError(name)


def extract_text(blob: bytes) -> str:
    ole = Ole(blob)
    wd = ole.stream("WordDocument")
    fib_flags = struct.unpack_from("<H", wd, 10)[0]
    which = (fib_flags >> 9) & 1  # fWhichTblStm
    tbl = ole.stream("1Table" if which else "0Table")

    fcMin = struct.unpack_from("<I", wd, 24)[0]
    ccpText = struct.unpack_from("<I", wd, 76)[0]
    ccpFtn = struct.unpack_from("<I", wd, 80)[0]
    ccpHdd = struct.unpack_from("<I", wd, 84)[0]

    fcClx = struct.unpack_from("<I", wd, 418)[0]
    lcbClx = struct.unpack_from("<I", wd, 422)[0]

    clx = tbl[fcClx : fcClx + lcbClx]
    # skip Prc entries to find the Pcdt (0x02) block
    i = 0
    pcdt = None
    while i < len(clx):
        if clx[i] == 0x01:
            cb = struct.unpack_from("<H", clx, i + 1)[0]
            i += 3 + cb
        elif clx[i] == 0x02:
            lcb = struct.unpack_from("<I", clx, i + 1)[0]
            pcdt = clx[i + 5 : i + 5 + lcb]
            break
        else:
            break

    if pcdt is None:  # no piece table -> single piece at fcMin
        raw = wd[fcMin : fcMin + ccpText * 2]
        return raw.decode("utf-16-le", "ignore")

    n = (len(pcdt) - 4) // 12
    cps = list(struct.unpack_from(f"<{n + 1}I", pcdt, 0))
    out = []
    for k in range(n):
        off = 4 * (n + 1) + k * 8
        fc = struct.unpack_from("<I", pcdt, off + 2)[0]
        compressed = bool(fc & 0x40000000)
        fc &= 0x3FFFFFFF
        cch = cps[k + 1] - cps[k]
        if compressed:
            chunk = wd[fc // 2 : fc // 2 + cch]
            out.append(chunk.decode("cp1252", "replace"))
        else:
            chunk = wd[fc : fc + cch * 2]
            out.append(chunk.decode("utf-16-le", "replace"))
    text = "".join(out)

    # Word control characters -> readable text
    text = text.replace("\r", "\n").replace("\x07", "\t|\t").replace("\x0b", "\n")
    text = text.replace("\x0c", "\n").replace("\x1e", "-").replace("\x13", "").replace("\x14", "").replace("\x15", "")
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch >= " ")
    return text


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    for path in sys.argv[1:]:
        with open(path, "rb") as f:
            blob = f.read()
        text = extract_text(blob)
        out_path = path + ".extracted.txt"
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"wrote {out_path} ({len(text)} chars)")


if __name__ == "__main__":
    main()
