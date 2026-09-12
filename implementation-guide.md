# Implementing Japanese Language Support in HabboAirPlus

*An implementation guide for adding Japanese language support to a HabboAirPlus-family client.
It was written for the HabboAirPlus maintainer and is shared here for anyone working on a fork.
Each section is self-contained, so the pieces can be added one at a time, in any order. Class
and method names are from a recent decompile; adapt them to your own source. Everything here is
client-side. No server changes, no new packets.*

---

## 0. Design principles (read first)

Three ideas make the whole thing work and stay maintainable:

1. **Overlay, never redefine.** Japanese is applied by *overwriting individual localization
   values* (`updateLocalization`), never by swapping the localization definition
   (`activateLocalizationDefinition`), which corrupts the client.

2. **Key on what's shared across hotels.** Localization keys are identical on every hotel;
   only the *values* differ by language. Catalog **pageNames** are stable across hotels;
   **pageIds** are not. So translate by key / by pageName, and one translation set becomes
   universal instead of per server.

3. **Never put Japanese on the wire.** The server strips non Latin characters from chat,
   quests, and messages. All Japanese that travels the network is encoded to Latin first and
   decoded client side.

4. **Be extra careful editing widely shared classes, and check how many layers deep the
   real behavior lives.** Several of the client's UI components (generic text fields,
   generic input widgets) are reused across dozens of unrelated windows, sometimes wrapping
   each other in layers. A fix that's correct for one specific screen but applied directly
   to a shared class, unconditionally, changes behavior everywhere that class is used, not
   just the screen being worked on; symptoms can show up far from the actual edit, since
   fixing something in one dialog can silently break or truncate text in completely
   unrelated windows. When a fix only needs to apply to one specific usage, prefer an
   opt-in flag the shared class defaults to off, set explicitly only where it's needed,
   over changing the shared class's default behavior. It's also worth confirming which
   layer actually owns the behavior being changed before writing the fix: a higher-level
   wrapper class may expose the property you need to change, but the code that actually
   needs to react to it can live one or more layers further down, in whatever lower-level
   component the wrapper delegates to internally. A flag added only at the wrapper layer
   can compile cleanly and appear to do nothing, because the layer that would actually act
   on it never sees the flag at all. And after any edit to a shared class, it's worth
   spot-checking a couple of unrelated screens that use it too, not just the one screen the
   change was meant for.

The whole thing is toggled with `:lang jp` and persisted so it survives a reboot.

---

## 1. The boot switch

**Goal:** `:lang jp` makes the client reboot into Japanese; any other language reverts it.

- Persist a `bootLang` field in a `SharedObject` (e.g. `SharedObject.getLocal("HabboAirPlus","/")`).
  `:lang jp` sets `data.bootLang = "jp"` and flushes; other languages clear it.
- Add a helper `shouldBootJapanese()` that returns `true` only when `bootLang == "jp"`.
- **Apply Japanese before the UI is built.** The right hook is
  `HabboLocalizationManager.onLocalizationLoaded`: when `shouldBootJapanese()` is true, load
  `texts_jp.txt` and, in that loader's COMPLETE handler, apply it and *then* call
  `localizationsReady()`. Because `localizationsReady()` dispatches the `"complete"` event
  that unlocks the UI, chaining it after the text is applied guarantees every widget is built
  with Japanese already in place. This is what fixes cached widgets, like the friends console
  counter that otherwise stays in the old language.

> ⚠️ **Do not remove `localizationsReady()`.** It's the method that unlocks the UI. Deleting it,
> easy to do by accident when editing the adjacent handler, crashes the client with
> `Error #1009` on the loading screen.

---

## 2. `texts_jp.txt`, the UI overlay

**Goal:** translate the whole interface universally.

- Format: plain `key=value`, one per line, `#` for comments.
- On boot (section 1), read the file and call
  `windowManager.localization.updateLocalization(key, value)` for each line.
- Because you key on the localization **key**, this is universal. `navigator.title` is
  `navigator.title` on every hotel, so overwriting it with Japanese covers all servers.

This one file carries the bulk of the translation, including two nice surprises:

