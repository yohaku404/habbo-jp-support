#!/usr/bin/env python3
# build-glyph-pack.py
#
# Builds jp-glyphs-by-style.bin from a "donor" SWF that already contains the
# Japanese glyph set (for example a working HabboAir build with JP embedded).
#
# The pack is keyed by font STYLE, not font id, so it can be applied to any
# AirPlus-family client regardless of how its font ids are numbered:
#
#     key   = "<fontName>|<bold>|<italic>"   e.g. "Ubuntu|0|0", "Volter Bold|1|0"
#     value = list of (charCode, glyphShapeBytes, advance) for the JP glyphs
#
# A glyph counts as "Japanese" if its char code is not present in the same
# style's glyph set of the CLEAN baseline (so Latin/Latin-1 is excluded).
#
# Usage:
#   python build-glyph-pack.py <donor.swf> <clean-baseline.swf> [out.bin]
#
# out.bin defaults to jp-glyphs-by-style.bin next to this script.

import sys, os, zlib, struct, pickle
from collections import defaultdict

def load(p):
    r = open(p, 'rb').read()
    if r[:3] == b'CWS': return b'FWS' + r[3:8] + zlib.decompress(r[8:])
    return r
def he(d):
    p = 8; nb = d[p] >> 3; p += ((5 + nb*4)+7)//8; p += 4; return p
def tags(d):
    p = he(d); out = []
    while p < len(d):
        h = struct.unpack_from('<H', d, p)[0]; p += 2; t = h >> 6; l = h & 0x3f
        if l == 0x3f: l = struct.unpack_from('<I', d, p)[0]; p += 4
        out.append((t, d[p:p+l])); p += l
        if t == 0: break
    return out
def parse_font(b):
    o=2; fl=b[o]; o+=1; o+=1; nl=b[o]; o+=1
    name=b[o:o+nl].split(b'\x00')[0].decode('latin1'); o+=nl
    wO=bool(fl&0x08); hasL=bool(fl&0x80)
    ng=struct.unpack_from('<H',b,o)[0]; o+=2; ots=o
    if wO: offs=[struct.unpack_from('<I',b,o+4*i)[0] for i in range(ng)]; o+=4*ng; cto=struct.unpack_from('<I',b,o)[0]; o+=4
    else: offs=[struct.unpack_from('<H',b,o+2*i)[0] for i in range(ng)]; o+=2*ng; cto=struct.unpack_from('<H',b,o)[0]; o+=2
    shapes=[b[ots+offs[i]:ots+(offs[i+1] if i+1<ng else cto)] for i in range(ng)]
    cpos=ots+cto; codes=[struct.unpack_from('<H',b,cpos+2*i)[0] for i in range(ng)]
    q=cpos+2*ng; adv=[0]*ng
    if hasL: q+=6; adv=[struct.unpack_from('<h',b,q+2*i)[0] for i in range(ng)]
    return dict(fl=fl,name=name,ng=ng,codes=codes,shapes=shapes,adv=adv)
def style_key(f): return "%s|%d|%d" % (f['name'], f['fl']&1, (f['fl']>>1)&1)

donor = load(sys.argv[1]); clean = load(sys.argv[2])
out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jp-glyphs-by-style.bin')

# clean baseline codes per style (to know which codes are "Latin", i.e. not JP)
clean_codes = defaultdict(set)
for t,b in tags(clean):
    if t==75:
        f=parse_font(b); clean_codes[style_key(f)] |= set(f['codes'])

# collect JP glyph sets per style from donor; for a style with more than one
# font, pick the variant shared by the majority of its fonts.
import hashlib
cand = defaultdict(list)   # style -> list of (hash, {code:(shape,adv)})
for t,b in tags(donor):
    if t!=75: continue
    f=parse_font(b); sk=style_key(f)
    base=clean_codes.get(sk,set())
    jp={f['codes'][i]:(f['shapes'][i],f['adv'][i]) for i in range(f['ng']) if f['codes'][i] not in base}
    if not jp: continue
    h=hashlib.md5(b''.join(struct.pack('<H',c)+jp[c][0] for c in sorted(jp))).hexdigest()
    cand[sk].append((h,jp))

pack={}
for sk,lst in cand.items():
    counts=defaultdict(int)
    for h,_ in lst: counts[h]+=1
    best=max(counts, key=counts.get)               # majority variant
    jp=next(j for h,j in lst if h==best)
    pack[sk]=[(c,jp[c][0],jp[c][1]) for c in sorted(jp)]
    print("style %-16s -> %d JP glyphs (%d font(s), %d variant(s))" % (sk, len(pack[sk]), len(lst), len(counts)))

open(out,'wb').write(zlib.compress(pickle.dumps(pack),9))
print("wrote", out, os.path.getsize(out), "bytes")
