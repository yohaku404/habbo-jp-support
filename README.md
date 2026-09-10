# Bringing Japanese Back to Habbo

### How two people rebuilt habbo.jp inside a Western client, one glyph at a time

*A long read for anyone who logged into habbo.jp one last time before the lights went out. Part memory, part engineering notebook.*

<div align="center"><img width="720" height="431" alt="View_jp" src="https://github.com/user-attachments/assets/0b1da872-da9e-41c9-87dd-f6cc617d4cda" />
</div>
<p align="center"><sub><b>Image 1.</b> The hotel view menu, as it looked on the original habbo.jp.</sub></p>

---

## Prologue: the room that closed

If you were there, you remember it differently than the shutdown notice did. Habbo Japan
was never a line in a press release. It was a specific shade of orange on the hotel view.
It was a font that sat a particular way inside the chat bubbles. It was ゴシゥク furniture
and ロストシティ and a house style of spelling that was slightly wrong
in exactly the right way, the kind of wrong that becomes a dialect if enough people love it.
And then it was gone. Folded away like a room whose owner stopped paying for the club.

<div align="center"><img width="579" height="382" alt="image" src="https://github.com/user-attachments/assets/19c49ebe-4ca3-41fc-81d3-c5c93bb1b05a" /></div>
<p align="center"><sub><b>Image 2.</b> Closing time on habbo.jp, before it was gone for good.</sub></p>

Some of us never really left. We kept the client on a drive somewhere. We kept the muscle
memory of walking a pixel avatar across a tiled floor. And eventually a small, stubborn
idea took hold, the kind that sounds trivial when you say it out loud and turns out to be
a mountain: *what if the language didn't have to die with the servers?* What if any hotel,
on any country's server, could speak real, official Japanese again, switched on with a
single command?

This is the story of how we got there. It is also, honestly, the story of almost not
getting there at all.

<div align="center"><img width="669" height="486" alt="10107638016" src="https://github.com/user-attachments/assets/2bcc5250-0d41-463b-ad74-b82fda591eee" /></div>
<p align="center"><sub><b>Image 3.</b> A public room in the original habbo.jp, months before the servers were shut down.</sub></p>

---

## Part I: The impossible thing

Every Habbo client edit starts the same way: you open the SWF in JPEXS, you find a class,
you change a value, you save. Most of this project was exactly that, thousands of times.
But before any of it could matter, we had to solve one problem that everyone said was
unsolvable: getting a single Japanese character to appear, live, in a real session.

One of the most respected Brazilian Habbo developers had said flatly that it was
impossible to send letters like that into chat. And at first, every experiment agreed
with her. You'd inject Japanese and it would come back as `????`. You'd edit the font and
the client would ignore you. You'd toggle every flag you could find and nothing moved.

The project died there. Not paused. *Dead*. When you cannot send one character, you don't
have a project. You have a folder you stop opening.

But there was one detail that refused to sit still. The Japanese wasn't turning into a
question mark. On some attempts it was turning into *nothing at all*. An empty bubble.
And an empty bubble, it turns out, is not a wall. It's a fingerprint.

---

## Part II: Reading the wire with G-Earth

To understand why the character vanished, we had to stop guessing and go look at the
actual bytes moving between the server and the client. That means G-Earth, the packet
tool that lets you watch and inject the raw protocol.

I went into my own room, said something ordinary, and found the incoming packet that
carried it. It was the `ChatMessageEvent`, header **2433**, and its shape was:

```
{i:0}{s:"text"}{i:0}{i:1}{i:0}{i:-1}
```

Read left to right, that's: the user's index, the text string, a gesture, a chat style,
and two trailing integers. Nothing exotic. The interesting part was the second field, the
string, and specifically *how* it got written.

When you tell G-Earth to inject `{s:"ただいま"}`, it helpfully encodes that string as
Latin-1. Latin-1 has no idea what a Japanese character is, so it writes `????`. That was
the source of the question marks. The tool was mangling the text before it ever reached
the wire.

So I stopped using `{s:...}`. I wrote the string field **by hand, as raw UTF-8 bytes**:
two length bytes, followed by the actual bytes of the character. To test with `た`, whose
UTF-8 encoding is `E3 81 9F` = `227 129 159`, the string field became
`{b:0}{b:3}{b:227}{b:129}{b:159}`, length three followed by the three bytes. The whole
expression:

```
{h:2433}{i:0}{b:0}{b:3}{b:227}{b:129}{b:159}{i:0}{i:1}{i:0}{i:-1}
```

