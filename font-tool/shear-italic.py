#!/usr/bin/env python3
# shear-italic.py
#
# Noto Sans CJK JP has no true italic (CJK fonts do not), so the italic and
# bold-italic style slots of the glyph pack are made by shearing the upright
# glyphs: x' = x + factor * y. This gives a faux-italic that matches the client's
# Latin italic slant. Bold is a real weight (Noto Bold), so it is left alone.
#
# This regenerates a pack's italic slots in place:
#   Ubuntu|0|1  from  Ubuntu|0|0   (italic from regular)
#   Ubuntu|1|1  from  Ubuntu|1|0   (bold-italic from bold)
#
# USAGE:
#   python shear-italic.py <pack.bin> [factor]
#
# factor defaults to -0.22 (about 12 degrees, matching Ubuntu Italic). It is the
# SWF y-down shear: negative leans the top of each glyph to the right.

import sys, zlib, pickle

# ---- SWF glyph SHAPE decode / shear / re-encode ----

class BitReader:
    def __init__(self, d): self.d = d; self.pos = 0
    def u(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.d[self.pos >> 3] >> (7 - (self.pos & 7))) & 1)
            self.pos += 1
        return v
    def sb(self, n):
        if n == 0: return 0
        v = self.u(n)
        return v - (1 << n) if v >> (n - 1) else v

class BitWriter:
    def __init__(self): self.bits = []
    def u(self, val, n):
        for i in range(n - 1, -1, -1): self.bits.append((val >> i) & 1)
    def sb(self, val, n):
        if n == 0: return
        if val < 0: val = (1 << n) + val
        self.u(val & ((1 << n) - 1), n)
    def bytes(self):
        while len(self.bits) % 8: self.bits.append(0)
        out = bytearray()
        for i in range(0, len(self.bits), 8):
            b = 0
            for j in range(8): b = (b << 1) | self.bits[i + j]
            out.append(b)
        return bytes(out)

def sbits(vals):
    n = 1
    while True:
        lo = -(1 << (n - 1)); hi = (1 << (n - 1)) - 1
        if all(lo <= v <= hi for v in vals): return n
        n += 1

def decode(shape):
    br = BitReader(shape); nf = br.u(4); nl = br.u(4); recs = []
    while True:
        if br.u(1) == 0:
            fl = br.u(5)
            if fl == 0: recs.append(('end',)); break
            move = None
            if fl & 1:
                mb = br.u(5); move = (br.sb(mb), br.sb(mb))
            f0 = br.u(nf) if fl & 2 else None
            f1 = br.u(nf) if fl & 4 else None
            ls = br.u(nl) if fl & 8 else None
            recs.append(('style', fl, move, f0, f1, ls))
        else:
            if br.u(1):
                nb = br.u(4) + 2
                if br.u(1): dx = br.sb(nb); dy = br.sb(nb)
                elif br.u(1): dx = 0; dy = br.sb(nb)
                else: dx = br.sb(nb); dy = 0
                recs.append(('line', dx, dy))
            else:
                nb = br.u(4) + 2
                recs.append(('curve', br.sb(nb), br.sb(nb), br.sb(nb), br.sb(nb)))
    return nf, nl, recs

def encode(nf, nl, recs):
    bw = BitWriter(); bw.u(nf, 4); bw.u(nl, 4)
    for r in recs:
        if r[0] == 'end':
            bw.u(0, 1); bw.u(0, 5); break
        if r[0] == 'style':
            _, fl, move, f0, f1, ls = r
            bw.u(0, 1); bw.u(fl, 5)
            if fl & 1:
                mb = sbits([move[0], move[1]]); bw.u(mb, 5); bw.sb(move[0], mb); bw.sb(move[1], mb)
            if fl & 2: bw.u(f0, nf)
            if fl & 4: bw.u(f1, nf)
            if fl & 8: bw.u(ls, nl)
        elif r[0] == 'line':
            _, dx, dy = r; nb = max(2, sbits([dx, dy]))
            bw.u(1, 1); bw.u(1, 1); bw.u(nb - 2, 4); bw.u(1, 1); bw.sb(dx, nb); bw.sb(dy, nb)
        else:
            _, cdx, cdy, adx, ady = r; nb = max(2, sbits([cdx, cdy, adx, ady]))
            bw.u(1, 1); bw.u(0, 1); bw.u(nb - 2, 4)
            bw.sb(cdx, nb); bw.sb(cdy, nb); bw.sb(adx, nb); bw.sb(ady, nb)
    return bw.bytes()

def shear(shape, s):
    nf, nl, recs = decode(shape)
    out = []
    for r in recs:
        if r[0] == 'style':
            _, fl, move, f0, f1, ls = r
            if move is not None:
                move = (int(round(move[0] + s * move[1])), move[1])
            out.append(('style', fl, move, f0, f1, ls))
        elif r[0] == 'line':
            _, dx, dy = r; out.append(('line', int(round(dx + s * dy)), dy))
        elif r[0] == 'curve':
            _, cdx, cdy, adx, ady = r
            out.append(('curve', int(round(cdx + s * cdy)), cdy, int(round(adx + s * ady)), ady))
        else:
            out.append(r)
    return encode(nf, nl, out)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python shear-italic.py <pack.bin> [factor]")
    path = sys.argv[1]
    factor = float(sys.argv[2]) if len(sys.argv) > 2 else -0.22
    pack = pickle.loads(zlib.decompress(open(path, 'rb').read()))
    plan = {'Ubuntu|0|1': 'Ubuntu|0|0', 'Ubuntu|1|1': 'Ubuntu|1|0'}
    for ital_style, upright_style in plan.items():
        if upright_style not in pack:
            print("skip %s (no %s in pack)" % (ital_style, upright_style)); continue
        pack[ital_style] = [(code, shear(shape, factor), adv) for code, shape, adv in pack[upright_style]]
        print("%s <- %s sheared by %.3f (%d glyphs)" % (ital_style, upright_style, factor, len(pack[ital_style])))
    open(path, 'wb').write(zlib.compress(pickle.dumps(pack), 9))
    print("wrote", path)


if __name__ == '__main__':
    main()
