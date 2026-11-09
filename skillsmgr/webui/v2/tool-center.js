/* Production v2 tools. All server-provided content is rendered as text. */
(function () {
  const api = window.SkillManagerDomain.api;

  const json = (body) => ({method:'POST', body:JSON.stringify(body)});

  const enc = encodeURIComponent;
  function stored(key,fallback){try{return localStorage.getItem(key)||fallback}catch(e){return fallback}}
  function remember(key,value){try{localStorage.setItem(key,value);return true}catch(e){return false}}
  const SCAN_MODES=['off','static','llm'];
  // Advisory SkillSpector evidence for one review; every value is rendered as text.
  const scanPanel=(ev)=>`
            <section v-if="${ev}" class="tp-scan" aria-label="SkillSpector scan">
              <div class="tp-sec-h"><h3>SkillSpector scan <small class="tp-count">external · advisory</small></h3><span :class="['pill', scanTone(${ev})]">{{scanStatus(${ev})}}</span></div>
              <p class="tp-fine">Findings from a separate tool. They do not block or allow anything here; you decide.</p>
              <p v-if="${ev}.reason" class="tp-fine">{{${ev}.reason}}</p>
              <p v-if="${ev}.reported" class="tp-fine">SkillSpector's own rating: {{${ev}.reported.recommendation ? human(${ev}.reported.recommendation) : 'none'}}<span v-if="${ev}.reported.score!=null"> (score {{${ev}.reported.score}} of 100)</span>.</p>
              <p v-if="${ev}.status==='completed' && !(${ev}.findings||[]).length" class="tp-empty">No findings reported.</p>
              <p v-for="(f,i) in (${ev}.findings||[])" :key="i" :class="['tp-issue', scanSeverity(f.severity)]"><b>{{human(f.severity||'')}} · {{f.id}}</b> {{f.pattern}} <span class="tp-mono">{{f.file||'-'}}:{{f.line||'-'}}</span><span v-if="f.explanation" class="tp-scan-line">{{f.explanation}}</span><span v-if="f.finding" class="tp-scan-line">Matched: <q class="tp-mono">{{f.finding}}</q></span><span v-if="f.remediation" class="tp-scan-line">Fix: {{f.remediation}}</span><span v-if="f.llm_review" class="tp-scan-line">LLM review: {{human(f.llm_review)}}</span></p>
              <p v-if="${ev}.omitted" class="tp-fine">{{${ev}.omitted}} more findings not shown.</p>
              <p v-for="(n,i) in (${ev}.egress||[])" :key="'g'+i" class="tp-fine">Data sent: {{n}}.</p>
            </section>`;

  const { toolGroups: TOOL_GROUPS } = window.SkillsV2Model;

  window.SkillsV2ToolCenter = {
    props: {page:String, records:{type:Array,default:()=>[]}, scopes:{type:Array,default:()=>[]}, target:Object},
    emits:['changed','inspect','preference'],
    data() { return {
      busy:false,error:'',result:null,sequence:0,readTokens:{},loading:{},qualityEnvelope:null, tab:'registry', source:'',op:'browse',view:'all-time',stale:false, pageNo:0,review:null,trust:false,
      runnerPreview:'',runner:'npx',runnerScope:'global',agents:'',filter:'',copy:false,listOnly:false,files:[],reviewedFiles:[],folderReviewed:false,folderTrust:false,folderDocuments:[],
      catalog:null,profile:{name:'',description:'',skills:'',targets:''},profilePreview:null,plan:null,planTargets:[],
      templates:null,templateName:'',templateBody:'',templatePreview:null,creating:false,skill:{name:'',description:'',category:'',version:'',license:'',compatibility:'',allowed_tools:'',body:'',scope:'global'},
      quality:null,severity:'all',search:'',report:null,reportKind:'',validateTarget:'',validationName:'',validationScope:'global',windowSize:'claude',project:'',workspace:null,consumer:'',
      systemDark:matchMedia('(prefers-color-scheme: dark)').matches,reducedMotion:matchMedia('(prefers-reduced-motion: reduce)').matches, theme:stored('skillsmgr-theme','system'),size:stored('skillsmgr-text-size','standard'),locale:stored('skillsmgr-locale','system'),
      profileFilter:'',profileExtra:'',chosen:'',sourceReview:null,sourceTarget:null,sourceSuccess:null,snapshots:null,historyName:stored('skillsmgr-history-name',''),externalScan:SCAN_MODES.includes(stored('skillsmgr-external-scan','off'))?stored('skillsmgr-external-scan','off'):'off',historyScope:stored('skillsmgr-history-scope','global'),history:null,textSnapshots:null,textSnapshotTarget:null,
    };
       },
    computed:{
      toolGroups(){return TOOL_GROUPS;},
      fieldLabels(){return {name:'Name',description:'Description',category:'Category',version:'Version',license:'License',compatibility:'Compatibility',allowed_tools:'Allowed tools'};},
      severityNames(){return {all:'All',error:'Errors',warning:'Warnings',info:'Info'};},
      severityCounts(){const c={all:0};for(const f of (this.quality&&this.quality.findings)||[]){c.all++;c[f.severity]=(c[f.severity]||0)+1;}return c;},
      skillNames(){return [...new Set(this.records.map(r=>r.name).filter(Boolean))].sort();},
      profileNames(){return this.profile.skills.split(',').map(x=>x.trim()).filter(Boolean);},
      pickableNames(){const q=this.profileFilter.trim().toLowerCase();return this.skillNames.filter(n=>!q||n.includes(q));},
      missingProfileNames(){return this.profileNames.filter(n=>!this.skillNames.includes(n));},
      reviewValid(){const r=this.review;return !!(r&&r.inspection&&r.inspection.validation&&r.inspection.validation.valid);},
      reportTitle(){return {stats:'Context use',validate:'Validation',consumer:'Consumer explanation',doctor:'Doctor report'}[this.reportKind]||'Report';},
      projectTone(){const s=((this.workspace||{}).project||{}).status||'';return /^(ok|observed|contained|inside)/.test(s)?'ok':s==='not-requested'?'off':'warn';},
      selected(){return this.target || (this.chosen !== '' ? this.records[Number(this.chosen)] : null) || null;
      },
      selectedWritable(){const t=this.selected;
      return !!(t&&t.addressable!==false&&(t.physical_path||t.path)&&this.scopes.some(s=>s.id===t.scope&&s.writable));
      },
      registryInventory(){const query=this.search.toLowerCase();return this.records.filter(r=>r.registry_provenance&&JSON.stringify([r.name,r.registry_provenance]).toLowerCase().includes(query));},
      folderConflicts(){const names=this.files.filter(f=>/(?:^|\/)SKILL\.md(?:\.disabled)?$/.test(f.webkitRelativePath||f.name)).map(f=>(f.webkitRelativePath||f.name).split('/').slice(-2,-1)[0]);return this.records.filter(r=>r.scope==='global'&&names.includes(r.name));},
      findings(){return ((this.quality && this.quality.findings)||[]).filter(f => (this.severity==='all'||f.severity===this.severity) && JSON.stringify(f).toLowerCase().includes(this.search.toLowerCase()));
      },
      unavailableSignals(){const groups=new Map();for(const signal of this.quality?.unavailable_signals||[]){const key=signal.signal+'\0'+signal.explanation;if(!groups.has(key))groups.set(key,{...signal,count:0});groups.get(key).count++;}return [...groups.values()];},
      claudeListing(){const l=this.quality&&this.quality.claude_listing;return l&&Number(l.instances_observed)>0?l:null;},
      runnerSignature(){return JSON.stringify([this.source.trim(),this.runner,this.runnerScope,this.agents,this.filter,this.copy,this.listOnly]);
      },
      localePreview(){try{return new Intl.NumberFormat(this.locale==='system'?undefined:this.locale).format(1234567.89)}catch(e){return 'Unavailable'}},
    },
    watch:{page:{immediate:true,handler(p,previous){this.sequence++;this.loading={};if(previous==='source-update'&&p!=='source-update')this.retireSource();this.error='';
      this.result=null;
      this.report=null;
       if(p==='profiles') this.loadCatalog();
       if(p==='templates') this.loadTemplates();
       if(p==='quality') this.loadQuality();
       if(p==='workspaces') this.loadWorkspace();
       if(p==='recovery-extra') this.loadHistory();
      }}, target(){this.sequence++;this.retireSource();
      this.snapshots=null;
      }, chosen(){this.sequence++;this.retireSource();
      this.snapshots=null;
      }, historyName(v){remember('skillsmgr-history-name',v)}, historyScope(v){remember('skillsmgr-history-scope',v)}},
    methods:{
      human(v){const t=String(v==null?'':v).replace(/[-_]+/g,' ').trim();return t?t.charAt(0).toUpperCase()+t.slice(1):'Unknown';},
      when(iso){if(!iso)return 'Not returned';const d=new Date(iso);if(isNaN(d))return String(iso);try{return new Intl.DateTimeFormat(this.locale==='system'?undefined:this.locale,{dateStyle:'medium',timeStyle:'short'}).format(d)}catch(e){return String(iso)}},
      fmtN(n){if(n==null||n==='')return '—';try{return new Intl.NumberFormat(this.locale==='system'?undefined:this.locale).format(n)}catch(e){return String(n)}},
      scopeLabel(id){if(!id)return '';const s=this.scopes.find(x=>x.id===id);return id==='global'?'Your library':(s&&s.label)||id;},
      sevTone(s){return {error:'bad',warning:'warn',info:'info',unavailable:'off'}[s]||'off';},
      sevIcon(s){return {error:'bad',warning:'warn',info:'info',unavailable:'off'}[s]||'info';},
      memberTone(s){return /observed|active|enabled/.test(s||'')?'ok':/disabled|off/.test(s||'')?'off':/diverg|differ/.test(s||'')?'warn':'bad';},
      precedenceLabel(a){const s=String((a.precedence||{}).status||'');return !s||/unknown|undocumented/.test(s)?'Load order not documented':'Load order documented';},
      precedenceTone(a){const s=String((a.precedence||{}).status||'');return !s||/unknown|undocumented/.test(s)?'off':'ok';},
      toggleProfileSkill(name,checked){const set=new Set(this.profileNames);if(checked)set.add(name);else set.delete(name);this.profile.skills=[...set].join(', ');},
      addProfileName(){const n=this.profileExtra.trim();if(!n)return;this.toggleProfileSkill(n,true);this.profileExtra='';},
      newProfile(){this.sequence++;this.profile={name:'',description:'',skills:'',targets:''};this.profilePreview=null;this.plan=null;},
      pretty(v){return JSON.stringify(v,null,2)},
      listingVerdict(l){const s=String((l||{}).status||'');
        if(s==='over_budget_estimate')return{text:'Over the listing budget (estimate)',tone:'warn'};
        if(s==='unknown')return{text:"Can't tell — a settings file couldn't be read",tone:'off'};
        if(s==='within_budget')return{text:'Fits the listing budget',tone:'ok'};
        return{text:'Budget status not recognised',tone:'off'};},
      listingPct(l){const b=Number(((l||{}).budget||{}).budget_chars_estimate)||0;const c=Number((l||{}).listing_chars)||0;return b>0?Math.round(1000*c/b)/10:0;},
      listingFill(l){return Math.min(Math.max(this.listingPct(l),1.5),100)+'%';},
      listingOver(l){return String((l||{}).status||'')==='over_budget_estimate';},
      listingAria(l){return this.fmtN((l||{}).listing_chars)+' of about '+this.fmtN(((l||{}).budget||{}).budget_chars_estimate)+" characters in Claude Code's skill listing";},
      listingSnippet(name){return '"skillOverrides": { '+JSON.stringify(String(name))+': "name-only" }';},
      async copyListingSnippet(name){try{if(navigator.clipboard)await navigator.clipboard.writeText(this.listingSnippet(name))}catch(e){}},
      listingExcludedLabel(key){return {disabled:'Turned off on disk',skillOverrides_off:'Off in settings',unreadable:'Could not be read',name_only:'Name only',skillOverrides_user_invocable_only:'User-invocable only',disable_model_invocation:'Model invocation disabled'}[key]||this.human(key);},
      toggleProfileTarget(id,checked){const targets=new Set(this.profile.targets.split(',').map(s=>s.trim()).filter(Boolean));if(checked)targets.add(id);else targets.delete(id);this.profile.targets=[...targets].join(', ');},
      retireSource(){const r=this.sourceReview;
      this.sourceReview=null;
      this.sourceTarget=null;
      this.trust=false;
      if(r&&r.review_state==='pending')api('/api/source-updates/reviews/'+enc(r.review_id),{method:'DELETE'}).catch(e=>{this.error='Could not cancel previous review: '+e.message})},
      async task(fn){if(this.busy)return;
       this.busy=true;
      this.error='';
      try{return await fn()}catch(e){this.error=e.message||String(e)}finally{this.busy=false}},
      async read(url,field,options){const generation=this.sequence;const token=(this.readTokens[field]||0)+1;this.readTokens[field]=token;this.loading[field]=true;this.error='';try{const data=await api(url,options);if(generation===this.sequence&&token===this.readTokens[field]){this[field]=data;return data;}}catch(e){if(generation===this.sequence&&token===this.readTokens[field])this.error=e.message;}finally{if(generation===this.sequence&&token===this.readTokens[field])this.loading[field]=false;}},
      async registry(){const operation=this.op;this.review=null;
      this.trust=false;
      this.result=null;
       await this.task(async()=>{const p={browse:this.op==='browse'||undefined,search:this.op==='search'?this.source.trim():undefined,curated:this.op==='curated'||undefined,fetch:this.op==='fetch'||undefined,source:this.op==='fetch'?this.source.trim():undefined,external_scan:this.op==='fetch'?this.scanOption():undefined,page:Number(this.pageNo)||0,per_page:25,view:this.view,allow_stale:this.stale};
      const r=await api('/api/install',json(p));
      this.result=r;
      if(operation==='fetch'&&r.review_id)this.review=r})},
      async commitRegistry(){if(!this.review||!this.trust)return;
      await this.task(async()=>{this.result=await api('/api/install',json({fetch:true,review_id:this.review.review_id,trust_confirmed:true}));
      this.review=null;
      this.trust=false;
      this.$emit('changed')})},
      async runRunner(run){if(this.busy||(run&&this.runnerPreview!==this.runnerSignature))return;
        const signature=this.runnerSignature;
        await this.task(async()=>{this.result=await api('/api/install',json({source:this.source.trim(),runner:this.runner,scope:this.runnerScope,agents:this.agents.split(',').map(x=>x.trim()).filter(Boolean),skills:this.filter.trim()?[this.filter.trim()]:undefined,copy:this.copy,list_only:this.listOnly,run}));if(!run)this.runnerPreview=signature;});
        if(run){this.runnerPreview='';this.$emit('changed');if(this.error)this.error+=' The command may have changed files before stopping. An inventory refresh was requested; inspect resulting files before retrying.';}
      },
      async copyCommand(){if(this.runnerPreview===this.runnerSignature&&this.result&&this.result.command)await navigator.clipboard.writeText(this.result.command)},
      folderSelectionMatches(files){return files.length===this.files.length&&files.every((file,index)=>file===this.files[index]);},
      resetFolder(files){this.files=files;this.reviewedFiles=[];this.folderReviewed=false;this.folderTrust=false;this.folderDocuments=[];},
      async reviewFolder(){if(!this.files.length||this.busy)return;
        const files=[...this.files];this.reviewedFiles=[];this.folderReviewed=false;this.folderTrust=false;
        await this.task(async()=>{const documents=[];
          for(const file of files.filter(f=>/(?:^|\/)SKILL\.md(?:\.disabled)?$/.test(f.webkitRelativePath||f.name)).slice(0,20))documents.push({path:file.webkitRelativePath||file.name,previewed:file.size<=524288,body:file.size<=524288?await file.text():'This document exceeds the 512 KiB preview limit. Inspect it locally.'});
          if(!this.folderSelectionMatches(files))return;
          this.folderDocuments=documents;this.reviewedFiles=files;this.folderReviewed=true;
        });
      },
      async uploadFolder(){if(!this.files.length||!this.folderReviewed||!this.folderTrust||this.folderConflicts.length||!this.folderSelectionMatches(this.reviewedFiles))return;
      const files=[...this.reviewedFiles];
      await this.task(async()=>{const f=new FormData();
      for(const file of files)f.append('files',file,file.webkitRelativePath||file.name);
      this.result=await api('/api/import',{method:'PUT',body:f});
      this.$emit('changed')})},
      loadCatalog(){this.read('/api/catalog','catalog')},
      async saveProfile(){await this.task(async()=>{this.catalog=await api('/api/catalog/profiles',json({name:this.profile.name.trim(),description:this.profile.description.trim(),skills:this.profile.skills.split(',').map(x=>x.trim()).filter(Boolean),targets:this.profile.targets.split(',').map(x=>x.trim()).filter(Boolean)}));
      this.result={message:'Profile metadata saved.'};
      this.$emit('changed')})},
      editProfile(name,p){this.sequence++;this.profile={name,description:p.description||'',skills:(p.skills||[]).join(', '),targets:(p.targets||[]).join(', ')};
      this.profilePreview=null;
      this.plan=null},
      async previewProfile(name){this.plan=null;
      this.profilePreview=null;
      await this.read('/api/catalog/profiles/'+enc(name)+'/preview','profilePreview')},
      async deleteProfile(name){if(!confirm('Delete profile metadata for '+name+'? Skill files remain.'))return;
      await this.task(async()=>{this.catalog=await api('/api/catalog/profiles/'+enc(name),{method:'DELETE'});
      this.profilePreview=null;
      this.plan=null;
      this.$emit('changed')})},
      async previewPlan(){const seen=new Set();
      const targets=[];
      for(const m of this.profilePreview.members||[])for(const i of m.instances||[]){const t={name:m.name,scope:i.scope,path:i.path||i.physical_path||''};
      const k=JSON.stringify(t);
      if(t.name&&t.scope&&t.path&&!seen.has(k)){seen.add(k);
      targets.push(t)}}if(!targets.length){this.error='No observed instances are available to enable.';
      return}this.planTargets=targets;
      await this.task(async()=>{this.plan=await api('/api/batch/preview',json({operation:'enable',targets,to_scopes:[],force:false}))})},
      async executePlan(){if(!this.plan||!this.plan.plan_id)return;
      await this.task(async()=>{this.result=await api('/api/batch/execute',json({operation:'enable',plan_id:this.plan.plan_id,targets:this.planTargets,to_scopes:[],force:false}));
      this.plan=null;
      this.$emit('changed')})},
      loadTemplates(){this.read('/api/templates','templates')},
      async readTemplate(name){this.templatePreview=null;
      await this.read('/api/templates/'+enc(name),'templatePreview')},
      async saveTemplate(){await this.task(async()=>{this.result=await api('/api/templates',json({name:this.templateName.trim(),body:this.templateBody||null}));
      this.loadTemplates()})},
      builtInTemplate(){this.templatePreview={name:'Built-in default',body:'---\nname: {name}\ndescription: A concise one-line summary of what this skill does.\nmetadata:\n  category: uncategorized\n---\n\n# {name}\n\nExplain what the skill does, when it should be invoked, and how it behaves.\n'}},
      useTemplate(){if(!this.templatePreview)return;
      this.skill.body=this.templatePreview.body.replace(/^---\s*\r?\n[\s\S]*?\r?\n---\s*(?:\r?\n|$)/,'');
      this.creating=true},
      async createSkill(){await this.task(async()=>{const p={...this.skill};
      delete p.scope;
      for(const k of Object.keys(p))if(!p[k])delete p[k];
      this.result=await api('/api/skills?scope='+enc(this.skill.scope),json(p));
      this.$emit('changed')})},
      async loadQuality(){this.quality=null;const envelope=await this.read('/api/doctor?scope=all&hygiene=1','qualityEnvelope');if(envelope){this.quality=envelope.hygiene||null;if(!this.quality)this.error='The server returned no hygiene report.';}},
      inspectInstance(i){const found=this.records.filter(r=>r.name===i.name&&r.scope===i.scope&&(!(i.physical_path||i.path)||(r.physical_path||r.path)===(i.physical_path||i.path)));
      const r=found.length===1?found[0]:null;
      if(r)this.$emit('inspect',r);
      else this.error='This exact instance is not in the current inventory. Refresh and try again.'},
      async showReport(kind){this.reportKind=kind;
      this.report=null;
      const url=kind==='doctor'?'/api/doctor?scope=all':'/api/stats?window='+enc(this.windowSize);
      await this.read(url,'report')},
      async validate(){const r=this.records[Number(this.validateTarget)];
      if(!r)return;
      await this.task(async()=>{this.reportKind='validate';this.report=null;
      await this.read('/api/validate','report',json({name:r.name,scope:r.scope}))})},
      async validateNamed(){if(!this.validationName.trim())return;await this.task(async()=>{this.reportKind='validate';this.report=null;await this.read('/api/validate','report',json({name:this.validationName.trim(),scope:this.validationScope}));});},
      loadWorkspace(){this.workspace=null;this.read('/api/workspaces'+(this.project.trim()?'?project='+enc(this.project.trim()):''),'workspace')},
      async explain(){this.reportKind='consumer';
      this.report=null;
      await this.read('/api/doctor?explain='+enc(this.consumer)+(this.project.trim()?'&project='+enc(this.project.trim()):''),'report')},
      scanOption(){return this.externalScan==='off'?undefined:this.externalScan},
      scanStatus(e){return {completed:'Scanned',incomplete:'Partial scan',unavailable:'Not available',timeout:'Timed out',error:'Scan failed'}[e.status]||'Unknown'},
      scanTone(e){if(e.status==='completed')return (e.findings||[]).length?'warn':'ok';return e.status==='incomplete'?'warn':'off'},
      scanSeverity(s){return ['CRITICAL','HIGH'].includes(String(s).toUpperCase())?'bad':'warn'},
      preference(key,value){if(!remember(key,value)){this.error='Browser storage is unavailable; preferences could not be saved.';return;}
      this.$emit('preference')},
      async maintain(which){if(!confirm((which==='rebuild'?'Rebuild':'Resync')+' the index from the filesystem?'))return;
      await this.task(async()=>{this.result=await api('/api/'+which,{method:'POST'});
      this.$emit('changed')})},
      async prepareSource(){const t=this.selected;
      if(!t||!this.files.length)return;
      await this.task(async()=>{const f=new FormData();
      f.append('name',t.name);
      f.append('scope',t.scope);
      f.append('target_path',t.physical_path||t.path);
      if(this.scanOption())f.append('external_scan',this.scanOption());
      for(const file of this.files)f.append('files',file,file.webkitRelativePath||file.name);
      const r=await api('/api/source-updates/reviews',{method:'POST',body:f});
      if(!this.alive||this.page!=='source-update'||this.selected!==t){if(r.review_id)await api('/api/source-updates/reviews/'+enc(r.review_id),{method:'DELETE'});
      throw Error('Target changed while the review was prepared. Review again.')}this.sourceTarget={name:t.name,scope:t.scope,path:t.physical_path||t.path};
      this.sourceReview=r;
      this.sourceSuccess=null})},
      async loadSnapshots(){const t=this.selected;
      if(!t)return;
      await this.read('/api/source-updates/snapshots?name='+enc(t.name)+'&scope='+enc(t.scope)+'&target_path='+enc(t.physical_path||t.path),'snapshots')},
      async snapshotReview(s){const t=this.selected;
      if(!t||!s.snapshot_id)return;
      await this.task(async()=>{const r=await api('/api/source-updates/reviews/from-snapshot',json({name:t.name,scope:t.scope,target_path:t.physical_path||t.path,snapshot_id:s.snapshot_id,external_scan:this.scanOption()}));
      if(!this.alive||this.page!=='source-update'||this.selected!==t){if(r.review_id)await api('/api/source-updates/reviews/'+enc(r.review_id),{method:'DELETE'});
      throw Error('Target changed while the review was prepared. Review again.')}this.sourceTarget={name:t.name,scope:t.scope,path:t.physical_path||t.path};
      this.sourceReview=r;
      this.sourceSuccess=null})},
      async cancelSource(){if(!this.sourceReview)return;
      await this.task(async()=>{await api('/api/source-updates/reviews/'+enc(this.sourceReview.review_id),{method:'DELETE'});
      this.sourceReview=null;
      this.sourceTarget=null;
      this.trust=false})},
      async applySource(){const t=this.sourceTarget;
      if(!t||!this.sourceReview||this.sourceReview.review_state!=='pending'||!this.sourceReview.validation||this.sourceReview.validation.valid!==true||!((this.sourceReview.comparison||{}).changed_files||[]).length||!this.trust)return;
      await this.task(async()=>{this.sourceSuccess=await api('/api/source-updates/reviews/'+enc(this.sourceReview.review_id)+'/commit',json({name:t.name,scope:t.scope,target_path:t.path,approve:true}));
      this.sourceReview=null;
      this.trust=false;
      this.$emit('changed')})},
      async loadHistory(){const n=++this.sequence;
      const name=this.historyName;
      const scope=this.historyScope;
      this.error='';
      try{const rows=await api('/api/history?limit=200'+(name?'&name='+enc(name):''));
      let snaps=null;
      if(name)snaps=await api('/api/history?name='+enc(name)+'&scope='+enc(scope)+'&snapshots=1');
      if(n===this.sequence&&name===this.historyName&&scope===this.historyScope){this.history=rows;
      this.textSnapshots=snaps;
      this.textSnapshotTarget={name,scope}}}catch(e){if(n===this.sequence)this.error=e.message}},
      async rollbackText(s){const t=this.textSnapshotTarget;
      if(!t||t.name!==this.historyName||t.scope!==this.historyScope||!s)return;
      if(!confirm('Restore this text snapshot for '+t.name+' in '+t.scope+'? Companion files and activation state are not restored.'))return;
      await this.task(async()=>{this.result=await api('/api/trash/'+enc(t.name)+'?snapshot='+enc(s)+'&scope='+enc(t.scope),{method:'POST'});
      this.$emit('changed');
      this.loadHistory()})},
    },
    mounted(){this.alive=true;
      this.darkMedia=matchMedia('(prefers-color-scheme: dark)');
      this.motionMedia=matchMedia('(prefers-reduced-motion: reduce)');
      this.darkListener=e=>{this.systemDark=e.matches};
      this.motionListener=e=>{this.reducedMotion=e.matches};
      this.darkMedia.addEventListener('change',this.darkListener);
      this.motionMedia.addEventListener('change',this.motionListener)},
    beforeUnmount(){this.alive=false;
      this.darkMedia.removeEventListener('change',this.darkListener);
      this.motionMedia.removeEventListener('change',this.motionListener);
      if(this.sourceReview && this.sourceReview.review_state==='pending'&&!this.sourceSuccess) api('/api/source-updates/reviews/'+enc(this.sourceReview.review_id),{method:'DELETE'}).catch(()=>{});
      },
    template:`
    <section :class="['v2-tools', page==='recovery-extra'?'':'page']" :aria-busy="busy">
      <div :class="['v2-tool-layout', {'v2-tool-layout-solo': page==='recovery-extra'||page==='tools'}]">
        <nav v-if="page!=='recovery-extra'&&page!=='tools'" class="v2-tool-nav" aria-label="Tools navigation">
          <a class="v2-tool-nav-home" href="#/tools"><span aria-hidden="true">←</span> All tools</a>
          <template v-for="g in toolGroups" :key="g.label">
            <span class="v2-tool-nav-label">{{g.label}}</span>
            <a v-for="item in g.items" :key="item.id" :href="'#/tools/'+item.id" :aria-current="page===item.id?'page':null">{{item.name}}</a>
          </template>
        </nav>
        <div class="v2-tool-content" :data-tool-page="page">
      <p v-if="error" class="v2-tool-error" role="alert">{{ error }}</p>
      <p v-if="busy" class="v2-tool-status" role="status"><span class="v2-dot" aria-hidden="true"></span>Working…</p><p v-else-if="Object.values(loading).some(Boolean)" class="v2-tool-status" role="status"><span class="v2-dot" aria-hidden="true"></span>Reading current evidence…</p>

      <template v-if="page==='tools'">
        <h1 class="h1" id="h1" tabindex="-1">Tools</h1>
        <p class="lede">Less frequent jobs: bring skills in, group them, check their health and tune this app.</p>
        <div class="tp-index">
          <section v-for="g in toolGroups" :key="g.label" :aria-labelledby="'tg-'+g.key">
            <h2 class="tp-eyebrow" :id="'tg-'+g.key">{{g.label}}</h2>
            <div class="v2-tool-links">
              <a v-for="item in g.items" :key="item.id" :href="'#/tools/'+item.id">
                <strong>{{item.name}}</strong>
                <span>{{item.text}}</span>
                <svg class="i i-s" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
              </a>
            </div>
          </section>
        </div>
      </template>

      <template v-else-if="page.startsWith('ai-')">
        <ai-center :page="page" :records="records" :scopes="scopes" :target="target" @changed="$emit('changed')"></ai-center>
      </template>

      <template v-else-if="page==='install'">
        <h1 class="h1" id="h1" tabindex="-1">Install</h1>
        <p class="lede">Bring a skill in from the skills.sh registry, a package command, or a folder on this computer. Nothing is written until you approve a review.</p>
        <div class="seg tp-tabs" role="group" aria-label="Install source">
          <button v-for="t in [['registry','Registry'],['runner','Package command'],['folder','Local folder']]" :key="t[0]" type="button" :aria-pressed="tab===t[0]" @click="tab=t[0];result=null;review=null">{{t[1]}}</button>
        </div>

        <template v-if="tab==='registry'">
          <form class="tp-search" role="search" @submit.prevent="op='search';pageNo=0;registry()">
            <label class="sr-only" for="tp-reg-q">Search query</label>
            <input id="tp-reg-q" class="field" type="search" v-model="source" placeholder="Search skills.sh — e.g. pdf, commit, testing" required>
            <button class="btn btn-ink" :disabled="busy||!source.trim()">Search</button>
          </form>
          <div class="tp-quick">
            <span>Or browse</span>
            <button v-for="v in [['all-time','Most installed'],['trending','Trending'],['hot','Hot']]" :key="v[0]" type="button" class="tp-link" :disabled="busy" @click="op='browse';view=v[0];pageNo=0;registry()">{{v[1]}}</button>
            <button type="button" class="tp-link" :disabled="busy" @click="op='curated';pageNo=0;registry()">Curated sources</button>
            <label class="tp-check"><input type="checkbox" v-model="stale"> Use cached results if offline</label>
          </div>
          <details class="tp-more">
            <summary>Have an exact skill ID?</summary>
            <form class="tp-inline" @submit.prevent="op='fetch';registry()">
              <label class="sr-only" for="tp-reg-id">Skill ID</label>
              <input id="tp-reg-id" class="field" v-model="source" placeholder="owner/repository/skill" required>
              <button class="btn btn-line" :disabled="busy">Fetch for review</button>
            </form>
          </details>

          <section v-if="review" class="card tp-panel tp-review" aria-labelledby="tp-rev-h">
            <header class="tp-panel-h">
              <div><h2 id="tp-rev-h">Review before installing</h2><p>Goes to your library (global store). Trust applies to this exact artifact only.</p></div>
              <span :class="['pill', reviewValid ? 'ok' : 'warn']">{{ reviewValid ? 'Validates' : 'Has warnings or blockers' }}</span>
            </header>
            <dl class="tp-dl">
              <dt>Source</dt><dd><code>{{(review.registry||{}).id||(review.registry||{}).source||'Not returned'}}</code></dd>
              <dt>Content hash</dt><dd><code>{{(review.registry||{}).registry_hash||(review.registry||{}).remote_registry_hash||'Not returned'}}</code></dd>
              <dt>Review expires</dt><dd>{{when(review.review_expires_at)}}</dd>
              <dt>Review ID</dt><dd><code>{{review.review_id}}</code></dd>
            </dl>
${scanPanel('(review.inspection||{}).external_scan')}
            <details class="tp-more"><summary>Validation and advisory risk evidence</summary><p class="tp-fine">Risk findings are heuristics, not a safety verdict.</p><pre>{{pretty(review.inspection||{})}}</pre></details>
            <div class="tp-confirm">
              <label class="tp-check"><input type="checkbox" v-model="trust"> I explicitly trust this reviewed artifact</label>
              <button class="btn btn-ink" :disabled="busy||!trust" @click="commitRegistry">Install reviewed artifact</button>
            </div>
          </section>

          <section v-if="result && Array.isArray(result.data)" class="tp-sec" aria-labelledby="tp-res-h">
            <div class="tp-sec-h"><h2 id="tp-res-h">Registry results</h2><span class="tp-count">{{result.data.length}} shown</span></div>
            <p v-if="!result.data.length" class="tp-empty">Nothing matched. Try a broader word, or browse the most installed skills.</p>
            <ul v-else class="tp-rows">
              <li v-for="(entry,index) in result.data" :key="index" class="v2-tool-row">
                <span class="tp-row-main"><strong class="tp-mono">{{entry.name||entry.id||entry.slug||'Registry source'}}</strong><small>{{entry.source||entry.id||entry.slug||'Source not returned'}}</small></span>
                <button class="btn btn-line btn-sm" type="button" :disabled="busy||!(entry.id||entry.slug)" @click="source=entry.id||entry.slug;op='fetch';registry()">Review</button>
              </li>
            </ul>
            <div v-if="op==='browse'" class="tp-pager">
              <button type="button" class="btn btn-soft btn-sm" :disabled="busy||Number(pageNo)<=0" @click="pageNo=Number(pageNo)-1;registry()">Previous</button>
              <span class="tp-count">Page {{Number(pageNo)+1}}</span>
              <button type="button" class="btn btn-soft btn-sm" :disabled="busy||result.data.length<25" @click="pageNo=Number(pageNo)+1;registry()">Next</button>
            </div>
            <details class="tp-more"><summary>Raw registry response</summary><pre>{{pretty(result)}}</pre></details>
          </section>

          <section class="tp-sec" aria-labelledby="tp-inv-h">
            <div class="tp-sec-h"><h2 id="tp-inv-h">Installed from the registry</h2><span class="tp-count">{{registryInventory.length}}</span></div>
            <p class="tp-fine">Copies that carry registry provenance. This does not mean an update is available.</p>
            <template v-if="records.some(r=>r.registry_provenance)">
              <label class="sr-only" for="tp-inv-q">Search inventory</label>
              <input id="tp-inv-q" class="field tp-filter" type="search" v-model="search" placeholder="Filter installed">
              <ul class="tp-rows"><li v-for="r in registryInventory.slice(0,200)" :key="r.name+':'+r.scope+':'+(r.physical_path||r.path)" class="v2-tool-row">
                <span class="tp-row-main"><strong class="tp-mono">{{r.name}}</strong><small>{{scopeLabel(r.scope)}} · {{r.registry_provenance.id||r.registry_provenance.source||'source known'}}<template v-if="r.registry_provenance.trusted===false"> · not recorded by this app for this copy, so unverified</template></small></span>
                <button class="btn btn-soft btn-sm" @click="$emit('inspect',r)">Open</button>
              </li></ul>
            </template>
            <p v-else class="tp-empty">None yet. Skills you install from the registry will be listed here.</p>
          </section>
        </template>

        <form v-if="tab==='runner'" class="card tp-panel" @submit.prevent="runRunner(false)">
          <div class="tp-set">
            <label class="tp-set-row"><span><b>Source</b><small>A GitHub repository holding skills.</small></span><input class="field" v-model="source" required placeholder="owner/repository" aria-label="Source"></label>
            <label class="tp-set-row"><span><b>Runner</b><small>Package tool used to run the skills CLI.</small></span><select class="field" aria-label="Runner" v-model="runner"><option>npx</option><option>pnpm</option><option>yarn</option><option>bunx</option></select></label>
            <label class="tp-set-row"><span><b>Destination</b><small>Your user folders, or the current project.</small></span><select class="field" aria-label="Destination" v-model="runnerScope"><option value="global">Global</option><option value="project">Project</option></select></label>
            <label class="tp-set-row"><span><b>Agents</b><small>Optional, comma separated, e.g. claude-code, codex.</small></span><input class="field" v-model="agents" aria-label="Agents (comma separated)"></label>
            <label class="tp-set-row"><span><b>Only this skill</b><small>Optional skill name filter.</small></span><input class="field" v-model="filter" aria-label="Skill filter"></label>
            <div class="tp-set-row"><span><b>Options</b></span><span class="tp-checks"><label class="tp-check"><input type="checkbox" v-model="copy"> Copy instead of link</label><label class="tp-check"><input type="checkbox" v-model="listOnly"> List only</label></span></div>
          </div>
          <div class="tp-cmd" v-if="result && result.command && runnerPreview===runnerSignature"><code>{{result.command}}</code><button type="button" class="btn btn-soft btn-sm" @click="copyCommand">Copy command</button></div>
          <p v-else class="tp-fine">Preview the command first. Run stays disabled until the preview matches these settings.</p>
          <div class="tp-acts">
            <button class="btn btn-line" :disabled="busy">Preview command</button>
            <button type="button" class="btn btn-ink" :disabled="busy||!source.trim()||runnerPreview!==runnerSignature" @click="runRunner(true)">Run command</button>
          </div>
        </form>

        <form v-if="tab==='folder'" class="card tp-panel" @submit.prevent="uploadFolder">
          <label class="tp-drop">
            <input type="file" class="sr-only" webkitdirectory directory multiple :disabled="busy" aria-label="Choose local skill folder" @change="resetFolder(Array.from($event.target.files))">
            <svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h6l2 2h8v10H4Z"/></svg>
            <b>{{ files.length ? files.length+' files selected' : 'Choose a skill folder' }}</b>
            <small>Imported into your library (global store). Existing skills are never overwritten here.</small>
          </label>
          <div class="tp-acts"><button type="button" class="btn btn-line" :disabled="busy||!files.length" @click="reviewFolder">Review selected folder</button></div>
          <section v-if="folderReviewed" class="tp-review-inner" aria-labelledby="tp-fold-h">
            <h2 id="tp-fold-h">Review folder import</h2>
            <p class="tp-fine">{{folderDocuments.filter(d=>d.previewed).length}} skill documents previewed of {{files.length}} files. At most 20 documents up to 512 KiB each are shown; companion file contents are not. Server validation runs during import.</p>
            <details class="tp-more"><summary>Selected files (first {{Math.min(200,files.length)}} of {{files.length}})</summary><p v-for="file in files.slice(0,200)" :key="file.webkitRelativePath||file.name" class="tp-mono tp-fine">{{file.webkitRelativePath||file.name}}</p></details>
            <details v-for="doc in folderDocuments" :key="doc.path" class="tp-more"><summary class="tp-mono">{{doc.path}}</summary><pre>{{doc.body}}</pre></details>
            <div v-if="folderConflicts.length" class="v2-tool-error"><p>These names already exist in your library. Update the existing copy instead.</p><p class="tp-acts"><button type="button" v-for="r in folderConflicts" class="btn btn-soft btn-sm" :key="r.name" @click="$emit('inspect',r)">Open {{r.name}}</button></p></div>
            <div class="tp-confirm">
              <label class="tp-check"><input type="checkbox" v-model="folderTrust"> I inspected the selected files, including files not previewed here, and approve the global destination</label>
              <button class="btn btn-ink" :disabled="busy||!folderTrust||folderConflicts.length">Import reviewed folder</button>
            </div>
          </section>
        </form>
      </template>

      <template v-else-if="page==='profiles'">
        <h1 class="h1" id="h1" tabindex="-1">Profiles</h1>
        <p class="lede">A named set of skills you want switched on together, for example “frontend work”. Applying one only turns on copies that already exist — it never installs or turns anything off.</p>
        <div class="tp-split">
          <section class="tp-list" aria-labelledby="tp-prof-h">
            <div class="tp-sec-h"><h2 id="tp-prof-h">Saved profiles</h2><button type="button" class="btn btn-soft btn-sm" @click="newProfile">New profile</button></div>
            <template v-if="catalog">
              <p v-if="!Object.keys(catalog.profiles||{}).length" class="tp-empty">No profiles yet. Fill in the profile details to create one.</p>
              <ul class="tp-rows"><li class="v2-tool-row tp-prof" :class="{on: profile.name===name}" v-for="(p,name) in catalog.profiles" :key="name">
                <span class="tp-row-main"><strong>{{name}}</strong><small>{{(p.skills||[]).length}} skills<template v-if="p.description"> · {{p.description}}</template></small></span>
                <span class="tp-acts"><button class="btn btn-line btn-sm" @click="previewProfile(name)">Preview</button><button class="btn btn-soft btn-sm" @click="editProfile(name,p)">Edit</button><button class="btn btn-danger btn-sm" :disabled="busy" @click="deleteProfile(name)" :aria-label="'Delete '+name">Delete</button></span>
              </li></ul>
            </template>
            <p v-else class="tp-acts"><button class="btn btn-soft" @click="loadCatalog">Retry profiles</button></p>
          </section>

          <form class="card tp-panel" @submit.prevent="saveProfile" aria-labelledby="tp-pform-h">
            <h2 id="tp-pform-h">{{ catalog && (catalog.profiles||{})[profile.name] ? 'Edit profile' : 'Profile details' }}</h2>
            <div class="tp-grid2">
              <label class="tp-field">Name <input class="field" v-model="profile.name" required></label>
              <label class="tp-field">Description <input class="field" v-model="profile.description" placeholder="Optional"></label>
            </div>
            <fieldset class="tp-pick">
              <legend>Skills <span class="tp-count">{{profileNames.length}} chosen</span></legend>
              <input class="field tp-filter" type="search" v-model="profileFilter" placeholder="Filter skills" aria-label="Filter skills">
              <div class="tp-pick-list">
                <label v-for="n in pickableNames" :key="n" class="tp-check"><input type="checkbox" :checked="profileNames.includes(n)" @change="toggleProfileSkill(n,$event.target.checked)"> <span class="tp-mono">{{n}}</span></label>
                <p v-if="!pickableNames.length" class="tp-fine">No observed skills match.</p>
              </div>
              <div class="tp-inline">
                <label class="sr-only" for="tp-extra">Add a name that is not installed</label>
                <input id="tp-extra" class="field" v-model="profileExtra" placeholder="Add a name not installed yet" @keydown.enter.prevent="addProfileName">
                <button type="button" class="btn btn-soft btn-sm" :disabled="!profileExtra.trim()" @click="addProfileName">Add</button>
              </div>
              <p v-if="missingProfileNames.length" class="tp-fine">Not installed anywhere: <span v-for="n in missingProfileNames" :key="n" class="tp-tag">{{n}} <button type="button" :aria-label="'Remove '+n" @click="toggleProfileSkill(n,false)">×</button></span></p>
            </fieldset>
            <fieldset class="tp-pick"><legend>Where to apply</legend>
              <div class="tp-checks"><label v-for="s in scopes" :key="s.id" class="tp-check"><input type="checkbox" :checked="profile.targets.split(',').map(t=>t.trim()).includes(s.id)" @change="toggleProfileTarget(s.id,$event.target.checked)">{{scopeLabel(s.id)}}</label></div>
              <p class="tp-fine">None ticked means every agent. You see the exact copies before anything changes.</p>
            </fieldset>
            <div class="tp-acts"><button class="btn btn-ink" :disabled="busy||!profile.name.trim()">Save profile</button></div>
          </form>
        </div>

        <section v-if="profilePreview" class="card tp-panel" aria-labelledby="tp-pp-h">
          <header class="tp-panel-h"><div><h2 id="tp-pp-h">{{profilePreview.name}}</h2><p>What applying this profile would touch.</p></div></header>
          <ul class="tp-rows"><li v-for="m in profilePreview.members" :key="m.name" class="v2-tool-row tp-member">
            <span class="tp-row-main"><strong class="tp-mono">{{m.name}}</strong><small v-for="i in m.instances" :key="i.scope+':'+(i.path||i.physical_path)">{{scopeLabel(i.scope)}} · <span class="tp-mono">{{i.path||i.physical_path}}</span></small></span>
            <span :class="['pill', memberTone(m.state)]">{{human(m.state)}}</span>
          </li></ul>
          <div class="tp-acts"><button class="btn btn-ink" :disabled="busy" @click="previewPlan">Review enable-only plan</button></div>
        </section>
        <section v-if="plan" class="card tp-panel" aria-labelledby="tp-plan-h">
          <header class="tp-panel-h"><div><h2 id="tp-plan-h">Enable plan</h2><p>{{plan.target_count || planTargets.length}} exact copies will be switched on. Nothing else is disabled, missing members are not installed, and differing copies stay different.</p></div></header>
          <ul class="tp-rows"><li v-for="t in planTargets" :key="t.name+t.scope+t.path" class="v2-tool-row"><span class="tp-row-main"><strong class="tp-mono">{{t.name}}</strong><small>{{scopeLabel(t.scope)}} · <span class="tp-mono">{{t.path}}</span></small></span></li></ul>
          <details class="tp-more"><summary>Plan details and blockers</summary><pre>{{pretty(plan)}}</pre></details>
          <div class="tp-acts"><button class="btn btn-ink" :disabled="busy||!plan.plan_id" @click="executePlan">Execute reviewed plan</button></div>
        </section>
      </template>

      <template v-else-if="page==='templates'">
        <h1 class="h1" id="h1" tabindex="-1">Templates</h1>
        <p class="lede">Starting documents for new skills. Saving a template does not create a skill.</p>
        <div class="tp-split">
          <section class="tp-list" aria-labelledby="tp-tl-h">
            <div class="tp-sec-h"><h2 id="tp-tl-h">Stored templates</h2><span class="tp-count" v-if="templates">{{(templates.templates||[]).length}}</span></div>
            <template v-if="templates">
              <ul class="tp-rows tp-pick-rows">
                <li v-for="n in templates.templates" :key="n"><button type="button" :class="{on: templatePreview && templatePreview.name===n}" @click="readTemplate(n)">{{n}}</button></li>
                <li><button type="button" class="tp-builtin" :class="{on: templatePreview && templatePreview.name==='Built-in default'}" @click="builtInTemplate()">Built-in default</button></li>
              </ul>
            </template>
            <p v-else class="tp-acts"><button class="btn btn-soft" @click="loadTemplates">Retry templates</button></p>
          </section>
          <div>
            <section v-if="templatePreview" class="card tp-panel" aria-labelledby="tp-tp-h">
              <header class="tp-panel-h"><div><h2 id="tp-tp-h" class="tp-mono">{{templatePreview.name}}</h2></div><button class="btn btn-ink btn-sm" @click="useTemplate">Use template</button></header>
              <pre class="tp-doc">{{templatePreview.body}}</pre>
            </section>
            <p v-else class="tp-empty tp-pane-empty">Choose a template to read it, then start a skill from it.</p>
          </div>
        </div>
        <form v-if="creating" class="card tp-panel" @submit.prevent="createSkill" aria-labelledby="tp-cs-h">
          <h2 id="tp-cs-h">Create skill from template</h2>
          <p class="tp-fine">Template frontmatter is dropped from the body; fill in the details below and replace any placeholders.</p>
          <div class="tp-grid2">
            <label v-for="field in ['name','description','category','version','license','compatibility','allowed_tools']" :key="field" :class="['tp-field',{'tp-wide':field==='description'}]">{{fieldLabels[field]}} <input class="field" v-model="skill[field]" :required="field==='name'||field==='description'"></label>
            <label class="tp-field">Save to <select class="field" aria-label="Target scope" v-model="skill.scope"><option value="global">{{scopeLabel('global')}}</option><option v-for="s in scopes.filter(s=>s.writable && s.id!=='global')" :key="s.id" :value="s.id">{{scopeLabel(s.id)}}</option></select></label>
          </div>
          <label class="tp-field">Instructions <textarea class="field tp-area" v-model="skill.body" rows="12"></textarea></label>
          <div class="tp-acts"><button class="btn btn-ink" :disabled="busy">Create skill</button><button type="button" class="btn btn-soft" @click="creating=false">Cancel</button></div>
        </form>
        <form class="card tp-panel" @submit.prevent="saveTemplate" aria-labelledby="tp-nt-h">
          <h2 id="tp-nt-h">New template</h2>
          <label class="tp-field">Name <input class="field" v-model="templateName" required placeholder="e.g. runbook"></label>
          <label class="tp-field">Document body <textarea class="field tp-area" v-model="templateBody" rows="8" placeholder="# Title&#10;&#10;## When to use&#10;&#10;## Steps"></textarea></label>
          <div class="tp-acts"><button class="btn btn-line" :disabled="busy">Save template</button></div>
        </form>
      </template>

      <template v-else-if="page==='quality'">
        <h1 class="h1" id="h1" tabindex="-1">Quality</h1>
        <p class="lede">What the files say about your skills: broken documents, weak descriptions, copies that drifted apart. It does not certify safety or which copy an agent loads.</p>
        <template v-if="quality">
          <section v-if="claudeListing" class="card tp-panel claude-listing" aria-labelledby="tp-cl-h">
            <header class="tp-panel-h">
              <div><h2 id="tp-cl-h">What Claude Code sees</h2><p>The skill listing Claude Code builds from the copies this report observed.</p></div>
              <span class="tp-acts"><span :class="['pill', listingVerdict(claudeListing).tone]">{{ listingVerdict(claudeListing).text }}</span><span v-if="claudeListing.confidence==='partial'" class="pill off">Partial</span></span>
            </header>
            <p v-if="(claudeListing.partial_reasons||[]).length" class="claude-flags"><span v-for="(reason,i) in claudeListing.partial_reasons" :key="i" class="claude-reason">{{ reason }}</span></p>
            <div class="meter">
              <div class="ml"><span>{{ fmtN(claudeListing.listing_chars) }} of ~{{ fmtN(claudeListing.budget.budget_chars_estimate) }} characters</span><b class="num">{{ listingPct(claudeListing) }}%</b></div>
              <div class="track" role="img" :aria-label="listingAria(claudeListing)"><i :class="{warn: listingOver(claudeListing)}" :style="{width: listingFill(claudeListing)}"></i></div>
            </div>
            <p class="tp-fine">{{ claudeListing.budget.assumption }}</p>
            <p v-if="Number(claudeListing.chars_to_free)>0" class="claude-free"><b>Free about {{ fmtN(claudeListing.chars_to_free) }} characters.</b> Switching descriptions to name-only removes their text from the listing.</p>
            <div v-if="((claudeListing.name_only_candidates||{}).candidates||[]).length">
              <div class="tp-sec-h"><h3>Name-only candidates</h3><span class="tp-count num">{{ fmtN(claudeListing.name_only_candidates.total) }} total</span></div>
              <p class="tp-fine">Ranked by description size only. Claude Code drops descriptions starting with the skills you use least, which this tool can't see.</p>
              <ul class="tp-rows">
                <li v-for="c in claudeListing.name_only_candidates.candidates" :key="(c.path||'')+c.name" class="v2-tool-row claude-cand">
                  <span class="tp-row-main"><strong class="tp-mono">{{ c.name }}</strong><small>{{ fmtN(c.description_chars) }} description characters · frees {{ fmtN(c.freed_chars) }} characters</small></span>
                  <span class="claude-snippet"><code>{{ listingSnippet(c.name) }}</code><button type="button" class="btn btn-soft btn-sm" @click="copyListingSnippet(c.name)">Copy</button></span>
                </li>
              </ul>
              <p v-if="claudeListing.name_only_candidates.omitted" class="tp-fine">{{ fmtN(claudeListing.name_only_candidates.omitted) }} more candidates not shown.</p>
            </div>
            <div v-if="((claudeListing.over_cap||{}).count||0) > 0">
              <div class="tp-sec-h"><h3>Descriptions cut per skill</h3><span class="tp-count num">{{ fmtN(claudeListing.over_cap.count) }}</span></div>
              <p class="tp-fine">Descriptions longer than {{ fmtN(claudeListing.over_cap.max_description_chars || claudeListing.max_description_chars) }} characters are cut even within budget.</p>
              <p class="tp-mono tp-fine">{{ (claudeListing.over_cap.names||[]).join(', ') }}<span v-if="claudeListing.over_cap.omitted"> and {{ fmtN(claudeListing.over_cap.omitted) }} more</span></p>
            </div>
            <details class="tp-more claude-excluded">
              <summary>What this estimate leaves out</summary>
              <ul class="tp-rows"><li v-for="(count,key) in (claudeListing.excluded||{})" :key="key" class="v2-tool-row"><span>{{ listingExcludedLabel(key) }}</span><span class="tp-count num">{{ fmtN(count) }}</span></li></ul>
              <p class="tp-fine">{{ fmtN(claudeListing.instances_observed) }} instances observed · {{ fmtN(claudeListing.listed_skills) }} entries listed.</p>
            </details>
          </section>
          <p v-else class="tp-empty">No Claude Code skills were observed in this report, so the listing budget is not estimated.</p>
          <div class="tp-toolbar">
            <div class="seg" role="group" aria-label="Severity">
              <button v-for="s in ['all','error','warning','info']" :key="s" type="button" :aria-pressed="severity===s" @click="severity=s">{{severityNames[s]}} <span class="n">{{severityCounts[s]||0}}</span></button>
            </div>
            <label class="sr-only" for="tp-q">Search findings</label>
            <input id="tp-q" class="field tp-filter" v-model="search" type="search" placeholder="Search findings">
            <button type="button" class="btn btn-soft btn-sm" @click="loadQuality">Refresh</button>
          </div>
          <div v-if="(quality.degraded||[]).length" class="v2-tool-error"><b>Incomplete evidence.</b> <span v-for="(item,i) in quality.degraded" :key="i">{{human(item.section||item)}}: {{item.reason||'unavailable'}}. </span></div>
          <p class="tp-count" role="status">{{findings.length}} matching findings</p>
          <ul class="tp-findings">
            <li v-for="(f,idx) in findings" :key="idx">
              <details>
                <summary><span :class="['tp-sev', sevTone(f.severity)]" :title="human(f.severity)"><ic :name="sevIcon(f.severity)"></ic><span class="sr-only">{{human(f.severity)}}:</span></span><span class="tp-f-t">{{f.title}}</span><span class="tp-count" v-if="(f.instances||[]).length">{{f.instances.length}} {{f.instances.length===1?'copy':'copies'}}</span></summary>
                <div class="tp-f-b">
                  <p v-if="f.explanation">{{f.explanation}}</p>
                  <p v-if="f.recommendation" class="tp-rec"><b>Suggested:</b> {{f.recommendation}}</p>
                  <p v-if="f.confidence" class="tp-fine">Confidence: {{human(f.confidence)}}</p>
                  <ul class="tp-rows"><li v-for="i in f.instances" :key="i.scope+':'+(i.path||i.physical_path)" class="v2-tool-row"><span class="tp-row-main"><strong class="tp-mono">{{i.name}}</strong><small>{{scopeLabel(i.scope)}} · <span class="tp-mono">{{i.path||i.physical_path}}</span></small></span><button class="btn btn-line btn-sm" @click="inspectInstance(i)">Open</button></li></ul>
                  <details class="tp-more"><summary>Finding evidence</summary><pre>{{pretty(f.evidence)}}</pre></details>
                </div>
              </details>
            </li>
          </ul>
          <p v-if="!findings.length" class="tp-empty">Nothing matches this filter.</p>
          <details v-if="unavailableSignals.length" class="tp-more evidence-limits"><summary>{{unavailableSignals.length}} kinds of evidence are unavailable</summary><p v-for="(signal,i) in unavailableSignals" :key="i">{{human(signal.signal)}} — {{signal.explanation}} <span v-if="signal.count>1">({{signal.count}} instances)</span></p></details>
        </template>
        <p v-else-if="loading.qualityEnvelope" class="tp-empty">Reading hygiene evidence…</p>
        <p v-else class="tp-empty">Hygiene evidence is unavailable. <button type="button" class="btn btn-soft btn-sm" @click="loadQuality">Retry</button></p>

        <h2 class="tp-eyebrow tp-gap">Diagnostics</h2>
        <div class="tp-cards">
          <section class="card tp-mini" aria-labelledby="tp-d1">
            <h3 id="tp-d1">Validate a copy</h3><p>Check one document against the skill format.</p>
            <select class="field" aria-label="Instance to validate" v-model="validateTarget"><option value="">Choose a copy</option><option v-for="(r,i) in records" :key="i" :value="String(i)">{{r.name}} · {{scopeLabel(r.scope)}}</option></select>
            <button class="btn btn-line btn-sm" :disabled="validateTarget===''||busy" @click="validate">Validate</button>
            <details class="tp-more"><summary>By name and scope</summary><form class="tp-stack" @submit.prevent="validateNamed"><label class="tp-field">Skill name<input class="field" v-model="validationName" required></label><label class="tp-field">Validation scope<select class="field" aria-label="Validation scope" v-model="validationScope"><option v-for="s in scopes" :key="s.id" :value="s.id">{{scopeLabel(s.id)}}</option></select></label><button class="btn btn-soft btn-sm" :disabled="busy">Validate named skill</button></form></details>
          </section>
          <section class="card tp-mini" aria-labelledby="tp-d2">
            <h3 id="tp-d2">Doctor</h3><p>Compare the index with the files on disk and list anything out of step.</p>
            <button class="btn btn-line btn-sm" @click="showReport('doctor')">Run doctor</button>
          </section>
          <section class="card tp-mini" aria-labelledby="tp-d3">
            <h3 id="tp-d3">Context use</h3><p>Estimate how much of a model's window your skills would take if read in full.</p>
            <select class="field" aria-label="Context window" v-model="windowSize"><option value="claude">Claude</option><option value="claude-haiku">Claude Haiku</option><option value="gpt-5.6">GPT-5.6</option><option value="gpt-5">GPT-5</option><option value="gpt-4o">GPT-4o</option><option value="gemini">Gemini</option><option value="gemini-2m">Gemini 2M</option></select>
            <button class="btn btn-line btn-sm" @click="showReport('stats')">Statistics</button>
          </section>
        </div>
        <section v-if="report" class="card tp-panel" aria-live="polite" aria-labelledby="tp-rep-h">
          <header class="tp-panel-h"><div><h2 id="tp-rep-h">{{reportTitle}}</h2></div>
            <span v-if="reportKind==='validate'" :class="['pill', report.valid?'ok':'bad']">{{report.valid?'Valid':'Validation issues found'}}</span>
            <span v-if="reportKind==='doctor'" :class="['pill', report.ok===true?'ok':report.ok===false?'warn':'off']">Index consistency: {{report.ok===true?'No issues reported':report.ok===false?'Attention needed':'See details'}}</span></header>
          <template v-if="reportKind==='stats'">
            <div class="tp-stats"><div><b class="num">{{fmtN(report.all_total)}}</b><small>copies observed</small></div><div><b class="num">{{fmtN(report.all_tokens)}}</b><small>estimated tokens</small></div><div><b class="num">{{report.window_tokens ? (Math.round(1000*report.all_tokens/report.window_tokens)/10)+'%' : '—'}}</b><small>of the {{report.window}} window</small></div></div>
            <p class="tp-fine">{{report.has_tiktoken?'Counted with a tokenizer.':'Heuristic estimate (about four characters per token).'}} Not a guarantee of available context.</p>
            <ul class="tp-rows"><li v-for="s in report.scopes||[]" :key="s.id" class="v2-tool-row"><span>{{scopeLabel(s.id)}}</span><span class="tp-count num">{{fmtN(s.count)}} skills · {{fmtN(s.tokens)}} tokens</span></li></ul>
            <h3 v-if="(report.largest||[]).length" class="tp-eyebrow tp-gap">Largest</h3>
            <ul class="tp-rows"><li v-for="(r,i) in report.largest||[]" :key="i" class="v2-tool-row"><span class="tp-row-main"><strong class="tp-mono">{{r.name}}</strong><small>{{scopeLabel(r.scope)}} · {{fmtN(r.tokens)}} tokens</small></span><button class="btn btn-line btn-sm" @click="inspectInstance(r)">Open</button></li></ul>
          </template>
          <p v-if="report.degraded && report.degraded.length" class="tp-fine">Incomplete evidence: {{report.degraded.map(d=>human(d.section||d)).join(', ')}}.</p>
          <ul v-if="(report.issues||[]).length" class="tp-rows"><li v-for="(issue,i) in report.issues" :key="i" class="v2-tool-row"><span><span :class="['tp-sev', sevTone(issue.level||issue.severity)]"><ic :name="sevIcon(issue.level||issue.severity)"></ic></span> {{human(issue.level||issue.severity)}} · {{issue.message||issue}}</span></li></ul>
          <div v-if="reportKind==='doctor'">
            <div v-for="(value,key) in report" :key="key" v-show="Array.isArray(value) && value.length" class="tp-doctor">
              <h3>{{human(key)}} <span class="tp-count">{{Array.isArray(value)?value.length:''}}</span></h3>
              <p v-for="(row,i) in value" :key="i" class="tp-mono tp-fine">{{typeof row==='object'?pretty(row):row}}</p>
            </div>
            <p class="tp-fine"><a href="#/tools/settings">Index maintenance</a> rebuilds the index from the files.</p>
          </div>
          <details class="tp-more"><summary>Report details</summary><pre>{{pretty(report)}}</pre></details>
        </section>
      </template>

      <template v-else-if="page==='workspaces'">
        <h1 class="h1" id="h1" tabindex="-1">Workspaces</h1>
        <p class="lede">Where each agent looks for skills, and what a given project folder adds. This is declared evidence — which copy an agent actually loads stays unknown.</p>
        <form class="tp-search" @submit.prevent="loadWorkspace">
          <label class="sr-only" for="tp-proj">Project path</label>
          <input id="tp-proj" class="field tp-mono" v-model="project" placeholder="/absolute/path/to/a/project" aria-label="Project path">
          <button class="btn btn-ink">Inspect project</button>
        </form>
        <template v-if="workspace">
          <section v-if="(workspace.project||{}).path || (workspace.project||{}).status!=='not-requested'" class="card tp-panel" aria-labelledby="tp-po-h">
            <header class="tp-panel-h"><div><h2 id="tp-po-h">Project</h2><p class="tp-mono">{{(workspace.project||{}).path||'No path requested'}}</p></div><span :class="['pill', projectTone]">Status: {{human((workspace.project||{}).status)}}</span></header>
            <ul class="tp-rows"><li v-for="root in ((workspace.project||{}).skills_roots||[])" :key="root.path" class="v2-tool-row"><span class="tp-mono">{{root.path}}</span><span :class="['pill', root.exists?'ok':'off']">{{root.exists?'Found':'Not present'}}</span></li></ul>
          </section>
          <section class="tp-sec" aria-labelledby="tp-ad-h">
            <div class="tp-sec-h"><h2 id="tp-ad-h">Agents and their skill folders</h2></div>
            <ul class="tp-rows">
              <li v-for="adapter in workspace.adapters||[]" :key="adapter.id" class="tp-adapter">
                <div class="v2-tool-row">
                  <span class="tp-row-main"><strong>{{adapter.label}}</strong><small>Reload: {{adapter.reload||'not documented'}}</small></span>
                  <span class="tp-acts"><span v-if="adapter.status==='verified'" class="pill ok">Verified</span><span :class="['pill', precedenceTone(adapter)]" :title="(adapter.precedence||{}).notes">{{precedenceLabel(adapter)}}</span><button class="btn btn-line btn-sm" @click="consumer=adapter.id;explain()">Explain</button></span>
                </div>
                <details class="tp-more"><summary>Folders and notes</summary><p v-if="(adapter.precedence||{}).notes" class="tp-fine">{{(adapter.precedence||{}).notes}}</p><p v-for="(root,i) in adapter.candidate_roots" :key="i" class="tp-mono tp-fine">{{root.absolute_path||root.relative_path||root.scope||'unknown'}}</p></details>
              </li>
            </ul>
          </section>
        </template>
        <p v-else class="tp-acts"><button class="btn btn-soft" @click="loadWorkspace">Retry workspaces</button></p>
        <form class="tp-inline tp-gap" @submit.prevent="explain">
          <label class="tp-field">Consumer to explain <select class="field" v-model="consumer" required><option value="" disabled>Choose an agent</option><option v-for="a in (workspace&&workspace.adapters)||[]" :key="a.id" :value="a.id">{{a.label}}</option></select></label>
          <button class="btn btn-soft" :disabled="!consumer">Explain consumer</button>
        </form>
        <section v-if="report" class="card tp-panel" aria-live="polite" aria-labelledby="tp-wr-h">
          <header class="tp-panel-h"><div><h2 id="tp-wr-h">{{reportTitle}}</h2><p v-if="report.explain && report.explain.resolution">Resolution: {{human(report.explain.resolution)}}</p></div></header>
          <p v-if="report.degraded && report.degraded.length" class="tp-fine">Incomplete evidence: {{report.degraded.map(d=>human(d.section||d)).join(', ')}}.</p>
          <p v-for="(issue,i) in (report.issues||[])" :key="i">{{human(issue.level||issue.severity)}} · {{issue.message||issue}}</p>
          <details class="tp-more" open><summary>Report details</summary><pre>{{pretty(report)}}</pre></details>
        </section>
      </template>

      <template v-else-if="page==='settings'">
        <h1 class="h1" id="h1" tabindex="-1">Settings</h1>
        <p class="lede">Stored in this browser only.</p>
        <section class="card tp-panel" aria-labelledby="tp-ap-h">
          <h2 id="tp-ap-h">Appearance</h2>
          <div class="tp-set">
            <div class="tp-set-row"><label for="tp-theme"><b>Theme</b><small>System follows your OS (currently {{systemDark?'dark':'light'}}).</small></label><select id="tp-theme" class="field" aria-label="Theme" v-model="theme" @change="preference('skillsmgr-theme',theme)"><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></div>
            <div class="tp-set-row"><label for="tp-size"><b>Text size</b><small>Large raises body text across both interfaces.</small></label><select id="tp-size" class="field" aria-label="Text size" v-model="size" @change="preference('skillsmgr-text-size',size)"><option value="standard">Standard</option><option value="large">Large</option></select></div>
            <div class="tp-set-row"><label for="tp-loc"><b>Regional format</b><small>Numbers and dates: <span class="num">{{localePreview}}</span>. Does not translate the interface.</small></label><select id="tp-loc" class="field" aria-label="Regional format" v-model="locale" @change="preference('skillsmgr-locale',locale)"><option value="system">System</option><option value="en-US">English (US)</option><option value="en-GB">English (UK)</option><option value="en-IN">English (India)</option></select></div>
          </div>
          <p class="tp-fine">Reduced motion is {{reducedMotion?'on':'off'}} in your OS; animations follow it automatically.</p>
        </section>
        <section class="card tp-panel" aria-labelledby="tp-sc-h">
          <h2 id="tp-sc-h">Security scanner</h2>
          <p class="tp-fine">Optionally run NVIDIA SkillSpector on a skill while you review a registry fetch or an update. Its findings are shown beside the review and never block or allow anything. It must be installed separately (<code>uv tool install skillspector</code>).</p>
          <div class="tp-set">
            <div class="tp-set-row"><label for="tp-scan"><b>Scan during reviews</b><small v-if="externalScan==='off'">Off. Nothing extra runs.</small><small v-else-if="externalScan==='static'">Pattern checks on this machine. Dependency names the skill declares may be sent to api.osv.dev.</small><small v-else>Adds SkillSpector's LLM review with your own key. Skill file contents are sent to that provider.</small></label><select id="tp-scan" class="field" aria-label="Scan during reviews" v-model="externalScan" @change="preference('skillsmgr-external-scan',externalScan)"><option value="off">Off</option><option value="static">Static checks</option><option value="llm">Static + your LLM key</option></select></div>
          </div>
          <p v-if="externalScan==='llm'" class="tp-fine">Bring your own key: set <code>SKILLSPECTOR_PROVIDER</code> and that provider's key (for example <code>ANTHROPIC_API_KEY</code>) in the terminal before starting <code>skills-mgr webui</code>. The key is passed only to SkillSpector, only for scans you ask for, and is never stored or shown here.</p>
        </section>
        <section class="card tp-panel" aria-labelledby="tp-ix-h">
          <h2 id="tp-ix-h">Index maintenance</h2>
          <p class="tp-fine">The files on disk are the truth; the index is a cache. Neither action edits a skill or repairs a broken document.</p>
          <div class="tp-set">
            <div class="tp-set-row"><span><b>Resync index</b><small>Add, refresh and drop rows to match the folders. Safe to run any time.</small></span><button class="btn btn-line" :disabled="busy" @click="maintain('resync')">Resync index</button></div>
            <div class="tp-set-row"><span><b>Rebuild index</b><small>Delete the index and read every folder again.</small></span><button class="btn btn-line" :disabled="busy" @click="maintain('rebuild')">Rebuild index</button></div>
          </div>
        </section>
        <p class="tp-fine tp-gap">Prefer the previous interface? <a href="/classic/">Open the classic view</a>.</p>
      </template>

      <template v-else-if="page==='source-update'">
        <h1 class="h1" id="h1" tabindex="-1">Update from folder</h1>
        <p class="lede">Replace one exact copy of a skill with a newer folder, after reviewing every change. A snapshot of the whole folder is kept so you can roll back.</p>
        <ol class="tp-steps">
          <li :class="{done: !!selected}">
            <h2>Choose the copy to update</h2>
            <select v-if="!target" class="field" aria-label="Exact instance" v-model="chosen" :disabled="busy||!!sourceReview"><option value="">Choose a copy</option><option v-for="(r,i) in records" :value="String(i)" :key="i">{{r.name}} · {{scopeLabel(r.scope)}}</option></select>
            <p v-if="selected" class="tp-target"><strong class="tp-mono">{{selected.name}}</strong> in {{scopeLabel(selected.scope)}}<small class="tp-mono">{{selected.physical_path||selected.path}}</small></p>
            <p v-if="selected && !selectedWritable" class="v2-tool-error">This copy can't be written by the app. Choose a copy in a writable folder.</p>
          </li>
          <li :class="{done: !!sourceReview}" v-if="selectedWritable">
            <h2>Pick the new folder, or roll back</h2>
            <form v-if="!sourceReview" class="tp-stack" @submit.prevent="prepareSource">
              <label class="tp-drop tp-drop-sm"><input type="file" class="sr-only" webkitdirectory directory multiple aria-label="Candidate folder" @change="files=Array.from($event.target.files)"><b>{{ files.length ? files.length+' files selected' : 'Choose candidate folder' }}</b></label>
              <div class="tp-acts"><button class="btn btn-ink" :disabled="busy||!files.length">Review candidate</button><button type="button" class="btn btn-soft" @click="loadSnapshots">Show snapshots</button></div>
            </form>
            <div v-if="snapshots && !sourceReview">
              <p v-if="!(Array.isArray(snapshots)?snapshots:snapshots.snapshots||[]).length" class="tp-empty">No snapshots kept for this copy yet.</p>
              <ul class="tp-rows"><li class="v2-tool-row" v-for="s in (Array.isArray(snapshots)?snapshots:snapshots.snapshots||[])" :key="s.snapshot_id"><span class="tp-row-main"><strong>{{when(s.created_at)}}</strong><small class="tp-mono">{{s.snapshot_id}}</small></span><span class="tp-acts"><span v-if="s.available===false" class="pill off">Unavailable</span><button class="btn btn-line btn-sm" :disabled="busy||s.available===false" @click="snapshotReview(s)">Review rollback</button></span></li></ul>
            </div>
          </li>
          <li v-if="sourceReview">
            <h2>Review and apply</h2>
            <section class="card tp-panel" aria-label="Review candidate">
              <header class="tp-panel-h"><div><p>Review {{sourceReview.review_id||'not persisted'}} · expires {{when(sourceReview.review_expires_at)}}</p></div><span :class="['pill', sourceReview.validation && sourceReview.validation.valid ? 'ok':'bad']">{{sourceReview.validation && sourceReview.validation.valid ? 'Valid' : 'Blocked'}}</span></header>
              <h3>Changes <span class="tp-count">{{((sourceReview.comparison||{}).changed_files||[]).length}} files</span></h3>
              <p v-if="!((sourceReview.comparison||{}).changed_files||[]).length" class="tp-empty">No file changes — nothing to apply.</p>
              <details v-for="change in ((sourceReview.comparison||{}).changed_files||[])" :key="change.path" class="tp-more"><summary><span :class="['tp-chg', change.status]">{{human(change.status)}}</span> <span class="tp-mono">{{change.path}}</span><span v-if="change.diff_truncated" class="tp-count"> · diff truncated</span></summary><p class="tp-fine">{{change.explanation}}</p><pre v-if="change.diff">{{change.diff}}</pre></details>
              <template v-if="((sourceReview.validation||{}).errors||[]).length || ((sourceReview.validation||{}).warnings||[]).length"><h3>Validation</h3>
              <p v-for="(issue,i) in ((sourceReview.validation||{}).errors||[])" :key="'e'+i" class="tp-issue bad">{{issue.message||issue}}</p>
              <p v-for="(issue,i) in ((sourceReview.validation||{}).warnings||[])" :key="'w'+i" class="tp-issue warn">Warning: {{issue.message||issue}}</p></template>
              <h3>Advisory risk</h3>
              <p class="tp-fine">{{(sourceReview.risk||{}).policy||'Risk findings are evidence, not a safety verdict.'}}</p>
              <p v-for="(f,i) in ((sourceReview.risk||{}).findings||[])" :key="i" class="tp-issue warn">{{f.message||f}}</p>
${scanPanel('sourceReview.external_scan')}
              <h3>Recovery</h3>
              <p class="tp-fine">The whole folder is snapshotted before replacement. On/off state after applying: {{sourceReview.activation_preserved ? (sourceReview.resulting_disabled ? 'off' : 'on') : 'not confirmed'}}.</p>
              <dl class="tp-dl"><dt>Current tree</dt><dd><code>{{sourceReview.current_hash||'Not returned'}}</code></dd><dt>Candidate tree</dt><dd><code>{{sourceReview.candidate_hash||'Not returned'}}</code></dd></dl>
              <details class="tp-more"><summary>Raw review evidence</summary><pre>{{pretty(sourceReview)}}</pre></details>
              <div class="tp-confirm">
                <label class="tp-check"><input type="checkbox" v-model="trust"> I approve this exact reviewed change</label>
                <span class="tp-acts"><button class="btn btn-ink" :disabled="busy||!trust||sourceReview.review_state!=='pending'||!sourceReview.validation||sourceReview.validation.valid!==true||!((sourceReview.comparison||{}).changed_files||[]).length" @click="applySource">Apply reviewed change</button><button class="btn btn-soft" :disabled="busy" @click="cancelSource">Cancel review</button></span>
              </div>
            </section>
          </li>
        </ol>
        <section v-if="sourceSuccess" class="card tp-panel" aria-live="polite"><header class="tp-panel-h"><div><h2>Change applied</h2><p>A snapshot of the previous folder was kept.</p></div><span class="pill ok">Done</span></header><details class="tp-more"><summary>Details</summary><pre>{{pretty(sourceSuccess)}}</pre></details></section>
      </template>

      <template v-else-if="page==='recovery-extra'">
        <div class="tp-sec-h tp-gap"><h2>History and text snapshots</h2><a class="tp-link" href="#/tools/source-update">Whole-folder snapshots →</a></div>
        <p class="tp-fine">Text rollback restores an older skill document only; companion files and on/off state are not restored.</p>
        <form class="tp-inline" @submit.prevent="loadHistory">
          <label class="tp-field">Skill name <input class="field" v-model="historyName" placeholder="All skills" list="tp-names"></label>
          <datalist id="tp-names"><option v-for="n in skillNames" :key="n" :value="n"></option></datalist>
          <label class="tp-field">Scope <select class="field" aria-label="Scope" v-model="historyScope"><option value="global">{{scopeLabel('global')}}</option><option v-for="s in scopes.filter(s=>s.id!=='global')" :key="s.id" :value="s.id">{{scopeLabel(s.id)}}</option></select></label>
          <button class="btn btn-soft">Load history</button>
        </form>
        <div v-if="history" class="card tp-panel tp-flush">
          <p v-if="!history.length" class="tp-empty">No history recorded.</p>
          <ul class="tp-rows"><li class="v2-tool-row" v-for="(row,i) in history" :key="row.id||i"><span class="tp-hist"><strong class="tp-mono">{{row.name}}</strong><span class="tp-act">{{human(row.action)}}</span></span><time class="tp-count" :datetime="row.at">{{when(row.at)}}</time></li></ul>
        </div>
        <template v-if="textSnapshots">
          <h3 class="tp-eyebrow tp-gap">Text snapshots</h3>
          <p v-if="!(textSnapshots.snapshots||[]).length" class="tp-empty">No text snapshots kept for this skill.</p>
          <ul class="tp-rows"><li v-for="s in (textSnapshots.snapshots || [])" :key="typeof s==='string'?s:JSON.stringify(s)" class="v2-tool-row"><span class="tp-mono">{{s}}</span><button class="btn btn-line btn-sm" :disabled="busy||!textSnapshotTarget||textSnapshotTarget.name!==historyName||textSnapshotTarget.scope!==historyScope" @click="rollbackText(typeof s==='string'?s:(s.name||s.snapshot))">Restore text snapshot</button></li></ul>
        </template>
      </template>

      <section v-if="result && !(page==='install' && tab==='registry' && Array.isArray(result.data))" class="card tp-panel" aria-live="polite" aria-labelledby="tp-result-h">
        <header class="tp-panel-h"><div><h2 id="tp-result-h">Result</h2><p v-if="result.message">{{result.message}}</p></div>
          <span v-if="result.partial" class="pill warn">Partial</span><span v-else-if="result.exit_code!=null" :class="['pill', result.exit_code===0?'ok':'bad']">Exit code: {{result.exit_code}}</span></header>
        <p v-if="result.command" class="tp-cmd"><code>{{result.command}}</code></p>
        <pre v-if="result.stdout||result.stderr">{{result.stdout}}{{result.stderr ? String.fromCharCode(10)+result.stderr : ''}}</pre>
        <ul class="tp-rows"><li v-for="(row,i) in (result.results||[])" :key="i" class="v2-tool-row">
          <span class="tp-row-main"><strong class="tp-mono">{{row.name||((row.target||{}).name)||'Target'}}</strong><small>{{scopeLabel(row.scope||((row.target||{}).scope)||'')}} · <span class="tp-mono">{{row.path||((row.target||{}).path)||''}}</span></small></span>
          <span>{{row.result==='already-set'?'Already set; no change':row.status}} {{row.error||row.message||''}}</span>
        </li></ul>
        <p v-if="result.partial" class="v2-tool-error">Partial result: successful changes remain; some targets failed.</p>
        <p v-if="result.imported">{{result.imported.length}} imported: {{Array.isArray(result.imported)?result.imported.join(', '):result.imported}}</p>
        <p v-if="result.skipped">{{result.skipped.length}} skipped: {{Array.isArray(result.skipped)?result.skipped.join(', '):result.skipped}}</p>
        <details class="tp-more"><summary>Result details</summary><pre>{{pretty(result)}}</pre></details>
      </section>
        </div>
      </div>
    </section>`
  };
})();
