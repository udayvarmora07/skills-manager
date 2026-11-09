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
      page: { immediate: true, handler() { this.error = ""; this.note = ""; this.load(); this.takeHandoff(); } },
      scope() { this.chosen = []; this.estimate = null; this.result = null; this.improve = null; this.improveEstimate = null; },
      agentScopes: { immediate: true, handler(list) { if (!this.scope && list.length) this.scope = (list.find((s) => s.id === "claude-code") || list[0]).id; } },
    },
    methods: {
      pct,
      fmt(n) { return n == null ? "–" : Number(n).toLocaleString(); },
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
      triggerBody(estimate) {
        const body = { scope: this.scope, repeats: Number(this.repeats), estimate };
        if (this.mode === "generate") Object.assign(body, { generate_for: this.chosen, per_skill: Number(this.perSkill), near_misses: Number(this.nearMisses) });
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
        <h1 class="h1" id="h1" tabindex="-1">{{ page==='ai-trigger' ? 'Trigger test' : 'Improve a description' }}</h1>
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
              <div class="seg" role="group" aria-label="Prompt source"><button type="button" :aria-pressed="mode==='generate'" @click="mode='generate'">Generate</button><button type="button" :aria-pressed="mode==='manual'" @click="mode='manual'">Write my own</button></div></div>
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
          <template v-else>
            <label for="ai-prompts" class="tp-fine">One request per line. End a line with <code>=&gt; skill-name</code> for the skill it should load, or <code>=&gt; none</code>.</label>
            <textarea id="ai-prompts" class="field ai-text" v-model="promptText" rows="8" placeholder="fill in this tax form PDF => pdf-forms"></textarea>
          </template>
          <div class="tp-acts"><button class="btn btn-line" :disabled="busy || !scope || (mode==='generate' ? !chosen.length : !parsedPrompts.length)" @click="estimateTrigger()">Check what will be sent</button></div>
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
          <ul class="tp-rows">
            <li v-for="s in result.skills" :key="s.name" class="v2-tool-row">
              <span class="tp-row-main"><strong class="tp-mono">{{ s.name }}</strong><small>Won {{ pct(s.hit_rate) }} of its {{ s.prompts }} prompts<span v-if="s.lost_to.length">; lost to {{ s.lost_to.map(l => skillLabel(l.name) + ' ×' + l.count).join(', ') }}</span></small></span>
              <span class="ai-row-acts"><span :class="['pill', verdictTone(s.verdict)]">{{ verdictLabel(s.verdict) }}</span><button v-if="s.verdict!=='fires'" class="btn btn-line btn-sm" @click="handoff(s.name)">Improve</button></span>
            </li>
          </ul>
          <details class="tp-more"><summary>Every prompt and what was chosen</summary>
            <table class="ai-table"><thead><tr><th>Prompt</th><th>Should load</th><th>Chosen</th></tr></thead>
              <tbody><tr v-for="p in result.prompts" :key="p.id"><td>{{ p.text }}</td><td class="tp-mono">{{ p.expected || 'none' }}</td><td class="tp-mono">{{ choiceList(p.choices) }}</td></tr></tbody></table></details>
          <p class="tp-fine">{{ result.run.advisory }} Invalid answers: {{ result.invalid_answers }}.</p>
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
    </div>`,
  };
})();
