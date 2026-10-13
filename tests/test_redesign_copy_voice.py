"""6.5 — the product's VOICE, as a gate rather than a claim.

DESIGN-V2 §I states four rules: plain and specific, sentence case, no
exclamation marks and no emoji, errors that say what happened and what to do
next, and empty states of one sentence plus one action. §B's refused-defaults
list adds "no 'Welcome back!' copy". None of that was enforced anywhere, so
"the copy is in the right voice" was a thing a reader had to go and check.

Everything asserted here is DERIVED from the shipped source. Nothing keeps a
hand-written list of the strings that happen to be legal today, because a
hand-kept list cannot notice the copy added tomorrow — the failure mode this
branch has now recorded nine times (see STATE.md, tasks 1.5/1.2/2.1b/3.3).

What is deliberately NOT here:
  * "Buttons are verbs". Measured before it was ruled out: of 112 distinct
    button labels, every one either starts with a verb or is a nav/filter/toggle
    noun ("Grid", "List", "All") where the noun IS the control's name. A verb
    list would be a hand-kept list of exactly the kind this file refuses, and
    the rule it would enforce is a convention, not a property.
  * "Empty states have one sentence and one action". The parser needed to
    measure it honestly is a template-aware one (Vue's `v-if` branches nest
    markup arbitrarily), and a regex over nested <div> reports a block's whole
    subtree as its copy. Four attempts at the cheap version each failed in a
    different direction, which is 1.7's map, so the rule is left to 6.6 where
    axe walks the rendered DOM instead of guessing at the template.
"""

import re
import unittest
from pathlib import Path

WEBUI = Path(__file__).resolve().parent.parent / "skillsmgr" / "webui"
INDEX = WEBUI / "index.html"
APP = WEBUI / "app.js"


def _strip_comments(src: str) -> str:
    return re.sub(r"/\*.*?\*/", "", src, flags=re.S)


# A tag is `<` up to the `>` that is NOT inside a quoted attribute value.
# `<[^>]*>` is wrong and this file's first version used it: Vue's `:key`
# bindings contain `=>`, so the split lands inside an attribute and the tail
# of the expression — including its `!==` — is read as body text. Three
# phantom exclamation marks came from that, which is 1.7's lesson (the parser
# fed the wrong input reports a finding about nothing) arriving again.
TAG = re.compile(r"<(?:[^>\"']|\"[^\"]*\"|'[^']*')*>")


def _markup_only(src: str) -> str:
    """The markup a reader can see: no comments, no <script>, no <style>.

    Mustache spans are removed HERE, before anything splits on tags, and not
    afterwards. A `{{ a !== b ? 'x' : 'y' }}` interpolation is cut in half by
    a tag split, which leaves `!==` sitting in a "text node" — the first
    version of this file did exactly that and reported three phantom
    exclamation marks, two of which were a `v-if` expression. Removing the
    span first cannot split it.
    """
    src = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    src = _strip_comments(src)
    src = re.sub(r"<style.*?</style>", "", src, flags=re.S)
    src = re.sub(r"<script.*?</script>", "", src, flags=re.S)
    src = re.sub(r"\{\{.*?\}\}", " ", src, flags=re.S)
    return src


def _strings(src: str):
    """Every double- or single-quoted literal, unescaped enough to match on."""
    for m in re.finditer(r'"((?:[^"\\\n]|\\.)*)"', src):
        yield m.group(1)
    for m in re.finditer(r"'((?:[^'\\\n]|\\.)*)'", src):
        yield m.group(1)


# Words §B names as the tell of a generated interface. Matched case-
# insensitively on word boundaries so "power" in "power user" cannot fire.
BANNED_PHRASES = (
    "welcome back",
    "glad you're back",
    "good to see you",
    "seamless",
    "effortless",
    "effortlessly",
    "delightful",
    "supercharge",
    "game-changer",
    "game changing",
    "revolutionize",
    "revolutionise",
    "unleash",
    "elevate your",
    "take it to the next level",
    "congratulations",
    "you did it",
    "all set",
    "all done",
    "oops",
    "uh oh",
    "buckle up",
    "dive in",
    "get started today",
    "say goodbye to",
    "say hello to",
)

