# Monetization — Five-Pass Analysis — 2026-10-30

**Version 1.0.0**

**AI manifest**: How this project could make money, worked out in five passes that each attack the one before. It reads the 2026-10-30 market (Anthropic org provisioning, Tessl pricing, AIR's $50M raise, paid skill marketplaces, consulting rates) plus a same-day pass over Reddit and X. It challenges the business model in @docs/14-competitive-product-business-strategy-2026-09-15.md rather than restating it. Proposals only: nothing here is approved, and every prediction is marked as one.

## Status and authority

**[NOTE]** This is research and strategy, not a decision. It changes no code,
CLI command, Store method or schema. Where it disagrees with
@docs/14-competitive-product-business-strategy-2026-09-15.md, that document
still stands until the maintainer chooses. Pricing figures from vendors,
marketplaces and sellers are their own claims and are marked as such. Where
this doc gives revenue targets, they are targets to test, not forecasts.

User-pain evidence comes from @docs/26-user-research-skills-context-2026-10-30.md.
This doc adds the money side.

## The starting position, measured

**[SPEC]** Measured on 2026-10-30, not estimated:

| Signal | Value |
|---|---|
| GitHub stars on this repo | 1 |
| PyPI downloads, last month (`skill-control-plane`) | 121 |
| Category leader (xingkongliang/skills-manager) | 7,079 stars, MIT, funded by a "Buy me a coffee" link |
| Other free managers | skills-hub 1,845; microsoft/apm 4,154; asm 961; all MIT |
| Most-installed skill on skills.sh | find-skills, about 4.1M installs |

**The leader has 7,079 stars and a tip jar.** That is the central fact. The
category's best-distributed product has not turned a free skills manager into
revenue. A plan that assumes this project will do so by being better must
explain what the leader is missing. "Better engineering" is not an answer
buyers can see.

## Pass 1 — The obvious answer, and why it fails

**The obvious answer:** keep the open-source core, then sell a Pro tier for
individuals and a Team tier for groups. That is the model in
@docs/14-competitive-product-business-strategy-2026-09-15.md (Pro USD 8–12 per
month, Team USD 15–25 per user per month).

**Why it fails as a first move:**

1. **The core job is being absorbed by the platforms.** Claude Code ships
   per-project `skillOverrides`. Codex has `[[skills.config]]`. Gemini has
   `skills disable`. Claude Team and Enterprise owners can now provision skills
   to everyone from an admin page, and Enterprise can turn on skill scanning
   ([Anthropic support](https://support.claude.com/en/articles/13119606-provision-and-manage-skills-for-your-organization)).
   Claude Code managed settings push plugin marketplaces to every machine
   ([managed settings docs](https://code.claude.com/docs/en/managed-settings)).
   Anyone who uses only one agent gets the on/off switch free.
2. **The free alternatives are good, popular, and look nicer.** Four MIT tools
   have between 961 and 7,079 stars. An individual will not pay USD 10 a month
   for a toggle they can get free.
3. **Paywalling a local Boolean breaks open source.** Docs/14 already says
   this. The code is MIT, so anyone can fork out a paywalled feature.
4. **Distribution is near zero.** At 121 downloads a month, even a 2%
   conversion rate is two people.

**Verdict:** selling this tool to individuals as a subscription is the weakest
of the options considered. It is not dead forever, but it cannot be the
first dollar.

## Pass 2 — Follow the money that already moves

Instead of asking what to charge for, ask who is already paying, how much, and
for what. Seven flows exist in the market today:

| # | Who pays | For what | Price signal (source) |
|---|---|---|---|
| 1 | Enterprises rolling out Claude | Rollout, training and governance, sometimes including a skills library | USD 85K / 150K / 235K packages ([AWS Marketplace listing](https://aws.amazon.com/marketplace/pp/prodview-nfcixwrexqdv2)); USD 9.5K–42.5K programmes ([ClaudeTraining](https://www.claudetraining.com/blog/claude-training-cost)); Anthropic is reported to be opening a consulting firm in Europe (X, @Kalshi, 1,053 likes) |
| 2 | Companies that need one integration | A custom skill wired to their systems | USD 2K–15K, seller-reported ([agensi](https://www.agensi.io/learn/how-to-monetize-skill-md-skills-developer-guide-2026)) |
| 3 | Security buyers | Vetting the skills and add-ons agents use | AIR raised USD 50M (Sequoia, Greenoaks) to vet agent skills ([TechCrunch](https://techcrunch.com/2026/09/01/air-raises-50m-to-help-companies-vet-the-skills-and-add-ons-ai-agents-use/)); Upwind is building skill scanners ([OpenTools](https://opentools.ai/news/upwind-series-c-runtime-security-endpoint-agent-scanner-roadmap)); at least two dozen agent-security vendors ([TechCrunch](https://techcrunch.com/2026/09/29/reco-raises-55m-as-ai-agent-security-startups-crowd-the-market/)) |
| 4 | Teams that author skills | Evals, reviews and a registry | Tessl: free tier, Team USD 100 per month, credits for evals ([Tessl pricing](https://tessl.io/pricing)) |
| 5 | Individuals | Skill packs | USD 99 for 20 skills; one seller reports USD 5K in 50 days, self-reported ([ryandoser.com](https://ryandoser.com/claude-ai-side-hustle/)) |
| 6 | Paid marketplaces | A cut of skill sales | Creators keep 70–85% ([agensi](https://www.agensi.io/learn/best-ai-agent-skills-marketplaces-2026), [SkillHQ](https://skillhq.dev/blog/how-to-make-money-selling-claude-code-skills)) |
| 7 | Platform and observability teams | Knowing which skills fire and what they cost | Claude Code exports a `skill_activated` OpenTelemetry event and per-skill token metrics ([monitoring docs](https://code.claude.com/docs/en/monitoring-usage)); Datadog and SquaredUp already sell dashboards on top |

**What the flows say:**

- **The large amounts go to services (flow 1) and to security (flow 3).** Both
  sell to organisations, and both sell an outcome or a risk reduction, not a
  file manager.
- **Skill content (flows 5 and 6) is being commoditised.** A 1,800-like X post
  advertised "970 skills and 273 agents for USD 0" against "USD 19 a skill" on
  paid marketplaces. A 935-upvote r/ClaudeAI thread was titled "Why are all the
  Claude Code skill files I see online completely pointless?". A Chinese post
  (594 likes) bundled thousands of skills into one "skill supermarket". When
  supply is free and mostly poor, the scarce thing is **judgement about which
  skills to keep**, not more skills.
- **Flow 7 is new and nobody owns the cross-agent version.** Usage telemetry
  exists for Claude Code only. Small tools (skillvitals, skill-observability)
  read transcripts, but no product answers "which of our 300 skills ever
  fire, in any agent, and what do they cost".

**Verdict:** the money is in organisations and outcomes. This project's assets
(validation, risk findings, effective-resolution, hygiene, provenance,
snapshots) are the raw material for an outcome. They are not yet sold as one.

## Pass 3 — Invert: sell the outcome, use the tool as the weapon

Change the question from "how do we sell the tool?" to "what result would
someone pay for, which this tool makes cheap for us to deliver?"

### The customer's own words (Reddit and X, 2026-10-30)

These came from reply threads, not from launch posts, so they are unprompted:

- "I run Claude Code, Codex, Grok, Antigravity, OpenCode and Muse side by side
  … across 2 machines, and keeping MCPs, skills and AGENTS.md/CLAUDE.md in sync
  between them is the most annoying part of my setup." (@raiomarco, replying
  to @theo)
- "I'd want a view of what each harness loads into context. Config drift
  between tools is the pain I'd fix first. A marketplace is the less
  interesting part." (@a_Lottes)
- "These should be separate tools. They create too much lock-in." (@GollyJer,
  objecting to a harness adding a skill manager)
- "Hosting and versioning are necessary but they are the easy half, the hard
  half is enforcement, because a skill an agent can quietly skip loading isn't
  an asset, it's a suggestion." (@wernerk_au, replying to @MatthewBerman)
- "You need to do constant testing of those skills to see if they're still
  needed as new models come out." (@revans)
- "What's the best way to achieve a set of shared team skills without a
  dependency on a 3rd party slop skill sharing tool?" (@paulenzCH)
- From a 557-upvote r/ClaudeCode audit of 926 sessions: "a lot of people
  assume the context window is just a hard cap, not a per-turn recurring
  cost."
- From a consultant with two paying clients: "These people don't care to know
  what model you're using, the harness, or even more so the skill you built
  out. They just care about the outcome."

@theo's question, "Should we take on more 'harness configuration' type stuff
in T3 Code? Skill manager, MCP marketplace, global agentmd/claudemd
management", drew 2,013 likes and mostly "yes" replies. That is both a demand
signal and a warning: a larger tool is considering this space.

### Three reframes that follow

1. **The unit is the agent setup, not the skill.** Users describe their pain as
   skills, MCP servers and AGENTS.md/CLAUDE.md drifting across several agents
   and machines. A product limited to skills covers about one third of what
   they asked for.
2. **The product people pay for is a fixed result.** "Your setup costs X
   tokens per turn before you type, these N skills can never fire, these two
   conflict, these three have risky capability, and here is the clean version"
   is a deliverable. A toggle UI is not.
3. **Neutrality is a feature.** Each platform will manage its own agent well
   and the others badly or not at all. A cross-agent tool that keeps files in
   the user's own Git repository answers the lock-in objection directly.

### Revenue shapes this enables

| Shape | What is sold | Why this project can deliver it | Time to first payment |
|---|---|---|---|
| A. Agent Setup Audit | A fixed-price report plus a cleaned configuration for one developer or one team | `doctor --hygiene`, `doctor --explain`, `tokens`, `risk_scan` and the planned listing-budget view already compute most of the report | Weeks |
| B. Skill CI | A GitHub Action that runs validate, hygiene, risk and budget on every pull request to a team's skills repository | All checks exist as stdlib code; free on public repositories, paid on private ones | 1–3 months |
| C. Team setup profiles | A Git-native shared profile of skills, MCP servers and AGENTS.md, translated into each agent's native settings, with a drift report per machine | Builds on Tier 1 item 1 in docs/26; no hosted service is required for the first version | 3–6 months |
| D. Fleet usage and cost | Which skills fire, in which agent, at what token cost, across an organisation | Claude Code OTel events plus transcript parsing; needs new code | 6+ months |
| E. Custom skills for clients | Building and maintaining skills wired to a client's systems | Services; the tool is used to quality-check the work | Weeks |

**Verdict:** A is the fastest money and teaches what B and C should be. B is the
cheapest product to build and the easiest to price. D is the largest
opportunity and the most crowded.

## Pass 4 — Stress test: scenarios and a pre-mortem

Assume it is 2027-10-30 and the plan failed. The most likely reasons, and what
would have prevented each:

| Failure scenario | Likelihood (judgement) | Early signal | Mitigation |
|---|---|---|---|
| The platforms absorbed it. Anthropic, OpenAI or T3 Code shipped cross-agent config and usage views | High for single-agent users; lower across vendors | @theo's poll; Anthropic org provisioning; Claude Code OTel events | Sell to people who run several agents. Services revenue (A, E) survives absorption; a toggle UI does not. |
| Skills faded as a format and got replaced by plugins, packages or something else | Medium | Hermes reads portable "Agent Plugins v1" packages; Claude plugins bundle skills | Treat "skill" as one artifact type among skills, MCP config, AGENTS.md, subagents and plugins. The audit sells the outcome, not the format. |
| Security vendors with USD 50M crushed the trust angle | High, if competing on scanning | AIR, Upwind, Snyk, Aikido, Tessl all scan | Do not sell scanning. Report risk findings as evidence inside the audit, and integrate external scanners as advisory sources (already proposed in docs/26 item 8b). A larger vendor could become an acquirer or partner. |
| Nobody paid for the audit | Medium | Fewer than 3 paid audits after 50 conversations | Kill criterion below. Fall back to custom-skill services (E), which have clearer, though seller-reported, demand. |
| A copycat cloned the free tool | Certain; MIT allows it | Forks | Expected and acceptable. The moat is reports, reputation and customer relationships, not code. |
| The founder spread across five products and finished none | High for a solo maintainer | More than one product line in progress at once | One shape at a time, in order, with a written kill date for each. |
| Unmaintained free surface caused a trust incident | Medium | A security report against a feature nobody uses | The repository's existing gates and hostile self-review continue to apply. Every paid output is local evidence, not a safety verdict. |

**Two scenarios that are better than expected:**

- **The audit becomes the distribution channel.** Every audit can end in a
  short public write-up with the client's permission: "This team's agents spent
  N tokens per turn on skills that never fired." The 926-session audit got 557
  upvotes and the "your setup wastes 75% of tokens" format circulates widely on
  X. Audits create the content that brings the next audits.
- **Chinese-language users adopt it.** Chinese posts on X recommend skills
  managers repeatedly. One user scanned 36 tool directories and found 1,887
  skills, with one skill in seven places. The category leader and CC Switch are
  both Chinese projects. A zh-CN interface costs little; it would need a
  maintainer decision, because the UI currently declares `lang="en"` on purpose
  (@docs/08-web-ui.md).

**Verdict:** the plan survives if it sells outcomes to multi-agent users and
teams, measures demand before building, and does not compete with funded
security vendors on scanning.

## Pass 5 — The decision, the numbers and the kill criteria

### Recommendation

1. **Start with the Agent Setup Audit (shape A).** A fixed-scope, fixed-price
   productized service, delivered with this tool.
2. **Publish a data report to bring buyers in.** Run this project's own
   validation, hygiene and risk checks over the most-installed public skills on
   skills.sh. Publish the result: how many are malformed, oversized, duplicated,
   risky, or never likely to activate. The 935-upvote "most skills are
   pointless" thread shows the audience exists. The report uses only public
   data and does not name a skill as malicious; findings are advisory, as the
   repository already requires.
3. **Build Skill CI (shape B) only after three paid audits** show which checks
   buyers actually care about.
4. **Build team setup profiles (shape C) only after teams ask twice** for the
   same shared-profile workflow during audits.
5. **Leave fleet analytics (shape D) and any marketplace for later.** They are
   the most crowded and the most expensive to build.

### Prices to test

These are starting prices to test with real buyers. Nobody has validated them.

| Offer | Starting price to test | Reference point |
|---|---|---|
| Solo setup audit (one developer, up to 3 agents) | USD 149–299 | Below a day of contractor time; above an impulse purchase |
| Team setup audit (up to 15 developers) | USD 1,500–3,500 | Well below the USD 9.5K–235K Claude rollout programmes |
| Skill CI, private repositories | USD 49–99 per organisation per month | Tessl Team is USD 100 per month |
| Team setup profiles | USD 8–15 per active developer per month | Lower than docs/14's Team range, because platforms now cover part of it |
| Custom skill build | USD 2K–8K per skill, plus a maintenance retainer | Seller-reported USD 2K–15K range |

### What success would look like

Targets, not forecasts:

- **30 days:** 50 conversations with people who run two or more agents, 3 paid
  audits, and the public skills report published.
- **90 days:** 10 paid audits, and one recurring offer (Skill CI or a
  maintenance retainer) with 3 paying organisations.
- **12 months:** about USD 5K–10K a month, split between services and recurring
  revenue. Ten team audits a month at USD 2,000 is USD 20K; five is USD 10K.
  Twenty organisations on Skill CI at USD 79 is USD 1,580 a month.

The arithmetic shows a pattern. **Services carry the first year; recurring
product revenue catches up only if the audits keep revealing the same needs.**

### Kill and pivot criteria

| Checkpoint | If this is true | Then |
|---|---|---|
| Day 30 | Fewer than 3 paid audits after 50 qualified conversations | Stop the audit offer. Switch to custom-skill services (shape E) for agencies, which have the clearest demand signal. |
| Day 90 | Audits sell but nobody asks for anything repeatable | Remain a services business and use the tool internally. Do not build a hosted product. |
| Day 90 | Two or more teams ask for the same shared profile or CI check | Build that one feature, and only that one. |
| Any time | A platform ships cross-agent configuration with drift views | Move the free tool toward evidence for the other vendors' agents; keep services. |

### What not to do

- **Do not build another marketplace.** At least eight exist, the largest is
  free, and content is commoditised.
- **Do not sell skill packs as the main business.** Free supply already
  exceeds demand.
- **Do not paywall local features in the MIT tool.** It invites a fork and
  costs trust.
- **Do not compete on security scanning.** Integrate scanners as advisory
  sources instead.
- **Do not start shapes C or D before A has paying customers.**

## Decisions this needs from the maintainer

**[?]**

| ID | Question | Why it matters |
|---|---|---|
| MON-Q1 | Is a services-first year acceptable, or must revenue be a product from day one? | It decides between shape A and shape B as the first move. |
| MON-Q2 | May the project's scope widen from skills to MCP configuration and AGENTS.md/CLAUDE.md? | Users name all three; it touches the scope model and needs an ADR before code. |
| MON-Q3 | Publish a public report on the most-installed skills? | Good for distribution, but it needs careful wording so advisory findings are not read as accusations. |
| MON-Q4 | Add a zh-CN interface? | Strong demand signal; reverses the current `lang="en"` decision. |
| MON-Q5 | Which docs/14 Pro and Team assumptions stay? | This doc argues the Pro tier should wait. |

## Method and limits

**[NOTE]** Research for this doc used agent-reach: X through the OpenCLI
`twitter` adapter on the maintainer's logged-in session (12 searches, 475
unique tweets, plus full reply threads under @theo's, @MatthewBerman's and
@gregisenberg's posts), and Reddit through `opencli browser` on old.reddit.com
(16 subreddit searches, 14 threads read in full). Web results came from
WebSearch and WebFetch. Raw files are in `/tmp/sm-research/m/` and are not
committed.

**Limits.**

- One X query (`"claude skills" money OR revenue OR "$"`) matched mostly
  financial news and was discarded as noise.
- Reddit's own search ranks loosely, so subreddit coverage is broad rather than
  complete.
- Every marketplace and seller earnings figure is self-reported by a party
  that profits from it.
- Likelihoods in Pass 4 are judgement, not measurement.
- No buyer has been interviewed. The prices above exist to be tested, not
  trusted.

## Sources

- [Provision and manage skills for your organization](https://support.claude.com/en/articles/13119606-provision-and-manage-skills-for-your-organization)
- [Claude Code managed settings](https://code.claude.com/docs/en/managed-settings)
- [Claude Code monitoring and the skill_activated event](https://code.claude.com/docs/en/monitoring-usage)
- [Tessl pricing](https://tessl.io/pricing) and [Skills on Tessl](https://tessl.io/blog/skills-are-software-and-they-need-a-lifecycle-introducing-skills-on-tessl)
- [AIR raises USD 50M (TechCrunch)](https://techcrunch.com/2026/09/01/air-raises-50m-to-help-companies-vet-the-skills-and-add-ons-ai-agents-use/)
- [Reco raises USD 55M as agent security crowds (TechCrunch)](https://techcrunch.com/2026/09/29/reco-raises-55m-as-ai-agent-security-startups-crowd-the-market/)
- [Upwind and agent scanners (OpenTools)](https://opentools.ai/news/upwind-series-c-runtime-security-endpoint-agent-scanner-roadmap)
- [Claude for Enterprise rollout package (AWS Marketplace)](https://aws.amazon.com/marketplace/pp/prodview-nfcixwrexqdv2)
- [Claude training cost guide](https://www.claudetraining.com/blog/claude-training-cost)
- [Monetize SKILL.md skills (agensi)](https://www.agensi.io/learn/how-to-monetize-skill-md-skills-developer-guide-2026)
- [AI agent skills marketplaces compared (agensi)](https://www.agensi.io/learn/best-ai-agent-skills-marketplaces-2026)
- [Selling Claude Code skills (SkillHQ)](https://skillhq.dev/blog/how-to-make-money-selling-claude-code-skills)
- [Monetize Claude Code skills (Agent37)](https://www.agent37.com/blog/monetize-claude-code-skills)
- [Claude skills side hustle (ryandoser.com)](https://ryandoser.com/claude-ai-side-hustle/)
- [skills.sh install rankings (LinklyAI)](https://github.com/LinklyAI/best-skills)
- X: [@theo on harness configuration](https://x.com/i/status/2115700736084648177), [@MatthewBerman on hosting and versioning skills](https://x.com/i/status/2062701931181809745), [@gregisenberg on charging for the work](https://x.com/i/status/2115172540238979474), [@bozhou_ai on 1,887 skills across 36 directories](https://x.com/i/status/2107130142543994934), [@_philschmid on free versus paid skills](https://x.com/i/status/2114773524787187804)
- Reddit: [most skill files are pointless](https://www.reddit.com/r/ClaudeAI/comments/1uhed8x/), [audit of 926 sessions](https://www.reddit.com/r/ClaudeCode/comments/1sd8t5u/), [I build AI agents for a living](https://www.reddit.com/r/AI_Agents/comments/1ojyu8p/), [5 lessons from an AI consulting company](https://www.reddit.com/r/AI_Agents/comments/1u87svs/), [silent AI failures in agency workflows](https://www.reddit.com/r/Entrepreneur/comments/1xbr8jv/), [Cursor's context breakdown](https://www.reddit.com/r/cursor/comments/1t6z9ft/)