- **The `:wired` editor** is not hardcoded. Every string is an `external.texts` key under
  `wiredmenu.*` (~180 of them). Just add those keys to `texts_jp.txt`; no ActionScript needed.
  Keep tokens like `%amount%`, `<font …>` and `\n` intact.
- **The gift box safety warning** is the key `gift.untrusted.banner.text` (see section 7 for a
  caveat).

**HTML tags in translated values don't always render, and it depends on how the string
reaches the screen.** The generic text component used throughout the client can display
real HTML (`<b>`, `<i>`, `<u>`, `<a href="...">`, `<br>`) when its content is set directly.
But when the same component's content is instead set through a `${localization.key}`
template reference, resolved later by a localization listener, that resolution path
writes the plain-text property instead of the HTML one, so HTML tags come through as
literal visible text (`<b>Are you sure?</b>` shows the tags on screen instead of bold
text). Whether a given piece of UI supports HTML in its translated string isn't
predictable from the key name or from other, similar-looking strings elsewhere in the
client, since it depends on which of the two paths that specific window happens to use;
`<br>`-based multi-line strings that already render correctly are not proof that `<b>`
will also work in that same string. If bold or other HTML formatting is needed somewhere
and it isn't rendering, that's this limitation, not a mistake in the translation file. It
isn't worth patching the shared component to force the HTML path everywhere purely for
cosmetic bolding: that component is reused too widely, and forcing HTML rendering on a
path that currently treats content as plain text risks turning any untrusted or
user-supplied string using the same path into interpretable markup.

---

## 3. The catalog, universal by pageName

**Goal:** translate catalog tab names and page bodies on every hotel.

**Why not pageId:** `pageId` is numeric and differs per hotel, and container nodes share the
same id, so keying by id makes every category resolve to the same name. Use the **pageName**
(e.g. `silver_shop`, `set_lodge`), which is stable everywhere.

**File format (`catalog_jp.txt`):**
- Tab names: `pageName|||JP`, e.g. `silver_shop|||シルバーショップ`
- Page bodies: `catalog_shop.<pageName>.text_N.ja=...`, one per text index the page uses.
- Store the JP name lines into a map as `"n_" + pageName`, and body lines as
  `"txt_" + pageName + "_" + index`.

**Consumers (two small hooks):**
- `CatalogNode.get localization`. Return the Japanese name via `"n_" + _pageName` when
  Japanese is active; also record `PageIdToName[String(_pageId)] = _pageName` here so the
  runtime can bridge pageId to pageName.
- `HabboCatalog.onCatalogPage`. When building the page's texts, replace each text with
  `"txt_" + PageIdToName[pageId] + "_" + index` if present.

**Line breaks:** the catalog page text field renders a real `\n`, not `<br>`. Store a
literal `\n` token in the file and convert it on load with `.split("\\n").join("\n")`.

**Discovering pageNames:** a temporary logger that records every `pageName` it sees as the tree
is browsed (a `:catdump`-style command) is the easiest way to build the full list. Remove it
before shipping.

**Where the source content comes from:** unlike interface strings, catalog names and
descriptions have no key anywhere in Habbo's own `external_texts`. There's no official source
to translate against. This content is sourced separately and translated from that source (see
section 11).

---

## 4. The "?" FAQ pages (habbopages)

**Goal:** translate the in client help pages.

- These are HTML pages served through `OnHabboPageOpen(path)`, which should return
  `"Title\nBody"` (Body is HTML, so `<br>` works here) or an empty string to let the server
  answer.
- Override by path from a `habbopages_jp.txt` of `path|||title\nbody`, loaded into a map and
  served before the server fallback.
- The real paths aren't always obvious (the chat page is `chat/chatting`, not something
  tidier), so a small logger that prints the requested path is the quickest way to find them.

Same sourcing note as the catalog: these pages have no official localization key either, so
the content is translated from an external source rather than an `external_texts` entry.

---

## 5. Typing Japanese across a Latin-1 wire

**Goal:** send and receive real Japanese in chat and DMs, client side only.

**Encoding.** Because the modified font only carries a few hundred Japanese glyphs, you don't
need to encode a full Unicode code unit. Encode the glyph's **index inside your charset
string** (`jpcharset.txt`, loaded at boot) instead. A few hundred entries fit in **two base 62
digits** (`0-9A-Za-z`), which is compact and passes the server's letters and digits filter
untouched. Prefix the whole payload with a marker, `~j~`. (An earlier version used hex, then
3 base 62 digits of the raw code unit; the 2 digit charset index scheme is the most compact.)