Why does that work when `{s:...}` doesn't? Because the client reads that field with
`readUTF`, which expects precisely `[2-byte length][UTF-8 bytes]`. Hand it real UTF-8
instead of Latin-1 mush and it decodes correctly. The client received *real Japanese*,
and that Japanese flowed down the normal rendering path all the way to the bubble.

The bubble came up **empty, not `?`**, and that emptiness was the proof. The character
was arriving intact. The only thing failing was the drawing step: the font's `draw()`
refusing to paint a glyph it didn't contain.

To be certain the packet itself wasn't broken, I built a control: a message mixing Latin
and Japanese, `Aた`.

```
{h:2433}{i:0}{b:0}{b:4}{b:65}{b:227}{b:129}{b:159}{i:0}{i:1}{i:0}{i:-1}
```

If the packet were malformed, nothing would render. If the packet were valid but the font
lacked the glyph, the `A` would paint and the `た` would not. That's exactly what happened.
Valid packet, missing glyph. The wall was the font, not the wire.

<div align="center"><img width="1322" height="676" alt="image1" src="https://github.com/user-attachments/assets/975723f6-5f87-4c00-9a05-f8e5d1a6bb8e" /></div>
<p align="center"><sub><b>Image 4.</b> The G-Earth injection panel, mid-test, sending the hand-built UTF-8 packet directly into a live room.</sub></p>

---

## Part III: The glyph that changed everything

The font turned out to be a genuinely nasty problem, and this is Max's part of the story.

The obvious move, opening the SWF, selecting the embedded `DefineFont3`, and adding
Japanese glyphs in JPEXS, does not work, and the reason is instructive. Flash has strict,
specific requirements for embedded fonts. Touch the font file directly and you can shift
its ID or break the metadata it expects; when that happens, Flash silently gives up on the
embedded font and falls back to a root default. That fallback is why toggling `embedFont`
did nothing: the client wasn't rendering with the font we thought it was.

Max went at it from underneath. He edited a source font's metadata so it would carry the
Japanese glyphs *and* impersonate the font the game actually uses: **Ubuntu**. Not the
ancient pixel `Volter` that everyone assumed, the one that just sits in the SWF as legacy
dead weight from a 2008-era build. Ubuntu is the real one. He essentially took another
font, dressed it up as Ubuntu convincingly enough that Flash accepted it, and embedded it
over the top. Then he ran my G-Earth expression against it.

The glyph rendered.

A real Japanese character, in a real bubble, in a live session. He sent me the screenshot
with the words *"Got it, you f$%ˆ&#@ bastard"*.

I want to be careful and honest about the credit, because we were careful about it that
night too. The byte-level G-Earth expression, the thing that proved the packet path and
turned the problem from "impossible" into "it's the font", was mine. The font breakthrough,
the thing that actually put a glyph on the screen, was Max's, and he built it on an
intuition nobody else had: that the answer was Ubuntu, not the font everyone kept staring
at. I had already given up. He wanted to be credited simply as **Max**, so: Max.

Two honest caveats we knew even in that first hour. It only works on a modified client,
because a vanilla Ubuntu font ships without Japanese glyphs. And it is client-side only.
The server reads Latin-1 and won't change, so there is no server-side version of this and
never will be. But the door was open. Everything that follows is what we did after we
walked through it.

<div align="center"><img width="1443" height="746" alt="image" src="https://github.com/user-attachments/assets/c49296c8-7dce-410c-97be-20d3fa119bb5" /></div>
<p align="center"><sub><b>Image 5.</b> The moment the first real Japanese glyph rendered in a live bubble by Max; the client accepting the injected packet.</sub></p>

---

## Part IV: Fixing the font it broke

Getting the glyph to render was the breakthrough. It also quietly wrecked everything else,
and cleaning that up turned into one of the most satisfying pieces of surgery in the whole
project.

The embed was done on the font tag itself, with no separate font mounted from outside, just
the Japanese glyphs added into the existing Ubuntu `DefineFont3`. The problem is what JPEXS
does when you embed: it **reprocesses all the Latin metrics**. The advances, and even the
outlines, of the original Latin glyphs get rebuilt from scratch. Suddenly the entire UI,
the names of people online, the room occupancy counter, every nick, all of it, came out
thicker, wider, and frankly ugly.

The reason is a small, easily-overlooked structure called `DefineFontAlignZones`. Those
alignment zones are the hint Flash uses to snap text to the pixel grid so it stays small
and crisp at UI sizes. JPEXS throws that structure away when it re-embeds, and without it
every string in the client goes soft and mushy. You don't notice how much work those hints
were doing until they're gone and the whole interface looks like it melted slightly.

