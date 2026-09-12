# habbo-jp-font-tool

A tiny tool that adds Japanese glyphs to a HabboAirPlus-family client's embedded
fonts **without destroying the Latin text**. It is the missing piece behind
"Japanese renders, and the Latin UI still looks right": crisp, pixel-snapped, with
bold and italic intact.

If you have tried adding glyphs in JPEXS and watched the whole interface go soft
and slightly thick, this is why, and this is the fix.

---

## Why adding glyphs in JPEXS breaks the UI

The client renders text from embedded `DefineFont3` tags. Next to each one sits a
`DefineFontAlignZones` tag: the pixel-snapping hints that keep small text crisp.
There is also a Flags byte per font whose bits say, among other things, whether
that font is **bold** or **italic** (the client picks an embedded font by name
*and* those two bits, and it does not synthesize faux bold/italic for embedded
fonts).

When you add glyphs through the JPEXS font panel, it re-embeds the whole tag: it
reprocesses the Latin outlines and metrics and drops the align zones. The result
is soft, slightly thickened Latin everywhere, and bold/italic can collapse to
regular. The damage happens *because of* how the panel re-embeds, so there is no
setting inside JPEXS that avoids it.

## What this tool does instead

It edits the font tags at the byte level and never reprocesses the Latin. For each
embedded font whose style it has Japanese glyphs for, it:

- keeps every original glyph exactly as it is (Latin outlines, advances, and their
  align zones stay byte for byte);
- appends only the Japanese glyphs the font is missing;
- preserves the Flags byte's Bold/Italic bits and the language byte, and turns on
  the wide offset/code flags (needed once the glyph count grows);
- rebuilds the align-zones tag in the new order: the real zone for each original
  glyph, a neutral zone for each Japanese glyph.

It matches fonts by **name and style** (Ubuntu / Volter, regular / bold / italic /
bold-italic), not by font id, so it works on any AirPlus-family client no matter
how its font ids are numbered. It is additive and safe to re-run: it only ever
adds glyphs a font is missing.

---

## Requirements

Python 3. Nothing else, no libraries.

## Usage

```
python inject-jp-fonts.py <in.swf> <out.swf> [jp-glyphs-by-style.bin]
```

- `<in.swf>` your client SWF (compressed CWS or uncompressed FWS both work).
- `<out.swf>` where to write the patched SWF.
- the glyph pack defaults to `jp-glyphs-by-style.bin` next to the script.

Example:

```
python inject-jp-fonts.py HabboAir.swf HabboAir.jp.swf
```

It prints each font it touched and the glyph counts. If it says
"No fonts matched", the SWF either is already patched or is not an AirPlus-family
client with Ubuntu/Volter fonts.

Where to run it in a build: the font tables are independent of the ActionScript,
so run it either on the clean baseline once (then build your client from the
patched baseline) or on the final built SWF. Both work.

---

## The glyph pack

`jp-glyphs-by-style.bin` holds the Japanese glyph shapes and advances, keyed by
font style (`Ubuntu|0|0`, `Volter Bold|1|0`, and so on). It is a zlib-compressed
pickle.

You can rebuild it from any SWF that already carries a Japanese glyph set, keyed
against a clean baseline so Latin is excluded:

```
python build-glyph-pack.py <donor-with-jp.swf> <clean-baseline.swf> [out.bin]
```

The donor supplies the Japanese glyphs; the clean baseline tells the builder which
codes are Latin (and therefore not copied). If a style appears on several fonts
with slightly different glyph sets, the builder keeps the majority variant.

---

## Font licensing

The tool script is just byte manipulation and is free to share. The **glyph pack
is font data**: the actual Japanese glyph outlines.

The glyphs in `jp-glyphs-by-style.bin` come from three free fonts: the Ubuntu-style
glyphs are **Noto Sans CJK JP** (Adobe's **Source Han Sans JP**), OFL 1.1; the
Volter-style pixel letters/kana/kanji are **DotGothic16**, OFL 1.1; and about 95
Volter symbols (arrows, stars, and similar) are **PixelMplus**, M+ FONT LICENSE.
All permit redistribution, subsetting, and embedding, so this pack is
redistributable. The license texts are in [`OFL.txt`](OFL.txt) and
[`MPLUS-FONT-LICENSE.txt`](MPLUS-FONT-LICENSE.txt), with full attribution and proof
status in [`NOTICE.md`](NOTICE.md); keep them alongside the pack, and do not release
a modified font under the reserved names "Noto", "Source Han", or "DotGothic16".

If you build a pack from a different font with `build-glyph-pack.py`, check that
font's own license first. If it does not allow redistribution, ship only the tool
and `build-glyph-pack.py` and let each user build their own pack.

---

## Notes and limits

- It targets the Ubuntu and Volter families the AirPlus client uses. Other font
  names are left untouched.
- Japanese glyphs get a neutral align zone (the same approach the working builds
  use); Latin keeps its real zones, which is what keeps the UI crisp.
- The FontBoundsTable is written as empty rects and kerning as empty. Dynamic
  text fields do not need real bounds; if your client somehow relies on embedded
  kerning, note that this drops it.
- It does not touch ActionScript. Making the client actually type, send, and
  display Japanese is the code side, separate from this.
