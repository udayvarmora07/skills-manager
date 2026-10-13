"""8.1 — `site/`, the landing page, is not allowed to lie about the product.

The page is one HTML file and one stylesheet, so there is no logic to test and
very little surface to break. That is exactly why it is dangerous: a landing
page is where unsupported claims go to survive code review, because prose is
not code and nothing in this repository has ever checked it.

So the gate is the opposite of a style guide. It DERIVES the page's facts out of
the files that own them and requires the page to agree:

- the two palettes, out of `skillsmgr/webui/styles.css` (a second copy that
  drifts is a site showing the product's colours to nobody — the same trick
  `check_design_tokens.py` runs for DESIGN.md);
- the command list, out of `docs/03-cli-surface.md`, which itself states the
  count of invocable names;
- the scope ids and their directory spellings, out of `skillsmgr/scopes.py`;
- the distribution name and the Python floor, out of `pyproject.toml`.

And the offline discipline of RULES #4/#5, which applies to a static page that
ships no CSP header of its own: no script, no inline handler, no form, and no
`src`/`url()` that leaves the directory.

Two things this deliberately does NOT assert, because asserting them would make
the gate vacuous:

1. That the page *looks* good. That is `tests/e2e/test_site.py` plus a human.
2. That `site/` is packaged. RULES says it must NOT be, so the assertion is in
   that direction — a packaging line that ships it fails here.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
INDEX = os.path.join(SITE, "index.html")
SITE_CSS = os.path.join(SITE, "site.css")
PRODUCT_CSS = os.path.join(ROOT, "skillsmgr", "webui", "styles.css")
CLI_DOC = os.path.join(ROOT, "docs", "03-cli-surface.md")
SCOPES_PY = os.path.join(ROOT, "skillsmgr", "scopes.py")
PYPROJECT = os.path.join(ROOT, "pyproject.toml")
MANIFEST = os.path.join(ROOT, "MANIFEST.in")

with open(INDEX, encoding="utf-8") as fh:
    HTML = fh.read()
with open(SITE_CSS, encoding="utf-8") as fh:
    CSS = fh.read()


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# derivation helpers — the page is compared against sources, never constants
# ---------------------------------------------------------------------------


#: Comments come out BEFORE any selector is located, which is 1.7's lesson
#: applied a second time and in the other order: `styles.css` mentions
#: ``[data-theme="dark"]`` inside a 6.1 banner comment and `:root` inside the
#: TOKENS banner, so a locate-then-strip scan reads prose and finds the wrong
#: brace. Stripping first also keeps an unbalanced apostrophe in a comment
#: from being read as the start of a string by any scanner downstream.
_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def _css_block(text, selector):
    """Every declaration body written for ``selector``, joined.

    Accumulating ALL matching blocks is not a convenience: the product's token
    layer closes `:root` and reopens it after a banner, so the palette lives in
    a second block and a first-match scan reports 25 tokens and no colours at
    all — which is the repo's "the gate is reading prose, not structure" class
    pointed at itself.
    """
    text = _COMMENT.sub(" ", text)
    bodies = []
    for match in re.finditer(re.escape(selector), text):
        start = text.find("{", match.start())
        if start < 0:
            continue
        depth = 0
        for j in range(start, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(text[start + 1 : j])
                    break
        else:
            return ""
    return " ".join(bodies)


def _decls(body):
    out = {}
    for name, value in re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", body):
        out[name] = " ".join(value.split())
    return out


#: Where the product declares each theme. NOT `:root` for light: the shipped
#: cascade puts the light palette on `[data-theme="light"], [data-theme="system"]`
#: and the dark one on `[data-theme="dark"]`, with the scale/space/radius steps
#: under `:root`. Reading the light colours out of `:root` returns a dict with
#: no `--bg` in it and a parity test written that way compares nothing.
PRODUCT_LIGHT = '[data-theme="light"]'
PRODUCT_DARK = '[data-theme="dark"]'


def _product_tokens(selector):
    body = _css_block(_read(PRODUCT_CSS), selector)
    return _decls(body)


def _site_tokens(selector):
    body = _css_block(CSS, selector)
    return _decls(body)


#: Every token the site is allowed to restate. It declares a subset of the
#: product's — a landing page has no modal, so it has no `--overlay` — but any
#: token it does declare must carry the product's value byte for byte.
PALETTE = [
    "bg", "surface", "surface-2", "surface-3",
    "ink", "ink-2", "ink-3", "ink-4",
    "line", "line-2", "line-3", "line-strong",
    "accent", "accent-2", "accent-3", "accent-ink", "accent-bg", "accent-line",
    "ok", "ok-bg", "warn", "warn-bg", "err", "err-bg", "mute", "mute-bg",
]


class SiteParityWithTheProduct(unittest.TestCase):
    """The page is the product's voice, so it may not improvise the vocabulary."""

    def test_every_palette_token_matches_the_product_in_light(self):
        site, product = _site_tokens(":root"), _product_tokens(PRODUCT_LIGHT)
        compared = 0
        for name in PALETTE:
            token = "--" + name
            if token not in site:
                continue
            self.assertIn(token, product, "the site declares a token the product does not")
            self.assertEqual(site[token], product[token], token + " drifted from styles.css")
            compared += 1
        self.assertGreater(compared, len(PALETTE) - 4, "the site stopped declaring the palette")

    def test_every_palette_token_matches_the_product_in_dark(self):
        site, product = _site_tokens('[data-theme="dark"]'), _product_tokens(PRODUCT_DARK)
        compared = 0
        for name in PALETTE:
            token = "--" + name
            if token not in site:
                continue
            self.assertIn(token, product, "the site declares a token the product does not")
            self.assertEqual(site[token], product[token], token + " drifted in dark")
            compared += 1
        self.assertGreater(compared, len(PALETTE) - 4, "the site lost its dark palette")

    def test_both_themes_declare_the_same_palette(self):
        # 1.4's finding: a *theme* token present in one theme and not the other
        # is a typo with a colour. It does not apply to the scale/space/radius
        # steps, which are theme-independent by design — asserting the whole
        # set matched would force the dark block to restate the type scale.
        light, dark = _site_tokens(":root"), _site_tokens('[data-theme="dark"]')
        for name in PALETTE:
            self.assertIn("--" + name, light, name + " is missing from the light theme")
            self.assertIn("--" + name, dark, name + " is missing from the dark theme")
        # And nothing theme-shaped may exist in one block only.
        themed = set(PALETTE)
        self.assertEqual((set(light) & themed) - (set(dark) & themed), set())
        self.assertEqual((set(dark) & themed) - (set(light) & themed), set())

    def test_the_type_families_are_the_vendored_ones(self):
        product = _product_tokens(":root")  # the families live with the scale
        site = _site_tokens(":root")
        for token in ("--sans", "--mono"):
            self.assertEqual(site[token], product[token], token + " is not the shipped stack")

    def test_the_scale_is_six_steps_and_there_are_no_raw_sizes(self):
        steps = {k: v for k, v in _site_tokens(":root").items() if k.startswith("--t-")}
        self.assertEqual(len(steps), 6, "the product has six steps and no seventh")
        self.assertTrue(all(v.endswith("rem") for v in steps.values()), steps)
        # The product's guard scans raw CSS, comments included; strip them here
        # first so this suite's own prose cannot become the failure.
        code = re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S)
        self.assertNotRegex(
            code, r"font-size\s*:\s*[^;]*px", "a px font-size is a seventh step"
        )

    def test_the_fonts_the_page_asks_for_are_shipped_beside_it(self):
        css = _read(os.path.join(SITE, "fonts", "geist.css"))
        for face in re.findall(r"url\(([^)]+)\)", css):
            path = os.path.join(SITE, "fonts", face.strip())
            self.assertTrue(os.path.isfile(path), "the site asks for a font it does not ship: " + face)