**Hook placement (this matters):**
- **Outgoing, room chat** (say / shout / whisper): encode in
  `ChatInputWidgetHandler`, **before** the `switch(chatType)`. Sitting in front of the switch
  means the chat type is preserved automatically, since the encode only swaps the text.
  *Do not* put this in a general chat input interceptor that runs earlier and forces
  everything into `say`, or you lose bold and whisper.
- **Incoming, room chat:** decode in `OnRoomChat`, the choke point every room message passes
  through before becoming a bubble. Detect the `~j~` prefix, read in groups of two, index back
  into the charset.
- **Outgoing, private messages:** encode in `MainView.onInput`, applied only to the text sent
  to `SendMsgMessageComposer`. Keep the **local echo** as the original text so the sender sees
  real Japanese.
- **Incoming, private messages:** decode in the `messageText` getter of
  `NewConsoleMessageMessageParser`.

A player on an unmodified client just sees the Latin payload as harmless gibberish, so nothing
breaks for them.

**`jpcharset.txt` is positional, not parsed.** The whole file content becomes one string, and
every character's *index in that string* is the data the encoder/decoder run on. Two
consequences worth keeping in mind when maintaining it:

- New characters must always be **appended at the end**. Inserting or reordering shifts every
  later character's index and breaks decoding for anything already sent using the old
  positions.
- The file can't safely carry an inline header or comments mixed into the character sequence
  itself, for the same reason. If you want one anyway, have the loader look for a literal
  marker (e.g. `###CHARSET_START###`) and only treat what comes after it as the real charset.
  A header above the marker stays free form and never becomes indexed data.

Like the other three data files, `jpcharset.txt` is worth loading with the same
remote-first, local-fallback pattern (section 11) rather than bundled-only, and its load
should be triggered independently at startup rather than gating any other file's load
behind its completion (see the charset-chaining pitfall in section 10).

**Private messages need their own length guard, separate from room chat's.** Private
messages run three base-62 digits per character (not the two-digit charset-index scheme
in room chat), and the messenger's input field has no built-in character limit the way the
room chat input does, so nothing stops the player from typing a message the server will
silently refuse. A refused private message doesn't error or notify the client either, it
just shows locally as sent but stays gray, undelivered, with no indication of why.

The server's payload ceiling for private messages sits around 126 characters (confirmed:
a 41-glyph Japanese message, `41 × 3 digits + 3 for the "~j~" marker = 126`, went through;
longer messages don't).

**Where the guard has to live, and where it doesn't work.** The obvious first attempt is
to hook the input widget's change event (fired after the field's content already changed)
and, if the projected encoded length is over budget, revert the field back to the last
known-valid content. This does not reliably work. A "change" event fires after the
underlying native text field has already accepted and rendered the keystroke; correcting
the value after the fact by writing a new string back into the field doesn't reliably
undo what the player already sees or typed, and the result is a guard that silently does
nothing; the player keeps typing past the limit, and the message still ends up refused.

The reliable point of interception is one layer lower: the native `textInput` event, which
fires *before* the character is accepted into the field, and which supports cancelling the
keystroke outright via the event's `preventDefault()`. This client already uses exactly
that pattern for a different limit (capping the number of lines in a multi-line field), so
the fix is to extend that same handler: project what the field's content would become if
the incoming character were accepted, compute its encoded length using the same
has-any-Japanese-character rule as the encoder, and call `preventDefault()` on the event if
that projection exceeds the ceiling. The character never appears in the field at all,
which is the same experience the native `maxChars` limit already gives room chat.

Because this event lives on the underlying text field component, not on the higher-level
input widget wrapping it, a length-guard flag added only to the wrapper (so it doesn't
affect other fields sharing the same wrapper class) isn't enough on its own; the flag needs
to be threaded one level further down, into the text field component itself, and the
wrapper's property becomes a pass-through to it. See the note in section 0 about editing
widely shared classes before doing this: the text field component here sits underneath
essentially every editable text field in the client, so the flag must default to `false`
and only get set to `true` by the specific private-message view, never as a change to the
component's default behavior.