There was no clean way to fix this inside JPEXS, because the damage happens *because of* how
JPEXS embeds. So the fix moved underneath the tool, to a binary edit of the file directly.
I wrote a parser for the `DefineFont3` tag that disassembles and reassembles it **byte by
byte, without loss**: the offset table, the glyph shapes, the advances, everything. With
that in hand I could rebuild the font deliberately instead of letting JPEXS rebuild it
carelessly: restore the original Latin glyphs, their outlines, advances, and bounds,
exactly as they appear in the clean, untouched font, and keep *only* the Japanese glyphs
the embed had added.

The last piece was putting the hint back. I re-inserted the `DefineFontAlignZones` that
JPEXS had discarded, remapped to the font's new glyph order: the original Latin glyphs
first, with their alignment zones intact, and the Japanese glyphs after them assigned a
neutral zone. Latin text got its crisp pixel-snapped rendering back; Japanese text sat
cleanly alongside it.

<div align="center"><img width="522" height="726" alt="IMG_2099" src="https://github.com/user-attachments/assets/d04ba1be-aaee-44a0-b2b4-84a701df5e1d" /></div>
<p align="center"><sub><b>Image 6.</b> The navigator list, before (left) and after (right) restoring the font's alignment zones (same data, radically different legibility).</sub></p>

The lesson underneath this one is about tools. JPEXS is indispensable, but it has opinions,
and one of them was quietly degrading the whole UI in the name of embedding a few glyphs.
Sometimes the only way to keep a tool's benefit without its side effect is to go one level
below it and do the surgery by hand.

---

## Part V: From one glyph to a whole language

Rendering one character is a magic trick. Translating an entire client is a construction
project, and the first thing you learn is that Habbo does not store "one text per language"
in a single tidy place. Text comes from several different sources, and each one needs its
own technique to intercept:

- Some text lives in a local translations table;
- Some is sent by the server already resolved into words;
- Some is assembled by widgets that cache their text the moment the screen is built;
- Some is hardcoded into ActionScript literals;
- Some, like the catalog and the chat, has its own quirks on top of all that.

Most of the real work was detective work: figuring out *where* each string was actually
coming from before we could decide *how* to replace it. What follows is the architecture
we ended up with, and, more importantly, the reasoning behind each decision.

<div align="center"><img width="563" height="628" alt="image" src="https://github.com/user-attachments/assets/f89988d9-1336-4c4b-8c60-25c54b091959" /></div>
<p align="center"><sub><b>Image 7.</b> A live example of the pageId trap: the sidebar collapsing several distinct categories into the same "クラブ" label, while the header description falls back to Portuguese entirely, since neither had a pageName-keyed translation to resolve to.</sub></p>

---

## Part VI: The switch, and booting into another language

Everything hangs off one toggle: `:lang jp`. The design goal was that it should feel like
a light switch (on means Japanese, off means back to normal) and that it should be safe
enough to ship.

Persistence uses a `SharedObject` (`HabboAirPlus`) with a single field, `bootLang`. When
it holds `"jp"`, the client boots into Japanese the next time it opens; any other value is
the hotel's native language. A crucial decision hides here: Japanese is applied as an
**overlay of text values**, not as a swap of the localization *definition*. Swapping the
definition (`activateLocalizationDefinition`) corrupts the client; overwriting individual
strings does not. So we never replace the language, we paint over it.

The other crucial decision is *when*. The overlay is applied early, inside
`HabboLocalizationManager.onLocalizationLoaded`, gated by `shouldBootJapanese()`. The
reason is a bug that taught us the whole principle: the friends console. Its "Friends(X)"
counter refused to turn Japanese no matter how many times you relogged, because the widget
*cached* its text at the moment it was built, before our overlay ran. The fix wasn't to
chase the widget; it was to apply Japanese *before the UI is constructed at all*, so the
cached value is already Japanese when the widget grabs it. Get the timing right and dozens
of "stubborn" strings fix themselves at once.

And one scar worth showing the reader, because it's the kind of thing that eats an entire
night: while editing `onLocalizationLoaded`, it is fatally easy to delete the adjacent
`localizationsReady()` method. That method dispatches the `"complete"` event that unlocks
the UI. Remove it and the client dies with `Error #1009` on the loading screen, every
time, with no obvious cause. We reverted, re-reverted, and method-diffed a working build
against a broken one before we found it. If you take one operational lesson from this
article: keep a known-good build and diff against it.

