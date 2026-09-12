#!/usr/bin/env python3
# inject-jp-fonts.py  (general, style-based)
#
# Adds the Japanese glyph set to a HabboAirPlus-family SWF's embedded fonts
# WITHOUT reprocessing the Latin outlines, so Latin text stays crisp and
# bold/italic keep working.
#
# It matches fonts by NAME + style (bold/italic), not by font id, so it works on
# any AirPlus-family client regardless of how its font ids are numbered. For each
# embedded font whose style has Japanese glyphs in the pack, it keeps every
# original glyph byte for byte and appends only the JP glyphs the font is missing.
#
# WHY A SEPARATE TOOL (not JPEXS "add glyphs"): the client renders text from
# binary DefineFont3 tags with a parallel DefineFontAlignZones tag that pixel-
# snaps small text. Adding glyphs through JPEXS reprocesses the Latin metrics and
# drops the align zones, turning the UI soft and flattening bold/italic. This
# tool edits the tags at the byte level instead.
#
# WHAT IT PRESERVES, per font it touches:
#   - every original glyph (Latin outlines, advances, and their align zones);
#   - the Flags byte's Bold/Italic bits and the LanguageCode byte;
#   - forces WideOffsets/WideCodes/HasLayout on (needed once glyph count grows).
# It rebuilds the align-zones tag in the new code-sorted order: the real zone for
# each original glyph, a neutral zone for each appended JP glyph.
#
# It is idempotent: re-running on an already-patched SWF changes nothing.
#
# USAGE:
#   python inject-jp-fonts.py <in.swf> <out.swf> [jp-glyphs-by-style.bin]
#
# The pack defaults to jp-glyphs-by-style.bin next to this script. Build a pack
# from a different glyph source with build-glyph-pack.py.

import sys, os, zlib, struct, pickle

NEUTRAL_ZONE = bytes([2]) + b'\x00' * 8 + bytes([0])   # NumZoneData=2, zeroed, mask 0


def load_swf(path):
    raw = open(path, 'rb').read()
    if raw[:3] == b'CWS':
        return b'FWS' + raw[3:8] + zlib.decompress(raw[8:]), raw[3]
    if raw[:3] == b'FWS':
        return raw, raw[3]
    raise SystemExit("Not an FWS/CWS SWF: %s" % path)


def header_end(d):
    p = 8
    nbits = d[p] >> 3
    p += ((5 + nbits * 4) + 7) // 8
    p += 4
    return p


def read_tags(d):
    p = header_end(d)
    out = []
    while p < len(d):
        h = struct.unpack_from('<H', d, p)[0]; p += 2
        tag = h >> 6; ln = h & 0x3f
        if ln == 0x3f:
            ln = struct.unpack_from('<I', d, p)[0]; p += 4
        out.append((tag, d[p:p + ln])); p += ln
        if tag == 0:
            break
    return out


def build_tag(tag, body):
    ln = len(body)
    if ln < 0x3f:
        return struct.pack('<H', (tag << 6) | ln) + body
    return struct.pack('<H', (tag << 6) | 0x3f) + struct.pack('<I', ln) + body


def parse_font(b):
    o = 2
    flags = b[o]; o += 1
    lang = b[o]; o += 1
    has_layout = bool(flags & 0x80)
    wide_off = bool(flags & 0x08)
    name_len = b[o]; o += 1
    name_raw = b[o:o + name_len]; o += name_len
    ng = struct.unpack_from('<H', b, o)[0]; o += 2
    ots = o
    if wide_off:
        offs = [struct.unpack_from('<I', b, o + 4 * i)[0] for i in range(ng)]; o += 4 * ng
        cto = struct.unpack_from('<I', b, o)[0]; o += 4
    else:
        offs = [struct.unpack_from('<H', b, o + 2 * i)[0] for i in range(ng)]; o += 2 * ng
        cto = struct.unpack_from('<H', b, o)[0]; o += 2
    shapes = [b[ots + offs[i]:ots + (offs[i + 1] if i + 1 < ng else cto)] for i in range(ng)]
    cpos = ots + cto
    codes = [struct.unpack_from('<H', b, cpos + 2 * i)[0] for i in range(ng)]
    q = cpos + 2 * ng
    asc = desc = lead = 0
    adv = [0] * ng
    if has_layout:
        asc = struct.unpack_from('<h', b, q)[0]; q += 2
        desc = struct.unpack_from('<h', b, q)[0]; q += 2
        lead = struct.unpack_from('<h', b, q)[0]; q += 2
        adv = [struct.unpack_from('<h', b, q + 2 * i)[0] for i in range(ng)]
    name = name_raw.split(b'\x00')[0].decode('latin1')
    return dict(flags=flags, lang=lang, name_raw=name_raw, name=name, ng=ng,
                codes=codes, shapes=shapes, adv=adv, asc=asc, desc=desc, lead=lead)