---

## 6. Pets that obey Japanese commands

**Goal:** the pet performs commands typed in Japanese, on any server.

The server interprets pet commands in *its own* language, so translating the pet's speech
breaks obedience. Two halves:

- **At boot,** before overwriting them with Japanese, capture the server's command words
  (`pet.command.0..N`) into the SharedObject (e.g. `petsrv_<index>`). Do this in
  `capturePetCommands()` called from the boot flow.
- **On send** (`RoomSession.sendChatMessage` or the pet command tool), translate the Japanese
  command back to the captured server word and send that raw.

**Showing Japanese in the player's own bubble is a separate problem from obedience. Solve it
separately.** The tempting approach is to watch for the server's echo of your own sent message
and swap it back to Japanese if it string matches what was sent. This is fragile: anything
that makes the echoed text differ even slightly from what was sent, whitespace, a pet name
that's drifted by a frame, silently breaks the match, with no error. Just an occasional bubble
that's in the wrong language for no visible reason.

The reliable approach: carry the Japanese text alongside the server language word from the
moment the command is issued, instead of reconstructing it later. Send the server word over
the wire exactly as above, unchanged, pet stays obedient. Separately, fire a second, client
only chat event carrying the Japanese text straight to the local bubble: same speaker, same
room, no network round trip. This is the same local echo idea already used for private
messages in section 5, just applied to a second message source.

**Command phrasing, if translating the button labels:** a bare `petName + " " + verb`
concatenation (e.g. "Fido eat") reads as a natural enough imperative in English/Portuguese,
but the equivalent bare concatenation in Japanese reads as grammatically incomplete to a
native speaker. Prefer a command form verb (食べて / 食べなさい rather than the dictionary
form 食べる) and a separator between name and command rather than a bare space. This only
affects the translated values in `texts_jp.txt`'s `pet.command.*` keys, not the mechanism
above.

---

## 7. Hardcoded windows

Two user facing strings are not plain `external.texts`:

- **Gift box warning.** `OnRoomEnter` rewrites `gift.untrusted.banner.text` every room entry,
  choosing the text by hotel domain, so it overrides whatever `texts_jp.txt` set. Gate that
  rewrite on `bootLang == "jp"` and set the Japanese text there instead.
- **"About HabboAirPlus" window.** The title/version/attribution literals live in
  `LilithCustoms` (the `LilithCustoms/About` handler, a `simpleAlert`). Swap them for Japanese
  when `bootLang == "jp"`; the RDF/comment lines (`Edited by Lilith`, `Sulake Oy.`) are
  metadata and don't show on screen.

---

## 8. The font (the enabling piece)

None of the on screen Japanese renders without a font that carries the glyphs, and this is the
part that's easiest to get subtly wrong: a font can look fixed (Japanese shows up) while
quietly breaking the Latin UI in ways that only surface screen by screen. This section is the
full process, because the naive version cost me three wrong builds before it was right.

### 8.1 Why you can't just add glyphs in JPEXS

The client renders text with a handful of embedded fonts, each stored as a `DefineFont3` tag
(tag 75). Two facts about how Flash uses them shape everything below:

- Flash matches an embedded font to a text field by a triple of `(fontName, isBold, isItalic)`,
  not by name alone. That's why the same visual family shows up many times in the SWF under one
  name: in this client there are a dozen `DefineFont3` tags all named `Ubuntu`, plus `Volter`
  and `Volter Bold`. They are not duplicates. Each one is a different weight/slant of the same
  face, distinguished only by two bits in the tag's flags byte.
- With embedded fonts, Flash does not synthesize faux bold or faux italic. If a text field asks
  for bold `Ubuntu` and no embedded `Ubuntu` tag is marked bold, the bold simply does not
  happen (it falls back or renders flat).

Adding glyphs to one of these tags straight from JPEXS's font panel breaks it. JPEXS
re-embeds the whole `DefineFont3`, and in doing so it reprocesses the Latin outlines and
metrics and drops the `DefineFontAlignZones` tag (tag 73), which is the pixel snapping hint
that keeps small text crisp. The result: Japanese appears, but every Latin string in the UI
goes soft and slightly thick, and any bold/italic can quietly collapse to regular. The damage
is real geometry change, not just the missing zones: the reprocessed Latin advances come out a
few units off from the originals, which is the tell that the outlines themselves were touched.

