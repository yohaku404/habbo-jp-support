# Font attribution and license notice

The Japanese glyphs in `jp-glyphs-by-style.bin` (and in any patched SWF this tool
produces) come from the three fonts below. All permit redistribution and
embedding. License texts are in `LICENSE-OFL.txt` (Noto and DotGothic16) and
`LICENSE-MPlus.txt` (PixelMplus); keep both alongside the pack.

The pack matches the HabboAirPlus client this project ships (the one the article
describes), so its font mix is that client's.

## Ubuntu-family styles (Ubuntu, UbuntuCondensed, UbuntuMedium, UbuntuThick)

**Noto Sans CJK JP** (distributed by Adobe as **Source Han Sans JP**)
Copyright 2014-2021 Adobe (https://www.adobe.com/), with Google.
**SIL Open Font License 1.1** (see `LICENSE-OFL.txt`).

Verified: the regular-weight glyphs match Noto Sans CJK JP geometrically (bounding
boxes identical across sampled kana and kanji, allowing for the SWF and TrueType
axis conventions). The other weights and the italics are the corresponding Noto
weights.

## Volter and Volter Bold styles

Two sources, both free:

- letters, kana, and kanji: **DotGothic16**
  Copyright 2020 The DotGothic16 Project Authors (Fontworks).
  **SIL Open Font License 1.1** (see `LICENSE-OFL.txt`).
- symbols and special punctuation (arrows, stars, the reference mark, degree and
  currency signs, gender and suit symbols, and similar; about 95 glyphs):
  **PixelMplus**
  Copyright (C) 2013 itouhiro; Copyright (C) 2002-2013 M+ FONTS PROJECT.
  **M+ FONT LICENSE** (see `LICENSE-MPlus.txt`).

Verified: the regular Volter letters/kana/kanji match DotGothic16 geometrically,
and the ~95 symbol glyphs match a PixelMplus weight and not DotGothic16 (they are
most consistent with PixelMplus 10 Regular; the M+ FONT LICENSE is the same across
PixelMplus weights).

## Reserved names

Under the OFL you may not release a modified font under the reserved names
"Noto", "Source Han", or "DotGothic16". This pack is glyph data for embedding, not
a font released under those names, so it does not use them.

## Rebuilding from your own fonts

`build-glyph-pack.py` lets you build your own pack from fonts you are entitled to
use, if you would rather not rely on this one.