def parse_align_zones(b):
    csm = b[2]
    recs = []
    o = 3
    while o < len(b):
        nzd = b[o]
        rl = 1 + 4 * nzd + 1
        recs.append(b[o:o + rl])
        o += rl
    return csm, recs


def serialize_font(fid, orig_flags, lang, name_raw, glyphs, asc, desc, lead):
    ng = len(glyphs)
    flags = (orig_flags & (0x01 | 0x02 | 0x10 | 0x20 | 0x40)) | 0x80 | 0x08 | 0x04
    head = struct.pack('<H', fid) + bytes([flags, lang, len(name_raw)]) + name_raw + struct.pack('<H', ng)
    offtab_size = ng * 4 + 4
    offs = []
    acc = offtab_size
    for g in glyphs:
        offs.append(acc)
        acc += len(g['shape'])
    cto = acc
    ot = b''.join(struct.pack('<I', x) for x in offs) + struct.pack('<I', cto)
    shp = b''.join(g['shape'] for g in glyphs)
    ct = b''.join(struct.pack('<H', g['code']) for g in glyphs)
    layout = struct.pack('<hhh', asc, desc, lead) + b''.join(struct.pack('<h', g['adv']) for g in glyphs)
    bounds = bytes((ng * 5 + 7) // 8)
    kern = struct.pack('<H', 0)
    return head + ot + shp + ct + layout + bounds + kern


def style_key(f):
    return "%s|%d|%d" % (f['name'], f['flags'] & 1, (f['flags'] >> 1) & 1)


def main():
    if len(sys.argv) < 3:
        raise SystemExit("usage: python inject-jp-fonts.py <in.swf> <out.swf> [jp-glyphs-by-style.bin]")
    in_swf, out_swf = sys.argv[1], sys.argv[2]
    pack_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jp-glyphs-by-style.bin')

    pack = pickle.loads(zlib.decompress(open(pack_path, 'rb').read()))
    d, ver = load_swf(in_swf)
    tags = read_tags(d)

    align_by_fid = {}
    for t, b in tags:
        if t == 73:
            align_by_fid[struct.unpack_from('<H', b, 0)[0]] = parse_align_zones(b)

    new_font = {}
    new_az = {}
    touched = 0
    for t, b in tags:
        if t != 75:
            continue
        fid = struct.unpack_from('<H', b, 0)[0]
        pf = parse_font(b)
        sk = style_key(pf)
        jp = pack.get(sk)
        if not jp:
            continue
        az_csm, az_recs = align_by_fid.get(fid, (1, []))
        code2az = {pf['codes'][i]: (az_recs[i] if i < len(az_recs) else NEUTRAL_ZONE)
                   for i in range(pf['ng'])}
        seen = set(pf['codes'])
        glyphs = [{'code': pf['codes'][i], 'shape': pf['shapes'][i], 'adv': pf['adv'][i]}
                  for i in range(pf['ng'])]
        added = 0
        for code, shape, adv in jp:
            if code not in seen:
                glyphs.append({'code': code, 'shape': shape, 'adv': adv})
                seen.add(code)
                added += 1
        if added == 0:
            continue   # already had them (idempotent)
        glyphs.sort(key=lambda g: g['code'])
        new_font[fid] = serialize_font(fid, pf['flags'], pf['lang'], pf['name_raw'],
                                       glyphs, pf['asc'], pf['desc'], pf['lead'])
        new_az[fid] = (struct.pack('<H', fid) + bytes([az_csm]) +
                       b''.join(code2az.get(g['code'], NEUTRAL_ZONE) for g in glyphs))
        touched += 1
        print("font %5d  %-16s  %d + %d JP = %d" % (fid, sk, pf['ng'], added, len(glyphs)))

    if touched == 0:
        raise SystemExit("No fonts matched the pack's styles (already patched, or not an AirPlus-family SWF).")

    out = []
    for t, b in tags:
        if t == 75 and struct.unpack_from('<H', b, 0)[0] in new_font:
            fid = struct.unpack_from('<H', b, 0)[0]
            out.append((75, new_font[fid]))
            out.append((73, new_az[fid]))
            continue
        if t == 73 and struct.unpack_from('<H', b, 0)[0] in new_font:
            continue
        out.append((t, b))

    prefix = d[8:header_end(d)]
    body = prefix + b''.join(build_tag(t, b) for t, b in out)
    data = b'CWS' + bytes([ver]) + struct.pack('<I', 8 + len(body)) + zlib.compress(body, 9)
    open(out_swf, 'wb').write(data)
    print("touched %d font(s); wrote %s (%d bytes)" % (touched, out_swf, len(data)))


if __name__ == '__main__':
    main()
