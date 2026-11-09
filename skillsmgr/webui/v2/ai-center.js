/* AI assist pages (docs/39). Bring your own key; every model answer is shown as
 * text and labelled as an estimate. Nothing here writes a skill except the
 * explicit "Use this description" action, which goes through the ordinary
 * PATCH edit route (snapshot + Undo in Recovery). */
(function () {
  const api = window.SkillManagerDomain.api;
  const post = (url, body) => api(url, { method: "POST", body: JSON.stringify(body || {}) });
  const pct = (v) => (v == null ? "–" : Math.round(v * 100) + "%");
  const HANDOFF = "skillsmgr-ai-target";

  window.SkillsV2AiCenter = {
    props: { page: String, records: { type: Array, default: () => [] }, scopes: { type: Array, default: () => [] }, target: Object },
    emits: ["changed"],
    data() {
      return {
        settings: null, form: { provider: "", model: "", base_url: "", api_key: "", max_run_tokens: 300000, max_day_tokens: 2000000 },
        busy: false, error: "", note: "", connection: null,
        scope: "", mode: "generate", chosen: [], filter: "", perSkill: 3, nearMisses: 2, promptText: "", repeats: 1,
        estimate: null, result: null,
        portName: "", portTarget: "codex", ported: null,
        question: "", askScope: "all", asked: null,
        evalName: "", evalMax: 10, evalResult: null, evalEstimate: null,
        savedCount: 0, savedPrompts: [], savedNote: "", savedError: "", savedBusy: false, savedRequest: 0,
        pastRuns: [], pastRun: null, historyError: "", historyBusy: false, historyRequest: 0,
        budgetChars: "", budgetMax: 5, budget: null, budgetEstimate: null, appliedNames: [],
        overlapLimit: 6, pairA: "", pairB: "", pairs: [], overlap: null, overlapEstimate: null,
        improveName: "", candidates: 2, improve: null, improveEstimate: null, applied: "",
      };
    },
    computed: {
      provider() { return ((this.settings && this.settings.providers) || []).find((p) => p.id === this.form.provider) || null; },
      configured() { return !!(this.settings && this.settings.configured); },
      agentScopes() {
        const counts = new Map();
        for (const r of this.records) if (!r.disabled) counts.set(r.scope, (counts.get(r.scope) || 0) + 1);
        return this.scopes.filter((s) => s.id !== "all" && counts.get(s.id)).map((s) => ({ id: s.id, label: s.id === "global" ? "Your library" : s.label || s.id, count: counts.get(s.id) }));
      },
      scopeSkills() {
        const seen = new Set(); const out = [];
        for (const r of this.records) if (r.scope === this.scope && !r.disabled && !seen.has(r.name)) { seen.add(r.name); out.push(r.name); }
        return out.sort();
      },
      pickable() { const q = this.filter.trim().toLowerCase(); return this.scopeSkills.filter((n) => !q || n.includes(q)); },
      parsedPrompts() {
        return this.promptText.split("\n").map((l) => l.trim()).filter(Boolean).map((line) => {
          const m = line.match(/^(.*?)\s*=>\s*([a-z0-9-]+|none)\s*$/);
          return m ? { text: m[1], expected: m[2] === "none" ? null : m[2] } : { text: line, expected: null };
        });
      },
      troubled() { return ((this.result && this.result.skills) || []).filter((s) => s.verdict !== "fires"); },
      usage() { return (this.settings && this.settings.usage) || null; },
    },
    watch: {
      page: { immediate: true, handler() { this.error = ""; this.note = ""; this.load(); this.takeHandoff(); this.loadSaved(); } },
      scope() { this.ported = null; this.loadSaved(); this.budget = null; this.budgetEstimate = null; this.pairs = []; this.overlap = null; this.overlapEstimate = null; this.chosen = []; this.estimate = null; this.result = null; this.improve = null; this.improveEstimate = null; },
      agentScopes: { immediate: true, handler(list) { if (!this.scope && list.length) this.scope = (list.find((s) => s.id === "claude-code") || list[0]).id; } },
    },
    methods: {
      pct,
      fmt(n) { return n == null ? "–" : Number(n).toLocaleString(); },
      relationTone(r) { return { "same-purpose": "bad", overlapping: "warn", uncertain: "note", distinct: "ok" }[r] || "off"; },
      relationLabel(r) { return { "same-purpose": "Same purpose", overlapping: "Overlapping", uncertain: "Uncertain: depends on order", distinct: "Distinct", unknown: "No clear answer" }[r] || r; },
      actionLabel(a) { return { merge: "Merge them", "narrow-descriptions": "Sharpen both descriptions", "keep-both": "Keep both as they are", review: "Answers disagreed: review yourself" }[a] || a; },
      budgetBody(estimate) { const b = { scope: this.scope, max_skills: Number(this.budgetMax), estimate }; if (String(this.budgetChars).trim()) b.budget_chars = Number(this.budgetChars); return b; },
      async estimateBudget() { this.budget = null; this.appliedNames = []; this.budgetEstimate = await this.guard(() => post("/api/ai/fit-budget", this.budgetBody(true))); },
      async runBudget() { const r = await this.guard(() => post("/api/ai/fit-budget", this.budgetBody(false))); if (r) { this.budget = r; this.budgetEstimate = null; this.load(); } },
      async applyShort(p) {
        if (!confirm("Replace the description of " + p.name + " in " + this.budget.scope + " with the shorter version? A snapshot of the current file is kept.")) return;
        const ok = await this.guard(() => api("/api/skills/" + encodeURIComponent(p.name) + "?scope=" + encodeURIComponent(this.budget.scope), { method: "PATCH", body: JSON.stringify({ description: p.proposed }) }));
        if (ok) { this.appliedNames.push(p.name); this.note = "Saved " + p.name + ". The previous version is in Recovery → history."; this.$emit("changed"); }
      },
      async port(estimate) { const r = await this.guard(() => post("/api/ai/porting-notes", { scope: this.scope, name: this.portName, target: this.portTarget, estimate })); if (r) { this.ported = r; if (!estimate) this.load(); } },
      async ask() { const r = await this.guard(() => post("/api/ai/ask", { question: this.question, scope: this.askScope })); if (r) { this.asked = r; this.load(); } },
      skillHref(name) { return "#/skill/" + encodeURIComponent(name); },
      librarySkills() { return [...new Set(this.records.filter((r) => r.scope === "global").map((r) => r.name))].sort(); },
      evalBody(estimate) { return { name: this.evalName, max_cases: Number(this.evalMax), estimate }; },
      async estimateEvals() { this.evalResult = null; this.evalEstimate = await this.guard(() => post("/api/ai/evals", this.evalBody(true))); },
      async runEvals() { const r = await this.guard(() => post("/api/ai/evals", this.evalBody(false))); if (r) { this.evalResult = r; this.evalEstimate = null; this.load(); } },
      evalVerdict(v) { return { helps: ["ok", "The skill helps"], "not-needed": ["warn", "Passes without the skill: it may no longer be needed"], "no-gain": ["warn", "No difference with the skill"], hurts: ["bad", "Worse with the skill"], ungraded: ["off", "No assertions to grade"] }[v] || ["off", v]; },
      addPair() { if (this.pairA && this.pairB && this.pairA !== this.pairB && this.pairs.length < 12) { this.pairs.push([this.pairA, this.pairB]); this.pairA = this.pairB = ""; } },
      overlapBody(estimate) { return { scope: this.scope, max_pairs: Number(this.overlapLimit), pairs: this.pairs, estimate }; },
      async estimateOverlap() { this.overlap = null; this.overlapEstimate = await this.guard(() => post("/api/ai/overlap-judge", this.overlapBody(true))); },
      async runOverlap() { const r = await this.guard(() => post("/api/ai/overlap-judge", this.overlapBody(false))); if (r) { this.overlap = r; this.overlapEstimate = null; this.load(); } },
      verdictTone(v) { return v === "fires" ? "ok" : v === "never-fires" ? "bad" : "warn"; },
      verdictLabel(v) { return { fires: "Fires", "never-fires": "Never fires", unreliable: "Unreliable", unknown: "Unknown" }[v] || v; },
      skillLabel(n) { return n === "(none)" ? "no skill" : n; },
      choiceList(choices) { return Object.entries(choices || {}).sort((a, b) => b[1] - a[1]).map(([k, n]) => this.skillLabel(k) + (n > 1 ? " ×" + n : "")).join(", "); },
      takeHandoff() {
        let t = null;
        try { t = JSON.parse(sessionStorage.getItem(HANDOFF) || "null"); sessionStorage.removeItem(HANDOFF); } catch (e) { t = null; }
        if (!t && this.target && this.page === "ai-improve") t = { scope: this.target.scope, name: this.target.name };
        if (t && t.scope) { this.scope = t.scope; this.$nextTick(() => { if (t.name) this.improveName = t.name; }); }
      },
      handoff(name) { try { sessionStorage.setItem(HANDOFF, JSON.stringify({ scope: this.scope, name })); } catch (e) { /* optional */ } location.hash = "#/tools/ai-improve"; },
      async guard(fn) {
        this.busy = true; this.error = ""; this.note = "";
        try { return await fn(); } catch (e) { this.error = (e && e.message) || String(e); return null; } finally { this.busy = false; }
      },
      async load() {
        const s = await this.guard(() => api("/api/ai/settings"));
        if (!s) return;
        this.settings = s;
        this.form = { provider: s.provider || "", model: s.model || "", base_url: s.base_url || "", api_key: "", max_run_tokens: s.max_run_tokens, max_day_tokens: s.max_day_tokens };
        this.loadRuns();
      },
      pickProvider() {
        const p = this.provider; if (!p) return;
        this.form.base_url = p.default_base_url; this.form.model = (p.suggested_models || [])[0] || "";
      },
      async save() {
        const body = { provider: this.form.provider, model: this.form.model, max_run_tokens: Number(this.form.max_run_tokens), max_day_tokens: Number(this.form.max_day_tokens) };
        if (this.provider && (this.form.base_url || "") !== this.provider.default_base_url) body.base_url = this.form.base_url;
        if (this.form.provider === "custom") body.base_url = this.form.base_url;
        if (this.form.api_key) body.api_key = this.form.api_key;
        const s = await this.guard(() => post("/api/ai/settings", body));
        if (s) { this.settings = s; this.form.api_key = ""; this.note = "Saved."; this.connection = null; }
      },
      async clearKey() { const s = await this.guard(() => post("/api/ai/settings", { clear_key: true })); if (s) { this.settings = s; this.note = "Stored key removed."; } },
      async turnOff() { const s = await this.guard(() => post("/api/ai/settings", { provider: null })); if (s) { this.settings = s; this.load(); this.note = "AI features are off and the stored key is deleted."; } },
      async testConnection() { const r = await this.guard(() => post("/api/ai/test-connection", {})); if (r) { this.connection = r; this.load(); } },
      async loadRuns() {
        const request = ++this.historyRequest;
        this.historyBusy = true; this.historyError = ""; this.pastRun = null;
        try { const r = await api("/api/ai/runs"); if (request === this.historyRequest) this.pastRuns = r.runs; }
        catch (e) { if (request === this.historyRequest) this.historyError = e.message || String(e); }
        finally { if (request === this.historyRequest) this.historyBusy = false; }
      },
      async openRun(id) {
        const request = ++this.historyRequest;
        this.historyBusy = true; this.historyError = ""; this.pastRun = null;
        try { const r = await api("/api/ai/runs/" + encodeURIComponent(id)); if (request === this.historyRequest) this.pastRun = r; }
        catch (e) { if (request === this.historyRequest) this.historyError = e.message || String(e); }
        finally { if (request === this.historyRequest) this.historyBusy = false; }
      },
      runText(run) { return JSON.stringify(run, null, 2); },
      async loadSaved() {
        const request = ++this.savedRequest; const scope = this.scope;
        this.savedPrompts = []; this.savedCount = 0; this.savedNote = ""; this.savedError = "";
        this.savedBusy = false;
        if (!scope) return;
        this.savedBusy = true;
        try { const r = await api("/api/ai/prompt-sets/" + encodeURIComponent(scope)); if (request === this.savedRequest) { this.savedPrompts = r.prompts; this.savedCount = r.prompts.length; } }
        catch (e) { if (request === this.savedRequest) this.savedError = e.message || String(e); }
        finally { if (request === this.savedRequest) this.savedBusy = false; }
      },
      async removePrompt(prompt) {
        if (this.savedBusy || !confirm("Remove this saved regression prompt?")) return;
        const scope = this.scope; const previous = this.savedPrompts;
        const request = ++this.savedRequest;
        let failure = "";
        this.savedBusy = true; this.savedError = ""; this.savedNote = "";
        const prompts = previous.filter((p) => p.text !== prompt.text || p.expected !== prompt.expected);
        try {
          const r = await post("/api/ai/prompt-sets", { scope, prompts, replace: true, expected_prompts: previous });
          if (request === this.savedRequest) { this.savedPrompts = r.prompts; this.savedCount = r.prompts.length; this.estimate = null; this.savedNote = "Prompt removed."; }
        } catch (e) {
          failure = e.message || String(e);
        } finally {
          if (request === this.savedRequest && failure) { await this.loadSaved(); if (scope === this.scope) this.savedError = failure; }
          else if (request === this.savedRequest) this.savedBusy = false;
          else if (scope === this.scope) await this.loadSaved();
        }
      },
      async saveTests() {
        if (this.savedBusy) return;
        ++this.savedRequest;
        const prompts = this.result.prompts.map((p) => ({ text: p.text, expected: p.expected }));
        const r = await this.guard(() => post("/api/ai/prompt-sets", { scope: this.result.scope, prompts }));
        if (r && r.scope === this.scope) { this.savedPrompts = r.prompts; this.savedCount = r.prompts.length; this.savedNote = "Saved. " + r.prompts.length + " regression prompts for this agent; re-run them after edits or a model change."; }
      },
      triggerBody(estimate) {
        const body = { scope: this.scope, repeats: Number(this.repeats), estimate };
        if (this.mode === "saved") body.saved = true;
        else if (this.mode === "generate") Object.assign(body, { generate_for: this.chosen, per_skill: Number(this.perSkill), near_misses: Number(this.nearMisses) });
        else body.prompts = this.parsedPrompts;
        return body;
      },
      async estimateTrigger() { this.result = null; this.estimate = await this.guard(() => post("/api/ai/trigger-test", this.triggerBody(true))); },
      async runTrigger() { const r = await this.guard(() => post("/api/ai/trigger-test", this.triggerBody(false))); if (r) { this.result = r; this.estimate = null; this.load(); } },
      improveBody(estimate) { return { scope: this.scope, name: this.improveName, candidates: Number(this.candidates), repeats: Number(this.repeats), estimate }; },
      async estimateImprove() { this.improve = null; this.applied = ""; this.improveEstimate = await this.guard(() => post("/api/ai/improve-description", this.improveBody(true))); },
      async runImprove() { const r = await this.guard(() => post("/api/ai/improve-description", this.improveBody(false))); if (r) { this.improve = r; this.improveEstimate = null; this.load(); } },
      async applyCandidate(c) {
        if (!confirm("Replace the description of " + this.improve.name + " in " + this.improve.scope + "? A snapshot of the current file is kept and you can restore it from Recovery.")) return;
        const ok = await this.guard(() => api("/api/skills/" + encodeURIComponent(this.improve.name) + "?scope=" + encodeURIComponent(this.improve.scope), { method: "PATCH", body: JSON.stringify({ description: c.description }) }));
        if (ok) { this.applied = c.description; this.note = "Description saved. The previous version is in Recovery → history."; this.$emit("changed"); }
      },
    },
    template: `
    <div class="ai-center">
      <p v-if="error" class="v2-tool-error" role="alert">{{ error }}</p>
      <p v-if="note" class="tp-fine" role="status">{{ note }}</p>
      <p v-if="busy" class="v2-tool-status" role="status"><span class="v2-dot" aria-hidden="true"></span>Working… model calls can take a minute.</p>

      <template v-if="page==='ai-settings'">
        <h1 class="h1" id="h1" tabindex="-1">AI settings</h1>
        <p class="lede">Connect your own model to test and improve how agents pick your skills. Off until you choose a provider.</p>
        <section class="card tp-panel" aria-labelledby="ai-conn-h">
          <header class="tp-panel-h"><h2 id="ai-conn-h">Model connection</h2>
            <span :class="['pill', configured ? 'ok' : 'off']">{{ configured ? 'Connected' : 'Off' }}</span></header>
          <div class="tp-set" v-if="settings">
            <div class="tp-set-row"><label for="ai-prov"><b>Provider</b><small>Anthropic, any OpenAI-compatible service, or a model running on this computer.</small></label>
              <select id="ai-prov" class="field" v-model="form.provider" @change="pickProvider()"><option value="">Choose…</option><option v-for="p in settings.providers" :key="p.id" :value="p.id">{{ p.label }}</option></select></div>
            <div class="tp-set-row" v-if="form.provider"><label for="ai-model"><b>Model</b><small>The exact model id your provider uses.</small></label>
              <span><input id="ai-model" class="field" v-model.trim="form.model" list="ai-models" autocomplete="off" spellcheck="false"><datalist id="ai-models"><option v-for="m in (provider && provider.suggested_models) || []" :key="m" :value="m"></option></datalist></span></div>
            <div class="tp-set-row" v-if="form.provider"><label for="ai-base"><b>Endpoint</b><small>Must be https, or http on this computer only.</small></label>
              <input id="ai-base" class="field tp-mono" v-model.trim="form.base_url" autocomplete="off" spellcheck="false"></div>
            <div class="tp-set-row" v-if="form.provider && (!provider || provider.needs_key || form.provider==='custom')"><label for="ai-key"><b>API key</b>
                <small v-if="settings.key_source==='settings' && settings.provider===form.provider">A key ending {{ settings.key_hint }} is stored. Leave blank to keep it.</small>
                <small v-else-if="settings.key_source && settings.key_source.startsWith('env:') && settings.provider===form.provider">Using {{ settings.key_source.slice(4) }} from the environment; it takes precedence.</small>
                <small v-else-if="provider && provider.env.length">Or set {{ provider.env.join(' / ') }} before starting the app, and leave this blank.</small></label>
              <input id="ai-key" class="field tp-mono" type="password" v-model="form.api_key" autocomplete="off" spellcheck="false" placeholder="Paste key"></div>
            <div class="tp-set-row"><label for="ai-run"><b>Cap per run</b><small>Input tokens one test may send. A run that would exceed it is refused before anything is sent.</small></label>
              <input id="ai-run" class="field num" type="number" min="1000" step="1000" v-model="form.max_run_tokens"></div>
            <div class="tp-set-row"><label for="ai-day"><b>Cap per day</b><small>Today so far: {{ fmt(usage && usage.input_tokens) }} input tokens in {{ fmt(usage && usage.calls) }} calls.</small></label>
              <input id="ai-day" class="field num" type="number" min="1000" step="1000" v-model="form.max_day_tokens"></div>
          </div>
          <div class="tp-acts"><button class="btn btn-ink" :disabled="busy || !form.provider || !form.model" @click="save()">Save</button>
            <button class="btn btn-line" :disabled="busy || !configured" @click="testConnection()">Test connection</button>
            <button class="btn btn-line" v-if="settings && settings.key_source==='settings'" :disabled="busy" @click="clearKey()">Remove stored key</button>
            <button class="btn btn-line" v-if="settings && settings.provider" :disabled="busy" @click="turnOff()">Turn AI off</button></div>
          <p v-if="connection" :class="['tp-fine']" role="status">{{ connection.ok ? 'Connection works' : 'The model answered, but not with the expected JSON; try a stronger model' }} · {{ connection.run.model }} · {{ fmt(connection.run.input_tokens) }} tokens in.</p>
        </section>
        <section class="card tp-panel" aria-labelledby="ai-priv-h">
          <h2 id="ai-priv-h">What leaves this computer</h2>
          <ul class="tp-fine ai-list">
            <li>Nothing, until you run a test. Each test shows exactly what it will send and its token estimate first.</li>
            <li>The trigger test sends skill names, descriptions and test prompts. Improving a description also sends the start of that one skill's body.</li>
            <li>A local provider (Ollama, LM Studio) keeps everything on this computer.</li>
            <li>{{ settings ? settings.storage : '' }} It is never shown again, logged or exported.</li>
            <li>This app has no login: it relies on listening only on this computer. Any program you run can reach it, and so could spend this key up to your caps.</li>
          </ul>
        </section>
      </template>

      <template v-else-if="!configured && settings">
        <h1 class="h1" id="h1" tabindex="-1">{{ {'ai-port':'Porting notes','ai-ask':'Ask your library','ai-trigger':'Trigger test','ai-improve':'Improve a description','ai-overlap':'Overlap check','ai-budget':'Fit the listing budget','ai-evals':'Does it help?'}[page] || 'AI assist' }}</h1>
        <section class="card tp-panel"><p>AI features are off. Connect a model first; nothing is sent until you run a test.</p>
          <div class="tp-acts"><a class="btn btn-ink" href="#/tools/ai-settings">Open AI settings</a></div></section>
      </template>

      <template v-else-if="page==='ai-trigger'">
        <h1 class="h1" id="h1" tabindex="-1">Trigger test</h1>
        <p class="lede">Will an agent actually pick your skills? Your model plays the agent, reading the same list of names and descriptions it sees, with all your other skills as competition.</p>
        <section class="card tp-panel" aria-labelledby="ai-tt-h">
          <h2 id="ai-tt-h">Set up</h2>
          <div class="tp-set">
            <div class="tp-set-row"><label for="ai-scope"><b>Agent</b><small>Whose skill list to test.</small></label>
              <select id="ai-scope" class="field" v-model="scope"><option v-for="s in agentScopes" :key="s.id" :value="s.id">{{ s.label }} ({{ s.count }})</option></select></div>
            <div class="tp-set-row"><span><b>Test prompts</b><small>Let the model write realistic requests, or write your own.</small></span>
              <div class="seg" role="group" aria-label="Prompt source"><button type="button" :aria-pressed="mode==='generate'" @click="mode='generate'">Generate</button><button type="button" :aria-pressed="mode==='manual'" @click="mode='manual'">Write my own</button><button type="button" :aria-pressed="mode==='saved'" :disabled="!savedCount" @click="mode='saved'">Saved tests ({{ savedCount }})</button></div></div>
            <div class="tp-set-row"><label for="ai-rep"><b>Repeats</b><small>Answers vary; repeating shows how stable a choice is. The skill order is shuffled each time.</small></label>
              <select id="ai-rep" class="field" v-model.number="repeats"><option v-for="n in 5" :key="n" :value="n">{{ n }}</option></select></div>
          </div>
          <template v-if="mode==='generate'">
            <div class="ai-pick">
              <input class="field" v-model="filter" placeholder="Filter skills" aria-label="Filter skills">
              <p class="tp-fine">{{ chosen.length }} of at most 40 chosen. <button class="btn btn-line btn-sm" type="button" @click="chosen = pickable.slice(0, 40)">Choose shown</button> <button class="btn btn-line btn-sm" type="button" @click="chosen = []">Clear</button></p>
              <div class="ai-checks"><label v-for="n in pickable" :key="n"><input type="checkbox" :value="n" v-model="chosen" :disabled="!chosen.includes(n) && chosen.length>=40"> <span class="tp-mono">{{ n }}</span></label></div>
            </div>
            <div class="tp-set">
              <div class="tp-set-row"><label for="ai-per"><b>Prompts per skill</b></label><select id="ai-per" class="field" v-model.number="perSkill"><option v-for="n in 6" :key="n" :value="n">{{ n }}</option></select></div>
              <div class="tp-set-row"><label for="ai-nm"><b>Near-miss prompts</b><small>Requests that look related but should not load any chosen skill.</small></label><select id="ai-nm" class="field" v-model.number="nearMisses"><option v-for="n in [0,1,2,3,4,5,6,7,8,9,10]" :key="n" :value="n">{{ n }}</option></select></div>
            </div>
          </template>
          <p v-else-if="mode==='saved'" class="tp-fine">Re-runs the {{ savedCount }} saved prompts and compares each skill with the last saved-test run, so a description edit or a model change that breaks triggering shows up.</p>
          <template v-else>
            <label for="ai-prompts" class="tp-fine">One request per line. End a line with <code>=&gt; skill-name</code> for the skill it should load, or <code>=&gt; none</code>.</label>
            <textarea id="ai-prompts" class="field ai-text" v-model="promptText" rows="8" placeholder="fill in this tax form PDF => pdf-forms"></textarea>
          </template>
          <details class="tp-more">
            <summary>Saved regression prompts ({{ savedCount }})</summary>
            <p v-if="!savedPrompts.length && !savedBusy" class="tp-empty">No saved prompts for this agent.</p>
            <ul class="tp-rows"><li v-for="(p,i) in savedPrompts" :key="JSON.stringify([p.text,p.expected])" class="v2-tool-row">
              <span class="tp-row-main"><strong>{{ p.text }}</strong><small>Should load: {{ p.expected || 'none' }}</small></span>
              <button class="btn btn-line btn-sm" :disabled="busy || savedBusy" :aria-label="'Remove saved prompt ' + (i+1)" @click="removePrompt(p)">Remove</button>
            </li></ul>
            <button class="btn btn-line btn-sm" :disabled="busy || savedBusy" @click="loadSaved()">Refresh saved prompts</button>
          </details>
          <p v-if="savedBusy" class="tp-fine" role="status">Loading saved prompts…</p>
          <p v-if="savedError" class="v2-tool-error" role="alert">{{ savedError }}</p>
          <p v-if="savedNote" class="tp-fine" role="status">{{ savedNote }}</p>
          <div class="tp-acts"><button class="btn btn-line" :disabled="busy || !scope || (mode==='generate' ? !chosen.length : mode==='saved' ? !savedCount : !parsedPrompts.length)" @click="estimateTrigger()">Check what will be sent</button></div>
          <div v-if="estimate" class="ai-confirm" role="region" aria-label="Before sending">
            <p v-for="(line,i) in estimate.egress" :key="i" class="tp-fine">{{ line }}</p>
            <p class="tp-fine">At most about {{ fmt(estimate.run.estimated_input_tokens) }} tokens to {{ estimate.run.model }}<span v-if="estimate.over_cap.length">; {{ estimate.over_cap.length }} descriptions are longer than the agent's cap and are cut, as the agent would.</span></p>
            <div class="tp-acts"><button class="btn btn-ink" :disabled="busy" @click="runTrigger()">Send and run test</button><button class="btn btn-line" :disabled="busy" @click="estimate=null">Cancel</button></div>
          </div>
        </section>

        <section v-if="result" class="card tp-panel" aria-labelledby="ai-res-h" aria-live="polite">
          <header class="tp-panel-h"><div><h2 id="ai-res-h">Result</h2><p>{{ result.listed }} skills listed · {{ result.prompts.length }} prompts × {{ result.repeats }} · {{ result.run.model }}</p></div>
            <span :class="['pill', troubled.length ? 'warn' : 'ok']">{{ troubled.length ? troubled.length + ' need work' : 'All fire' }}</span></header>
          <div class="ai-stats"><div><b class="num">{{ pct(result.recall) }}</b><small>of prompts picked the right skill</small></div>
            <div v-if="result.false_trigger_rate!=null"><b class="num">{{ pct(result.false_trigger_rate) }}</b><small>of near-misses loaded a skill anyway</small></div>
            <div><b class="num">{{ fmt(result.run.input_tokens) }}</b><small>input tokens used</small></div></div>
          <div v-if="result.prompt_source==='saved'" class="ai-confirm">
            <p v-if="!result.compared_with" class="tp-fine">First saved-test run for this agent; the next one will be compared with it.</p>
            <p v-else-if="!result.changes.length" class="tp-fine">No skill changed since the last saved-test run.</p>
            <p v-for="c in result.changes" :key="c.name" class="tp-fine"><span :class="['pill', c.regressed ? 'bad' : 'ok']">{{ c.regressed ? 'Worse' : 'Better' }}</span> <span class="tp-mono">{{ c.name }}</span>: {{ pct(c.before) }} → {{ pct(c.after) }}</p>
          </div>
          <ul class="tp-rows">
            <li v-for="s in result.skills" :key="s.name" class="v2-tool-row">
              <span class="tp-row-main"><strong class="tp-mono">{{ s.name }}</strong><small>Won {{ pct(s.hit_rate) }} of its {{ s.prompts }} prompts<span v-if="s.lost_to.length">; lost to {{ s.lost_to.map(l => skillLabel(l.name) + ' ×' + l.count).join(', ') }}</span></small></span>
              <span class="ai-row-acts"><span :class="['pill', verdictTone(s.verdict)]">{{ verdictLabel(s.verdict) }}</span><button v-if="s.verdict!=='fires'" class="btn btn-line btn-sm" @click="handoff(s.name)">Improve</button></span>
            </li>
          </ul>
          <details class="tp-more"><summary>Every prompt and what was chosen</summary>
            <table class="ai-table"><thead><tr><th>Prompt</th><th>Should load</th><th>Chosen</th></tr></thead>
              <tbody><tr v-for="p in result.prompts" :key="p.id"><td>{{ p.text }}</td><td class="tp-mono">{{ p.expected || 'none' }}</td><td class="tp-mono">{{ choiceList(p.choices) }}</td></tr></tbody></table></details>
          <div class="tp-acts" v-if="result.prompt_source!=='saved'"><button class="btn btn-line btn-sm" :disabled="busy || savedBusy" @click="saveTests()">Save these prompts as regression tests</button></div>
          <p class="tp-fine">{{ result.run.advisory }} Invalid answers: {{ result.invalid_answers }}.</p>
        </section>
      </template>

      <template v-else-if="page==='ai-port'">
        <h1 class="h1" id="h1" tabindex="-1">Porting notes</h1>
        <p class="lede">Before copying a skill to another agent: which of its settings that agent does not document, and which parts of its text assume a particular agent. The facts are found without AI; your model only explains them.</p>
        <section class="card tp-panel" aria-labelledby="ai-po-h">
          <h2 id="ai-po-h">Choose a skill and a target</h2>
          <div class="tp-set">
            <div class="tp-set-row"><label for="ai-scope5"><b>From</b></label><select id="ai-scope5" class="field" v-model="scope"><option v-for="s in agentScopes" :key="s.id" :value="s.id">{{ s.label }} ({{ s.count }})</option></select></div>
            <div class="tp-set-row"><label for="ai-pon"><b>Skill</b></label><select id="ai-pon" class="field" v-model="portName"><option value="">Choose…</option><option v-for="n in scopeSkills" :key="n" :value="n">{{ n }}</option></select></div>
            <div class="tp-set-row"><label for="ai-pot"><b>Target agent</b><small>Agents whose documented frontmatter keys are recorded.</small></label><select id="ai-pot" class="field" v-model="portTarget"><option v-for="c in (settings && settings.consumers) || []" :key="c.id" :value="c.id">{{ c.label }}</option></select></div>
          </div>
          <div class="tp-acts"><button class="btn btn-line" :disabled="busy || !portName" @click="port(true)">Find the facts</button></div>
        </section>
        <section v-if="ported" class="card tp-panel" aria-labelledby="ai-por-h" aria-live="polite">
          <header class="tp-panel-h"><div><h2 id="ai-por-h">{{ ported.name }} → {{ ported.target_label }}</h2><p v-if="ported.source">Key list from <span class="tp-mono">{{ ported.source }}</span></p></div>
            <span :class="['pill', ported.portable ? 'ok' : 'warn']">{{ ported.portable ? 'Nothing agent-specific found' : ported.facts.length + ' thing(s) to check' }}</span></header>
          <ul v-if="ported.facts.length" class="tp-rows"><li v-for="f in ported.facts" :key="f.id" class="v2-tool-row"><span class="tp-row-main"><strong>{{ f.kind==='frontmatter' ? 'Setting' : 'Text' }}: {{ f.detail }}</strong><small v-if="f.line" class="tp-mono">{{ f.line }}</small>
            <small v-for="n in (ported.notes||[]).filter(n => n.fact===f.id)" :key="n.fact + n.suggestion">{{ n.explanation }} <b>Suggestion:</b> {{ n.suggestion }}</small></span></li></ul>
          <template v-if="!ported.portable && !ported.notes">
            <p v-for="(line,i) in (ported.egress||[])" :key="i" class="tp-fine">{{ line }} About {{ fmt(ported.run.estimated_input_tokens) }} tokens to {{ ported.run.model }}.</p>
            <div class="tp-acts"><button class="btn btn-ink" :disabled="busy" @click="port(false)">Send and explain</button></div>
          </template>
          <p v-if="ported.summary" class="tp-fine">{{ ported.summary }}</p>
          <p v-if="ported.dropped_notes" class="tp-fine">{{ ported.dropped_notes }} note(s) about things not in the facts were dropped.</p>
        </section>
      </template>

      <template v-else-if="page==='ai-ask'">
        <h1 class="h1" id="h1" tabindex="-1">Ask your library</h1>
        <p class="lede">Describe a task in your own words and get the skills that fit it. Every suggested skill is checked against your real library.</p>
        <section class="card tp-panel" aria-labelledby="ai-ask-h">
          <h2 id="ai-ask-h" class="sr-only">Question</h2>
          <form class="tp-stack" @submit.prevent="ask()">
            <label for="ai-q" class="tp-fine">Question</label>
            <input id="ai-q" class="field" v-model="question" maxlength="500" placeholder="Which skill helps me write release notes?" autocomplete="off">
            <div class="tp-set"><div class="tp-set-row"><label for="ai-asks"><b>Search</b></label><select id="ai-asks" class="field" v-model="askScope"><option value="all">All agents</option><option v-for="s in agentScopes" :key="s.id" :value="s.id">{{ s.label }}</option></select></div></div>
            <p class="tp-fine">Sends your question with skill names and the first 300 characters of each description; never skill bodies. At most 300 skills, narrowed by matching words first.</p>
            <div class="tp-acts"><button class="btn btn-ink" type="submit" :disabled="busy || !question.trim()">Ask</button></div>
          </form>
        </section>
        <section v-if="asked" class="card tp-panel" aria-labelledby="ai-ans-h" aria-live="polite">
          <header class="tp-panel-h"><div><h2 id="ai-ans-h">Answer</h2><p>Searched {{ asked.searched }} skills, sent {{ asked.sent }} · {{ asked.run.model }}</p></div></header>
          <p>{{ asked.answer }}</p>
          <p v-if="!asked.matches.length" class="tp-empty">No skill in your library fits.</p>
          <ul class="tp-rows"><li v-for="m in asked.matches" :key="m.name" class="v2-tool-row">
            <span class="tp-row-main"><a class="tp-link tp-mono" :href="skillHref(m.name)">{{ m.name }}</a><small>{{ m.why }}</small><small>{{ m.scopes.join(', ') }}</small></span></li></ul>
          <p v-if="asked.dropped_unknown" class="tp-fine">{{ asked.dropped_unknown }} suggestion(s) were dropped because no such skill exists.</p>
        </section>
      </template>

      <template v-else-if="page==='ai-evals'">
        <h1 class="h1" id="h1" tabindex="-1">Does it help?</h1>
        <p class="lede">Runs a skill's own <code>evals/evals.json</code> cases through your model twice, with and without the skill, and grades both with the cases' own assertions. Results are saved in the skill's eval workspace.</p>
        <section class="card tp-panel" aria-labelledby="ai-ev-h">
          <h2 id="ai-ev-h">Choose a skill</h2>
          <div class="tp-set">
            <div class="tp-set-row"><label for="ai-evn"><b>Skill</b><small>Skills in your library. Add cases in <code>evals/evals.json</code> inside the skill's folder first.</small></label><select id="ai-evn" class="field" v-model="evalName"><option value="">Choose…</option><option v-for="n in librarySkills()" :key="n" :value="n">{{ n }}</option></select></div>
            <div class="tp-set-row"><label for="ai-evm"><b>Cases</b><small>At most this many, in file order.</small></label><select id="ai-evm" class="field" v-model.number="evalMax"><option v-for="n in [1,3,5,10,15,20]" :key="n" :value="n">{{ n }}</option></select></div>
          </div>
          <div class="tp-acts"><button class="btn btn-line" :disabled="busy || !evalName" @click="estimateEvals()">Check what will be sent</button></div>
          <div v-if="evalEstimate" class="ai-confirm" role="region" aria-label="Before sending">
            <p v-for="(line,i) in evalEstimate.egress" :key="i" class="tp-fine">{{ line }}</p>
            <p class="tp-fine">At most about {{ fmt(evalEstimate.run.estimated_input_tokens) }} tokens to {{ evalEstimate.run.model }}.</p>
            <div class="tp-acts"><button class="btn btn-ink" :disabled="busy" @click="runEvals()">Send and run</button><button class="btn btn-line" :disabled="busy" @click="evalEstimate=null">Cancel</button></div>
          </div>
        </section>
        <section v-if="evalResult" class="card tp-panel" aria-labelledby="ai-evr-h" aria-live="polite">
          <header class="tp-panel-h"><div><h2 id="ai-evr-h">{{ evalResult.name }} · iteration {{ evalResult.iteration }}</h2><p>{{ evalResult.cases }} cases · {{ evalResult.run.model }} · {{ fmt(evalResult.run.input_tokens) }} input tokens</p></div>
            <span :class="['pill', evalVerdict(evalResult.verdict)[0]]">{{ evalVerdict(evalResult.verdict)[1] }}</span></header>
          <div class="ai-stats">
            <div><b class="num">{{ pct((evalResult.benchmark.variants.with_skill||{}).pass_rate) }}</b><small>cases passed with the skill</small></div>
            <div><b class="num">{{ pct((evalResult.benchmark.variants.without_skill||{}).pass_rate) }}</b><small>without it</small></div>
          </div>
          <table class="ai-table"><thead><tr><th>Case</th><th>With skill</th><th>Without</th></tr></thead>
            <tbody><tr v-for="c in [...new Set(evalResult.results.map(r => r.case))]" :key="c"><td class="tp-mono">{{ c }}</td>
              <td v-for="v in ['with_skill','without_skill']" :key="v">{{ (r => !r ? '–' : !r.graded ? 'Not graded' : r.passed + ' / ' + r.total + ' assertions')(evalResult.results.find(r => r.case===c && r.variant===v)) }}</td></tr></tbody></table>
          <p class="tp-fine">Graded only by the assertions in evals.json; ungraded cases: {{ evalResult.benchmark.ungraded_cases }}. {{ evalResult.run.advisory }}</p>
        </section>
      </template>

      <template v-else-if="page==='ai-budget'">
        <h1 class="h1" id="h1" tabindex="-1">Fit the listing budget</h1>
        <p class="lede">Agents only show the model so many characters of skill descriptions; past that, descriptions are dropped and those skills stop firing. This shortens the largest descriptions, then re-tests them, and marks a shorter version safe only if its skill still wins as often.</p>
        <section class="card tp-panel" aria-labelledby="ai-bu-h">
          <h2 id="ai-bu-h">Set up</h2>
          <div class="tp-set">
            <div class="tp-set-row"><label for="ai-scope4"><b>Agent</b></label><select id="ai-scope4" class="field" v-model="scope"><option v-for="s in agentScopes" :key="s.id" :value="s.id">{{ s.label }} ({{ s.count }})</option></select></div>
            <div class="tp-set-row"><label for="ai-bch"><b>Budget in characters</b><small>Leave blank for Claude Code to use its measured estimate. Other agents need a number (Codex uses 2% of its context).</small></label><input id="ai-bch" class="field num" type="number" min="100" v-model="budgetChars" placeholder="Measured"></div>
            <div class="tp-set-row"><label for="ai-bmax"><b>Descriptions to shorten</b><small>Largest first.</small></label><select id="ai-bmax" class="field" v-model.number="budgetMax"><option v-for="n in 10" :key="n" :value="n">{{ n }}</option></select></div>
          </div>
          <div class="tp-acts"><button class="btn btn-line" :disabled="busy || !scope" @click="estimateBudget()">Measure and check what will be sent</button></div>
          <div v-if="budgetEstimate" class="ai-confirm" role="region" aria-label="Before sending">
            <p class="tp-fine">Listing: {{ fmt(budgetEstimate.listing_chars) }} characters; budget: {{ fmt(budgetEstimate.budget_chars) }} ({{ budgetEstimate.source }}).</p>
            <p v-if="budgetEstimate.status==='within-budget'" class="tp-fine">Already within budget. Nothing to do and nothing will be sent.</p>
            <p v-else-if="budgetEstimate.status==='nothing-to-shorten'" class="tp-fine">{{ fmt(budgetEstimate.chars_to_free) }} characters over, but no description is long enough to shorten usefully. Consider turning some skills off or name-only instead.</p>
            <template v-else>
              <p class="tp-fine">{{ fmt(budgetEstimate.chars_to_free) }} characters over. Would shorten: <span class="tp-mono">{{ budgetEstimate.chosen.join(', ') }}</span>.</p>
              <p v-for="(line,i) in budgetEstimate.egress" :key="i" class="tp-fine">{{ line }}</p>
              <p class="tp-fine">At most about {{ fmt(budgetEstimate.run.estimated_input_tokens) }} tokens to {{ budgetEstimate.run.model }}.</p>
              <div class="tp-acts"><button class="btn btn-ink" :disabled="busy" @click="runBudget()">Send, shorten and re-test</button><button class="btn btn-line" :disabled="busy" @click="budgetEstimate=null">Cancel</button></div>
            </template>
          </div>
        </section>
        <section v-if="budget && budget.proposals" class="card tp-panel" aria-labelledby="ai-bur-h" aria-live="polite">
          <header class="tp-panel-h"><div><h2 id="ai-bur-h">Shorter descriptions</h2><p>Safe versions free {{ fmt(budget.safe_savings) }} of {{ fmt(budget.chars_to_free) }} characters needed.</p></div>
            <span :class="['pill', budget.fits ? 'ok' : 'warn']">{{ budget.fits ? 'Would fit' : 'Still over' }}</span></header>
          <div v-for="p in budget.proposals" :key="p.name" class="ai-cand">
            <h3><span class="tp-mono">{{ p.name }}</span> <span :class="['pill', p.safe ? 'ok' : 'bad']">{{ p.safe ? 'Still triggers' : 'Triggers less' }}</span></h3>
            <p>{{ p.proposed }}</p>
            <p class="tp-fine">Saves {{ fmt(p.saves_chars) }} characters. Won {{ pct(p.recall_before) }} of its prompts before, {{ pct(p.recall_after) }} after.</p>
            <details class="tp-more"><summary>Current description</summary><p>{{ p.current }}</p></details>
            <div class="tp-acts"><button class="btn" :class="p.safe ? 'btn-ink' : 'btn-line'" :disabled="busy || appliedNames.includes(p.name)" @click="applyShort(p)">{{ appliedNames.includes(p.name) ? 'Saved' : 'Use shorter version' }}</button></div>
          </div>
          <p v-if="!budget.fits" class="tp-fine">Not enough to fit. Turning rarely used skills off, or name-only in Claude Code settings (see Quality → What Claude Code sees), frees more.</p>
          <p class="tp-fine">{{ budget.run.advisory }}</p>
        </section>
      </template>

      <template v-else-if="page==='ai-overlap'">
        <h1 class="h1" id="h1" tabindex="-1">Overlap check</h1>
        <p class="lede">Pairs of skills an agent could confuse, or whose instructions contradict each other. Each pair is judged twice with the order swapped, and quoted conflicts must appear word for word in the files.</p>
        <section class="card tp-panel" aria-labelledby="ai-ov-h">
          <h2 id="ai-ov-h">Set up</h2>
          <div class="tp-set">
            <div class="tp-set-row"><label for="ai-scope3"><b>Agent</b></label><select id="ai-scope3" class="field" v-model="scope"><option v-for="s in agentScopes" :key="s.id" :value="s.id">{{ s.label }} ({{ s.count }})</option></select></div>
            <div class="tp-set-row"><label for="ai-ovn"><b>Pairs to judge</b><small>The most similar pairs are found without AI first; only these are sent.</small></label><select id="ai-ovn" class="field" v-model.number="overlapLimit"><option v-for="n in 12" :key="n" :value="n">{{ n }}</option></select></div>
            <div class="tp-set-row"><span><b>Also compare</b><small>Optional: two skills you suspect overlap.</small></span>
              <span class="ai-row-acts"><select class="field" v-model="pairA" aria-label="First skill"><option value="">Skill…</option><option v-for="n in scopeSkills" :key="n" :value="n">{{ n }}</option></select><select class="field" v-model="pairB" aria-label="Second skill"><option value="">Skill…</option><option v-for="n in scopeSkills" :key="n" :value="n">{{ n }}</option></select><button class="btn btn-line btn-sm" type="button" :disabled="!pairA||!pairB||pairA===pairB" @click="addPair()">Add</button></span></div>
          </div>
          <p v-if="pairs.length" class="tp-fine">Chosen: <span v-for="(p,i) in pairs" :key="i" class="tp-mono">{{ p[0] }} + {{ p[1] }}<button class="btn btn-line btn-sm" type="button" @click="pairs.splice(i,1)" :aria-label="'Remove ' + p.join(' and ')">×</button> </span></p>
          <div class="tp-acts"><button class="btn btn-line" :disabled="busy || !scope" @click="estimateOverlap()">Find pairs and check what will be sent</button></div>
          <div v-if="overlapEstimate" class="ai-confirm" role="region" aria-label="Before sending">
            <p class="tp-fine">{{ overlapEstimate.candidates_found }} candidate pair{{ overlapEstimate.candidates_found===1?'':'s' }} found; {{ overlapEstimate.pairs_judged===1 ? 'this one' : 'the top ' + overlapEstimate.pairs_judged }} would be judged:</p>
            <ul class="tp-fine ai-list"><li v-for="p in overlapEstimate.pairs" :key="p.skills.join('+')"><span class="tp-mono">{{ p.skills.join(' + ') }}</span> ({{ p.sources.join(', ') }})</li></ul>
            <p v-for="(line,i) in overlapEstimate.egress" :key="i" class="tp-fine">{{ line }}</p>
            <p class="tp-fine">At most about {{ fmt(overlapEstimate.run.estimated_input_tokens) }} tokens to {{ overlapEstimate.run.model }}.</p>
            <div class="tp-acts"><button class="btn btn-ink" :disabled="busy || !overlapEstimate.pairs_judged" @click="runOverlap()">Send and judge</button><button class="btn btn-line" :disabled="busy" @click="overlapEstimate=null">Cancel</button></div>
          </div>
        </section>
        <section v-if="overlap" class="card tp-panel" aria-labelledby="ai-ovr-h" aria-live="polite">
          <header class="tp-panel-h"><div><h2 id="ai-ovr-h">Judged pairs</h2><p>{{ overlap.pairs_judged }} pair{{ overlap.pairs_judged===1?'':'s' }} · {{ overlap.run.model }} · {{ fmt(overlap.run.input_tokens) }} input tokens</p></div></header>
          <p v-if="!overlap.judgements.length" class="tp-empty">No pairs were judged.</p>
          <div v-for="j in overlap.judgements" :key="j.skills.join('+')" class="ai-cand">
            <h3><span class="tp-mono">{{ j.skills[0] }}</span> + <span class="tp-mono">{{ j.skills[1] }}</span> <span :class="['pill', relationTone(j.relation)]">{{ relationLabel(j.relation) }}</span></h3>
            <p class="tp-fine">Found by {{ j.sources.join(', ') }}. Suggestion: {{ actionLabel(j.recommendation) }}<span v-if="j.router_confusion">; an agent could pick the wrong one</span>.</p>
            <p v-if="j.shared_requests.length" class="tp-fine">Requests both could claim: {{ j.shared_requests.join(' · ') }}</p>
            <div v-for="(c,i) in j.conflicts" :key="i" class="ai-conflict"><p><b>{{ j.skills[0] }}:</b> <q>{{ c.a_quote }}</q></p><p><b>{{ j.skills[1] }}:</b> <q>{{ c.b_quote }}</q></p><p class="tp-fine">{{ c.why }}</p></div>
            <p v-if="j.unverified_quotes" class="tp-fine">{{ j.unverified_quotes }} quoted conflict(s) were dropped because the text is not in the files.</p>
            <template v-for="n in j.skills" :key="n"><p v-if="j.boundaries[n]" class="tp-fine">Could add to <span class="tp-mono">{{ n }}</span>: “{{ j.boundaries[n] }}” <button class="btn btn-line btn-sm" @click="handoff(n)">Improve {{ n }}</button></p></template>
            <p v-if="j.merged_description" class="tp-fine">Merged description idea: {{ j.merged_description }}</p>
          </div>
          <p class="tp-fine">{{ overlap.run.advisory }}</p>
        </section>
      </template>

      <template v-else-if="page==='ai-improve'">
        <h1 class="h1" id="h1" tabindex="-1">Improve a description</h1>
        <p class="lede">Your model proposes new descriptions, then each one is re-tested against prompts it never saw. Only a measurable improvement is recommended.</p>
        <section class="card tp-panel" aria-labelledby="ai-im-h">
          <h2 id="ai-im-h">Choose a skill</h2>
          <div class="tp-set">
            <div class="tp-set-row"><label for="ai-scope2"><b>Agent</b></label><select id="ai-scope2" class="field" v-model="scope"><option v-for="s in agentScopes" :key="s.id" :value="s.id">{{ s.label }} ({{ s.count }})</option></select></div>
            <div class="tp-set-row"><label for="ai-name"><b>Skill</b></label><select id="ai-name" class="field" v-model="improveName"><option value="">Choose…</option><option v-for="n in scopeSkills" :key="n" :value="n">{{ n }}</option></select></div>
            <div class="tp-set-row"><label for="ai-cand"><b>Proposals</b></label><select id="ai-cand" class="field" v-model.number="candidates"><option v-for="n in 3" :key="n" :value="n">{{ n }}</option></select></div>
            <div class="tp-set-row"><label for="ai-rep2"><b>Repeats</b></label><select id="ai-rep2" class="field" v-model.number="repeats"><option v-for="n in 5" :key="n" :value="n">{{ n }}</option></select></div>
          </div>
          <div class="tp-acts"><button class="btn btn-line" :disabled="busy || !improveName" @click="estimateImprove()">Check what will be sent</button></div>
          <div v-if="improveEstimate" class="ai-confirm" role="region" aria-label="Before sending">
            <p v-for="(line,i) in improveEstimate.egress" :key="i" class="tp-fine">{{ line }}</p>
            <p class="tp-fine">About {{ fmt(improveEstimate.run.estimated_input_tokens) }} tokens to {{ improveEstimate.run.model }}.</p>
            <div class="tp-acts"><button class="btn btn-ink" :disabled="busy" @click="runImprove()">Send and propose</button><button class="btn btn-line" :disabled="busy" @click="improveEstimate=null">Cancel</button></div>
          </div>
        </section>
        <section v-if="improve" class="card tp-panel" aria-labelledby="ai-cands-h" aria-live="polite">
          <header class="tp-panel-h"><div><h2 id="ai-cands-h">Proposals for {{ improve.name }}</h2><p>{{ improve.prompt_count }} test prompts, half held back from the model when it wrote these.</p></div>
            <span :class="['pill', improve.verdict==='improved' ? 'ok' : 'warn']">{{ improve.verdict==='improved' ? 'Better description found' : 'Nothing beat the current one' }}</span></header>
          <div class="ai-cand"><h3>Current</h3><p>{{ improve.current }}</p>
            <p class="tp-fine">Picked for {{ pct(improve.baseline.overall.recall) }} of its prompts ({{ pct(improve.baseline.holdout.recall) }} held-out); stayed out of {{ pct(improve.baseline.overall.near_miss_avoided) }} of the others.</p></div>
          <div v-for="(c,i) in improve.candidates" :key="i" class="ai-cand">
            <h3>Proposal {{ i+1 }} <span :class="['pill', c.recommended ? 'ok' : 'off']">{{ c.recommended ? 'Recommended' : 'Not better' }}</span></h3>
            <p>{{ c.description }}</p>
            <p class="tp-fine">Picked for {{ pct(c.overall.recall) }} ({{ pct(c.holdout.recall) }} held-out); stayed out of {{ pct(c.overall.near_miss_avoided) }} of the others. {{ c.chars }} characters. {{ c.rationale }}</p>
            <div class="tp-acts"><button class="btn" :class="c.recommended ? 'btn-ink' : 'btn-line'" :disabled="busy || applied===c.description" @click="applyCandidate(c)">{{ applied===c.description ? 'Saved' : 'Use this description' }}</button></div>
          </div>
          <p class="tp-fine">{{ improve.run.advisory }} {{ fmt(improve.run.input_tokens) }} input tokens used.</p>
        </section>
      </template>

      <section class="card tp-panel" aria-labelledby="ai-history-h">
        <header class="tp-panel-h"><h2 id="ai-history-h">Past runs</h2>
          <button class="btn btn-line btn-sm" :disabled="historyBusy" @click="loadRuns()">Refresh past runs</button></header>
        <p class="tp-fine">Latest 20 saved runs across AI tools.</p>
        <p v-if="historyError" class="v2-tool-error" role="alert">{{ historyError }}</p>
        <p v-if="historyBusy" class="tp-fine" role="status">Loading past runs…</p>
        <p v-else-if="!pastRuns.length" class="tp-empty">No saved runs yet.</p>
        <ul class="tp-rows"><li v-for="r in pastRuns" :key="r.run_id" class="v2-tool-row">
          <span class="tp-row-main"><strong>{{ r.kind }}<span v-if="r.status==='disconnected'"> · Partial run</span></strong><small>{{ r.started }} · {{ r.model }}<span v-if="r.scope"> · {{ r.scope }}</span><span v-if="r.name"> · {{ r.name }}</span></small></span>
          <button class="btn btn-line btn-sm" :disabled="historyBusy" :aria-label="'View run ' + r.run_id" @click="openRun(r.run_id)">View</button>
        </li></ul>
        <div v-if="pastRun" aria-live="polite"><h3>Saved run details</h3><p class="tp-fine">Saved model output, shown as text. Results are estimates.</p>
          <pre class="ai-run-text tp-mono" tabindex="0" aria-label="Saved run details">{{ runText(pastRun) }}</pre></div>
      </section>
    </div>`,
  };
})();