class SiteFactsAreDerived(unittest.TestCase):
    """Every claim on the page is re-derived from the file that owns it."""

    def test_every_command_named_on_the_page_is_a_real_command(self):
        doc = _read(CLI_DOC)
        # The doc's own headings are the authoritative surface; `ls`, `rm` and
        # `gui` are folded into their parent heading there, and `disable` /
        # `enable` share one, which is why this is a subset and not equality.
        documented = set(re.findall(r"^### `([a-z]+)", doc, flags=re.M))
        listed = re.findall(r"<li><code>([a-z]+)</code>", HTML)
        self.assertGreaterEqual(len(listed), 20, "the CLI list was gutted")
        for name in listed:
            self.assertIn(name, documented, "the page names a command the doc does not document")

    def test_the_headline_command_count_is_the_documents_own(self):
        doc = _read(CLI_DOC)
        stated = re.search(r"Command count:\s*\*\*(\d+) top-level", doc)
        self.assertIsNotNone(stated, "the CLI doc stopped stating its own command count")
        words = {
            20: "Twenty", 21: "Twenty-one", 22: "Twenty-two", 23: "Twenty-three",
            24: "Twenty-four", 25: "Twenty-five", 26: "Twenty-six",
            27: "Twenty-seven", 28: "Twenty-eight", 29: "Twenty-nine", 30: "Thirty",
        }
        count = int(stated.group(1))
        self.assertIn(count, words, "the doc states a count the page cannot spell")
        self.assertIn(words[count] + " commands", HTML, "the headline number lost its source")

    def test_every_scope_row_is_a_real_scope_with_a_real_directory(self):
        src = _read(SCOPES_PY)
        # `Scope("claude-code", "Claude Code", home / ".claude/skills", ...)`
        pairs = re.findall(r'Scope\(\s*"([a-z-]+)",\s*"([^"]+)",\s*home\s*/\s*"([^"]+)"', src)
        self.assertGreaterEqual(len(pairs), 7, "the scope table is no longer derivable")
        by_id = dict((sid, (label, rel)) for sid, label, rel in pairs)
        rows = re.findall(
            r"<tr><td>([^<]+)</td><td class=\"path\">([^<]+)</td>"
            r"<td class=\"ident\">([a-z-]+)</td></tr>",
            HTML,
        )
        self.assertGreaterEqual(len(rows), 8)
        known = set(by_id) | {"global"}
        for label, directory, sid in rows:
            self.assertIn(sid, known, "the page names a scope that does not exist")
            if sid == "global":
                continue  # its directory is derived from paths, checked below
            self.assertEqual(label, by_id[sid][0], "the scope's label drifted")
            self.assertEqual(directory, "~/" + by_id[sid][1], "the scope's directory drifted")
        self.assertIn("global", [r[2] for r in rows], "the tool's own store is missing")

    def test_the_global_scope_directory_is_the_one_paths_builds(self):
        # `global` is the one row whose path is not a `home / "…"` literal, so
        # deriving it needs `paths.py`. This assertion was written because the
        # page shipped `$SKILLS_MANAGER_DATA/skills` — one path component short,
        # naming a directory the tool never creates.
        paths_src = _read(os.path.join(ROOT, "skillsmgr", "paths.py"))
        self.assertIn('manager = selected / "skills-manager"', paths_src)
        self.assertRegex(paths_src, r"def skills_dir\(\)[\s\S]{0,200}?data_dir\(\)")
        self.assertIn(
            "$SKILLS_MANAGER_DATA/skills-manager/skills",
            HTML,
            "the global row must spell the path the tool actually builds",
        )

    def test_the_install_snippet_is_the_distribution_name(self):
        project = _read(PYPROJECT)
        name = re.search(r'^name\s*=\s*"([^"]+)"', project, flags=re.M).group(1)
        self.assertIn("pip install " + name, HTML)
        self.assertIn("pipx install " + name, HTML)
        self.assertNotIn(
            "pip install skills-manager", HTML, "that is the repo name, not the distribution"
        )

    def test_the_python_floor_is_the_packaging_floor(self):
        project = _read(PYPROJECT)
        floor = re.search(r'requires-python\s*=\s*">=(\d+)\.(\d+)"', project)
        self.assertIsNotNone(floor, "pyproject stopped stating a floor")
        self.assertIn("Python %s.%s+" % (floor.group(1), floor.group(2)), HTML)

    def test_the_licence_claim_is_the_packaging_licence(self):
        project = _read(PYPROJECT)
        declared = re.search(r'license\s*=\s*"([^"]+)"', project).group(1)
        self.assertIn(declared, HTML, "the page names a licence the package does not declare")

    def test_the_runtime_has_no_dependencies_to_claim_honesty_about(self):
        project = _read(PYPROJECT)
        # `dependencies` may be absent or an empty list; either is "stdlib only".
        block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", project, flags=re.M | re.S)
        self.assertTrue(block is None or not block.group(1).strip())
        self.assertIn("standard library only", HTML)