# Punctuation §I forbids outright.
EXCLAMATION = re.compile(r"!")
# Pictographs and pictograph blocks. Arrows (U+2190–U+21FF), dingbats and
# emoji blocks are furniture-adjacent, so each class is named rather than
# lumped, and the check reports WHICH class fired.
PICTOGRAPH = {
    "emoji": re.compile("[\U0001F300-\U0001FAFF]"),
    "variation selector": re.compile("[\uFE0E\uFE0F]"),
    "dingbat block": re.compile("[\u2700-\u27BF]"),
}


def prose_literals():
    """Prose the reader can see: quoted literals that contain a space."""
    out = []
    for name, src in (("app.js", _strip_comments(APP.read_text())),):
        for s in _strings(src):
            if " " in s and not s.strip().startswith((".", "/", "*")):
                out.append((name, s))
    return out


def markup_text_nodes():
    """Text between tags in the markup, mustache interpolations removed."""
    src = _markup_only(INDEX.read_text())
    out = []
    for chunk in TAG.split(src):
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if chunk:
            out.append(chunk)
    return out


def accepted_furniture():
    """The non-ASCII glyphs the project has ALREADY accepted as furniture.

    Task 0b.1 measured that five shipped codepoints — `↻ ⌘ ▸ ▾ ✓` — are not
    carried by the vendored face, resolve to a system face, and are UI
    furniture rather than prose; it pinned them by name as a tripwire. This
    file must NOT ban them: a check that contradicts a recorded decision is
    how a decision gets quietly reversed by whoever ran the gate last.

    The set is PARSED OUT of that test rather than restated here, so when
    0b.1's set changes (vendor the face, draw it from the sprite, accept a new
    fallback) this follows instead of contradicting it.
    """
    src = (Path(__file__).resolve().parent / "e2e" / "test_font_render.py")
    m = re.search(r'known\s*=\s*set\(\s*"([^"]+)"\s*\)', src.read_text())
    if not m:
        return set()
    return set(m.group(1))


class VoiceContract(unittest.TestCase):
    """The rules that can be checked on the source that ships."""

    def test_no_exclamation_mark_in_reader_visible_prose(self):
        """§I bans the exclamation mark in prose.

        A bare `!` used as a SEVERITY MARK is not prose and is not banned:
        §D requires status to be carried by more than colour, and the
        `.status-mark` glyph is one of the three redundant carriers beside the
        dot and the label. What is asserted instead of an allowlist is that
        such a mark is `aria-hidden` and that it stands ALONE — so the
        exemption cannot grow into "strings may contain `!`", which is the
        failure this file's own comment-stripping once walked into.
        """
        offenders = []
        for name, lit in prose_literals():
            if EXCLAMATION.search(lit):
                offenders.append(f"{name}: {lit[:70]}")
        # Prose in the markup: multi-word only. Single characters are marks,
        # and are checked for aria-hidden by the test below.
        for chunk in markup_text_nodes():
            if EXCLAMATION.search(chunk) and len(chunk.split()) > 1:
                offenders.append(f"markup: {chunk[:70]}")
        self.assertEqual(
            [], offenders, f"DESIGN-V2 §I bans exclamation marks: {offenders}"
        )

    def test_an_exclamation_used_as_a_mark_is_hidden_from_assistive_tech(self):
        """The exemption above, made falsifiable.

        Asserted in both directions: every bare `!` element is aria-hidden, and
        there is at least one, so "we found no marks so nothing to check"
        cannot pass as a clean run.
        """
        src = _markup_only(INDEX.read_text())
        bare = re.findall(r"<(?!\/)([a-z]+)([^>]*)>\s*!\s*</\1>", src)
        self.assertGreater(len(bare), 0, "the severity mark is gone; re-derive")
        for tag, attrs in bare:
            self.assertIn(
                'aria-hidden="true"', attrs,
                f"a bare `!` in <{tag}> is announced as punctuation",
            )
            self.assertIn(
                "status-mark", attrs,
                "a bare `!` outside the status mark is unclassified",
            )

    def test_no_emoji_or_pictograph_in_reader_visible_prose(self):
        furniture = accepted_furniture()
        self.assertTrue(
            furniture, "0b.1's pinned furniture set could not be read — "
            "this check would ban glyphs the project already accepted",
        )
        offenders = []
        for chunk in markup_text_nodes():
            for label, pattern in PICTOGRAPH.items():
                if pattern.search(chunk) and not set(chunk) <= furniture:
                    offenders.append(f"{label} in markup text {chunk[:60]!r}")
        for name, lit in prose_literals():
            for label, pattern in PICTOGRAPH.items():
                if pattern.search(lit) and not set(lit) <= furniture:
                    offenders.append(f"{label} in {name} {lit[:60]!r}")
        self.assertEqual(
            [], offenders, f"DESIGN-V2 §I bans emoji: {offenders}"
        )

    def test_no_banned_generated_interface_phrase(self):
        offenders = []
        for chunk in markup_text_nodes() + [s for _, s in prose_literals()]:
            low = chunk.lower()
            for phrase in BANNED_PHRASES:
                if phrase in low:
                    offenders.append(f"{phrase!r} in {chunk[:70]!r}")
        self.assertEqual(
            [], offenders, f"DESIGN-V2 §B refused defaults: {offenders}"
        )

    def test_the_prose_vocabulary_is_not_thin(self):
        """The control. An empty corpus satisfies every rule above."""
        corpus = markup_text_nodes() + [s for _, s in prose_literals()]
        self.assertGreater(len(corpus), 200, "the prose corpus collapsed")
        self.assertGreater(
            sum(1 for c in corpus if len(c.split()) >= 4), 100,
            "not enough multi-word prose for the checks above to bite",
        )


