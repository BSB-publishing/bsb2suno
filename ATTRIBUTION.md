# Attribution and licences

The lyrics this repo writes are built from the inputs below. Each keeps its own licence. Every
generated `.notes.txt` repeats the credits, and every `.json` records the pinned revisions it was
built with.

| Input | Source | Licence | Pin |
|---|---|---|---|
| Lyric text | Berean Standard Bible, the BSB-publishing/bsb2usfm USJ release v5.20 (`BSB_usj.zip`) | Public Domain (berean.bible, since 2023-04-30) | `pins.json` `releases` (tag, sha256); the text fingerprint, checked against the alignment file name |
| Line structure, voices, speaking-verb gender | bcv-commons/hebrew-clause-lines v0.2, bcv-commons/greek-nt-clause-lines v0.2 | CC BY-SA 4.0 | `pins.json` |
| Setting; refrains, acrostics, couplet halves, psalm headings | bcv-commons/passage-facts v0.2 | CC BY-SA 4.0 | `pins.json` |
| Stanza breaks (episode, participant, setting) | bcv-commons/clause-connectives v0.1, bcv-commons/clause-columns v1.2 | CC BY-SA 4.0 | `pins.json` |
| The join | bcv-commons/full-alignments-manual v1.1, layer `eng_BSB+manual+bsb-tables` (the BSB translation tables) | CC0 | `pins.json` |
| Indexes, verse map | bcv-commons/compact-alignments `_index/` | CC0 | `pins.json` |
| Chapter fingerprints | bcv-commons/compact-alignments-meta `_fingerprints.txt` | CC0 | `pins.json` |
| Psalm headings, delivery notes (chapter moods) | bcv-commons/passage-facts v0.2 (`fm.ps.*`, `delivery`: Glyssen, CC BY 4.0 + MIT) | CC BY-SA 4.0 | `pins.json` |
| Verse text, tokenizer, fingerprint code | bcv-commons/bibles `tools/verse-text` 2.0.0, vendored in `vendor/verse_text/` | CC0 | commit in `pins.json` |

**Credit line** (as the clause-lines cards ask):

> Hebrew Bible Clause Lines (v0.1) / Greek New Testament Clause Lines (v0.1), bcv-commons, CC BY-SA 4.0.
> Clause layout: bcv-commons. Lines: Miqra according to the Masorah (CC BY-SA 4.0) and unfoldingWord
> Literal Text (CC BY-SA 4.0). Notes: unfoldingWord Translation Notes (CC BY-SA 4.0). Domains: UBS
> Dictionaries (CC BY-SA 4.0). Syntax: MACULA, Clear Bible / Biblica (CC BY 4.0).
> Passage Facts, bcv-commons, CC BY-SA 4.0.

**Share-alike.** The words of the lyrics are the BSB's (public domain). The way they are cut into
lines and stanzas, and the voice tags, come from CC BY-SA 4.0 data. If you publish the
generated lyric sheets, credit bcv-commons as above and treat that layout as CC BY-SA 4.0.

The verse map behind the alignment indexes is TVTMS (STEPBible Data, Tyndale House, Cambridge, CC BY 4.0).