/* "Explain with AI" inside an install or update review (docs/39 A5). Every
 * claim shown quotes the file it names; risk opinions never change findings. */
(function () {
  const api = window.SkillManagerDomain.api;
  const post = (url, body) => api(url, { method: "POST", body: JSON.stringify(body || {}) });
  window.SkillsV2AiBriefing = {
    props: { kind: String, reviewId: String },
    data() { return { configured: null, busy: false, error: "", estimate: null, brief: null }; },
    watch: { reviewId() { this.estimate = null; this.brief = null; this.error = ""; } },
    async mounted() { try { this.configured = !!(await api("/api/ai/settings")).configured; } catch (e) { this.configured = false; } },
    methods: {
      body(estimate) { return { kind: this.kind, review_id: this.reviewId, estimate }; },
      async run(estimate) {
        this.busy = true; this.error = "";
        try { const r = await post("/api/ai/review-briefing", this.body(estimate)); if (estimate) { this.estimate = r; this.brief = null; } else { this.brief = r; this.estimate = null; } }
        catch (e) { this.error = (e && e.message) || String(e); } finally { this.busy = false; }
      },
      matchLabel(m) { return { yes: "Description matches what it does", partly: "Description is partly accurate", no: "Description does not match what it does", unclear: "Could not tell" }[m] || m; },
      matchTone(m) { return { yes: "ok", partly: "warn", no: "bad" }[m] || "off"; },
      opinionLabel(o) { return { "likely-real": "Model thinks this is real", "likely-false-positive": "Model thinks this is a false alarm", unclear: "Model is unsure" }[o] || o; },
    },
    template: `
    <section v-if="reviewId" class="ai-brief" aria-label="AI briefing">
      <div class="tp-panel-h"><h3>Explain with AI <small class="tp-count">your own key · advisory</small></h3>
        <a v-if="configured===false" class="btn btn-line btn-sm" href="#/tools/ai-settings">Set up AI</a>
        <button v-else-if="!estimate && !brief" class="btn btn-line btn-sm" :disabled="busy || configured===null" @click="run(true)">Explain this change</button></div>
      <p v-if="error" class="v2-tool-error" role="alert">{{ error }}</p>
      <p v-if="busy" class="v2-tool-status" role="status"><span class="v2-dot" aria-hidden="true"></span>Working…</p>
      <div v-if="estimate" class="ai-confirm">
        <p v-for="(line,i) in estimate.egress" :key="i" class="tp-fine">{{ line }}</p>
        <p class="tp-fine">At most about {{ estimate.run.estimated_input_tokens.toLocaleString() }} tokens to {{ estimate.run.model }}.</p>
        <div class="tp-acts"><button class="btn btn-ink btn-sm" :disabled="busy" @click="run(false)">Send and explain</button><button class="btn btn-line btn-sm" :disabled="busy" @click="estimate=null">Cancel</button></div>
      </div>
      <div v-if="brief" aria-live="polite" class="ai-brief-body">
        <p>{{ brief.summary }}</p>
        <p><span :class="['pill', matchTone(brief.description_matches)]">{{ matchLabel(brief.description_matches) }}</span></p>
        <template v-if="brief.capabilities.length"><h4>What it can do</h4>
          <p v-for="(c,i) in brief.capabilities" :key="'c'+i" class="tp-fine"><b>{{ c.kind }}</b>: {{ c.text }} <span class="tp-mono">{{ c.file }}</span> <q class="tp-mono">{{ c.quote }}</q></p></template>
        <template v-if="brief.claims.length"><h4>Changes</h4>
          <p v-for="(c,i) in brief.claims" :key="'k'+i" class="tp-fine">{{ c.text }} <span class="tp-mono">{{ c.file }}</span> <q class="tp-mono">{{ c.quote }}</q></p></template>
        <template v-if="brief.mismatches.length"><h4>Not in the description</h4>
          <p v-for="(c,i) in brief.mismatches" :key="'m'+i" class="tp-fine">{{ c.text }} <span class="tp-mono">{{ c.file }}</span> <q class="tp-mono">{{ c.quote }}</q></p></template>
        <template v-if="brief.finding_opinions.length"><h4>Second opinion on risk findings</h4>
          <p v-for="o in brief.finding_opinions" :key="'o'+o.index" class="tp-fine">Finding {{ o.index + 1 }} ({{ o.finding_severity }} {{ o.finding_kind }}): {{ opinionLabel(o.opinion) }}. {{ o.why }}</p></template>
        <p class="tp-fine"><span v-if="brief.dropped_unquoted">{{ brief.dropped_unquoted }} claim(s) dropped because their quote is not in the files. </span>{{ brief.notes[0] }} {{ brief.run.model }}.</p>
      </div>
    </section>`,
  };
})();
