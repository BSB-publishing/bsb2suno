"""The lyric-language text: one edition, verse by verse, read the shared bcv-commons way.

Text comes from helloAO (the route ``catalog/e/eng/text-route.json`` gives for BSB), is
converted to USJ and extracted with the vendored ``tools/verse-text`` package, so the verse
text, its tokens and the book fingerprint are exactly those the alignments were built on.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vendor" / "verse_text"))

from bcv_tokenize import file_hash, fingerprints, strip_marks, tokenize  # noqa: E402
from helloao_to_usj import merge_book_usj  # noqa: E402
from verse_text import extract_usj, first_number  # noqa: E402

from . import config, fetch  # noqa: E402

PARAGRAPH_MARKERS = {"p", "m", "pmo", "pm", "pi", "pi1", "pi2", "nb", "po", "pr", "mi"}
POETRY_PREFIX = "q"


@dataclass
class Verse:
    chapter: int
    verse: int
    text: str
    tokens: list[str]
    spans: list[tuple[int, int]] | None  # char offsets of each token in ``text``; None if not reproducible


@dataclass
class BookText:
    edition: str
    book: str
    verses: dict[tuple[int, int], Verse]
    fingerprint: str
    chapter_fingerprints: dict[int, str]
    paragraph_starts: set[tuple[int, int]] = field(default_factory=set)  # a prose paragraph opens at this verse
    heading_before: set[tuple[int, int]] = field(default_factory=set)    # a section heading stands before this verse
    poetry_verses: set[tuple[int, int]] = field(default_factory=set)     # the edition sets the verse in poetic lines
    translation_meta: dict = field(default_factory=dict)
    titles: dict[tuple[int, int], str] = field(default_factory=dict)       # superscription before this verse

    @property
    def file_hash(self) -> str:
        return file_hash(self.fingerprint)

    def chapter_verses(self, chapter: int) -> list[Verse]:
        return [v for (c, _), v in sorted(self.verses.items()) if c == chapter]


def token_spans(text: str) -> list[tuple[int, int]] | None:
    """Character offsets of the tokens ``tokenize(text)`` gives, or None where the
    per-character reading cannot reproduce them (scripts with context-dependent rules)."""
    spans: list[tuple[int, int]] = []
    start = None
    for i, ch in enumerate(text):
        s = strip_marks(ch)
        is_word = bool(s) and all(unicodedata.category(c)[0] in ("L", "M") for c in s)
        if is_word and start is None:
            start = i
        elif not is_word and start is not None and s != "":
            spans.append((start, i))
            start = None
    if start is not None:
        spans.append((start, len(text)))
    if [strip_marks(text[a:b]) for a, b in spans] != tokenize(text):
        return None
    return spans


def _walk_layout(usj: dict, book: BookText) -> None:
    """Paragraph starts, headings and poetic verses from the USJ's paragraph markers."""
    chapter = 0
    last_verse: tuple[int, int] | None = None
    pending_heading = False
    for node in usj["content"]:
        if node.get("type") == "chapter":
            chapter = int(node["number"])
            continue
        if node.get("type") != "para":
            continue
        marker = node.get("marker", "")
        content = node.get("content", []) or []
        if marker.startswith("s") or marker in ("ms", "mr", "d"):
            pending_heading = True
            continue
        opens_with_verse = bool(content) and isinstance(content[0], dict) and content[0].get("type") == "verse"
        verse_nums = [int(first_number(x["number"])) for x in content
                      if isinstance(x, dict) and x.get("type") == "verse"]
        if opens_with_verse:
            here = (chapter, verse_nums[0])
            if marker in PARAGRAPH_MARKERS:
                book.paragraph_starts.add(here)
            if pending_heading:
                book.heading_before.add(here)
        if marker.startswith(POETRY_PREFIX):
            for v in ([last_verse] if last_verse and not opens_with_verse else []) + [(chapter, n) for n in verse_nums]:
                book.poetry_verses.add(v)
        if verse_nums:
            last_verse = (chapter, verse_nums[-1])
            pending_heading = False