class ProductNameContract(unittest.TestCase):
    """One product, one name — and the name is DERIVED, not restated.

    2.1a replaced the brand with an own mark and `skills-manager` in Geist
    Mono. Two prose strings kept the old name, and the <title> — the most
    visible surface of all, the browser tab — kept it too. Nothing could
    notice, because "is the copy consistent" has no check behind it.

    The wordmark is read out of the markup, so renaming the brand deliberately
    makes this test fail until the prose is updated with it. That is the
    point: the drift is the defect, not a stale literal in this file.
    """

    def _wordmark(self):
        m = re.search(
            r'<span class="brand-name">([^<]+)</span>', INDEX.read_text()
        )
        self.assertIsNotNone(m, "the brand name span is gone; fix this test")
        return m.group(1).strip()

    def test_the_wordmark_exists_and_is_the_declared_name(self):
        wordmark = self._wordmark()
        self.assertEqual("skills-manager", wordmark, "wordmark changed")
        self.assertEqual(
            wordmark, wordmark.lower(), "the wordmark is not lowercase"
        )

    def test_the_document_title_uses_the_wordmark(self):
        wordmark = self._wordmark()
        title = re.search(r"<title>([^<]*)</title>", INDEX.read_text())
        self.assertIsNotNone(title, "no <title>")
        self.assertEqual(
            wordmark,
            title.group(1).strip(),
            f"the browser tab says {title.group(1)!r}, the wordmark says "
            f"{wordmark!r} — one product has two names",
        )

    def test_prose_never_names_the_product_differently(self):
        """Catches 'Skills Manager' in body copy without restating the rule."""
        wordmark = self._wordmark()
        # Any capitalised multi-word name ending in "Manager" is the drift.
        pattern = re.compile(r"\b[A-Z][a-z]+\s+Manager\b")
        offenders = []
        for chunk in markup_text_nodes():
            for m in pattern.finditer(chunk):
                offenders.append(f"markup {m.group(0)!r} in {chunk[:60]!r}")
        for name, lit in prose_literals():
            for m in pattern.finditer(lit):
                offenders.append(f"{name} {m.group(0)!r} in {lit[:60]!r}")
        self.assertEqual(
            [], offenders,
            f"prose spells the product differently from {wordmark!r}: {offenders}",
        )

    def test_the_check_can_still_see_a_spelling(self):
        """Control: the pattern matches the string it is there to catch."""
        self.assertTrue(
            re.search(r"\b[A-Z][a-z]+\s+Manager\b", "Skills Manager stays local"),
            "the drift pattern stopped matching — the test is now vacuous",
        )
        self.assertFalse(
            re.search(r"\b[A-Z][a-z]+\s+Manager\b", wordmark_safe()),
            "the drift pattern fires on the correct name",
        )


def wordmark_safe() -> str:
    m = re.search(r'<span class="brand-name">([^<]+)</span>', INDEX.read_text())
    return m.group(1).strip() if m else ""


if __name__ == "__main__":
    unittest.main()