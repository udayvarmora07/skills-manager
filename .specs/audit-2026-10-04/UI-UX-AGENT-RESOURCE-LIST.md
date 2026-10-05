# The UI/UX Reference List — for feeding an AI coding agent

**Research date:** 2026-09-30 · **Sources:** open web, Reddit (via OpenCLI), X (via OpenCLI)
**Verification:** every GitHub star count below was read from the GitHub API today. Every URL marked ✅ was fetched live. Things I could not verify are listed as such rather than presented as fact.

---

## Read this first: the mechanism, not the shopping list

A list of component libraries will not stop your agent producing generic UI. What stops it is **replacing the model's defaults with your own, persistently, in a file it reads every session.** The libraries are the raw material. This is the delivery mechanism.

The stack, in order of leverage:

| # | Layer | What it does | Cost |
|---|---|---|---|
| 1 | **`DESIGN.md`** | Your design system as a file the agent reads every session. Tokens + rationale. | Free |
| 2 | **An anti-slop skill** | Replaces the model's default aesthetic instincts with rules. | Free |
| 3 | **A mechanical linter** | Catches violations without an LLM. Runs in pre-commit. | Free |
| 4 | **shadcn MCP + registry** | Gives the agent *real, installable* components instead of hallucinated ones. | Free |
| 5 | **A taste reference** | 2–3 real DESIGN.md files from brands you admire. | Free |