---

## Part VII: texts_jp, the workhorse

The core of the interface translation is almost boring, which is exactly why it's good. A
plain `key=value` file, `texts_jp.txt`, is loaded at boot and applied by a loop that calls
`updateLocalization(key, value)` for every line. Any localization key in the client can be
overwritten this way.

The elegant part is *universality*, and it's worth dwelling on because it's the single
most important design idea in the project. Localization **keys** are identical on every
Habbo hotel: `navigator.title` is `navigator.title` whether you're on the Brazilian,
German, or Turkish server. Only the **value** differs by language. So when we translate by
*key*, we cover every server at once. A German hotel's `navigator.title` gets overwritten
with Japanese exactly the same way the Brazilian one does. We didn't build a "Brazilian
Japanese client"; we built a universal one, and we got that for free by keying on the
thing that's shared instead of the thing that varies.

The whole UI rides this path, and so does a surprise guest we'll get to: the `:wired`
editor, whose ~180 menu strings turned out to be ordinary `wiredmenu.*` keys.

<div align="center"><img width="580" height="604" alt="image" src="https://github.com/user-attachments/assets/d1a2cb39-905c-4a57-b9bb-af3f0d29c7fb" /></div>
<p align="center"><sub><b>Image 8.</b> The hotel navigator, fully translated by key; the same overlay that covers every hotel.</sub></p>

<div align="center"><img width="391" height="524" alt="image" src="https://github.com/user-attachments/assets/a48322ec-697a-4604-99ea-15537c2e20a2" /></div>
<p align="center"><sub><b>Image 9.</b> Nearly two thousand achievement points worth of interface, translated the same way as everything else: by key.</sub></p>

<div align="center"><img width="224" height="229" alt="IMG_1000" src="https://github.com/user-attachments/assets/a04beebc-7c4c-4b8d-a465-db56fb7a8cc3" /></div>
<p align="center"><sub><b>Image 10.</b> Even the dance picker speaks Japanese now.</sub></p>

---

## Part VIII: Typing Japanese across a wire that only speaks Latin-1

The font let us *see* Japanese. It did not let us *send* it. The server strips non-Latin
characters out of chat, out of quests, out of messages. Anything that isn't Latin gets cut
before it comes back. So the whole system is built on one rule we could never violate:
**never put Japanese on the wire.**

The strategy that falls out of that rule is simple to state and pleasant to build. On the
way out, the client encodes Japanese into a string of pure Latin characters. On the way in,
it decodes them back. The wire only ever carries Latin, the server relays it untouched, and
any client running the modified launcher reconstructs the Japanese on the other side. It's
100% client-side: no new packet, no change to the server, and I reused the composers that
already existed rather than inventing a protocol.

**The encoding, and how it kept shrinking.** The chat has a length limit, so every byte the
payload spends is a byte of Japanese the player can't type. The encoding went through three
generations, and each one was a squeeze for more characters.

It started as hex. Simple, but wasteful: two hex digits per byte, and the chat filled up
fast. The first real improvement was the alphabet. Base-62 (`0-9A-Za-z`, letters and
digits only) is exactly the set the server's filter passes untouched, and it carries far
more information per character than hex, so the same text took noticeably less room. In
that second generation, each character was written as **three base-62 digits of its full
16-bit code unit** (`n = d₂·62² + d₁·62 + d₀`), decoded back with `String.fromCharCode`.
Three digits because `62³ = 238,328` comfortably covers the whole 65,536-code-unit range.

The final generation came from a realization about our own limits. The modified font only
carries a few hundred Japanese glyphs, and those are the only characters that can ever
render anyway. So there was no reason to encode a full 16-bit code unit capable of
addressing all of Unicode. It was enough to encode the glyph's **index inside our own
`JPCharset` table** (the character list loaded from `jpcharset.txt`). A few hundred entries
fit easily in **two base-62 digits** (`62² = 3,844`, far more than we needed), so each
character dropped from three digits to two, a straight 33% cut, which is a third more
Japanese per message. Encode becomes "find the glyph's position in `JPCharset`, write it as
two base-62 digits"; decode becomes "read two digits, index back into `JPCharset`." The
scheme also gained a quiet safety property: it can only ever represent characters the font
can actually draw.

Both versions carry the same `~j~` marker up front, so the decoder always knows a payload
when it sees one.

**Where the hooks live, and why it matters?** This is the part that took real care, because
the *placement* of each hook is load-bearing.