def lift_descriptive(chapter_json: dict, book: str, books: tuple[str, ...] = ("PSA",)) -> tuple[dict, dict[int, str]]:
    """helloAO now gives a psalm superscription inside verse 1 as ``{"text", "descriptive": true}``.
    verse-text 2.0.0 does not know that flag and would read the title as verse text, which
    changes the fingerprint (BSB PSA: e0860a31 instead of the aligned c867de4b). Move each such
    piece out to a ``hebrew_subtitle`` item before its verse, which the converter reads as
    ``\\d``, a title. Only in ``books`` (editions.toml descriptive_title_books; BSB: the Psalms):
    ZEC 12:1's oracle heading is also flagged ``descriptive`` by helloAO but is verse text in BSB.
    Returns the fixed chapter and {verse: superscription}."""
    ch = chapter_json["chapter"]
    if book not in books:
        return chapter_json, {}
    content, titles = [], {}
    for item in ch.get("content", []):
        if isinstance(item, dict) and item.get("type") == "verse":
            desc = [x for x in item.get("content", []) if isinstance(x, dict) and x.get("descriptive")]
            if desc:
                titles[int(item["number"])] = " ".join(x["text"] for x in desc)
                content.append({"type": "hebrew_subtitle", "content": [x["text"] for x in desc]})
                item = {**item, "content": [x for x in item["content"] if x not in desc]}
        content.append(item)
    return {**chapter_json, "chapter": {**ch, "content": content}}, titles


LEAK = re.compile(r"(?<=[^\s\d])(\d{1,3}):(\d{1,3}) ")
LINK_TARGET = re.compile(r"\|[1-4A-Z][A-Z0-9]{2} \d+:\d+(?:[-–]\d+(?::\d+)?)?")


def _usj_text(n) -> str:
    return n if isinstance(n, str) else "".join(_usj_text(c) for c in n.get("content", []) or [])


def footnote_texts(usj_dir: Path, book: str) -> dict[tuple[int, int], list[str]]:
    """{(chapter, verse): [footnote text as "C:V text"]} from a USJ book with footnotes."""
    path = usj_dir / f"{book}.usj"
    if not path.exists():
        return {}
    out: dict[tuple[int, int], list[str]] = {}
    cv = [0, 0]

    def walk(n) -> None:
        if not isinstance(n, dict):
            return
        if n.get("type") == "chapter":
            cv[0] = int(n["number"])
        elif n.get("type") == "verse":
            cv[1] = int(first_number(n["number"]))
        elif n.get("type") == "note":
            out.setdefault((cv[0], cv[1]), []).append(_usj_text(n))
            return
        for c in n.get("content", []) or []:
            walk(c)

    walk(json.loads(path.read_text(encoding="utf-8")))
    return out


def cut_leaked_footnotes(chapter_json: dict, notes: dict[tuple[int, int], list[str]]) -> tuple[dict, list[str]]:
    """helloAO's BSB JSON (seen 2026-11-18) merges some footnotes into words-of-Jesus text runs,
    as "...house2:49 Or I had to be about My Father’s business?”", and leaves ``footnotes`` empty:
    135 verses in MAT, MRK, LUK, JHN, ACT, 1CO, HEB, REV. Cut each leaked note, matched exactly
    against the edition's own footnotes (with helloAO's ``|BOOK C:V`` link targets dropped).
    Returns the fixed chapter and the refs of leaks that could not be cut."""
    ch = chapter_json["chapter"]
    c = int(ch["number"])
    unresolved: list[str] = []
    content = []
    for item in ch.get("content", []):
        if isinstance(item, dict) and item.get("type") == "verse":
            v = int(item["number"])
            new = []
            for x in item.get("content", []):
                if isinstance(x, dict) and isinstance(x.get("text"), str) and any(
                        (int(m.group(1)), int(m.group(2))) == (c, v) for m in LEAK.finditer(x["text"])):
                    t = LINK_TARGET.sub("", x["text"])
                    for n in notes.get((c, v), []):
                        t = t.replace(n, "")
                    if any((int(m.group(1)), int(m.group(2))) == (c, v) for m in LEAK.finditer(t)):
                        unresolved.append(f"{c}:{v}")
                    else:
                        x = {**x, "text": t}
                new.append(x)
            item = {**item, "content": new}
        content.append(item)
    return {**chapter_json, "chapter": {**ch, "content": content}}, unresolved


