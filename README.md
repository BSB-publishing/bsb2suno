# bsb2suno

Suno lyrics from the **Berean Standard Bible**. The lyric words are the BSB's own, verbatim. Where the
lines break, who sings them, and whether the chapter is sung or told come from the Hebrew and Greek
text, through bcv-commons data.

```
python3 -m bsb2suno RUT 1            # one chapter → output/RUT/RUT_001.suno.txt + .json
python3 -m bsb2suno PSA 23 136       # several
python3 -m bsb2suno JON all          # a whole book
make examples                        # RUT 1, PSA 23, PSA 136, EXO 15, LUK 1
make test
make cast                            # rebuild config/cast.csv from the data (keeps manual rows)
```

Needs Python ≥ 3.11 and `pyarrow` (`pip install -e .`; the tool reads `config/` from the repository,
so install it editable). The first run downloads its inputs into `cache/` (git-ignored, about 100 MB)
at the revisions pinned in [`pins.json`](pins.json). The tests download too.

For the BSB, clone [BSB-publishing/bsb2usfm](https://github.com/BSB-publishing/bsb2usfm) next to this
repository. Its USJ footnotes are used to cut the footnote text helloAO merged into 135 verses
(`footnotes_usj_dir` in `pins.json`). Without it, those verses keep the stray text and their chapters fall
back to verse-end line breaks (a warning names them).

## What it reads, per chapter

| Piece | Dataset (pinned in `pins.json`) | Used for |
|---|---|---|
| Structure | `bcv-commons/hebrew-clause-lines` v0.2 (Tanakh), `bcv-commons/greek-nt-clause-lines` v0.2 (NT) | line breaks, paragraph ends, quotations and speakers |
| Setting and forms | `bcv-commons/passage-facts` v0.2 | song / poetic lines / prose; refrains, acrostics, couplet halves, psalm headings |
| Stanza breaks | `bcv-commons/clause-connectives` v0.1, `bcv-commons/clause-columns` v1.2 | where a long stanza is split |
| Lyric text | BSB from bible.helloao.org, the route `bcv-commons/bibles` gives for BSB; read with the vendored `tools/verse-text` 2.0.0 | the words |
| The join | `bcv-commons/full-alignments-manual` v1.1, layer `eng_BSB+manual+bsb-tables` | which BSB token each Hebrew/Greek word (MACULA key) is rendered by |

The join uses the **full** BSB alignment, the publisher's own interlinear tables. It links every source
token, function words included, plus the words the editor supplied. Clause-line `words` are MACULA keys;
`_index/<BOOK>_keys.json` / `_fn_keys.json` of compact-alignments turn each `srcOrd` / `fnOrd` back into
a key. Spans are keyed by spine verse and read from the BSB verse the pinned verse map gives (Psalm titles
and the like). If no full layer exists, the compact alignment (content words only) is used. If neither
exists for the text, lines break at verse ends.

The book's text fingerprint has to match the alignment file name. If it doesn't, the latest aligned
version is used for the chapters whose chapter fingerprint matches ours (`_fingerprints.txt` in
compact-alignments-meta), and the other chapters break at verse ends. Nothing is aligned to text it
wasn't built on.

## The rules

**Line breaks.** Each clause line starts a new lyric line at the *earliest BSB token any of its words
aligned to*. That is "the target token aligned to the first aligned word", taken in BSB order rather than
Hebrew/Greek order. Source order fails: a Hebrew line usually opens with וַ "and", which BSB renders late
or folds away, and BSB reorders clauses. Taking the breaks in BSB order gives Ruth 1:6 as

```
When Naomi heard in Moab
that the LORD had attended to His people
by providing them with food,
she and her daughters-in-law prepared
to leave the land of Moab.
```

A clause line with no aligned word adds no break, so it stays with the line before. A verse always starts
a line. A line shorter than 3 words joins its neighbour in the same verse and voice (`lines.min_words`).

Three forms of the Hebrew text (passage-facts v0.2) add line starts, through the alignment:
- **Refrains:** each line the text repeats (`fm.tx.refrain`) is a line of its own.
- **Acrostics:** a new acrostic letter (`fm.tx.acrostic`) starts a line.
- **Couplet halves:** in Psalms, Proverbs and Job, a poetic verse also breaks where its second half starts
  (`fm.tx.halves`, the main accent; `lines.poetry`).

**Stanzas.** A stanza ends at the line holding the end of a clause line with `para_end` (Leningrad) or
`para_end_mam`. In an acrostic whose letters cover several verses (Psalm 119, Lamentations 3), each new letter
starts a stanza; the comment block names it (`119:9-12 · ב Beth`). A stanza over 12 lines (`stanzas.max_lines`)
is split at verse starts, where the Hebrew/Greek most clearly starts something new. The signals come from the
clause that opens the verse:

| Signal | Source | Weight |
|---|---|---|
| a new episode: Hebrew וַיְהִי / וְהָיָה with no actor, Greek καὶ ἐγένετο | clause-connectives `episode`, clause-columns | 3 |
| "and now", a Greek development connective (δέ, οὖν, τότε), a time clause | clause-connectives | 1 |
| a setting clause | clause-columns `line` | 1 |
| a new participant in narration | clause-columns `part_switch` | 1 |
| the narrator taking over from a speaker, or a speaker from the narrator | the quote data | 1 |

A split weighs one more stanza (cost 2) against the break it can use. The Greek has no paragraph marks, so in
the NT these signals alone shape the stanzas. Nothing here depends on the edition, so the stanzas, and the
cut points built on them, are the same in every language. An edition may add its own headings or paragraphs
as extra weight (`edition_heading_weight`, `edition_paragraph_weight`, `edition_paragraphs`). They are off for
BSB.

**Voices.** Where `quotation` is set, the line is sung by the speaker's *voice class*: `female`, `male`,
`group`, `female_group` or `divine`. Outside quotes it is the narrator, the persona's lead. Each class
becomes a tag that names a kind of voice, such as `[Female Vocal]`, `[Choir]` or `[Deep Male Vocal]`. A
tag never names a person, because Suno doesn't know who Naomi is. Who each tag stands for is listed in
the comment block (`# Voices: [Female Vocal] Naomi, Ruth; [Female Choir] two daughters-in-law, the women`).

- **Where tags go.** A tag is written where the voice changes. `[Lead Vocal]` marks the return to the
  narrator.
- **Nested quotes.** A quote inside a speech (Eve quoting God, GEN 3:3) is sung by the outer speaker.
- **Where the classes come from.** The classes are in [`config/cast.csv`](config/cast.csv), keyed by
  the clause lines' `speaker_id`, which is the same in every edition and language. See
  [Configuration](#configuration).

**Setting.** If passage facts set ≥ half the chapter as song (`fm.ms.song`, `qt.song`), the setting is
**song**. If song and poetic lines (`fm.ms.lines`, `fm.ed.*`, `fm.tr.poetry`) together reach half, it is
**poetry** (sung verses). Otherwise it is **prose** (narrative ballad). The setting only shapes the
sections; the style line comes from the book's profile, so a book sounds the same in every chapter.

**Sections.** Each stanza is a `[Verse n]`: a song verse, not a Bible verse (the comment block gives its
verse range). In a prose chapter, a stanza the facts set as song or poetry is a `[Bridge]` (Ruth's vow, the
Magnificat). A line the Hebrew/Greek repeats in its chapter (`fm.tx.refrain`) is a `[Chorus]`, e.g.
"And there was evening, and there was morning" in Genesis 1, in every edition alike. Where the refrain comes
back inside one stanza (Psalm 136), the stanza stays whole as call and response: `[Lead Vocal]` / `[Choir]`.
`layout.toml` sets the chorus source (the text's refrains, or the edition's repeated lines), its style, and
which section tags are written (all, only `[Chorus]`/`[Bridge]`, or none).

**Writing.** Nothing is shortened, paraphrased or added. The comment block gives each section's verse
range, the superscription and the psalm-heading terms (`fm.ps.*`: for the leader, the instruments, the
tune), the selahs and any one-letter-per-verse acrostic (all noted, not sung), the credits, and a warning when the lyrics run past
`--max-chars` (default 5000), so you know to shorten them. Any shortening done later should be listed
there.

## Configuration

All choices of sound live in `config/`. The files are meant to be edited by hand by anyone: the
settings are TOML files with a comment on every setting, and the cast is a spreadsheet. Everything is
keyed so that it carries over to other books, editions and languages.

| File | Edit with | Keyed by | Holds |
|---|---|---|---|
| [`profiles.toml`](config/profiles.toml) | any text editor | profile name | style line, Suno persona names (`persona.female` / `persona.male`), the tag for each voice type |
| [`books.toml`](config/books.toml) | any text editor | book, optionally edition | profile and lead (`female` / `male`) per book; per edition `style_suffix` (e.g. `, sung in Spanish`), its own personas or tags |
| [`cast.csv`](config/cast.csv) | Excel, LibreOffice, Google Sheets | `speaker_id` (source data) | voice of each of the 1,448 speakers |
| [`cast-rules.toml`](config/cast-rules.toml) | any text editor | none | the rules that give speakers their voice |
| [`layout.toml`](config/layout.toml) | any text editor | none | the defaults: text (word counting, line-start punctuation), setting codes, lines, stanzas, section tags, chorus, psalm marks, length limits |
| [`editions.toml`](config/editions.toml) | any text editor | edition | the edition's text fixes, style suffix, own song choices and personas, and any layout setting |
| [`languages.toml`](config/languages.toml) | any text editor | ISO 639-3 code | the edition language's words for trimming speaker names and spotting groups; the Hebrew letter names |

A layout setting is looked up in three layers, and the later one wins:

1. `layout.toml`, the defaults;
2. `languages.toml [<iso>.layout]`, for every edition in that language (e.g. `count = "characters"` for Chinese);
3. `editions.toml [<EDITION>.layout]`, for that edition.

A choice read from the Hebrew/Greek stays in the code, because it holds for every edition. A choice read
from an edition's words or layout is a setting.

A mistake in a file (a misspelt profile, an unknown voice or fix, a broken line) stops the run with the file,
the row or book, and what is allowed.

**Profiles.** A profile is chosen per book, never per chapter. In Suno, save one persona per profile
and lead, then type its name into `profiles.toml` (`persona.female = "My Country F"`). The comment
block shows which persona to select. `--profile` / `--lead` override a book for one run.

**Cast.** `cast.csv` has one row per speaker:

| Column | What it holds |
|---|---|
| `voice` | one of `narrator`, `female`, `male`, `group`, `female_group`, `divine` |
| `basis` | which rule set the voice |
| `name` | the speaker's name |
| `source` | the Hebrew/Greek word naming them |
| `words` | how many words they speak |
| `books` | the books they speak in |
| `label_BSB` | the edition's own name for them |
| `note` | free text |

To change a speaker, set `voice` and type `manual` in `basis`; [`make cast`](scripts/build_cast.py)
rebuilds the other rows from the data and never changes manual ones. Six are seeded that way, e.g. Wisdom in
Proverbs is female. Save the file as CSV (UTF-8).

The rules in `cast-rules.toml` read Hebrew/Greek words, not English:

- **group:** several people named (`speaker_members`, or several lemmas), or a word like עַם / πᾶς naming
  the speaker;
- **divine:** at least 80% of the speaker's quotes carry passage-facts' `divine` flag (the LORD, God, Jesus,
  the Spirit);
- **the speaking verb:** the verb that introduces the speaker. A plural verb means a group, וַתֹּאמֶר "she
  said" a woman (Acsah, Balaam's donkey). Gender is read from the Hebrew and Aramaic only, because a Greek
  participle agrees with its noun ("a voice saying" is feminine like φωνή);
- **female:** the head word naming the speaker is a word for a woman (אִשָּׁה, בַּת, γυνή, μήτηρ ...) or a
  woman's name (רוּת, Μαρία ...);
- **male:** otherwise.

`make cast` also reads the edition's names for plural speakers ("the Levites", "the women"), using
`languages.toml`. It then stores the result by speaker, so another edition inherits it.

## Output

`output/<BOOK>/<BOOK>_<CCC>.suno.txt`: the style line, the `#` comment block, then the lyrics (paste
the part after the comment block into Suno). `.json` has the same lyrics with every line's verse, BSB
token, quotation id, speaker (id, label, voice class) and clause segment. It also holds the profile
(name, lead, persona, style, tags), the text fingerprint, the alignment file and the pins.

`scripts/cut_points.py [--limit N] [BOOK ...]` lists where each chapter over N characters
(`length.cut_limit`, 4000) can be cut at its section markers into parts under N. It prefers acrostic
letters, then source paragraph ends.

## Fixes to the helloAO text

The text is checked against the fingerprints the alignments were built on. Three helloAO problems are
repaired before reading. Each is a narrow, data-checked fix in `bsb2suno/edition.py`, switched on per
edition in `editions.toml` (`fixes`):

- Psalm superscriptions now come inside verse 1 (`"descriptive": true`). They are read as titles, as
  before. This applies to PSA only.
- 135 footnotes are merged into words-of-Jesus text ("house2:49 Or I had to be about…"). They are cut by
  exact match against the BSB's own footnotes, read from the sibling repo `../bsb2usfm` (configurable
  in `pins.json`; a warning names any verse that cannot be cut).
- A stray `vvv` table marker in GEN 35:18.

With these, 1,182 of 1,189 chapters match the aligned text.

## Licences

Code: MIT (see [`LICENSE`](LICENSE)). `config/cast.csv` and the other files built from bcv-commons data:
CC BY-SA 4.0. The vendored `vendor/verse_text/` is CC0 (bcv-commons/bibles). The lyric text is the BSB
(public domain). The line and voice structure comes from CC BY-SA 4.0 data, so
credit bcv-commons when you publish lyric sheets. See [ATTRIBUTION.md](ATTRIBUTION.md).