For room chat, meaning normal bubbles (`say`), bold (`shout`), and whisper, the encode goes
into `ChatInputWidgetHandler`, deliberately **before** the `switch(chatType)` that decides
which of the three it is. Sitting in front of that switch means the chat type is preserved
for free: the encode only swaps the text, and say/shout/whisper each continue down their own
branch untouched. One trap here, learned the hard way: this must *not* live in
`LilithCustoms.ParseChatInput`, because that intercepts earlier in the pipeline and forces
everything into a plain `say`, flattening bold and whisper. The decode for room chat is in
`OnRoomChat` inside `LilithCustoms`, the choke point every room message passes through on
its way to becoming a bubble.

Private messages take a parallel path. The encode goes into `MainView.onInput`, applied
only to the text headed for `SendMsgMessageComposer`; crucially, the *local echo* keeps the
original text, so you see your own message in real Japanese rather than the encoded form.
The decode lives in the `messageText` getter of `NewConsoleMessageMessageParser`, which is
where an incoming private message is read before it's shown.

There's a smaller discovery worth recording here too. Private messages run an older
generation of the encoding than room chat, three base-62 digits per character instead of
two, and that difference turned out to matter. The server accepts a private message up to
some fixed payload length, and a message that goes over it doesn't error, doesn't reject
loudly, it just sits there in gray, sent but never delivered, with nothing in the client
telling you why.

Finding the actual number took two separate manual counts, and the first one was wrong. A
hand-counted 112-character Latin message that supposedly still went through didn't square
with a 126-character encoded Japanese message that also went through, since a fixed byte
ceiling can't let the larger payload past and reject the smaller one. Recounting by hand
a second time turned "112" into "120," and the contradiction disappeared. Both numbers
turned out to sit close together, both consistent with the same ceiling somewhere around
126 characters, which is exactly the length of the longest confirmed Japanese message:
41 glyphs at three digits each, plus the three-character `~j~` marker. The room chat
input already truncates before you can type past its limit; the messenger's input field
had no such guard, so it was possible to type a message the server would silently refuse.

The first attempt at fixing that fixed nothing. Watching the field for changes and
reverting it once the projected message got too long sounded reasonable and compiled
clean, and did precisely nothing at runtime: by the time a "something changed" event
fires, the character is already sitting in the field, already rendered, already typed.
Writing a shorter string back over it doesn't put the toothpaste back in the tube. The
actual fix lived one layer further down than expected, on the native event that fires
*before* a keystroke is accepted rather than after, the same one already quietly capping
line counts elsewhere in the client. Once the guard moved there, blocking the character
outright instead of trying to undo it, it worked exactly like the room chat limit always
had: type up to the edge, and the wall simply isn't there to walk through.

The beautiful consequence of all of it: a player on an *unmodified* client sees the raw
payload, a little run of gibberish like `8aa7190__ajau1121`, while every modified client
in the room reads it as clean 日本語. The Japanese is real, it survives a hostile server,
and it's invisible noise to anyone without the launcher.

<div align="center"><img width="214" height="217" alt="IMG_1001" src="https://github.com/user-attachments/assets/84d927ad-620b-42f4-9d18-69bb218feaa1" /></div>
<p align="center"><sub><b>Image 11.</b> Respect given in Japanese. Real text, still 100% client-side.</sub></p>

---

## Part IX: The catalog, and the tyranny of the pageId

The catalog was the deepest trap in the project, and the story of it is really a story
about choosing the right key.

The instinct is to translate catalog pages by their `pageId`. Don't. The `pageId` is
numeric and it **changes from hotel to hotel**, so a translation keyed by id works on one
server and nowhere else. Worse, many container nodes share the same id (`-1`), so keying by
id makes *every* category collapse to the same name. We watched an entire store turn into
the word "Clubes" once because of exactly this.

The only key that is stable across every server is the **pageName** (`silver_shop`,
`gaming_projectiles`, `bc_val15`). So the catalog is indexed by pageName end to end:

- Tab names as `pageName|||JP`, e.g. `silver_shop|||シルバーショップ`.
- Page bodies as `catalog_shop.<pageName>.text_N.ja=...`.

On the code side, `CatalogNode.get localization` returns the Japanese name via
`"n_" + pageName`, and `HabboCatalog.onCatalogPage` injects the bodies via
`"txt_" + pageName`, using a `PageIdToName` bridge that the client builds at runtime as it
sees each node. It's a small amount of bookkeeping that buys total universality.

Two field notes that cost real time:

First, **rendering**. The catalog's page text field renders a real `\n` as a line break,
*not* an HTML `<br>`. So in the file we store a literal `\n` token and the loader converts
it with `.split("\\n").join("\n")`. Get this wrong and every multi-line description runs
together into a wall of text.

Second, a **regression that looked like a catastrophe**. Late in the project the whole
store reverted to Portuguese while everything else stayed Japanese. The cause wasn't the
code. It was a catalog file that had been re-exported in the *raw* format (keyed by
`pageId`, with `catalog_shop.<id>.localization.ja=` lines) instead of the pageName format
the hooks require. The parser silently ignored the unfamiliar format, and the entire store
fell back. The lesson: the file format and the code that reads it are a contract, and a
"cleaner-looking" export can quietly break it.

<div align="center"><img width="574" height="631" alt="image" src="https://github.com/user-attachments/assets/793795a8-c18d-4d4d-9ffb-119f3585437a" /></div>
<p align="center"><sub><b>Image 12.</b> The catalog, translated by pageName instead of the unstable, per-hotel pageId.</sub></p>

---

## Part X: The FAQ pages, the wired menus, and the pets that obey

Three smaller systems, each with a lesson.

**The FAQ pages.** The FAQ pages ("?" buttons) are HTML served by the client through
`OnHabboPageOpen(path)`, which returns `"Title\nBody"` or an empty string that lets the
server answer. We override them by path from a `habbopages_jp.txt` of `path|||title\nbody`.
The catch was discovery: the real paths aren't always what you'd guess (the chat page is
`chat/chatting`, not something tidier), so we added a logger and read them straight out of
the running client. Unlike the catalog, these bodies are HTML and render `<br>`.

**The wired editor.** The "Wired Creator Tools" and "Wired Logs" windows *looked* hardcoded,
exactly the kind of thing you brace yourself to fight. They weren't. Every string was an
ordinary `external.texts` key under `wiredmenu.*`. Adding those keys to `texts_jp.txt`
translated the entire editor, tokens like `%amount%` and `<font>` preserved, with zero
ActionScript. Sometimes the boss fight is a locked door with the key already in it.

**The pets that obey.** This one is my favorite, because the naive fix breaks the feature,
and because the *first* fix we shipped looked correct and wasn't.

The server interprets pet commands in *its own* language. Translate the pet's speech to
Japanese and the pet stops obeying, because now you're sending it a word it doesn't
recognize. The solution has two halves. At boot, we *capture* the server's command words
(`pet.command.0..N`) into a `SharedObject` before we overwrite them with Japanese. Then,
when a command is sent, we **translate it back** to the captured server word and send that
raw, so the pet hears the word it was born knowing.

That much worked immediately: the pet obeyed. What didn't work, for a while, was the other
half — making *your own speech bubble* show Japanese instead of the translated-back server
word you'd just sent. The first attempt tried to catch this the same way regular room chat
gets decoded: watch for the server's echo of your own message and swap it back to Japanese
if it matched what you'd sent. It sometimes worked and sometimes silently didn't, and the
silence was the problem — no error, no crash, just an occasional plain-language bubble with
no clue why.

The actual cause was a race, not a typo: the string comparison the swap depended on was
fragile against anything the server might do to the text on its way back (whitespace,
case, a pet name that had drifted by one frame), and any mismatch failed the whole
substitution with nothing to show for it.

The fix that stuck skips string-matching entirely. The Japanese text is carried alongside
the server-language text from the moment the command button is clicked, instead of being
reconstructed later by comparing strings. The server-language text still goes out over the
wire exactly as before: the pet's behavior never changes. But right after that send, the
client also fires a second, synthetic chat event of its own: same speaker, same room, no
network trip, carrying the Japanese text straight to the bubble. It's the same "local echo"
trick already in use for private messages (Part VIII) and, as it turns out, for one other
UI alert already living in the client under a different name, proof the pattern was
already trusted here, just not yet pointed at this feature.

<div align="center"><img width="299" height="289" alt="IMG_1002" src="https://github.com/user-attachments/assets/1a77b960-5499-440e-9e6b-32ec8bc77597" /></div>
<p align="center"><sub><b>Image 13.</b> The pet obeys in its native tongue while the player speaks (and is heard) in Japanese.</sub></p>

---

## Part XI: The promo buttons (where does this text even come from?)

The hotel-view promo buttons ("See the rare!", "See the pack!") fought us harder than
anything except the font, and the fight is a good lesson in not trusting your assumptions
about where a string lives; twice over, as it turned out.