TABLE_MARKER = re.compile(r"\s+vvv(?=\s)")


def drop_table_markers(chapter_json: dict) -> dict:
    """helloAO's BSB has the BSB tables' joint-phrase marker ``vvv`` as a word in GEN 35:18
    ("she named vvv him Ben-oni"); it is not text."""
    ch = chapter_json["chapter"]

    def fix(x):
        if isinstance(x, str):
            return TABLE_MARKER.sub("", x)
        if isinstance(x, dict) and isinstance(x.get("text"), str):
            return {**x, "text": TABLE_MARKER.sub("", x["text"])}
        return x
    content = [{**it, "content": [fix(x) for x in it["content"]]} if isinstance(it, dict) and it.get("type") == "verse"
               else it for it in ch.get("content", [])]
    return {**chapter_json, "chapter": {**ch, "content": content}}


FIXES = ("descriptive-titles", "table-markers", "leaked-footnotes")


def load_book(edition: str, book: str) -> BookText:
    """The edition's text of a book, with the text fixes editions.toml lists for the edition."""
    ed = fetch.pins()["editions"][edition]
    ecfg = config.edition(edition)
    fixes = ecfg.get("fixes", [])
    unknown = [f for f in fixes if f not in FIXES]
    if unknown:
        raise config.ConfigError(f"config/editions.toml [{edition}]: unknown fix(es) {', '.join(unknown)}; "
                                 f"known: {', '.join(FIXES)}")
    meta = fetch.helloao_books(ed["helloao_id"])[book]
    notes_dir = ed.get("footnotes_usj_dir") if "leaked-footnotes" in fixes else None
    notes = footnote_texts((fetch.ROOT / notes_dir).resolve(), book) if notes_dir else {}
    title_books = tuple(ecfg.get("descriptive_title_books", []))
    chapters, titles, leaks = [], {}, []
    for c in range(meta["firstChapterNumber"], meta["lastChapterNumber"] + 1):
        fixed = fetch.helloao_chapter(ed["helloao_id"], book, c)
        t: dict[int, str] = {}
        if "descriptive-titles" in fixes:
            fixed, t = lift_descriptive(fixed, book, title_books)
        if "table-markers" in fixes:
            fixed = drop_table_markers(fixed)
        bad: list[str] = []
        if "leaked-footnotes" in fixes:
            fixed, bad = cut_leaked_footnotes(fixed, notes)
        chapters.append(fixed)
        leaks.extend(bad)
        titles.update({(c, v): s for v, s in t.items()})
    if leaks:
        print(f"warning: {book}: footnote text leaked into verse text, not cut (no matching footnote"
              f"{'' if notes else '; footnotes_usj_dir not found'}): {', '.join(leaks)}", file=sys.stderr)
    usj = merge_book_usj(book, chapters)
    verses: dict[tuple[int, int], Verse] = {}
    for ch, vs in extract_usj(usj).items():
        for v in vs:
            key = (int(ch), int(v["verse"]))
            verses[key] = Verse(key[0], key[1], v["text"], tokenize(v["text"]), token_spans(v["text"]))
    fp, ch_fps = fingerprints({k: v.text for k, v in verses.items()})
    bt = BookText(edition, book, verses, fp, ch_fps, translation_meta=chapters[0].get("translation", {}), titles=titles)
    _walk_layout(usj, bt)
    return bt