So the rule is: **do not let anything reprocess the tag. Edit it at the byte level instead**,
and treat the existing good Latin as untouchable.

### 8.2 The approach that works: keep Latin byte for byte, append Japanese

The reliable build does not start from the damaged, JPEXS-embedded font at all. It starts from
a known good SWF (a build whose Latin is already crisp and correct) and, for each font tag,
keeps every original glyph exactly as it is, then appends only the Japanese glyphs that aren't
already present. Nothing about the Latin side is recomputed. You are adding rows to the end of
a table, not rebuilding the table.

You need two inputs:

1. **The good base SWF.** Its fonts have the correct Latin outlines, advances, and align zones.
   This is the source of truth for everything Latin.
2. **A donor SWF that already contains the full Japanese glyph set** (for example the
   JPEXS-embedded build, soft Latin and all). You only take its *Japanese* glyph shapes from
   it. Its Latin is discarded.

For every font tag present in both, the merged tag is: *all* of the base tag's glyphs,
untouched, plus each donor glyph whose character code the base doesn't already have. Then sort
the combined glyph list by character code so the code table stays ascending.

### 8.3 The `DefineFont3` fields that must survive the rebuild

When you disassemble and reassemble the tag, three things have to be carried across exactly or
the font breaks in a way that's hard to trace back. The tag layout is:

```
FontID              UI16
Flags               UI8   <- bit0 Bold, bit1 Italic, bit2 WideCodes,
                            bit3 WideOffsets, bit4 ANSI, bit5 SmallText,
                            bit6 ShiftJIS, bit7 HasLayout
LanguageCode        UI8
FontNameLen         UI8
FontName            bytes
NumGlyphs           UI16
OffsetTable         UI16[NumGlyphs] or UI32 each if WideOffsets
CodeTableOffset     UI16 or UI32 (WideOffsets)
GlyphShapeTable     the glyph shape records, concatenated
CodeTable           UI16[NumGlyphs] (WideCodes) or UI8 each
-- if HasLayout: --
FontAscent          SI16
FontDescent         SI16
FontLeading         SI16
FontAdvanceTable    SI16[NumGlyphs]
FontBoundsTable     RECT[NumGlyphs]
KerningCount        UI16
KerningTable        ...
```

The three that bite:

1. **The Bold and Italic bits in the Flags byte (and the LanguageCode byte after it).** This is
   the one that cost the most. If you hardcode the flags when you re-serialize (say, always
   writing "has layout, wide offsets, wide codes"), you wipe the Bold and Italic bits, and every
   styled variant collapses to regular. In this client the styled `Ubuntu` tags carry, for
   example, bold+italic, italic-only, bold-only, and regular, each in a separate tag with the
   same name. Read the original flags byte and OR your forced bits onto the *style* bits you
   found there, don't replace them. Same for the LanguageCode byte: copy the original, don't
   assume zero.

2. **WideOffsets and WideCodes must be forced on for the enlarged font.** Once you append a few
   thousand Japanese glyphs, the glyph count and the byte offsets into the shape table both blow
   past what 16-bit fields can address. So even if the original tag used narrow offsets (the
   `Volter` tags did), the rebuilt tag has to set WideOffsets (bit3) and WideCodes (bit2) and
   write those tables as 32-bit offsets / 16-bit codes. These are storage-width flags, not
   style, so forcing them is safe. Set HasLayout (bit7) too, since you're writing the advance
   table.

3. **The align zones (tag 73) have to be rebuilt parallel to the new glyph order.** A
   `DefineFontAlignZones` tag is `FontID UI16`, `CSMTableHint UI8`, then one `ZoneRecord` per
   glyph *in the same order as the font's glyphs*. A normal Latin record is
   `NumZoneData=2`, two 4-byte zone entries, one `ZoneMask` byte = 10 bytes. After you sort the
   merged glyph list, emit one zone record per glyph: the original Latin record for glyphs that
   had one (match by character code), and a neutral record for the appended Japanese glyphs.
   Neutral = `NumZoneData=2`, eight zero bytes, `ZoneMask=0`. The Japanese glyphs render fine
   with neutral zones; the point of preserving the real Latin zones is that the Latin stays as
   crisp as it was in the base.