We tried the obvious thing first: the promo article's `buttonText`. We overrode the getter,
forced it to return a marker, and… nothing changed on screen. We moved to the widget that
paints the button, `PromoArticleWidget.setArticleContent`, forced *its* caption to a
marker, and again nothing changed. Two confident fixes, zero effect. The text was coming
from somewhere we hadn't found.

The breakthrough was a memory, not a discovery. Earlier, when the buttons had briefly
lived in `texts_jp.txt` as `landing.view.<event>.button` keys, *some of them had
translated*. That was the tell: the button really is resolved through localization, by
that key. And because that key, like every localization key, is identical on every hotel,
one set of key translations covers every server. So the reliable, shippable answer was the
same universal idea as the rest of the client: translate by key, applied through
`updateLocalization`.

We also wanted something for *future* events, without waiting for a manual update every
time the game shipped a new key with the same recycled phrase behind it ("See the items!"
alone sits behind dozens of different `landing.view.*` keys across event cycles). The idea
was a **value-based fallback**: a phrase map, keyed by the source-language text itself
rather than by the localization key, so a brand-new key with a phrase we'd already seen
would translate itself with zero manual work.

We built it. We shipped it. It never fired once.

Chasing that down turned into its own small investigation, and the answer is worth
recording because it closes a door that's tempting to keep reopening. The client's
localization system, `CoreLocalizationManager`, stores every string in a single
`Dictionary` keyed **only** by localization key; `getLocalization`, `updateLocalization`,
and the listener system that widgets like `TextController` use for `${key}`-style captions
are all key-indexed, end to end. There is no point in that pipeline where a *resolved
value* passes through code before the specific key's listeners are already wired to that
exact key. A phrase map has nothing to attach to; there's no seam in the architecture that
exposes "the text that's about to be shown" independent of "the key it came from." We
tried multiple hook points (the manager's `getLocalization` override, a boot-time full
sweep, a listener-level intercept) and each one turned out to require a value the system
never actually produces anywhere reachable.

So the honest ending: value-based fallback isn't a bug we didn't quite finish. It's not
compatible with this client's localization architecture at all, full stop. The key-based
answer, the same one that already covers every hotel, turned out to *be* the complete
answer, not a placeholder for a smarter one. We stopped digging once the shape of the wall
became clear instead of continuing to look for a door that wasn't there.

---

## Part XII: The philosophy, in one sentence

If there's a single idea that made this whole thing universal instead of a
one-server hack, it's this: **key on what's shared, not on what varies.**

Localization keys are shared across hotels; values aren't, so translate by key.
Catalog pageNames are shared; pageIds aren't, so index by pageName. Every time we were
tempted to reach for the convenient, server-specific handle, it led to a client that only
worked in one place. Every time we reached for the shared handle, universality came out
for free, and, as Part XI ended up proving the hard way, the corollary holds too: when a
system truly has no shared handle to grab, no amount of cleverness invents one for you.

---

## Part XIII: War stories (a field guide to the traps)

For anyone who tries to extend or rebuild this, here is the short list of things that will
eat your evening, collected in one place:

- Deleting `localizationsReady()` by accident → `Error #1009` at boot. Keep a good build and
  diff.
- Removing a boot-timer block and taking `ResetVariablesValues()` or the `WindowManager`
  assignment with it → `WindowManager` becomes null → `#1009` again.
- Keying the catalog by `pageId` → the whole store collapses or reverts. Use pageName.
- Feeding the catalog a raw `.localization.ja` export instead of the `pageName|||JP` format
  → silent fallback to the old language.
- Putting Japanese on the wire → the server eats it. Always encode to ASCII first.
- Placing the chat encode in `ParseChatInput` instead of before the `switch(chatType)` →
  every message is flattened into a plain `say`, silently killing bold and whisper. Hook
  position isn't cosmetic; it decides what survives.
- Chaining the catalog/landing loaders off the `jpcharset.txt` load: if that one file goes
  missing, the whole chain (catalog, help pages, buttons) falls together while `texts_jp`
  survives on its own path. Decouple it, or at least know the symptom.
- Assuming you found where a string comes from. Force a marker and *prove* it before you
  build the real fix.
- Assuming a phrase-level fallback can sit anywhere near a key-indexed localization system
  → it can't. If every read and every write in the pipeline is keyed, there's no seam left
  for a value to pass through unintercepted. Confirm the architecture before building
  around it, not after.
- Swapping a pet's spoken bubble by string-matching the server's echo against what was
  sent → fragile, fails silently on any drift between the two strings. Carry the
  already-known translation forward explicitly instead of trying to recognize it after the
  fact.
