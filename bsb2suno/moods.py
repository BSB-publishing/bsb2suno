"""Chapter moods: where the Hebrew/Greek itself gives a reason for a chapter's own style.

A book keeps one style (its profile). A chapter gets its own style only where the source says
something about how it sounds:

- ``heading``   a psalm-heading term naming the kind of piece (תְּפִלָּה a prayer, תְּהִלָּה praise,
                לְתוֹדָה thanksgiving, שִׁיר יְדִידֹת a love song, the sabbath) or הַלְלוּ יָהּ in the text;
                and the instruments the heading names (בִּנְגִינוֹת strings, הַנְּחִילוֹת flutes)
- ``song``      a song in narrative: the Masoretic song layout covers the chapter, in a book that
                is not itself song (EXO 15, DEU 32, JDG 5, 2SA 22, 1CH 16)
- ``delivery``  most of the chapter is speech delivered one way (passage-facts ``delivery``):
                a lament (EZK 19), a prayer (NEH 9), a rebuke (MAT 23)

Which cue gives which mood is in config/moods.toml; the words the mood adds to the style line
are in config/profiles.toml ([moods], [instruments]). Facts are in source chapters; the chapter
of the edition is found through the verse map.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from . import structure, textforms
from .config import ConfigError, toml
from .config import book as config_book

# Heading terms of the text that name a kind of piece, and the mood they give.
HEADING_MOODS = {
    "fm.ps.tefillah": "prayer",
    "fm.ps.tehillah": "praise",
    "fm.ps.halleluyah": "praise",
    "fm.ps.letodah": "thanksgiving",
    "fm.ps.yedidot": "love_song",
    "fm.ps.shabbat": "sabbath",
}
HEADING_INSTRUMENTS = {"fm.ps.neginot": "strings", "fm.ps.nechilot": "flutes"}


@dataclass
class Mood:
    mood: str | None                 # e.g. "lament"; None = only an instrument
    basis: str                       # heading, song, delivery
    evidence: str                    # what in the source gave it
    instruments: tuple[str, ...] = ()
    style: str | None = None         # a whole style line set by hand (books/<BOOK>.toml)


def _verses(ref: str) -> list[tuple[int, int]]:
    """The verses of a passage-facts ref ("LUK 1:68-73", "PSA 3:1", "GEN 1:31-2:3")."""
    m = re.match(r"\S+ (\d+):(\d+)(?:-(?:(\d+):)?(\d+))?", ref)
    if not m:
        return []
    c, a = int(m[1]), int(m[2])
    c2 = int(m[3]) if m[3] else c
    b = int(m[4]) if m[4] else a
    if c2 != c:
        return [(c, v) for v in range(a, 200)]          # to the chapter end; the rest is the next chapter
    return [(c, v) for v in range(a, b + 1)]


def book_moods(book: str, facts: list[dict], rows: list[dict], to_ed, layout: dict) -> dict[int, Mood]:
    """Edition chapter -> its mood, for every chapter of the book that has one."""
    cfg = toml("moods.toml")
    codes = textforms.codes()
    spine = sorted({(r["chapter"], r["verse"]) for r in rows})
    by_ch: dict[int, list[tuple[int, int]]] = {}
    for cv in spine:
        by_ch.setdefault(cv[0], []).append(cv)

    def ed_chapter(c: int) -> int | None:
        vs = by_ch.get(c) or [(c, 1)]
        e = to_ed(vs[len(vs) // 2])
        return e[0] if e else None

    found: dict[int, list[Mood]] = {}

    # 1. heading terms and halleluyah
    hd: dict[int, list[str]] = {}
    for f in facts:
        if f.get("kind") == "form" and f.get("value") in {**HEADING_MOODS, **HEADING_INSTRUMENTS}:
            hd.setdefault(int(f["first"][2:5]), []).append(f["value"])
    for c, vals in hd.items():
        moods = [HEADING_MOODS[v] for v in vals if v in HEADING_MOODS]
        inst = tuple(dict.fromkeys(HEADING_INSTRUMENTS[v] for v in vals if v in HEADING_INSTRUMENTS))
        terms = [codes.get(v, v).removeprefix("heading: ").removeprefix("mark: ").split(": a term of the text")[0]
                 for v in dict.fromkeys(vals)]
        found.setdefault(c, []).append(Mood(moods[0] if moods else None, "heading", "; ".join(terms), inst))

    # 2. a song in narrative
    sv = structure.setting_verses(facts, spine, layout.get("setting"))
    share = layout.get("setting", {}).get("share", 0.5)
    not_songs = set(cfg.get("song", {}).get("not_songs", []))
    if len(sv["song"]) < share * max(len(spine), 1):          # the book itself is not song
        for c, vs in by_ch.items():
            n_song = sum(1 for cv in vs if cv in sv["song"])
            if n_song >= share * len(vs) and f"{book} {c}" not in not_songs:
                found.setdefault(c, []).append(Mood("song", "song", f"Masoretic song layout over {n_song} of {len(vs)} verses"))

    # 3. delivery covering most of the chapter
    dcfg = cfg.get("delivery", {})
    group_of = {}
    for g, labels in dcfg.get("groups", {}).items():
        for lab in labels:
            group_of[lab] = g
    known = set(codes.values())
    bad = sorted(lab for lab in group_of if lab not in known)
    if bad:
        raise ConfigError(f"config/moods.toml [delivery.groups]: unknown delivery label(s) {', '.join(bad)} "
                          "(use the labels of passage-facts codes.tsv, e.g. \"lament\", \"praying\")")
    cover: dict[int, dict[str, set]] = {}
    for f in facts:
        if f.get("kind") != "delivery":
            continue
        g = group_of.get(codes.get(f["value"], ""))
        if g:
            for cv in _verses(f["ref"]):
                if cv in by_ch.get(cv[0], ()):
                    cover.setdefault(cv[0], {}).setdefault(g, set()).add(cv)
    min_share = dcfg.get("min_share", 0.4)
    for c, groups in cover.items():
        g, vs = max(groups.items(), key=lambda x: len(x[1]))
        n = len(by_ch[c])
        if len(vs) >= min_share * n:
            found.setdefault(c, []).append(Mood(g, "delivery", f"speech delivered as {g} over {len(vs)} of {n} verses"))

    # one mood per chapter, by the priority in moods.toml; instruments are kept from the heading
    order = cfg.get("priority", [])
    out: dict[int, Mood] = {}
    for c, ms in found.items():
        e = ed_chapter(c)
        if e is None:
            continue
        with_mood = sorted((m for m in ms if m.mood), key=lambda m: order.index(m.mood) if m.mood in order else len(order))
        inst = tuple(dict.fromkeys(i for m in ms for i in m.instruments))
        best = with_mood[0] if with_mood else ms[0]
        ev = "; ".join(dict.fromkeys(m.evidence for m in ms))
        out[e] = Mood(best.mood, best.basis, ev, inst)
    return out


def apply_overrides(book: str, found: dict[int, Mood], profile) -> dict[int, Mood]:
    """The [chapters.N] blocks of config/books/<BOOK>.toml laid over the source's moods."""
    out = dict(found)
    for n, ch in (config_book(book).get("chapters") or {}).items():
        c = int(n)
        src = found.get(c)
        where = f"config/books/{book}.toml [chapters.{c}]"
        if "style" in ch:
            out[c] = Mood(src.mood if src else None, "manual", where, (), ch["style"])
        elif "mood" in ch:
            m = ch["mood"]
            if not m:
                out.pop(c, None)
                continue
            if m not in (profile.moods or {}):
                raise ConfigError(f"{where}: mood {m!r} is not in config/profiles.toml [moods]; "
                                  f"choose from {', '.join(profile.moods or {})}")
            out[c] = Mood(m, "manual", where + (f" (the source: {src.evidence})" if src else ""),
                          src.instruments if src else ())
    return out


def chapter_style(profile, mood: Mood | None) -> tuple[str, str | None]:
    """(the chapter's style line, the words its mood added, or None when it keeps the book style)."""
    if mood is None:
        return profile.style, None
    if mood.style:
        return mood.style, "its own style line"
    words = [w for w in ([profile.moods.get(mood.mood, "")] if mood.mood else [])
             + [profile.instruments.get(i, "") for i in mood.instruments] if w]
    if not words:
        return profile.style, None
    added = ", ".join(words)
    return f"{profile.base_style}, {added}{profile.suffix}", added


def summary(moods: dict[int, Mood]) -> Counter:
    return Counter(m.mood or "instrument" for m in moods.values())
