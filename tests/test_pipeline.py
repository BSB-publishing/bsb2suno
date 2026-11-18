"""End-to-end checks on real data (downloaded into cache/ on first run)."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bsb2suno import align, cast, config, edition, lines, profiles, structure  # noqa: E402
from bsb2suno.__main__ import apply_layout_defaults, build_chapter  # noqa: E402


class Args:
    style = None
    profile = None
    lead = None
    max_lines = None
    min_words = None
    max_chars = None


def build(book, chapter):
    bt = edition.load_book("BSB", book)
    al = align.load("BSB", book, bt.file_hash, bt.chapter_fingerprints)
    rows = structure.clause_lines(book, set(range(0, 200)))
    facts = structure.passage_facts(book)
    sp = lines.speaker_labels(rows, al, bt, cast.gather(rows, facts))
    args = Args()
    apply_layout_defaults(args)
    res = build_chapter(book, chapter, "BSB", bt, al, rows, sp, facts, align.verse_map("BSB"), args)
    return bt, al, res


def words(s):
    return re.findall(r"[^\W\d_]+", s)


class TestSpan(unittest.TestCase):
    def test_parse_span(self):
        self.assertEqual(align.parse_span("5"), [5])
        self.assertEqual(align.parse_span("5-7"), [5, 6, 7])
        self.assertEqual(align.parse_span("4,6"), [4, 6])
        self.assertEqual(align.parse_span("L3,1,2"), [3, 1, 2])
        self.assertEqual(align.parse_span("~"), [])


class TestRuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bt, cls.al, cls.res = build("RUT", 1)

    def test_fingerprint_matches_alignment(self):
        self.assertEqual(self.bt.file_hash, "8b23cf7f")
        self.assertEqual(self.al.kind, "full")
        self.assertFalse(self.al.chapters_off)

    def test_lyrics_are_the_text_verbatim(self):
        """Every word of the chapter, in order, nothing added or dropped."""
        sung = [ln["text"] for s in self.res["data"]["sections"] for ln in s["lines"]]
        text = " ".join(v.text for v in self.bt.chapter_verses(1))
        self.assertEqual(words(" ".join(sung)), words(text))

    def test_voices(self):
        lyr = self.res["lyrics"]
        tags = set(re.findall(r"^\[[^\]]+\]$", lyr, re.M))
        self.assertIn("[Female Vocal]", tags)    # Naomi, Ruth
        self.assertIn("[Female Choir]", tags)    # the two daughters-in-law (1:10), the women (1:19)
        self.assertIn("[Bridge]", tags)          # Ruth 1:16-17, set as poetry
        self.assertFalse(any("Naomi" in t or "Ruth" in t for t in tags))   # tags never name a person
        self.assertIn("Naomi", self.res["full"].split("\n\n")[1])         # names are in the comment block

    def test_profile_is_the_books(self):
        prof = profiles.for_book("BSB", "RUT")
        self.assertTrue(self.res["full"].startswith(prof.style + "\n"))
        self.assertEqual(self.res["data"]["profile"]["name"], prof.name)

    def test_reordered_clauses_get_own_lines(self):
        v6 = [ln["text"] for s in self.res["data"]["sections"] for ln in s["lines"] if ln["verse"] == "1:6"]
        self.assertEqual(v6[0], "When Naomi heard in Moab")
        self.assertIn("by providing them with food,", v6)


class TestCast(unittest.TestCase):
    def test_rules(self):
        def info(lemma, name="", members=False, quotes=0, divine=0):
            i = cast.SpeakerInfo(members=members, quotes=quotes, divine=divine)
            if lemma:
                i.lemmas[lemma] += 1
            if name:
                i.names[name] += 1
            return i
        rules = config.cast_rules()
        self.assertEqual(cast.rule_voice(info("אִשָּׁה"), rules)[0], "female")
        self.assertEqual(cast.rule_voice(info("אִשָּׁה אָדוֹן"), rules)[0], "female")     # master's wife
        self.assertEqual(cast.rule_voice(info("אָב נַעֲרָה"), rules)[0], "male")          # the girl's father
        self.assertEqual(cast.rule_voice(info("רָחֵל, לֵאָה"), rules)[0], "female_group")
        self.assertEqual(cast.rule_voice(info("אָב, אֵם"), rules)[0], "group")
        self.assertEqual(cast.rule_voice(info("θεός", quotes=10, divine=10), rules)[0], "divine")
        self.assertEqual(cast.voice_of(None, None), rules["unknown"])

    def test_speaking_verb(self):
        """Hebrew verb gender and number name the voice: Acsah "she said", the Hivites "they said"."""
        table = config.cast_table()
        self.assertEqual(table["c0134"]["voice"], "female")     # Acsah, JOS 15:19
        self.assertEqual(table["c0130"]["voice"], "group")      # the Hivites, JOS 9
        # a Greek participle agrees with its noun, not a person: "a voice saying" stays male (default)
        self.assertNotEqual(table["n0364"]["voice"], "female")

    def test_nested_quote_sung_by_outer_speaker(self):
        _, _, res = build("GEN", 3)
        lyr = res["lyrics"].split("\n")
        i = lyr.index("God has said,")
        self.assertFalse(lyr[i + 1].startswith("["))     # Eve goes on singing God's words


class TestTextForms(unittest.TestCase):
    """passage-facts v0.2: refrains, acrostics, couplet halves, psalm headings."""

    def test_refrain_is_the_chorus(self):
        _, _, res = build("GEN", 1)
        ch = [s for s in res["data"]["sections"] if s["label"] == "Chorus"]
        evening = [s for s in ch if any(ln["text"].startswith("And there was evening") for ln in s["lines"])]
        self.assertEqual(len(evening), 6)               # evening and morning, days 1-6
        saw = [s for s in ch if s["lines"][0]["text"] == "And God saw"]
        self.assertGreaterEqual(len(saw), 2)            # "And God saw that it was good" (the text's own refrain too)
        self.assertNotIn("Then God said,", [ln["text"] for s in ch for ln in s["lines"]])

    def test_acrostic_letters_start_stanzas(self):
        _, _, res = build("PSA", 119)
        starts = [s["verses"][0] for s in res["data"]["sections"] if any(ln["acrostic"] for ln in s["lines"])]
        self.assertEqual(len(starts), 22)
        self.assertEqual(starts[:3], ["119:1", "119:9", "119:17"])
        self.assertIn("ב Beth", res["full"])

    def test_heading_terms_and_selah_noted(self):
        _, _, res = build("PSA", 3)
        self.assertIn("Heading terms (not sung): a psalm", res["full"])
        self.assertIn("Selah at 3:2, 3:4, 3:8", res["full"])

    def test_half_b_starts_a_line(self):
        _, _, res = build("PSA", 23)
        texts = [ln["text"] for s in res["data"]["sections"] for ln in s["lines"]]
        self.assertIn("He guides me in the paths of righteousness for the sake of His name.", texts)

    def test_section_tag_modes(self):
        from bsb2suno import render
        self.assertEqual(render.section_tag("Verse 3"), "[Verse 3]")
        self.assertEqual(render.section_tag("Verse 3", number_verses=False), "[Verse]")
        self.assertIsNone(render.section_tag("Verse 3", "chorus_bridge"))
        self.assertEqual(render.section_tag("Chorus", "chorus_bridge"), "[Chorus]")
        self.assertIsNone(render.section_tag("Chorus", "none"))


class TestConfig(unittest.TestCase):
    def test_layers(self):
        self.assertEqual(config.merge({"a": {"x": 1, "y": 2}}, {"a": {"y": 3}}), {"a": {"x": 1, "y": 3}})
        self.assertIn("text", config.layout("BSB"))

    def test_count_units(self):
        self.assertEqual(lines.count_units("In the beginning, God"), 4)
        self.assertEqual(lines.count_units("起初，神创造天地。", "characters"), 7)

    def test_stanzas_split_at_source_breaks(self):
        _, _, res = build("MRK", 1)
        starts = [s["verses"][0] for s in res["data"]["sections"]]
        self.assertIn("1:9", starts)       # Καὶ ἐγένετο ἐν ἐκείναις ταῖς ἡμέραις: a new episode


class TestPsalm(unittest.TestCase):
    def test_superscription_kept_out_of_verse(self):
        bt, al, res = build("PSA", 23)
        self.assertEqual(bt.file_hash, "c867de4b")
        self.assertEqual(al.kind, "full")
        self.assertEqual(res["data"]["setting"], "poetry")
        self.assertTrue(res["lyrics"].split("\n")[1].startswith("The LORD is my shepherd"))
        self.assertIn("A Psalm of David.", res["full"])   # in the comment block


if __name__ == "__main__":
    unittest.main()
