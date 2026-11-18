"""(Re)build config/cast.csv, the table of who sings each speaker, from the source data.

    python3 scripts/build_cast.py              # all books, edition BSB   (make cast)
    python3 scripts/build_cast.py --edition X  # also record edition X's names for the speakers
    python3 scripts/build_cast.py RUT          # only re-check the speakers of some books

Every speaker_id in the clause lines gets a row: its voice by the rules in cast-rules.toml, the
Hebrew/Greek word naming it (source), how many words it speaks, its books, and the edition's
name for it (label_<EDITION>). A row whose basis is "manual" is a hand decision: its voice, name
and note are kept as they are. Labels of other editions already in the file are kept too.

The edition's labels give one more rule, which only this script applies: a label holding one of
the languages.toml label_group / label_female_group words ("the women", "his brothers") makes the
speaker a group. The result is saved as the speaker's voice, so other editions do not need that
language's word list.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bsb2suno import align, cast, config, edition, fetch, lines, structure  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edition", default="BSB")
    ap.add_argument("books", nargs="*", help="limit to these books (default: all)")
    a = ap.parse_args()

    rules = config.cast_rules()
    old = _old_rows()
    ed = fetch.pins()["editions"][a.edition]
    lw = config.language(ed["iso"])
    label_group = {w.lower() for w in lw.get("label_group", [])}
    label_fgroup = {w.lower() for w in lw.get("label_female_group", [])}

    info: dict[str, cast.SpeakerInfo] = defaultdict(cast.SpeakerInfo)
    words: Counter = Counter()
    books: dict[str, set] = defaultdict(set)
    labels: dict[str, Counter] = defaultdict(Counter)
    order = list(fetch.helloao_books(ed["helloao_id"]))
    for b in a.books or order:
        rows = structure.clause_lines(b, set(range(200)))
        for sid, i in cast.gather(rows, structure.passage_facts(b)).items():
            info[sid].add(i)
        for r in rows:
            sid = cast.speaker_id(r) if r.get("quotation") else None
            if sid:
                words[sid] += len(r["words"])
                books[sid].add(b)
        bt = edition.load_book(a.edition, b)
        al = align.load(a.edition, b, bt.file_hash, bt.chapter_fingerprints)
        for sid, sp in lines.speaker_labels(rows, al, bt, {}).items():
            if sp.label and sid in words:
                labels[sid][sp.label] += 1
        print(b, file=sys.stderr, end=" ", flush=True)
    print(file=sys.stderr)

    rows = []
    seen = set()
    for sid, n in words.most_common():
        i = info[sid]
        label = labels[sid].most_common(1)[0][0] if labels[sid] else ""
        voice, basis = cast.rule_voice(i, rules)
        if voice != "female_group" and label:
            lw_ = set(re.findall(r"[\w’'-]+", label.lower()))
            if lw_ & label_fgroup:
                voice, basis = "female_group", f"label:{a.edition}"
            elif voice != "group" and lw_ & label_group:
                voice, basis = "group", f"label:{a.edition}"
        prev = old.get(sid, {})
        row = {**prev,                                    # keeps other editions' label_ columns
               "speaker_id": sid, "voice": voice, "basis": basis, "name": label,
               "source": (i.names.most_common(1)[0][0] if i.names else
                          i.lemmas.most_common(1)[0][0] if i.lemmas else ""),
               "words": n, "books": " ".join(sorted(books[sid], key=order.index)),
               f"label_{a.edition}": label}
        if a.books and prev:          # a run on some books: keep what the whole Bible gave
            row.update({k: prev[k] for k in ("words", "books", "name", f"label_{a.edition}") if prev.get(k)})
        if prev.get("basis") == "manual":
            row.update(voice=prev["voice"], basis="manual", name=prev.get("name") or label)
        rows.append(row)
        seen.add(sid)
    for sid, prev in old.items():          # keep manual rows (and, for a partial run, every row) not seen
        if sid not in seen and (prev.get("basis") == "manual" or a.books):
            rows.append(prev)
    rows.sort(key=lambda r: (-int(r.get("words") or 0), r["speaker_id"]))
    editions = sorted({k[6:] for r in rows for k in r if k.startswith("label_")} | {a.edition})
    path = config.write_cast(rows, editions)
    c, w = Counter(), Counter()
    for r in rows:
        c[r["voice"]] += 1
        w[r["voice"]] += int(r.get("words") or 0)
    tot = sum(w.values()) or 1
    print(f"{len(rows)} speakers -> {path.relative_to(ROOT)}")
    for v in cast.VOICES:
        print(f"  {v:<13}{c[v]:>5} speakers {w[v] / tot:>6.1%} of quoted words")
    return 0


def _old_rows() -> dict[str, dict]:
    """The current cast.csv, so manual rows and other editions' labels are kept."""
    return dict(config.cast_table())


if __name__ == "__main__":
    raise SystemExit(main())