class SiteShipsNothingRemote(unittest.TestCase):
    """RULES #4/#5 apply to a page with no CSP header of its own."""

    def test_there_is_no_script_and_no_inline_handler(self):
        self.assertNotIn("<script", HTML)
        self.assertNotRegex(HTML, r"\son[a-z]+\s*=", "an inline event handler")

    def test_there_is_no_form(self):
        self.assertNotIn("<form", HTML)

    def test_every_asset_reference_resolves_inside_the_site(self):
        refs = re.findall(r'(?:src|href)="([^"]+)"', HTML)
        local = anchors = 0
        for ref in refs:
            if ref.startswith("http://") or ref.startswith("https://"):
                # A hyperlink to the project's own repository is not a fetch.
                self.assertTrue(
                    ref.startswith("https://github.com/"),
                    "an asset or stylesheet is loaded from off-origin: " + ref,
                )
                continue
            path = ref.split("#")[0]
            if path in (".", "./"):
                # The wordmark links the page to itself. Normalising "./" joins
                # it onto SITE and then demands a *file* called the directory.
                self.assertTrue(os.path.isdir(SITE), "the self link has no directory")
                local += 1
                continue
            if not path:
                # A pure in-page anchor names no file at all; `skip-link` and
                # the masthead nav are all of them. Normalising "#main" would
                # join it onto SITE and then look for a file called the
                # directory itself, which is the assertion failing for a reason
                # that has nothing to do with the page.
                self.assertTrue(
                    re.fullmatch(r"#[a-z0-9-]+", ref), "a fragment that is not a plain id: " + ref
                )
                self.assertIn(
                    'id="%s"' % ref[1:], HTML, "an in-page link points at no element: " + ref
                )
                anchors += 1
                continue
            local += 1
            target = os.path.normpath(os.path.join(SITE, path))
            if target.startswith(SITE + os.sep):
                self.assertTrue(
                    os.path.exists(target), "the page links a file that is not there: " + ref
                )
            else:
                # The footer's doc links point out of site/ at files in THIS
                # repository, which is the only legitimate way out: they must
                # resolve to a real file under the checkout, never to a
                # directory outside it (a `../..` would walk to $HOME).
                self.assertTrue(
                    target.startswith(ROOT + os.sep), "a link escapes the repository: " + ref
                )
                self.assertTrue(
                    os.path.isfile(target), "the page links a repository file that is not there: " + ref
                )
        self.assertGreater(local, 5, "the page stopped linking its own assets")
        self.assertGreater(anchors, 4, "the page stopped linking itself")

    def test_no_css_url_leaves_the_directory(self):
        css_dir = os.path.dirname(SITE_CSS)
        for url in re.findall(r"url\(([^)]+)\)", CSS):
            ref = url.strip().strip("'\"")
            self.assertNotIn("://", ref, "a remote url() in the site stylesheet")
            target = os.path.normpath(os.path.join(css_dir, ref))
            self.assertTrue(target.startswith(css_dir + os.sep), "url() escapes: " + ref)
            self.assertTrue(os.path.exists(target), "url() names a missing file: " + ref)

    def test_every_image_carries_an_alt(self):
        for img in re.findall(r"<img\b[^>]*>", HTML):
            self.assertRegex(img, r'\salt="[^"]+"', "an image with no alt: " + img[:60])

    def test_the_hero_image_is_a_real_capture_and_is_used_once(self):
        path = os.path.join(SITE, "assets", "hero-library.png")
        self.assertTrue(os.path.isfile(path))
        self.assertGreater(os.path.getsize(path), 20000, "a placeholder is not a screenshot")
        self.assertEqual(HTML.count("assets/hero-library.png"), 1)


class SiteIsNotPackaged(unittest.TestCase):
    """RULES: `site/` is a repository artefact, never a wheel member."""

    def test_no_packaging_line_ships_site(self):
        for path in (PYPROJECT, MANIFEST):
            for line in _read(path).splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or not stripped:
                    continue
                self.assertNotRegex(
                    stripped, r"^[\"']?(site|site/)[\"'/]?$", path + " would ship site/"
                )
                self.assertNotIn('"site"', stripped, path + " would ship site/")
                self.assertNotIn("site/", stripped, path + " would ship site/")

    def test_the_package_gate_does_not_know_about_site(self):
        gate = _read(os.path.join(ROOT, "check_package_data.py"))
        # Not `assertNotIn("site")`: the module says "site-packages" in prose,
        # so a bare substring search fails on the word rather than on a path.
        # What must not exist is a `site` PATH in any of its member sets.
        for path_literal in re.findall(r'Path\("([^"]+)"\)', gate):
            self.assertFalse(
                path_literal == "site" or path_literal.startswith("site/"),
                "the packaging gate has started reading site/",
            )
        self.assertNotIn('"site"', gate, "the packaging gate would ship site/")


if __name__ == "__main__":
    unittest.main()