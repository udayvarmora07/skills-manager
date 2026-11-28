/* Exact-instance operations for the existing v2 library. No inferred targets. */
(function () {
  "use strict";
  const { api } = window.SkillManagerDomain;
  const request = (url, payload) => api(url, { method: "POST", body: JSON.stringify(payload) });
  const key = (r) => JSON.stringify([r.name, r.scope, r.physical_path || r.path || ""]);
  const exact = (r) => ({ name: r.name, scope: r.scope, path: r.path || r.physical_path || "", physical_path: r.physical_path || r.path || "" });

  window.SkillsV2LibraryTools = {
    props: { records: Array, scopes: Array, catalog: Object },
    emits: ["changed", "catalog-changed", "inspect", "source", "removed"],
    data() { return { selected: [], cap: 200, busy: false, error: "", result: null, notice: "", operation: "", frozen: [], excluded: [], plan: null, planPayload: null, targets: [], force: false, tags: "", tagOperation: "add", profile: "", profileChoice: "", profileBase: null, opener: null, sequence: 0, query: "", scopeFilter: "all", tagFilter: "" }; },
    computed: {
      rows() {
        const seen = new Set(), query = this.query.trim().toLowerCase();
        return (this.records || []).filter(r => {
          if ((this.scopeFilter !== "all" && r.scope !== this.scopeFilter) ||
              !String(r.name).toLowerCase().includes(query) ||
              (this.tagFilter === "__untagged" ? this.tagsFor(r).length > 0 : this.tagFilter && !this.tagsFor(r).includes(this.tagFilter.slice(4)))) return false;
          const id = key(r); if (seen.has(id)) return false; seen.add(id); return true;
        });
      },
      profileNames() { return Object.keys(this.catalog?.profiles || {}).sort(); },
      tagOptions() { return [...new Set(Object.values(this.catalog?.tags || {}).flat())].sort(); },
      shown() { return this.rows.slice(0, this.cap); },
      selectedRows() { const ids = new Set(this.selected); return (this.records || []).filter(r => ids.has(key(r))); },
      hidden() { const ids = new Set(this.rows.map(key)); return this.selected.filter(id => !ids.has(id)).length; },
      writableScopes() { return (this.scopes || []).filter(s => s.writable); },
      syncAmbiguous() { return this.operation === "sync" && new Set(this.frozen.map(r => r.name)).size !== this.frozen.length; },
    },
    methods: {
      key,
      plural(n, one, many) { return window.SkillsV2Model.plural(n, one, many); },
      readOnly(r) { return window.SkillManagerDomain.observeRecord(r).readOnly; },
      writable(r) { const observed=window.SkillManagerDomain.observeRecord(r);return r.addressable !== false && !observed.linkEscape && !observed.readOnly && this.writableScopes.some(s => s.id === r.scope); },
      selectable(r) {return window.SkillsV2Model.validName(r.name);},
      fileState(r) {const state=window.SkillManagerDomain.observeRecord(r);return state.linkEscape?"Linked outside root":state.notAddressable?"Not addressable":state.isDisabled?"File disabled":"File enabled";},
      needsReview(r) {const state=window.SkillManagerDomain.observeRecord(r);return state.malformedDocument&&!state.linkEscape;},
      tagsFor(r) {
        const tags = this.catalog?.tags?.[r.name];
        return Array.isArray(tags) ? tags : [];
      },
      scopeLabel(id) { return window.SkillsV2Model.scopeName(id, (this.scopes || []).find(s => s.id === id)?.label); },
      selectShown() { this.selected = [...new Set([...this.selected, ...this.shown.filter(r=>this.selectable(r)&&this.writable(r)).map(key)])]; },
      begin(operation) {
        this.opener = document.activeElement; this.operation = operation; this.error = ""; this.plan = null; this.planPayload = null;
        if (operation === "profile") { this.profile = ""; this.profileChoice = ""; this.profileBase = null; }
        const metadata=["tags","profile"].includes(operation);
        this.frozen = this.selectedRows.filter(metadata?this.selectable:this.writable).map(exact);
        this.excluded=metadata?[]:this.selectedRows.filter(r=>!this.writable(r)).map(exact);this.targets = []; this.force = false;
        this.$nextTick(() => this.$refs.review.showModal());
        if (["enable", "disable", "remove"].includes(operation)) this.preview();
      },
      close() { if (!this.busy) { ++this.sequence; this.$refs.review.close(); } },
      restoreFocus() { if (this.opener?.isConnected) this.opener.focus(); },
      invalidate() { this.plan = null; this.planPayload = null; this.error = ""; },
      async preview() {
        if (this.busy || !this.frozen.length || this.syncAmbiguous) return;
        const seq = ++this.sequence;
        this.busy = true; this.error = ""; this.plan = null;
        const payload = { operation: this.operation, targets: this.frozen.map(r => ({...r})), to_scopes: [...this.targets], force: this.force };
        try { const plan = await request("/api/batch/preview", payload); if (seq === this.sequence) { this.plan = plan; this.planPayload = payload; } }
        catch (e) { if (seq === this.sequence) this.error = e.message; }
        finally { if (seq === this.sequence) this.busy = false; }
      },
      async execute() {
        if (this.busy || !this.plan?.plan_id || !this.planPayload) return;
        this.busy = true; this.error = "";
        try {
          this.result = await request("/api/batch/execute", { ...this.planPayload, plan_id: this.plan.plan_id });
          if (this.operation === "remove") this.$emit("removed", (this.result.results || []).filter(r => r.trash_path));
          this.selected = []; this.$refs.review.close(); this.$emit("changed");
        } catch (e) { this.error = e.message; this.plan = null; this.planPayload = null; }
        finally { this.busy = false; }
      },
      async updateTags() {
        if (this.busy || !this.tags.trim()) return;
        this.busy = true; this.error = "";
        try { const catalog = await request("/api/catalog/tags", { names: [...new Set(this.frozen.map(r => r.name))], operation: this.tagOperation, tags: this.tags.split(",").map(t => t.trim()).filter(Boolean) }); this.notice=`Tags updated for ${this.plural(new Set(this.frozen.map(r=>r.name)).size, "skill")}.`;this.$refs.review.close(); this.$emit("catalog-changed", catalog); }
        catch (e) { this.error = e.message; } finally { this.busy = false; }
      },
      chooseProfile() {
        const previous = this.catalog?.profiles?.[this.profileChoice];
        this.profileBase = previous ? JSON.parse(JSON.stringify(previous)) : null;
        this.error = "";
      },
      async saveProfile() {
        const name = this.profileChoice || this.profile.trim(), previous = this.profileBase;
        if (this.busy || !name || (this.profileChoice && !previous)) return;
        if (!this.profileChoice && Object.prototype.hasOwnProperty.call(this.catalog?.profiles || {}, name)) {
          this.error = `A profile named ${name} already exists. Choose it from the list to add to it.`; return;
        }
        this.busy = true; this.error = "";
        const payload = { ...(previous || {}), name, expected_profile: previous,
          skills: [...new Set([...(previous?.skills || []), ...this.frozen.map(r => r.name)])],
          targets: [...new Set([...(previous?.targets || []), ...this.frozen.map(r => r.scope)])] };
        try { const catalog = await request("/api/catalog/profiles", payload); this.notice = `Selection saved to ${name}.`; this.$refs.review.close(); this.$emit("catalog-changed", catalog); }
        catch (e) { this.error = e.message; } finally { this.busy = false; }
      },
    },
    template: `
      <section class="v2-instances" aria-label="Skill copies">
        <div class="instance-filters"><label>Find a skill<input class="field" type="search" v-model="query"></label><label>Location<select class="field" v-model="scopeFilter"><option value="all">All locations</option><option v-for="scope in scopes" :key="scope.id" :value="scope.id">{{scopeLabel(scope.id)}}</option></select></label><label>Tag<select aria-label="Tag" class="field" v-model="tagFilter"><option value="">All tags</option><option value="__untagged">Untagged</option><option v-for="tag in tagOptions" :key="tag" :value="'tag:' + tag">{{tag}}</option></select></label></div>
        <p class="state-note" v-if="notice" role="status">{{notice}}</p>
        <div class="instance-bar"><button type="button" class="btn btn-line btn-sm" @click="selectShown">Select shown copies</button><span>{{ shown.length }} of {{ rows.length === 1 ? '1 copy' : rows.length + ' copies' }} shown</span></div>
        <div class="instance-selection" v-if="selected.length"><b>{{ plural(selected.length, 'exact copy', 'exact copies') }} selected</b><span v-if="hidden">, {{ hidden }} hidden by filters</span><div class="instance-actions"><button class="btn btn-line btn-sm" v-for="op in ['enable','disable','sync','remove','tags','profile']" :key="op" @click="begin(op)">{{ {enable:'Enable',disable:'Disable',sync:'Sync',remove:'Move to trash',tags:'Edit tags',profile:'Save as profile'}[op] }}</button><button class="btn btn-soft btn-sm" @click="selected=[]">Clear selection</button></div></div>
        <div class="instance-results card" v-if="result" role="status"><h2 class="h2">Batch results</h2><p>{{ result.partial || result.partial_failure ? 'Some targets failed. Successful changes remain in place.' : 'The operation finished. Review each target below.' }}</p><ul><li v-for="(r,i) in result.results || []" :key="i"><b>{{ r.name || r.target?.name }} · {{ r.scope || r.target?.scope }}</b> — {{ r.result === 'already-set' ? 'Already set; no change' : r.status }}<span v-if="r.error"> · {{ r.error }}</span><span v-if="r.result && r.result !== 'already-set'"> · {{ typeof r.result === 'string' ? r.result : JSON.stringify(r.result) }}</span></li></ul><button class="btn btn-line btn-sm" @click="result=null">Dismiss results</button></div>
        <div class="instance-list card"><article class="instance-row" v-for="r in shown" :key="key(r)"><label><input type="checkbox" :value="key(r)" v-model="selected" :disabled="!selectable(r) || !writable(r)"><span><b>{{r.name}}</b><small>{{scopeLabel(r.scope)}}<span v-if="readOnly(r)"> · linked copy is read-only</span><span v-else-if="!writable(r)"> · file writes unavailable</span></small><code>{{r.physical_path || r.path}}</code><span class="instance-tags"><span v-for="tag in tagsFor(r)" :key="tag">{{tag}}</span></span></span></label><div class="instance-actions"><span class="pill">{{fileState(r)}}</span><span class="pill bad" v-if="needsReview(r)">Document needs review</span><button type="button" class="btn btn-line btn-sm" @click="$emit('inspect',r)">Open</button><button type="button" class="btn btn-line btn-sm" :disabled="!writable(r)" @click="$emit('source',r)">Review update</button></div></article><p class="state-note" v-if="!rows.length">No exact copies match these filters.</p></div>
        <button class="btn btn-line" v-if="rows.length>shown.length" @click="cap+=200">Show {{Math.min(200,rows.length-shown.length)}} more copies</button>
        <dialog class="instance-dialog" ref="review" aria-labelledby="instance-review-title" @cancel.prevent="close" @close="restoreFocus"><h2 id="instance-review-title" class="h2">{{ {tags:'Edit tags',profile:'Save selection as profile',enable:'Review enabling copies',disable:'Review disabling copies',sync:'Review copying to places',remove:'Review moving to trash'}[operation] }}</h2><p>{{plural(frozen.length, 'exact copy', 'exact copies')}} · {{plural(new Set(frozen.map(r=>r.name)).size, 'skill name')}}</p><p v-if="operation==='remove'" class="state-note">Removal moves each selected copy to that agent's own trash folder. You can restore it from Trash &amp; backups while the copy is still there, and the result toast offers Undo.</p><p v-if="syncAmbiguous" role="alert" class="state-note err">Select one source copy per skill name before syncing. Multiple selected sources could disagree.</p><ul class="instance-targets" tabindex="0" aria-label="Selected skill copies"><li v-for="r in frozen" :key="key(r)"><b>{{r.name}} · {{scopeLabel(r.scope)}}</b><code>{{r.physical_path}}</code></li></ul>
          <template v-if="operation==='sync'"><fieldset><legend>Copy to these places</legend><label v-for="s in writableScopes" :key="s.id"><input type="checkbox" v-model="targets" :value="s.id" :disabled="busy" @change="invalidate">{{scopeLabel(s.id)}}</label></fieldset><label><input type="checkbox" v-model="force" :disabled="busy" @change="invalidate">Overwrite existing copies</label><button type="button" class="btn btn-line" :disabled="busy || !targets.length || syncAmbiguous" @click="preview">Review places</button></template>
          <template v-if="operation==='tags'"><p>Tags apply to every copy of these skills. They're stored in Jackfield, not in the skill files.</p><label>Operation<select class="field" v-model="tagOperation"><option value="add">Add</option><option value="remove">Remove</option></select></label><label>Tags, separated by commas<input class="field" v-model="tags"></label></template>
          <template v-if="operation==='profile'"><p>Add selected names and locations to a profile. Saving does not change skill files.</p><label>Choose a profile<select aria-label="Choose a profile" class="field" v-model="profileChoice" @change="chooseProfile"><option value="">Create a new profile</option><option v-for="name in profileNames" :key="name" :value="name">{{name}}</option></select></label><label v-if="!profileChoice">Profile name<input class="field" v-model="profile"></label></template>
          <p class="state-note" v-if="excluded.length">{{plural(excluded.length, 'selected copy', 'selected copies')}} {{excluded.length === 1 ? 'is' : 'are'}} excluded because file writes are unavailable. Tags and profile metadata can still be changed for those names.</p><ul class="instance-targets" v-if="excluded.length"><li v-for="r in excluded" :key="key(r)">{{r.name}} · {{scopeLabel(r.scope)}}<code>{{r.physical_path}}</code></li></ul><p class="state-note" v-if="!frozen.length">No selected copies support this operation.</p>
          <p class="state-note" v-if="busy" role="status">Working…</p><p class="state-note err" v-if="error" role="alert">{{error}}</p><button class="btn btn-line" v-if="!plan && frozen.length && !busy && !['sync','tags','profile'].includes(operation)" @click="preview">Review again</button><p class="state-note" v-if="plan">{{plural(plan.target_count, 'copy', 'copies')}} reviewed. The selected copies, places and options are fixed for this review, but file contents may change before you apply it. Each place can succeed or fail independently.</p>
          <div class="instance-actions"><button class="btn btn-line" :disabled="busy" @click="close">Cancel</button><button v-if="operation==='tags'" class="btn btn-ink" :disabled="busy||!tags.trim()" @click="updateTags">Update tags</button><button v-else-if="operation==='profile'" class="btn btn-ink" :disabled="busy||(!profileChoice && !profile.trim())" @click="saveProfile">Save profile</button><button v-else class="btn btn-ink" :disabled="busy||!plan?.plan_id" @click="execute">{{ {enable:'Enable copies',disable:'Disable copies',sync:'Copy to places',remove:'Move to trash'}[operation] }}</button></div>
        </dialog>
      </section>`,
  };
})();