The `FontBoundsTable` can be written as empty RECTs (a run of zero-size rectangles), and if the
original had no kerning you write `KerningCount=0`. Flash doesn't need real bounds for dynamic
text field rendering. Don't drop a non-empty kerning table if one exists, though; carry it.

### 8.4 The procedure, end to end

1. Decompress the SWF (`CWS` is zlib; swap the header to `FWS` and inflate the body) so you're
   working on the raw tag stream. Remember the version byte and rebuild the 4-byte file length
   when you recompress.
2. Walk the tag stream of both SWFs. Index the base's `DefineFont3` (75) and
   `DefineFontAlignZones` (73) tags by FontID. Index the donor's font tags by FontID.
3. For each font that the donor expanded (its glyph count is much larger than the base's):
   parse the base tag fully (flags, language, name, ascent/descent/leading, and per glyph:
   shape bytes, code, advance). Build a code -> align-zone-record map from the base's tag 73.
4. Start the merged glyph list as the base's glyphs, verbatim. Parse the donor tag the same
   way and append every donor glyph whose code isn't already in the base. Sort the merged list
   by code.
5. Re-serialize the `DefineFont3`: original style flags OR forced WideOffsets/WideCodes/
   HasLayout, original LanguageCode and name, the new glyph count, freshly computed offset
   table, the concatenated shapes, the code table, then ascent/descent/leading and the advance
   table, zeroed bounds, zero kerning.
6. Re-serialize the matching `DefineFontAlignZones`: FontID, the base's CSM hint, then one zone
   record per glyph in the sorted order (real record by code, neutral for the appended
   Japanese).
7. Reassemble the tag stream: keep the base SWF's tags in order, but for each expanded font,
   emit your rebuilt font tag followed by its rebuilt align-zones tag, and drop the base's
   original align-zones tag for that font (you're replacing it). Recompress to `CWS`.

Do this for *all* the expanded families, not just the body text ones. Missing the bold family
is exactly what leaves titles looking un-bolded while everything else looks fixed.

### 8.5 Verify before testing in game

A few cheap checks catch the mistakes that otherwise only show up as "some titles aren't bold":

- The rebuilt SWF parses cleanly end to end and the last tag is `End` (0).
- Font tag count and align-zone tag count match the base's (including any align-zone tags for
  IDs that aren't `DefineFont3`; leave those untouched).
- Each expanded font's glyph count equals the donor's, and every expanded font has a matching
  align-zones tag.
- Per expanded font, the Bold/Italic bits read back exactly as they were in the base. This is
  the check that would have caught the regression immediately.
- Within a font, the code table is sorted and has no duplicates, and a known Latin code (`A`,
  0x41) and a known Japanese code (for example あ, 0x3042) are both present.

### 8.6 The short version

Never reprocess the tag; edit bytes. Keep the good Latin untouched and only append Japanese.
Preserve the flags byte's Bold and Italic bits and the language byte, force the width flags on,
and rebuild the align zones parallel to the new glyph order with neutral zones for the Japanese.
Fix every weight, including the bold and italic tags, not just the regular one.

### 8.7 A tool that does all of this

You do not have to do the byte surgery by hand. There is a small Python tool that
performs exactly the process above, and it is what produced the crisp result:

**https://github.com/yohaku404/habbo-jp-support/tree/main/font-tool**

`python inject-jp-fonts.py <in.swf> <out.swf>` keeps every Latin glyph byte for
byte, appends only the Japanese glyphs, preserves each font's Bold/Italic flags,
and rebuilds the align zones. It matches fonts by name and style, not by font id,
so it works regardless of how a given client numbers its fonts. Run it on the
clean baseline (then build from the patched baseline) or on the final SWF; it is
additive and safe to re-run. The repo's `TUTORIAL.md` covers usage and how to
rebuild the glyph pack from your own font source. One note: the glyph pack is font
data, so redistributing it depends on the source font's license.

---

## 9. File layout

The client loads these from `app:/Language/Japanese/`:

- `texts_jp.txt`, the UI/wired/gift overlay (`key=value`).
- `catalog_jp.txt`, catalog names and bodies (pageName format).
- `habbopages_jp.txt`, the "?" pages (`path|||title\nbody`).
- `jpcharset.txt`, the charset string used by the chat encoder/decoder.

They ship alongside the SWF in the AIR app's `Language/Japanese/` folder.

---

## 10. Pitfalls (a short field guide)

- Deleting `localizationsReady()` causes `Error #1009` at boot. Keep a known good build and
  diff.
- Keying the catalog by `pageId`, or feeding it a raw `catalog_shop.<pageId>.localization`
  export instead of the `pageName|||JP` format, makes the whole store silently revert.
- Putting Japanese on the wire means the server eats it. Always encode to ASCII first.
- Placing the chat encode before vs. after `switch(chatType)` decides whether bold/whisper
  survive. Hook position is load bearing.
- Chaining the catalog/help-page loaders off the charset load (calling the function that
  kicks off catalog and help-page loading from inside the charset file's own load-complete
  handler) means that if the charset load never completes, catalog and help pages never
  even get requested, not a failed request, an unmade one. This isn't a theoretical risk:
  it's what happens the moment the charset file's loading path changes and the two aren't
  decoupled to match. If `texts_jp.txt` loads fine on its own path but catalog and help
  pages silently stay in the hotel's native language with no error at all, check whether
  their load is still gated behind the charset's completion event before looking anywhere
  else. The fix is to have each of the four data files kick off its own load independently
  at startup, with no file's loading waiting on another file's load event to fire first.
- Swapping a pet's spoken bubble by string matching the server's echo is fragile and fails
  silently. Carry the Japanese text forward from the moment the command is sent instead of
  reconstructing it later.
- Rebuilding a font tag with hardcoded flags wipes the Bold and Italic bits, and every styled
  variant collapses to regular with no error (section 8.3). The symptom is titles and labels
  that render un-bolded or un-italicized while body text looks fine. Read the original flags
  byte and keep its style bits; only force the width/layout bits. And fix every weight,
  including the separate bold and italic font tags, not just the regular one, or the bold
  ones stay broken while everything else looks solved.
- The `texts_jp.txt` loader needs the same `\n` unescape the catalog loader already has
  (`.split("\\n").join("\n")`) applied to each value before calling `updateLocalization`.
  Without it, any multi line string (confirmation dialogs, error messages) shows a literal
  `\n` on screen instead of a line break, even though the source file's escaping is correct.
  **Order matters here, and getting it backward is easy to do without noticing:** each raw
  line also carries a trailing `\r` that needs stripping before the value is usable, and that
  strip must run first, inside the check for it (`if the last character is \r, strip it`),
  with the unescape running unconditionally after. If the unescape ends up nested inside that
  same `if` instead, and the `\r` strip ends up running unconditionally after it, every
  value's last character gets silently truncated, whether or not it happened to end in `\r`,
  because the unconditional strip now cuts one character off values that never had a
  trailing `\r` at all. This shows up as one-character-short button labels and truncated
  sentence endings across the entire UI, everywhere the affected code path is used, with no
  error to point at the cause. If translated text starts losing its last character
  network-wide, check this ordering before anything else.

---

## 11. Keeping the translation data current

A note on maintenance, separate from the implementation above.

Two of the four data files (`catalog_jp.txt`, `habbopages_jp.txt`) translate content that has
no key in Habbo's own `external_texts`. There's no official list to diff against when new
catalog pages or help topics ship, which means keeping them current is manual work: finding
what's new, translating it, and correctly re-keying it (by pageName, by path) so it doesn't
silently regress the way a raw pageId export did once already (section 3).

I maintain a public repository with current versions of all four files:
**https://github.com/yohaku404/habbo-jp-translation**

That repository stays maintained as the reference source for updates going forward: new events,
new catalog pages, terminology fixes. A fork can pull from it periodically, or just use it as a
place to check before assuming something is missing. Either way it stays current, so nobody has
to track all of this by hand.

---

*Questions, corrections, and requests for exact file samples are welcome through the repository.*

Built by Yohaku, with the font rendering breakthrough by [@maxph3](https://github.com/maxph3).
