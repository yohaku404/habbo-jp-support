# Font attribution and license notice

The Japanese glyphs in `jp-glyphs-by-style.bin` (and in any patched SWF this tool
produces) are taken from:

**Noto Sans CJK JP** (also distributed by Adobe as **Source Han Sans JP**)
Copyright 2014-2021 Adobe (https://www.adobe.com/), with Google.
Licensed under the **SIL Open Font License, Version 1.1**.

The full license text is in [`OFL.txt`](OFL.txt) in this folder, and is also
available at https://openfontlicense.org and https://github.com/notofonts/noto-cjk.

## What this means for reuse

The SIL OFL 1.1 permits redistribution, modification (including subsetting), and
embedding. This glyph pack is a subset of Noto Sans CJK JP, redistributed under the
same license, with the notice kept as required.

Reserved Font Names: under the OFL you may not release a modified font under the
names "Noto" or "Source Han". This pack is glyph data for embedding, not a font
released under those names, so it does not use them.

## Rebuilding from your own font

If you would rather not rely on this pack, `build-glyph-pack.py` lets you build your
own from any font you are entitled to use. Noto Sans CJK JP is a good default: it is
free, OFL-licensed, and covers the Japanese ranges this tool needs.