**Why this works** (the core insight, from [designbycurio.com](https://designbycurio.com/learn/give-your-ai-design-taste)):
> "Taste, for an AI, is just specificity supplied consistently from outside."

You do not prompt an agent to "not use Inter." You set `typography.h1.fontFamily` in a file. The prompt carries the task; the file carries the taste.

---

## 1. `DESIGN.md` — the single highest-leverage thing you can add

**Origin:** Google Stitch (Google Labs), open-sourced as a vendor-neutral spec.
**Spec:** https://github.com/google-labs-code/design.md — **28,179★, Apache-2.0** ✅

Two layers:
1. **YAML front matter** = machine-readable tokens (`colors`, `typography`, `rounded`, `spacing`, `components`)
2. **Markdown body** = human-readable *rationale* — why each choice exists

Tokens give exact values; prose gives reasoning. That division is why it beats a prompt.

**I tested the official linter. It works:**

```bash
npx @google/design.md lint DESIGN.md              # validates tokens, WCAG contrast
npx @google/design.md diff  DESIGN.md DESIGN-v2.md   # token-level regression detection
```

⚠️ **Gotcha I hit:** the package name `@google/design.md` has an npm resolution conflict. The documented `npx @google/design.md lint` works, but the project also documents a fallback alias for when it doesn't:
```bash
npx -p @google/design.md designmd lint DESIGN.md
```

**Verified linter behaviour** (I ran it):
- ✅ Flags `missing-primary` when you define colors but no `primary` — *"The agent will auto-generate key colors, reducing your control over the palette"*
- ✅ Flags `missing-sections` for absent `spacing` / `rounded` — *"will fall back to agent defaults"*
- ✅ Flags `broken-ref` for invalid component sub-tokens
- ✅ **WCAG contrast check works.** I tested `#cccccc` on `#ffffff` and got:
  > `[warning] contrast-ratio: textColor (#cccccc) on backgroundColor (#ffffff) has contrast ratio 1.61:1, below WCAG AA minimum of 4.5:1`

**Limitation I found (important):** the contrast rule only checks pairs declared *inside* `components.*.textColor` / `backgroundColor`. Colors defined at the top level in `colors:` are **not** contrast-checked against each other. Declare the pairs you care about explicitly.

Component sub-tokens must be from this exact list (I hit the `broken-ref` error finding this):
`backgroundColor`, `textColor`, `typography`, `rounded`, `padding`, `size`, `height`…
(Use `rounded`, **not** `borderRadius` — that errors.)

### Ready-made DESIGN.md files — 73 real brands

**https://github.com/VoltAgent/awesome-design-md** — **118,914★, MIT** ✅

Real brand systems reverse-engineered into DESIGN.md, each with a `preview.html`. Served at `https://getdesign.md/<brand>/design-md` — I verified `/claude/` and `/apple/` return 200 ✅

Brands include: **Apple, Stripe, Linear, Notion, Figma, Framer, Vercel, Tesla, Ferrari, Lamborghini, Nike, Spotify, NVIDIA, Airbnb, Shopify, Supabase, MongoDB, Raycast, Cursor, Mistral, Cohere, Ollama, xAI** — plus a *"Retro Web / DESIGN.md Nostalgia"* series (Dell 1996, Nintendo.com 2001) if you want deliberate period-accurate vintage UI.

**Pick 2–3 that match the vibe you want and use them as taste references.**

### Extract a DESIGN.md from any site you admire

| Tool | URL | Stars | Note |
|---|---|---|---|
| **design-md-chrome** | https://github.com/bergside/design-md-chrome | **2,929★, MIT** | Chrome extension. Point it at any site → get its design system. |
| **dembrandt** | https://github.com/dembrandt/dembrandt | **3,588★, MIT** | CLI, one command: logo, colors, typography, borders. |
| **Hallmark `study`** | https://www.usehallmark.com | — | `hallmark study <screenshot \| URL>` — extracts the *DNA* (macrostructure, type-pairing, colour anchor) from a design. Emits a portable `design.md`. Refuses pixel-clones. |

---

### More skills named on X — all verified live today

| Skill | Repo | Stars | What it does |
|---|---|---|---|
| **emilkowalski/skills** | `emilkowalski/skills` | **42,339★** | Ex-Framer Motion lead. *"Skills for Designers and Engineers"* — highest motion craft here |
| **mattpocock/skills** | `mattpocock/skills` | **272,709★** | *"Skills for Real Engineers"* |
| **addyosmani/agent-skills** | `addyosmani/agent-skills` | **100,075★** | Production-grade engineering skills |
| **vercel-labs/agent-skills** | `vercel-labs/agent-skills` | **31,756★** | Vercel official. Includes `web-design-guidelines` |
| **anti-slop** | `miqdadbadjuber/anti-slop` | **4,131★** | Rules for filtering generic AI output across UI, copy, *and* code. Works with Claude Code, Codex, Cursor, Antigravity, Cline |
| **jakubkrehel/skills** | `jakubkrehel/skills` | **7,379★** | *"help you build great interfaces"* |
| **MengTo/Skills** | `MengTo/Skills` | **6,489★** | Design skills for Codex/Claude/Cursor |
| **MengTo/threeui** | `MengTo/threeui` | **6,342★** | 160+ free three.js components, each ships a prompt |
| **dmmulroy/anti-slop** | `dmmulroy/anti-slop` | **5,030★** | ⚠️ **Oxlint rules for low-evidence TS/JS — a code-quality linter, not design** |
| **petergyang/no-ai-slop** | `petergyang/no-ai-slop` | **11,577★** | ⚠️ Prose only |

**ui-skills.com** https://www.ui-skills.com ✅ 200 — a *curated, human-organized* UI-skill catalog. Better browsing than scrolling skills.sh.

### Curated skill registry
**https://www.skills.sh** ✅ — the install registry behind nearly every link on X. Agent-agnostic (Claude Code, Codex, Cursor, Gemini CLI, Copilot, OpenCode):
```bash
npx skills add <owner>/<repo> --skill <name>
```

### A third architectural camp: linters, not skills
Not everyone thinks skills are the answer. Two voices worth weighing:
> **@dexhorthy** (400 likes): *"you should have a linter. Hands down… Use **ast analysis** to tell your coding agents what needs to be fixed… BUT if your anti-slop strategy is an LLM and a handful of linters, **you're gonna be disappointed**."*

> **@tiny_frontier**: *"Skills guide; checks enforce."*

**Read that as a three-layer argument**, which is the architecture this whole list points to: DESIGN.md (constraint) → skill (guidance) → linter (enforcement). Layers 1 and 2 are prompt-time; layer 3 is the only one that runs without a model.

---

## 2. Anti-slop skills — verified, ranked

Ranked by GitHub stars, all read from the API today. **All install via `npx skills add`.**

| Skill | Repo | Stars | License | Install |
|---|---|---|---|---|
| **ui-ux-pro-max** | `nextlevelbuilder/ui-ux-pro-max-skill` | **131,895★** | — | `npx ui-ux-pro-max-cli init --ai <agent>` |
| **taste-skill** | `Leonxlnx/taste-skill` | **91,459★** | MIT | `npx skills add https://github.com/Leonxlnx/taste-skill` |
| **Impeccable** | `pbakaus/impeccable` | **72,842★** | Apache-2.0 | `npx impeccable install` |
| **Hallmark** | `Nutlope/hallmark` | **29,347★** | MIT | `npx skills add nutlope/hallmark` |
| **vibecoded-design-tells** | `JCarterJohnson/vibecoded-design-tells` | 506★ | see repo | `unszip skill/unslop-ui.skill -d ~/.claude/skills/` |
| **design-extract** | `Manavarya09/design-extract` | **4,149★** | MIT | see below |
| **VibeCurb** | `Yu-369/VibeCurb` | 977★ | MIT | rule/skill files for Cursor, Claude Code, Windsurf, Gemini CLI |
| **avoid-ai-design** | `funboy322/avoid-ai-design` | 87★ | MIT | `npx skills add funboy322/avoid-ai-design` |
| **humanize-ui** | `umitkaanusta/humanize-ui` | 64★ | MIT | MIT skill linking Claude to tasteful UI resources |
| **fudge-design-md** | `scroobius-pip/fudge-design-md` | 111★ | MIT | DESIGN.md guides generated from real website references |

**design-extract** is worth calling out — it is the most capable extractor I found:
```bash
/extract-design https://stripe.com    # Claude Code plugin
designlang diff <siteA> <siteB>       # compare two sites
designlang history                    # track design changes over time
```
Pulls colors, fonts, spacing, shadows, components into optimized markdown, and emits **Tailwind config, CSS vars, React theme, shadcn/ui theme, Figma Variables JSON, W3C tokens, and an HTML preview**. Flags: `--depth 5`, `--screenshots`, `--dark`, `--interactions` (captures hover/focus/keyframes).

### DESIGN.md registries
- **designmd.sh** https://designmd.sh/ ✅ 200 — "basically skills.sh for design systems"
- **designkit.sh** https://designkit.sh/ ✅ 200 — competing registry
- **getdesign.md** https://getdesign.md ✅ 200 — 73 real brands (see §1)

⚠️ **Integrity warning on Reddit-sourced tools.** The Reddit researcher flagged that a striking number of high-scoring posts in this space are single-author product launches with suspiciously aligned upvote patterns — the same author posting shadcn-slop criticism, Kobra Systems, and a component collection within days. Treat **VibeCurb, shadcnuikit.com, Kobra Systems, forever-components** as one user's promotional claim, not consensus. Several design-audit skills had their *own* before/after screenshots criticized in-thread as still looking AI-generated.

**Impeccable is the exception** — it has independent organic endorsement across four subreddits, and one critic conceded *"the guy behind it seems to have some serious skill"* while disliking the website.

### The four that matter

**Impeccable** (72,842★, Apache-2.0) — *the only mechanical gate I found.*
> "1 skill, 24 commands, live browser iteration, and **61 deterministic detector rules** for AI-generated frontend design."

**The 61 rules run with no LLM and no API key.** That makes it a pre-commit lint, not a prompt — the only non-generative enforcement mechanism in this entire list.

Its named tells: *"Inter for everything, purple-to-blue gradients, cards nested in cards, gray text on colored backgrounds, the rounded-square icon tile above every heading."* Plus: never pure black/gray (always tint), **never bounce/elastic easing (feels dated)**.

Its architectural idea is worth stealing even if you skip the install: `/impeccable init` writes **`PRODUCT.md`** (audience, purpose, constraints, voice — *what* the product is) **separately** from **`DESIGN.md`** (visual direction — *how* it looks). Two files, two concerns. Good template for your own setup.

**Supports OpenCode** (this harness) — `npx impeccable install --providers=opencode` ✅ verified in its README.

**taste-skill** (91,459★) — *"The Anti-Slop Frontend Framework for AI Agents."* Install name is `design-taste-frontend`. Ships both code skills **and image-generation skills for reference boards** — the workflow is: generate reference frames, hand them to Codex/Cursor/Claude for implementation.

**ui-ux-pro-max** (131,895★) — 192 reasoning rules, 79 searchable UI styles, 50 product palettes with reasoning profiles, 74 font pairings, 119 UX guidelines. Has its own site: https://uupm.cc ✅
**Explicitly supports OpenCode:** `npx ui-ux-pro-max-cli init --ai opencode` ✅

**Hallmark** (29,347★, by Together AI) — *"a design skill that refuses to look AI-generated."* 21 themes, **57 slop-test gates** + a pre-emit self-critique. Four verbs:
| Verb | What it does |
|---|---|
| *(default)* | Build new UI — picks a macrostructure, applies rules, runs the slop test before returning |
| `hallmark audit <target>` | Score existing code, punch list, no edits |
| `hallmark redesign <target>` | Throw out structure, keep copy + IA + brand, rebuild with a different fingerprint |
| `hallmark study <screenshot\|URL>` | Extract the DNA from a design you admire |

Live demo: https://www.usehallmark.com ✅

**avoid-ai-design** (87★) — the most *rigorous* one despite low stars. It catalogs **67 AI tells**, each ranked by **who notices**: **P0** a layperson, **P1** a designer/developer, **P2** craft. It also documents **second-order defaults** — the escape hatches AI reaches for *once you ban purple gradients* (cream+terracotta, near-black+acid-green, all-caps mono chrome, one colored headline word) are now themselves a recognizable cluster. Ships a zero-dependency scanner:
```bash
node ~/.claude/skills/avoid-ai-design/scripts/detect.mjs src/
# exit code 2 when P0/P1 found → usable as a CI gate
```

---

## 3. The authoritative voice: Anthropic's `frontend-design` skill

**https://github.com/anthropics/skills/tree/main/skills/frontend-design** (repo: 179,118★)

The best-written statement of the problem. Verbatim from its `SKILL.md`:

- Persona: *"act as the design lead at a design studio known for giving every client a distinct visual identity that is not mistaken for anyone else's."*
- **Ground the design in the subject matter** — *"a design for a toy for girls aged 8–11 will be very aesthetically different from a dashboard for financial analysts."*
- **Hero:** *"Open with the most characteristic thing in the subject's world."* It names the default explicitly: *"a big number with a small label, supporting stats, and a gradient accent is the default treatment, so only use it if that's truly the best option."*
- **Typography:** *"You don't need a different typeface for display or headline text and body content: use one family or two, and if two, make them clearly distinct."*
- **"Avoid these default typographic treatments; they are the commonest tells of a generated page":** accenting a single word in a headline; all-caps labels; unnecessary labels above content.
- Structural devices must *encode information*, not decorate. It cites `01 / 02 / 03` numbering as an over-used tell.
- *"Use non-user-triggered motion sparingly and deliberately, only to draw attention."*

---

## 4. Components the agent can actually install

### Copy-paste model (source lands in YOUR repo — agent can restyle freely)

This distinction matters: copy-paste means the agent owns the code and can modify it without fighting a package.

| Library | URL | Best for |
|---|---|---|
| **shadcn/ui** | https://ui.shadcn.com | Baseline. 124,895★, MIT ✅ |
| **ReUI** | https://reui.io | **1,149 free components**, 81 categories, both Radix + Base UI, `llms.txt` ✅ |
| **Magic UI** | https://magicui.design | Animation layer. **Has official MCP** (`magicuidesign/mcp`) |
| **Aceternity UI** | https://ui.aceternity.com | High-drama 3D/spotlight/aurora. ⚠️ overusing it is itself a slop tell |
| **Cult UI** | https://www.cult-ui.com | **100+ AI agent blocks** (AISDK agent patterns) |
| **Kibo UI** | https://kibo-ui.com | AI chat primitives, tables, dropzones |
| **Tremor** | https://www.tremor.so | Dashboards + charts. ⚠️ docs reorganized, old paths 404 |
| **assistant-ui** | https://github.com/assistant-ui/assistant-ui | MIT chat primitives, 12,361★ |
| **Skiper UI** | https://skiper-ui.com | Deliberately *"un-common"* — off-default by design |
| **Kokonut UI** | https://kokonutui.com | Free marketing blocks |

**Non-React ports** (all MIT, all copy-paste): **shadcn-vue** https://www.shadcn-vue.com (10,651★) · **shadcn-svelte** https://shadcn-svelte.com (9,170★)

### True Web Components (framework-free — best escape from "every React site looks the same")
**Shoelace** https://shoelace.style (13,833★) · **Web Awesome** https://webawesome.com · **FAST** https://fast.design (9,674★) · **Lit** https://lit.dev (21,843★)

### Headless / npm (vendor owns the code)
**Radix UI** https://www.radix-ui.com · **Base UI** https://base-ui.com · **Ark UI** https://ark-ui.com · **Headless UI** https://headlessui.com (28,768★) · **DaisyUI** https://daisyui.com (42,513★) · **Open Props** https://open-props.style

⚠️ **daisyUI's real repo is `saadeghi/daisyui` (42,513★).** The `daisyui/daisyui` org repo has 8★ — it's a decoy, don't link it.

### 21st.dev — the one built for agents
**https://21st.dev** — 12,000+ components, and **every component ships as a prompt**. Its pitch: *"copy the prompt, paste it anywhere"* — works in any tool, not just their plugin. Has CLI + MCP + a "Design Bug Bot" that reviews UI in PRs.

---

## 5. MCP servers — how the agent gets real components

### shadcn MCP (official — install this first)

```bash
npx shadcn@latest mcp init --client opencode     # or claude | cursor | vscode | codex
```

**I ran this in a scratch dir against this OpenCode harness — it worked cleanly** and wrote:
```json
{ "mcp": { "shadcn": { "type": "local", "command": ["npx","shadcn@latest","mcp"], "enabled": true } } }
```

**Pair it with the shadcn skill** — `npx skills add shadcn/ui`. The MCP gives registry access; the skill gives project context and correct API usage. Complementary, install both.

### The registry mechanism (bigger than any single library)

`npx shadcn add @<registry>/<component>` works against **any** registry, not just shadcn's. A registry is just JSON at a URL template.

**This is the highest-leverage move if you already have a codebase:** publish your own design system as a registry and the agent stops inventing components.

### Others

| Server | Endpoint | Note |
|---|---|---|
| **ReUI MCP** | `https://mcp.reui.io` | Free tier. Also `https://reui.io/llms.txt` ✅ — feed straight to agent |
| **Context7** | npm `@upstash/context7-mcp` | 62,557★. Version-specific docs. Solves "agent invents APIs that don't exist" |
| **Figma MCP** | `https://mcp.com.figma.mcp/mcp` | Key tool: `get_design_context`. ⚠️ desktop server needs paid seat |
| **Magic UI MCP** | `github.com/magicuidesign/mcp` | Official |
| **21st MCP** | https://21st.dev/mcp | Free tier (2 installs/day) |

---

## 6. Inspiration & reference

### Galleries — verified live today
| Site | URL | Status |
|---|---|---|
| **Godly** | https://godly.website | ✅ 200 — best curated gallery |
| **UI Movement** | https://uimovement.com | ✅ 200 — micro-interactions |
| **Navbar Gallery** | https://www.navbar.gallery | ✅ 200 — agents over-genericize navbars specifically |
| **One Page Love** | https://onepagelove.com | ✅ 200 |
| **Minimal Gallery** | https://minimal.gallery | ✅ 200 |
| **Httpster** | https://httpster.net | ✅ 200 — WebGL/canvas focused |
| **The FWA** | https://thefwa.com | ✅ 200 — human-judged |
| **Webby Awards** | https://www.webbyawards.com | ✅ 200 |
| **Bento Grids** | https://bentogrids.com | ✅ 200 — *see correction below* |
| **Awwwards** | https://www.awwwards.com | live, 403 to bots |
| **Land-book / Lapa Ninja** | — | live, 403 to bots |
| **refs.gallery** | https://refs.gallery | live, 429 rate-limited (retry later) |

⚠️ **Correction:** the correct bento-grid domain is **`bentogrids.com`**, not `bento-grids.com` (which does not resolve). Also verified: https://www.a1.gallery/style/bento ✅ and https://www.uwarp.design/bentogrids ✅

### Screenshots & flows — where the agent learns *layout*
| Site | URL | Note |
|---|---|---|
| **Mobbin** | https://mobbin.com | Industry standard. **Paid** |
| **Pageflows** | https://pageflows.com | ✅ 200 — *user-flow sequences*. Best answer to "AI builds a page with no flow" |
| **Nicelydone** | https://nicelydone.club | ✅ 200 |
| **Screenlane** | https://screenlane.com | ✅ 200 — free tier |
| **Refero** | https://refero.design | ✅ 200 — design ref + code |
| **Pttrns** | https://pttrns.com | ✅ 200 — mobile patterns |

### A dissenting view worth hearing (from r/web_design)
A practitioner thread on "the one design inspiration tool you use" produced this critique, which is the most useful thing in the thread:
> "Awwwards is nice to look at but the sites are often so far removed from actual useable websites — it's more just design for designers." — u/saalaadin
>
> Another commenter: *"Awwwards sacrifices usability for ego. We're supposed to be building usable tools that serve a purpose."*

Same thread, named tools people actually use: **Mobbin** (real-world UX), **Dribbble** (UI ideas only, same "not real-world UX" problem), **21st.dev** (copy-paste for vibe coding), **GSAP** (SVG animation), **simple.design**, and one person who just uses **physical art books** — *"it forces me to slow down… slow is fast."*

**Takeaway: use Awwwards/Godly for aesthetic ceiling, but Mobbin/Pageflows for structure.** Agents default to pretty-and-useless.

### 3D / WebGL reference
| Resource | URL | Status |
|---|---|---|
| **mesh3d** | https://mesh3d.gallery | ✅ 200 — the dedicated 3D reference, filter by tech/tag/maker |
| **Bruno Simon** | https://bruno-simon.com | ✅ 200 — *the* recommended 3D learning resource. A Reddit top-vote: *"you could probably build 80% of that site after going through it"* (75↑) |
| **Three.js examples** | https://threejs.org/examples | ✅ 200 — ground truth for what's buildable |
| **GSAP Vault** | https://gsapvault.com/blog/gsap-animation-examples | ✅ 200 — 114 examples, 9 free w/ copy-paste |
| **GSAP showcase** | https://gsap.com/showcase | ✅ 200 |
| **Spline** | https://spline.design | ✅ 200 — browser 3D tool |
| **Landing.love** | https://landing.love | ✅ 200 |
| **Rive** | https://rive.app | ✅ root — ⚠️ `/community` now 404s |
| Awwwards Three.js tag | https://www.awwwards.com/websites/three-js/ | live, 403 to bots |
| Codrops | https://tympanus.net/codrops | live, 403 to bots |
| ShaderToy | https://www.shadertoy.com | live, 403 to bots — best source of real GLSL |

⚠️ **Reddit's honest verdict on 3D sites:** reference value high, production-advice value low. Commenters on a "how much would a 3D WebGL site cost" thread (304↑): *"usability and readability are horrible"*, *"Classic form over function"*, *"barely legible on mobile"*, *"it is slow loading-wise."* Also note the cost thread ranged from $5k to $18k with zero consensus.

### ⭐ Agent-ready galleries — built to be fed to an agent

These are the highest-ROI additions from X. Unlike Awwwards, each one is structured to be consumed by a model.

| Site | URL | Status | What it is |
|---|---|---|---|
| **Refero Styles** | https://styles.refero.design | ✅ 200 | **2,000+ real product sites, each as an AI-readable DESIGN.md.** Colors, typography, spacing. *The single largest DESIGN.md source.* Page is JS-rendered so I could not independently confirm the 2,000 count — treat that number as the creator's claim |
| **Component Gallery** | https://component.gallery | ✅ 200 | *"examples from the world of design systems."* Look up any component and see how dozens of mature systems solve it. This teaches structure, not just style |
| **Kinetics** | https://kinetics.colorion.co | ✅ 200 | **153 spring-physics motion effects — I verified the count on-page.** Each ships copyable CSS, React code, **and a ready-made AI prompt** |
| **ScrollTide** | https://www.scrolltide.co | ✅ 200 | 200+ **full build prompts** for 3D and scroll-driven sites. Each is a complete design brief, not a component |
| **ThreeUI** | https://threeui.com | ✅ 200 | @MengTo. 160+ free three.js components + landing pages. *"Copy the prompt or source, give it to your agent, then change theme, lighting, motion or layout"* |
| **Kage** | https://kage.design | ✅ 200 | UI inspiration mapped straight to prompts |
| **ui-skills.com** | https://www.ui-skills.com | ✅ 200 | Curated human-organized UI-skill catalog |
| **ThreeUI demo** | https://sunset-tutorial.mengto.here.now/ | — | Full tutorial with the actual prompts |

### Single-element galleries — where agents over-genericize
Agents have the weakest priors on these specific elements, so targeted references pay off disproportionately.
**nav** https://www.navbar.gallery ✅ · **CTA** https://cta.gallery · **footer** https://footer.design · **404** https://404s.design · **hero** https://supahero.io · **recent** https://recent.design

### Design resources outside the Western bubble
A genuinely useful angle from X (@thedennisobaro1): *"That's why so much AI-generated design looks identical. Same tools. Same references. Same output."*
**UI Notes** https://uinotes.com · **Wit Design** https://wwit.design (Chinese) · **UI Bowl** https://uibowl.io · **Zcool** https://www.zcool.com.cn
If your UI looks like every other AI output, training on a different design tradition is a structural fix no banned-list provides.

### A free mega-repo
**bradtraversy/design-resources-for-developers** — fonts, icons, illustrations, colors, UI kits, templates in one place.


The OP's complaint about Awwwards: *"either way too 'experimental' or just flat-out unusable in practice."*

| Site | URL | Status |
|---|---|---|
| **maxibestof.one** | https://maxibestof.one | 403 to bots (likely live) — named by 2 users. **"Less known, high quality, filter by fonts"** — best fit for the font-pairing use case |
| **toools.design** | https://www.toools.design/ | ✅ 200 — meta-directory of 1,500+ design resources |
| **Landingfolio** | https://landingfolio.com | conversion-focused landing pages |
| **CSS Zen Garden** | https://csszengarden.com | same content, thousands of stylesheets |
| **are.na** | https://are.na | moodboards |
| **cosmos.so** | https://cosmos.so | ✅ 200 |
| **Fontjoy** | https://fontjoy.com | ✅ 200 — font pairings. 4,585↑ on r/InternetIsBeautiful; the only font tool with genuine non-promotional endorsement |
| **Competitor websites** | — | **The top-voted answer (84↑):** *"Realistically, I go on competitors websites. Seeing real concrete examples that are being used is what really helps me."* |

### Performance warning on the slop aesthetic
A practitioner (u/bazgrim_dev) on why AI motion is not just an aesthetic problem:
> "AI's use of animations, glow, shadows, and hovers are probably the worst offenders from a dev perspective. Causes significant slow down, long paint times, and some browsers do not play well with certain combinations."

---

## 7. Fonts, color, motion, icons

### Fonts — pick deliberately, this is a top-tier slop tell
**Google Fonts** https://fonts.google.com · **Google Fonts Knowledge** https://fonts.google.com/knowledge *(typographic guidance, not just downloads)* · **Fontshare** https://fontshare.com · **Fontsource** https://fontsource.org (6,150★, self-host) · **Bunny Fonts** https://fonts.bunny.net (GDPR-friendly)

A Reddit practitioner put it bluntly: *"Go look for a font you like, so it's not the standard Claude font or the standard jetbrains mono/roboto Google fonts."*

### Color — generate, don't let the model invent
**Radix Colors** https://www.radix-ui.com/colors ✅ — 12-hue × 12-step accessible scales. **Best single tool here.** A Redditor: *"just look for a palette website and get some new colors that are again, not the standard generated glowy blah."*
**OKLCH** https://oklch.com · **Adobe Color** https://color.adobe.com · **Coolors** https://coolors.co (403 to bots) · **APCA** https://www.apca.org — perceptual contrast, better than WCAG 2 for UI

### Icons — one set, never mixed
**Phosphor** https://phosphoricons.com — 6 weights incl. duotone; **more distinctive than Lucide, so a better anti-slop lever**
**Lucide** https://lucide.dev — the current default (⚠️ default = recognizable)
**Iconify** https://icon-sets.iconify.design · **Tabler** https://tabler.io/icons
⚠️ **Feather** https://feathericons.com — minimal but dated-looking; counterproductive for anti-slop

### Motion
**cubic-bezier.com** https://cubic-bezier.com · **easings.net** https://easings.net · **MDN CSS animations** https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_animations
⚠️ **Never bounce/elastic easing** — named by both Impeccable and Anthropic as a dated tell.

---

## 8. Communities worth following (subscribers as of 2026-09-30)

**Design-focused**
| Subreddit | Subs | Best for |
|---|---|---|
| r/web_design | 979,218 | Real-world website design. Best inspiration threads |
| r/UXDesign | 250,955 | Working UX pros. **Best source for reference-tool recommendations** |
| r/UI_Design | 240,781 | Critique threads, visual-hierarchy reasoning |
| r/FigmaDesign | 158,143 | Figma kits, Figma MCP, Design Agent news |
| r/design_critiques | 133,898 | Teardowns — extracts *what reviewers actually flag* |
| r/webdesign | 86,367 | Annual inspiration-site listicles |

**AI-agent design (where the tooling lives)**
| Subreddit | Subs | Note |
|---|---|---|
| r/ClaudeAI | 1,162,995 | Highest-engagement anti-slop threads. Auto-TL;DR bot summaries after ~50-100 comments are genuinely useful |
| r/LocalLLaMA | 837,724 | ⚠️ Requested in scope — **no design content surfaced.** Model-serving focused |
| r/reactjs | 514,460 | |
| r/ClaudeCode | 428,717 | Skills, CLAUDE.md, workflows |
| r/vibecoding | 368,603 | Loud "AI UI all looks the same" discussion. Mixed quality, heavy self-promo |
| r/claudeskills | 83,609 | **Dedicated skills sub.** Best single sub for this task |
| r/ClaudeDesign | 25,797 | Claude's design/artifact mode |
| r/vibedesigns | **964** | Tiny/new, explicitly about fighting AI design looks. Watch, don't rely |

**Stack:** r/webdev (3.3M) · r/reactjs · r/Frontend · r/nextjs · r/tailwindcss · r/shadcn (10,213)

---

## 9. Workflows practitioners actually use

**1. Token-lock before generating a single screen** — the most repeated structural fix (r/UXDesign, u/nikhil_akki):
> "Consistency isn't a reference problem at all imo, it's a tokens problem. Lock your spacing scale, type ramp, radii, one accent and your control set before you generate a single screen... Skip that and prompt screen by screen and you get twelve mini design systems."

**2. Negative constraints + semantic tokens in your agent config file:**
> "Define strict negative design constraints and a semantic token system (e.g., no raw hex codes, hard limit on border-radius, force flat dividers and tabular views for data density)."

**3. Feed a realistic, messy dataset before the UI:**
> "Provide a realistic and messy JSON dataset or schema first, including varying string lengths, empty states, edge cases, and pagination, to inform visual hierarchy."

**4. Image-gen as the design spec, not decoration** (u/stumpyinc):
> "If Claude Design looks lacking, throw that same prompt at an image gen model like ChatGPT and hand that image to Claude Design to recreate it. You basically will not get something ugly going that route."

**5. Replicate a specific named site** (u/mitterb, 121↑ — most-upvoted technique in a 455-upvote thread):
> "You find a website you want to replicate from Dribbble or Awwwards and then ask Claude to replicate X website's layout with your brand colors and identity."

**6. "Iterate on X until Y"** (u/Ok_Letterhead1945):
> "If you say 'iterate on x until y', it will make sweeping progress on x, then stop precisely once it reaches y. This usually will make tons of beneficial changes that you wouldn't even know how to ask for."

**7. Keep skill files modular + diff against known-good outputs** (u/Future_AGI) — this solves a real failure mode:
> "Keep a few reference 'good' outputs and diff new generations against them, or the rules rot as the prompt grows."
> "Once context grows past a few turns, models start ignoring instructions and quietly drift back to the mean."

**8. Headless vision QA loop** — screenshot at 1440px and 375px, feed back for critique.

**9. Build a style-guide page, then refine element by element** (u/smickie) — every element on one page, ~an hour each, "so it doesn't trigger that part of your brain that says slop."

**10. Feed it the Apple HIG** — mentioned, untested by the poster.

### What does NOT work (equally useful)
- **Opinionated audits on established products.** u/hakansan: *"I've found impeccable a bit too opinionated… When you have an established web app with a user base you inherently know that some design decisions are there because they help with conversion/retention."* Another: *"all I got out of a bunch of usage was a recommendation to use a darker shade of gray and four lines of css."*
- **One-shot prompting.** u/stumpyinc: *"no more trying to 'one-shot' sites or projects… that whole concept is silly to me."*
- **Screenshots alone.** u/bluesjammer: *"the visual nuances are missing like knowing where an animation is required, shadow values, colors etc are just off."* And u/nikhil_akki: *"Screenshots aren't the real assets but the list is, just the screenshots become the trap."*

### The dissent you should hear
Not everyone wants non-standard UI. r/vibecoding, u/duckface3000:
> "Cognitive load to learn new form and interaction patterns hurts conversion and usability... Unless you're building a marketing landing page, personal portfolio, or an artistic website, following standard UI is going to produce the best results. It's product design 101."

And u/canarydev on shadcn, which reframes the whole problem:
> "shadcn isn't making things slop. it's just what slop reaches for because it's fastest. same thing for bootstrap, material ui. the default of the era always collects the low effort stuff"

**Read that as: for internal tools and CRUD products, aggressively fighting the default is the wrong goal. The slop problem is real for marketing pages, portfolios, and consumer-facing brand surfaces — which is presumably what you're building.**

---

## 10. The copy-paste agent config block

The most directly usable artifact found on X. Add this to your agent's config file (e.g. `CLAUDE.md`). Published by @Voxyz_ai and independently by @davidarngar.

> **Frontend references.** Use only when building a new page, when I say something looks bad, or when I name one of these sites. For small changes, just do the work.
>
> - **Style**: pick a DESIGN.md that fits the product from `styles.refero.design` or `VoltAgent/awesome-design-md` on GitHub. Put it in the project root and add an `@` import for it, so from then on everything follows its colors, typography and spacing.
> - **Components**: check 21st.dev first, and call its MCP directly if it's installed. It has a free usage limit, so tell me what you're looking for before you call it. Then check `component.gallery` to see how mature design systems handle the same component.
> - **Motion**: get a ready-made prompt or React code from `kinetics.colorion.co`.
> - If it still feels off when it's done: run **polish** and **distill** from Impeccable.
>
> **The project's existing design system and components come first. Outside references only fill in what hasn't been decided yet.** If an MCP, skill or CLI you need isn't installed, ask me whether to install it, and don't imitate it yourself. If you can't read a page's actual content, stop and ask me to paste it in. **Don't fill anything in from memory.** Every time you use an outside reference, tell me which one and what you changed. Show me what you'll add first, and don't write it until I confirm.

### The most important line in it
@gregisenberg's framing, which explains the whole approach:
> "The HTML is the finished dish. The design.md is the recipe. The skills are the ingredients."

And the mistake he says people make:
> "They nail one screen and then everything else looks generic. Design.md solves this. One file keeps every page, every format, every medium consistent."

@gregisenberg's seven steps (a 3,517-like thread):
> "**Don't create a design system from scratch. Find a brand you love.** Linear, Stripe, Vercel, whatever resonates. Study it. Use ChatGPT or Claude to help you extract the design language into your own design.md file… **Taste is developed, not downloaded.**"

@arlanoska adds the discipline that keeps it honest:
> "An 8px radius token is the wrong answer for an 8px gap. **Values with no match get flagged instead of a made-up name.**"
> "A screenshot shows the default state. **The bugs live in the others.** — Invalid input should send nothing. Pending should block a second submit."

And @davidarngar, which is the failure mode to avoid:
> "**Don't give the model thousands of styles at once — pick one DESIGN.md, keep it in context, and make the model stick to it. Constraints create consistency.**"

⚠️ **That last one contradicts the "2,000 DESIGN.md files" pitch, and it is the more correct advice.** A library of 2,000 styles is for *you* to choose from. The agent gets **one**.

### The highest-engagement single prompt on X
@Voxyz_ai's four-source diagnosis — use it as a checklist for "what's still generic?":
> - **No idea what style to go for** → Refero Styles
> - **Components look rough** → 21st.dev + Component Gallery
> - **Motion feels flat** → Kinetics
> - **Done, but something still feels off** → Impeccable: *bolder, distill, polish* turn "make it look better" into specific changes

The award-bar self-check prompt (@kajikent, 3,739 likes — highest-engagement prompt for this exact goal), translated from Japanese:
> "Aim for a quality bar that could win an Awwwards, Webby Awards, or FWA award. **Self-check whether you've met that bar, and keep repeating the quality upgrade yourself until you do.**"

### The "shot list" prompt — stop describing, start specifying
@awp_Akira. This one fixes a real, specific failure:
> "The secret is **you stop describing the site and start handing the model a shot list.** Most people type 'a premium arctic puffer jacket store with a video hero' — the model has to invent the whole structure, so it guesses differently every run. Instead you write the page as an **ordered list of sections and give each one a job**:
> ```
> 01 hero, full bleed video, nav over it, one product in frame, nothing competing
> 02 ticker, single line, specs only, loops forever
> 03 catalog, 3 cols desktop / 2 tablet / 1 mobile, image first, price last
> 04 story, one image, one paragraph, done
> ```
> Now the model isn't designing anything, **it's filling a structure you already locked in.**"

### Component contracts
@Boris_Jov: *"Every component gets a contract first — small JSON with purpose, usage rules, allowed props, a11y requirements, code sample. **Contract → code. Code must match exactly.**"* Plus strict rules: *"Use existing components only. No local copies. One primary button per screen. If something's missing? Stop and ask."* He reports an **85% first-prompt retrieval rate** as a result.

### Screenshot loop with a twist (@emilkowalski, ex-Framer Motion lead, 42,339★)
> "I reached a point where basically all of my animations work is done without touching the code. Start with `/prototype` to see a few different variants, tell it to use `/animate` for the right easing and timing, then run `/prep-for-prod` — perf, a11y, mobile checks. **Since almost every 'taste' decision related to animation has a logical reason, this can get you pretty far even when you don't know much about motion.**"

Two concrete opinions from him worth stealing outright:
> "I'm like 98% sure that you should set **`text-wrap: pretty;` by default globally**."
> "Don't forget to **stagger your animations** if you animate a lot of elements."

### The negative-constraint pattern for motion
@twoclipping published a full XML-structured motion prompt whose `<direction>` block ends with an explicit ban list — the transferable trick is the ban list itself:
> "**Banned: crossfades, blur-ins, brightness 'developing', 3D flips, particles, glows, holds longer than 1s, anything that looks like a template.**"

@notdwd states the underlying principle:
> "**When you give AI nothing, it falls back to the same generic shit everyone else is posting.** Give it great work to study, then let it handle the execution."

---

## 11. Design system standards (read these for *rules*)

**Material Design 3** https://m3.material.io ✅ — most complete tokenized spec
**Apple HIG** https://developer.apple.com/design/human-interface-guidelines ✅ — typographic/motion judgment
**Carbon** https://carbondesignsystem.com ✅ — enterprise density · **Fluent 2** https://fluent2.microsoft.design ✅
**Polaris** https://polaris.shopify.com ✅ · **Primer** https://primer.style/product ✅
**DesignSystems.com** https://www.designsystems.com ✅ — directory
**Design Tokens spec** https://www.designtokens.org/tr/2025.10/format/ ✅ — *this is what DESIGN.md is modeled on*
**Style Dictionary** https://styledictionary.com · **Tokens Studio** https://tokens.studio
**Untitled UI** https://untitledui.com ✅ — huge free design system

**Figma kits:** Untitled UI free kit https://www.untitledui.com/free-figma-ui-kit ✅ (Pro paid) · **Penpot** https://www.penpot.dev ✅ (free/open-source Figma alternative)
⚠️ I could **not** find a current official shadcn Figma kit. Treat as unavailable.

---

## 12. What practitioners actually say (Reddit, verbatim)

Thread: *"Any advice to escape the AI slop web design look?"* — r/vibecoding, 44 comments

The most substantive answer, u/FreeEye5 — worth reading in full:
> "Design everything. Every element of your site, have an opinion about it. The boxes, the buttons, the accents, the menus. Pick a colour palette. Even put together a mood board of random unrelated images that fit the vibe. **Most importantly, do all this before prompting.**
>
> The main thing that drives AI slop is a lack of imagination, and all it takes is some dreaming. If you can picture your site in your head, then the work becomes bringing it to life. Now you're working towards a goal, and you can prompt specifically and meaningfully. It takes longer, and you don't get what you want straight away, but that's the point. Now that you're actually creating something new from your imagination, you've broken the slop barrier."

Other answers from the same thread:
- **u/Due-Boot-8540:** *"Search for component libraries and UI kits on GitHub. Storybooks are a good source for best practice. It's probably easier to fork a good repo and use it as a starter than wasting hours trying to make the shore that AI tends to spit out."*
- **u/Interesting-Stuff123:** built a site using *"a lot of anti AI Claude Code skills that help me such as pbakaus/impeccable"*
- **u/BlasterLizardCo:** *"try feeding/training it with good designs that were made by hand by other people… try designing it yourself and training the AI to follow your design pattern."*
- **u/SeattleArtGuy** (joke, but a real technique): name a specific site as the target — *"make the site look like cnn.com"* — instead of describing an aesthetic in adjectives.
- **u/jlemrond:** *"Make it look like a 90s website. Everyone will assume you built it 30 years ago!"*
- **Counter-advice, u/kosro_de:** *"If you don't know what makes a design good or stand out, you're going to have a hard time building one that is/does. Vibecoding doesn't change that fact."* — the honest ceiling on tooling.

---

## 13. The tell-list, ranked by DATA (not opinion)

**[vibecoded-design-tells](https://github.com/JCarterJohnson/vibecoded-design-tells) — 506★** is the only empirically-grounded source in this entire list. It mined **3,214,533 Reddit posts** across 47 subreddits (2020–2026) from the public Arctic Shift archive, then harvested **3,033 comments from 125 canonical threads**. Reproducible with plain Python — no API key, no auth. It even adversarially re-verified its own findings: **11 of 12 held up, 1 was rejected as a keyword artifact.**

I pulled the actual ranking from its `comment_tell_counts.csv`:

| Tell | % of comments | Neg. sentiment |
|---|---|---|
| "Screams AI" / soulless / slop | **6.4%** | 135 |
| "All looks the same" / template / cookie-cutter | **6.1%** | 126 |
| shadcn / Tailwind default kit | **2.5%** | 16 |
| Purple / violet ("AI purple") | **2.3%** | 29 |
| Gradients everywhere / gradient text | **2.0%** | 21 |
| Too many animations / Framer fade-ins | 1.1% | 6 |
| Rounded corners / pill buttons | 0.8% | 10 |
| Dark mode + neon glow | 0.7% | 3 |
| Emoji / ✨ sparkles / 🚀 in copy | 0.5% | 4 |
| Generic sans (Inter / Geist) | 0.4% | 7 |
| Three-column feature cards | 0.4% | 1 |
| Mesh / blob / aurora backgrounds | 0.3% | 3 |
| Glassmorphism / frosted glass | 0.2% | 2 |
| Same hero: huge headline + 2 buttons | 0.2% | 3 |
| Centered everything / endless whitespace | 0.2% | 3 |
| Bento grid | **0.1%** | 1 |

### Two findings that contradict most advice online

**1. The top two tells are not features — they're sameness itself.** "Screams AI" and "all looks the same" each appear in ~13% of on-topic posts, an order of magnitude above any individual feature. Negative sentiment 91% of the time. **This is the thesis: you are not penalized for a specific color, you are penalized for looking recognizable.** Hence DESIGN.md matters more than any banned-word list.

**2. The "obvious" offenders are the *least* complained-about.** Bento grids (0.1%), glassmorphism (0.2%), aurora backgrounds (0.3%) sit at the bottom — and mesh/aurora was **formally rejected** as a keyword artifact in adversarial verification. Most anti-slop blog posts lead with glassmorphism and bento grids. The data says nobody actually minds those.

**Ranked by real complaint volume: shadcn/Tailwind defaults > AI purple > gradients > too many animations > rounded/pill > neon glow > emoji > Inter.**

It ships three skills: `unslop-ui` (websites), `unslop-text` (prose), `unslop-code` (source). The UI one has a standalone scanner whose **exit code equals the high-severity finding count → usable as a CI gate**.

### The tell-list moves. This is the important part.
The same research shows the target keeps shifting. A practitioner in r/ClaudeAI:
> "The first version also got fair criticism that its 'after' example swapped the 2024 purple gradient for the 2026 look (a cream background with a serif display font and sage green), which is its own tell now."

> "'Don't ship the current default' is a purely stylistic choice."

Vibe-coding mentions rose from ~2 per 10,000 posts (2022) → 278 (2024) → 336 (2025). **Any static banned-list will be obsolete within a year.** This is the strongest argument for the DESIGN.md approach: a token system constrains *permanently*, while a banned-list only constrains *until the next default*.

---

## 14. The complete tell-list (consensus view)

Consensus across Anthropic, Impeccable, avoid-ai-design, and Reddit practitioners. Ordered by the DATA above where they agree, flagged where they don't:

**Immediately reads as AI (P0):**
- Inter / Roboto / system-stack for everything
- Purple→indigo→blue gradient
- Gradient-filled headline text
- Centered hero → subhead → two buttons → three feature cards
- `rounded-2xl` + `shadow-lg` + `backdrop-blur` on everything (untouched shadcn defaults)
- Cards nested in cards
- Emoji as feature icons
- "Elevate your workflow" / "Seamless" / "Powerful" copy; "Get Started" CTA
- Sparkle ✨ as the AI motif
- Logo walls as plain text wordmarks

**Second-order defaults** (the escape hatches, now themselves recognizable — from avoid-ai-design):
- Cream + terracotta (Claude's own interface color)
- Near-black + one acid-green or vermilion accent
- Broadsheet hairlines
- All-caps / monospace template chrome; one accented headline word
- Decorative `01 / 02 / 03`
- Fake window dots
- Emerald fallback green

**A designer notices (P1):**
- 3–6 identical icon+heading+text card grids
- Gray text on colored backgrounds; pure black/gray (always tint)
- Rounded-square icon tile above every heading
- Bounce/elastic easing
- Generic CTA labels ("Learn more")
- Same fade-up on every section; count-up stats
- Unstyled `<div>` rectangles standing in for product screenshots
- Three-tier pricing presented as concentric rings
- No `tabular-nums` on data; no focus states

---

## Recommended setup — copy/paste

```bash
# 1. THE MECHANISM — write DESIGN.md in your project root.
#    Tokens (exact values) + prose (why). This is what replaces the model's defaults.
npx @google/design.md lint DESIGN.md

# 2. A taste reference it didn't write — pick ONE, not many.
#    (A library of 2,000 is for YOU to choose from. The agent gets one.)
#    Browse:  https://styles.refero.design          2,000+ real products as DESIGN.md
#              https://getdesign.md/<brand>/design-md   73 hand-curated brands
#    Or extract from a site you admire:
#    designlang https://stripe.com --depth 5

# 3. Anti-slop skill (pick ONE to start)
npx skills add https://github.com/Leonxlnx/taste-skill
npx impeccable install --providers=opencode     # supports opencode ✅
npx ui-ux-pro-max-cli init --ai opencode

# 4. Real components, not hallucinated ones
npx shadcn@latest mcp init --client opencode     # verified working on this harness ✅
npx skills add shadcn/ui

# 5. Agent-readable references (all verified 200 today)
#    https://component.gallery    how mature systems solve the same component
#    https://kinetics.colorion.co  153 motion effects, each with a prompt

# 6. Mechanical gate in pre-commit (no LLM, no API key)
node ~/.claude/skills/avoid-ai-design/scripts/detect.mjs src/   # exit 2 = P0/P1 found
```

**Order matters, and it's a three-layer architecture:**

| Layer | What | When it runs |
|---|---|---|
| **Constraint** | `DESIGN.md` tokens | Every prompt, permanently |
| **Guidance** | an anti-slop skill | Every prompt |
| **Enforcement** | a linter / CI gate | Every commit, no model |

Steps 1–2 do most of the work and cost nothing. **If you only do one thing: write the DESIGN.md.**

The X consensus is explicit that layer 1 alone is insufficient but layer 3 is what makes it stick — *"skills guide; checks enforce."* A skill file also decays: *"once context grows past a few turns, models start ignoring instructions and quietly drift back to the mean."* Only a linter doesn't forget.

### What NOT to do
- ❌ **Don't hand the agent thousands of styles at once.** Pick one DESIGN.md and make it stick. Constraints create consistency; a pile of references creates noise.
- ❌ Don't ban glassmorphism / bento grids / aurora backgrounds as your main strategy — the data says people don't complain about these (0.1–0.3% of comments). You'd be fighting a non-problem.
- ❌ Don't rely on a static banned-list. The default moves yearly; tokens don't.
- ❌ Don't run opinionated audits on an established product with conversion-driven decisions.
- ❌ Don't one-shot it. Practitioners are explicit that good output needs many tailoring passes.
- ❌ Don't fight the default on internal tools and CRUD products — standard UI is genuinely correct there.

---

## Not verified — check before relying on

- **`refs.gallery` / `siteinspire.com`** — live but 429 rate-limited from here; retry later
- **`https://mcp.com.figma.mcp/mcp`** — Figma MCP *docs* verified; the endpoint failed to connect from my host
- **Rive community** — `rive.app/community` now 404s
- **Tremor docs** — reorganized, old paths 404
- **shadcn Figma kit** — no current official kit located
- **shadcn ports for Angular / Solid / React Native / Ruby** — listed on shadcn.io but GitHub URLs not resolved
- **Framelink / Canva / Webflow / Penpot / Framer / MasterGo MCP** — confirmed only as *listed* in an MCP roundup; endpoints not individually tested
- **`Nfont` / `DaFont` / `Khroma` / `ColorBox` / `colorbrewer2.org`** — not verified. Avoid DaFont for commercial output (many unlicensed/derivative fonts)
- **`maxibestof.one`** — returns 403 to non-browser clients; likely live but unconfirmed
- **Refero Styles' "2,000+ files"** — the site is live and JS-rendered. I confirmed the DESIGN.md concept works but could **not** independently verify the count. Treat 2,000 as the creator's claim.
- **`cyw/scroll-world`** (claimed 6,096★) and **`Ibelick/improve-ui`** — named on X, no matching GitHub repo found. Unverified.
- **`slopbeth`, `deslop`, `humanize` (@aashatwt), `anti-ai-slop-writing`, `unslop` (@poteto)** — named on X, GitHub URLs not found. Unverified.
- **Mobbin MCP, Flowbite Pro, Refero pricing** — users' assertions, not verified
- **Some Reddit-sourced repos carry an astroturf risk** — see the integrity warning in §3
- **`opencli twitter tweet <id>` does not exist** — use `opencli twitter thread <id>`. `article` needs the article tweet's own ID, not the `t.co` container ID. X search hard rate-limits (~15–30 min); `thread`/`article` are unaffected.

**A note on the X thread** (@charliejhills, 1,455 likes, Aug 2026) — I re-verified all six UI-related entries live. Every count was **higher** than posted, so the list is directionally accurate. But note **only 6 of the 15 are UI-related**: `humanizer` (53,050★), `stop-slop` (17,668★) and `no-ai-slop` (11,577★) are **prose** de-sloppers; `i-have-adhd` and `archify` are output-formatting and diagram tools. Don't install 15 skills for a UI problem.

| Skill | Thread (Aug 2026) | Verified (Sep 30 2026) |
|---|---|---|
| ui-ux-pro-max | 120,460 | **131,895** |
| awesome-design-md | 110,052 | **118,914** |
| taste-skill | 79,935 | **91,459** |
| impeccable | 62,115 | **72,842** |
| design.md | 27,479 | **28,179** |
| hallmark | 26,835 | **29,347** |

## Accounts worth following

**@pbakaus** (Impeccable) · **@MengTo** (ThreeUI — 47-min tutorials with real prompts) · **@stitchbygoogle** (DESIGN.md) · **@nutlope** (Hallmark) · **@emilkowalski** (motion craft, ex-Framer Motion lead) · **@gregisenberg** (long-form AI-design workflows) · **@Leonxlnx** (taste-skill) · **@andybroncek** (curates mesh3d.gallery) · **@Voxyz_ai** and **@davidarngar** (independently published the best practical workflow summary) · **@awwwards** (free daily award-level feed)

## Sources

- Anthropic `frontend-design` SKILL.md — https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md
- Google DESIGN.md spec — https://github.com/google-labs-code/design.md
- **vibecoded-design-tells** (3.2M-post data mining) — https://github.com/JCarterJohnson/vibecoded-design-tells
- VoltAgent/awesome-design-md — https://github.com/VoltAgent/awesome-design-md
- Impeccable — https://github.com/pbakaus/impeccable · https://impeccable.style
- avoid-ai-design — https://github.com/funboy322/avoid-ai-design
- design-extract — https://github.com/Manavarya09/design-extract
- Reddit r/web_design inspiration thread (218↑) — https://www.reddit.com/r/web_design/comments/1ko8f6i/
- Reddit r/ClaudeAI "beautiful UIs instead of generic slop" (455↑, 122 comments) — post `1ws9oix`
- Reddit r/vibecoding anti-slop thread — https://www.reddit.com/r/vibecoding/comments/1ubewk8/
- Reddit r/UXDesign tokens-not-references — post `1vz1zpq`
- X @charliejhills 15-skills thread — https://x.com/charliejhills/status/2092898653820400076
- **@gregisenberg DESIGN.md workflow** (3,517 likes) — https://x.com/gregisenberg/status/2052110589682749869
- **@Voxyz_ai four-source workflow + CLAUDE.md block** (749 likes) — https://x.com/Voxyz_ai/status/2104284941437784139
- **@awp_Akira shot-list prompt** — https://x.com/awp_Akira/status/2104477836782236081
- **@kajikent award-bar self-check prompt** (3,739 likes) — https://x.com/kajikent/status/2105095422448746573
- **@MengTo ThreeUI launch** (9,156 likes) — https://x.com/MengTo/status/2090817187900780961
- **@emilkowalski motion workflow** (2,761 likes) — https://x.com/emilkowalski/status/2099948779864793303
- **@stitchbygoogle DESIGN.md announcement** (18,118 likes) — https://x.com/stitchbygoogle/status/2046624729403142320
- designbycurio, "How to Give Your AI Design Taste" — https://designbycurio.com/learn/give-your-ai-design-taste