- Bundling translation files inside the same package as a client you don't control the
  release schedule for → every fix waits on someone else's timeline. Fetch live data
  instead of shipping it frozen inside the app.

<div align="center"><img width="1098" height="742" alt="image" src="https://github.com/user-attachments/assets/a4be52e3-372e-422f-bb2f-646798ace460" /></div>
<p align="center"><sub><b>Image 14.</b> Where each translated string comes from, and how each source gets
intercepted before it reaches the player.</sub></p>

---

## Part XIV: Shipping without shipping

Every fix so far lived inside the SWF, or in a `.txt` file sitting next to it on disk. That
was fine for building the thing. It was a real problem for *maintaining* it.

HabboAirPlus isn't ours. Lilith owns the client, ships her own updates on her own schedule,
and none of that has anything to do with when we finish translating a new event's landing
page. Every prior version of the translation files lived bundled inside the same folder as
the client itself, which meant that keeping the Japanese support current required either
convincing Lilith to bundle our latest `.txt` files into her next release, or asking every
single person running the modified client to manually replace files on their own disk by
hand, forever, every time a new event shipped. Neither scales. Neither is sustainable for
a two-person side project translating a hotel that's been closed for over a decade.

The fix, in hindsight, is almost embarrassingly simple, and it's the same trick every
"live-updating" app has used since patch files existed: don't bundle the data, *fetch* it.

`texts_jp.txt`, `catalog_jp.txt`, and `habbopages_jp.txt` now live in a public GitHub
repository instead of only on disk. At boot, the client tries to pull each file straight
from there first. Only if that fails (no connection, GitHub having a bad moment, a
request that neither completes nor explicitly errors within a few seconds) does it fall
back to the copy still bundled locally, exactly as before. Editing a file in the
repository is now the entire deployment process. No client rebuild, no waiting on anyone
else's release cycle, no asking a dozen people to swap files by hand. Push a commit, wait
a few minutes for GitHub's CDN to catch up, and every modified client picks it up the next
time it opens.

`jpcharset.txt` got a smaller, related fix along the way. Because the file is read
positionally (the index of each character *is* the data the base-62 chat encoding runs
on) it had never been able to carry a header explaining what it was or why the order
mattered, on pain of shifting every character after it. A one-line marker
(`###CHARSET_START###`) fixed that: everything above the marker is now free-form
commentary, everything below it is the untouched, position-sensitive character list the
client actually reads. Small fix, but it turned a file that only made sense if you already
knew its rules into one that explains itself.

None of this changed a single line of translated text. It changed how a *correction* to
translated text reaches everyone who's already running the client; from "eventually,
maybe, if I remember to tell people" to "the next time they open it."

<div align="center"><img width="927" height="277" alt="Screenshot 2026-09-09 at 04 08 10" src="https://github.com/user-attachments/assets/ab5e35a5-1a0e-4f7b-9b8c-bb00c9f05e45" /></div>
<p align="center"><sub><b>Image 15.</b> The GitHub repository the client now reads from directly; a commit here is the entire deployment process.</sub></p>

---

## Epilogue: why any of this matters

A hotel that closes doesn't have to take its language with it.

That's the whole reason, underneath the packet dumps and the font metadata and the base-62
encoding. Somewhere, someday, someone is going to open this client, type `:lang jp`, and
see the orange and the katakana and the slightly-wrong-in-the-right-way spelling, and feel,
for one second, like they walked back into a room they were sure had been locked forever.

We almost didn't finish it. We finished it because Max got one character through, and
because neither of us could quite let the room stay closed.

*For Max, and for habbo.jp. You have my deepest gratitude!* 🕯️

<div align="center"><img width="777" height="570" alt="image" src="https://github.com/user-attachments/assets/15f9c595-af98-4b1f-907e-5b68463b2a33" /></div>
<p align="center"><sub><b>Image 16.</b> ……ただいま。 ("...I'm home.")</sub></p>

---

### Credits

- **Concept, the G-Earth byte expression, the DefineFont3 binary repair and alignment-zone
  restoration, translation, and client engineering:** [Yohaku](https://github.com/yohaku404).
- **The font rendering breakthrough (editing font metadata, impersonating Ubuntu, putting
  the first live glyph on screen), and the HTML archives used as the source for translating
  the catalog, FAQ pages, and other content with no key in Habbo's official
  `external_texts`**: [Max](https://github.com/maxph3).
- Built on [HabboAirPlus](https://github.com/LilithRainbows/HabboAirPlus) by Lilith. Japanese terminology follows official habbo.jp usage.
