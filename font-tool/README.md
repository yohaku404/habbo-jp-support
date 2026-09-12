# font-tool

The tool behind the font fix described in this repo's article (Part IV): it adds
Japanese glyphs to a HabboAirPlus-family client's embedded fonts **without**
destroying the Latin text. Latin stays crisp and pixel-snapped, and bold/italic
keep working, because the original Latin glyphs are kept byte for byte and only
the Japanese glyphs are appended.

Quick use:

```
python inject-jp-fonts.py <in.swf> <out.swf>
```

Full explanation, why JPEXS breaks the UI, how to rebuild the glyph pack, and the
font-licensing note are in **[TUTORIAL.md](TUTORIAL.md)**.

Contents:

- `inject-jp-fonts.py` the injector (matches fonts by name and style, not by id).
- `build-glyph-pack.py` rebuilds the glyph pack from your own font source.
- `jp-glyphs-by-style.bin` the Japanese glyph pack, keyed by font style.
- `TUTORIAL.md` the full guide.
