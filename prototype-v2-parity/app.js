const {
   createApp 
} = Vue;

createApp({
  data(){
    return {
      qualitySkillName: 'code-review',
qualityScope: 'Codex',
qualityValidation: null,
qualityWindow: 128000,
qualityDoctorRows: [
  {
    title: 'Index entry has no observed file', kind: 'Missing on disk', scope: 'Global library', status: 'Review',
    evidence: 'The sample index lists old-review, but the global skill folder does not contain that file.',
    path: '~/.local/share/skills-manager/skills/old-review/SKILL.md', link: 'settings'
  },
  {
    title: 'Indexed content is out of date', kind: 'Stale index', scope: 'Global library', status: 'Review',
    evidence: 'The observed code-review file differs from the last indexed content. The disk copy is authoritative.',
    path: '~/.local/share/skills-manager/skills/code-review/SKILL.md', link: 'settings'
  },
  {
    title: 'Two copies have different content', kind: 'Copy divergence', scope: 'Claude Code', status: 'Review',
    evidence: 'code-review exists in both Codex and Claude Code, but the observed contents differ. This alone does not establish which is preferred.',
    path: '~/.claude/skills/code-review/SKILL.md', link: 'map'
  }
],
qualitySizeRows: [
  { name: 'code-review', scope: 'Codex', path: '~/.codex/skills/code-review/SKILL.md', characters: 6400 },
  { name: 'incident-notes', scope: 'Codex', path: '~/.codex/skills/incident-notes/SKILL.md', characters: 3200 },
  { name: 'frontend-patterns', scope: 'Claude Code', path: '~/.claude/skills/frontend-patterns/SKILL.md', characters: 18420 },
  { name: 'code-review', scope: 'Claude Code', path: '~/.claude/skills/code-review/SKILL.md', characters: 6800 }
],
      mobileMenu: false, commandOpen: false, commandQuery: '', formError: '',
      runnerMode: 'copy', installTarget: 'Codex', registryMode: 'Search', allowCached: false,
      sourceScenario: 'Ready', chosenFolderFiles: [], candidateFiles: [],
      profileDescription: '', profileAdditional: '', profileTargets: ['Codex', 'Claude Code'], profilePicked: [],
      profileDescriptions: {'Frontend review': 'A review set for changes to browser interfaces.', Writing: 'Writing and review helpers.'},
      profileEdit: false, profileScopeMap: {'Frontend review':['Codex','Claude Code'], Writing:[]}, batchState: 'Ready', bulkReviewed: false, bulkTargets: ['Claude Code'], bulkOverwrite: false,
      trashItems: ['meeting-notes', 'old-review'], historyName: '', archiveName: '',
      templateBodies: {'Blank skill': '# Instructions\n\nDescribe the workflow.\n', 'Review checklist': '# Review checklist\n\n- Read the change.\n- Check keyboard navigation.\n- Record evidence and open questions.\n'},
      skillBody: '# Instructions\n\nDescribe the workflow.\n', category: '', version: '', license: '', compatibility: '', allowedTools: '', editingId: null,
      editorView: 'Write', pendingEffect: null, reviewFacts: [], reviewDiff: false, resultRows: [],
      sourceSnapshot: true, dialogKind: '',
      page:'tools',mainNav:[['home','Home'],['skills','Skills'],['map','Sync map'],['inbox','Inbox'],['recovery','Recovery']],toolNav:[['install','Install'],['profiles','Profiles'],['quality','Quality'],['workspaces','Workspaces'],['templates','Templates'],['settings','Settings']],groups:[{
        title:'Add & organize',note:'Bring skills in and arrange them for your work.',items:[{
          name:'Install',desc:'Find a skill or bring one from a folder.',href:'#/tools/install'
        },{
          name:'Profiles',desc:'Save a set of skills for a particular job.',href:'#/tools/profiles'
        },{
          name:'Templates',desc:'Start a new skill from a reusable structure.',href:'#/tools/templates'
        }]
      },{
        title:'Inspect',note:'Understand what is present and where it is found.',items:[{
          name:'Quality',desc:'Review findings, validation and diagnostics.',href:'#/tools/quality'
        },{
          name:'Workspaces',desc:'Inspect project discovery and agent consumers.',href:'#/tools/workspaces'
        }]
      },{
        title:'Maintain',note:'Care for your library and preferences.',items:[{
          name:'Recovery',desc:'Review trash, history, snapshots and backups.',href:'#/recovery'
        },{
          name:'Settings',desc:'Adjust appearance, formats and the index.',href:'#/tools/settings'
        }]
      }],installTab:'Registry',installState:'Ready',registryQuery:'',registry:[{
        name:'code-review',desc:'A structured approach to reviewing changes.',source:'github.com/example/skills',version:'v1.4.0'
      },{
        name:'web-accessibility',desc:'Find barriers in web interfaces.',source:'github.com/example/skills',version:'v2.1.0'
      },{
        name:'incident-notes',desc:'Capture a clear record during an incident.',source:'github.com/example/operations',version:'v1.0.2'
      }],folderPicked:false,pkg:'npx',runnerAgent:'codex',runnerScope:'global',runnerSource:'example/skills',runnerFilter:'',dryRun:true,listOnly:false,profiles:['Frontend review','Writing'],profileForm:false,profileName:'',profileMembers:{
        
      },profile:'Frontend review',profileState:'Ready',members:[['code-review','Codex · ~/.codex/skills/code-review','Found'],['web-accessibility','Claude Code · ~/.claude/skills/web-accessibility','Missing'],['frontend-patterns','Codex and Claude Code','Copies differ']],qualityTab:'Findings',qualityState:'Ready',qualityQuery:'',severity:'All severities',findings:[{
        title:'Frontmatter could not be parsed',name:'incident-notes',scope:'Codex',severity:'Error',evidence:'Line 4 is missing a closing quote. The description cannot be read.',path:'~/.codex/skills/incident-notes/SKILL.md'
      },{
        title:'Large skill body',name:'frontend-patterns',scope:'Claude Code',severity:'Warning',evidence:'The body is 18,420 characters. Consider moving reference material to a separate file.',path:'~/.claude/skills/frontend-patterns/SKILL.md'
      },{
        title:'Copies differ',name:'code-review',scope:'Codex and Claude Code',severity:'Info',evidence:'The two discovered copies have different content.',path:'~/.codex/skills/code-review/SKILL.md'
      }],workspacePath:'/projects/skills-manager',workspaceState:'Ready',templates:['Blank skill','Review checklist'],template:'Blank skill',templateCreate:false,templateUse:false,newTemplate:'',templateMarkdown:'# Instructions\n',newSkillName:'',newSkillDescription:'',newSkillTarget:'Global library',theme:'system',textSize:'standard',locale:'',skillSearch:'',tag:'All tags',skillView:'Instances',selected:[],editSkill:false,skills:[{
        id:'1',name:'code-review',desc:'Review changes for correctness and risk.',scope:'Codex',path:'~/.codex/skills/code-review/SKILL.md',state:'Enabled',tags:['review']
      },{
        id:'2',name:'code-review',desc:'Review changes for correctness and risk.',scope:'Claude Code',path:'~/.claude/skills/code-review/SKILL.md',state:'Enabled',tags:['review']
      },{
        id:'3',name:'frontend-patterns',desc:'Build maintainable web interfaces.',scope:'Codex',path:'~/.codex/skills/frontend-patterns/SKILL.md',state:'Disabled',tags:['frontend']
      }],recoveryTab:'Trash',recoveryState:'Ready',historyScope:'All scopes',importType:'Regular backup',overwrite:false,message:'',result:'',tagOperation:'Add',tagName:'',reviewRows:[],dialogTitle:'',dialogText:'',dialogDetail:'',dialogAction:'Continue',dialogNeedsCheck:false,dialogBlocked:'',confirmed:false,opener:null
    };
    
  },computed:{
qualityVisibleFindings() {
  if (this.qualityState === 'Empty') return [];
  return this.filteredFindings.filter(f => this.qualityState !== 'Partial' || f.scope === 'Codex');
},
qualityVisibleDoctor() {
  return this.qualityDoctorRows.filter(d => this.qualityState !== 'Partial' || d.scope !== 'Claude Code');
},
qualityVisibleSizes() {
  return this.qualitySizeRows.filter(s => this.qualityState !== 'Partial' || s.scope === 'Codex');
},
qualityScopeStats() {
  const totals = {};
  for (const s of this.qualityVisibleSizes) {
    if (!totals[s.scope]) totals[s.scope] = { scope: s.scope, count: 0, characters: 0 };
    totals[s.scope].count++;
    totals[s.scope].characters += s.characters;
  }
  return Object.values(totals).map(r => {
    const tokens = Math.ceil(r.characters / 4);
    return { ...r, tokens, percent: ((tokens / this.qualityWindow) * 100).toFixed(1) };
  });
},
qualityLargest() {
  return [...this.qualityVisibleSizes].sort((a, b) => b.characters - a.characters);
},
    isTool(){
      return this.page==='tools'||this.toolNav.some(n=>n[0]===this.page)
    },filteredRegistry(){
      const rows=this.registry.filter(s=>(s.name+' '+s.desc).toLowerCase().includes(this.registryQuery.toLowerCase())); return this.registryMode==='Curated'?rows.filter(s=>s.name!=='incident-notes'):this.registryMode==='Leaderboard'?[...rows].reverse():rows;
    },filteredFindings(){
      return this.findings.filter(f=>(this.severity==='All severities'||f.severity===this.severity)&&(f.title+' '+f.name).toLowerCase().includes(this.qualityQuery.toLowerCase()))
    },filteredSkills(){
      return this.skills.filter(s=>(s.name+' '+s.desc+' '+s.path).toLowerCase().includes(this.skillSearch.toLowerCase())&&(this.tag==='All tags'||(this.tag==='Untagged'?!s.tags.length:s.tags.includes(this.tag))))
    },command(){
      const quote = (value) => "'" + value.replace(/'/g, "'\\''") + "'";
      return `${this.pkg} skills add ${quote(this.runnerSource)} -a ${this.runnerAgent}${this.runnerScope==='global'?' -g':''}${this.runnerMode==='copy'?' --copy':''}${this.listOnly?' -l':''}${this.runnerFilter?' -s '+quote(this.runnerFilter):''}`
    },formatPreview(){
      return new Intl.DateTimeFormat(this.locale||undefined,{
        dateStyle:'long'
      }).format(new Date(2026,10,6))+' · '+new Intl.NumberFormat(this.locale||undefined).format(1234567.89)
    },systemDark(){
      return matchMedia('(prefers-color-scheme: dark)').matches
    },reducedMotion(){
      return matchMedia('(prefers-reduced-motion: reduce)').matches
    },visibleHistory(){
      let rows=[['code-review updated','Codex · source review','Today'],['meeting-notes removed','Global · moved to trash','Yesterday']];
      return rows.filter(r=>(this.historyScope==='All scopes'||r[1].startsWith(this.historyScope))&&(!this.historyName||r[0].includes(this.historyName)))
    }, previewHtml() {
      return SkillsV2Model.renderDoc(this.skillBody);
    }, allTags() {
      return [...new Set(this.skills.flatMap(s => s.tags))].sort();
    }, hiddenSelected() {
      return this.selected.filter(id => !this.filteredSkills.some(s => s.id === id)).length;
    }, currentMembers() {
      if (this.profile === 'Frontend review' && !this.profileMembers[this.profile]) return this.members;
      return this.profileMembers[this.profile] || [];
    }, profileInstanceRows() {
      const rows=[]; for(const member of this.currentMembers) for(const scope of (this.profileScopeMap[this.profile]||[])) { const copy=this.skills.find(s=>s.name===member[0]&&s.scope===scope); const siblings=this.skills.filter(s=>s.name===member[0]&&(this.profileScopeMap[this.profile]||[]).includes(s.scope)); const differs=new Set(siblings.map(s=>s.body).filter(Boolean)).size>1; rows.push({name:member[0],scope,path:copy?.path||this.scopeRoot(scope)+'/'+member[0]+'/SKILL.md',status:!copy?'Missing':copy.state==='Disabled'?'Disabled':copy.state==='Invalid'?'Invalid':differs?'Copies differ':'Observed'}); } return rows;
    }, templateContent() {
      return this.templateBodies[this.template] || '';
    }, commandResults() {
      return [...this.toolNav, ['skills', 'Skills'], ['recovery', 'Recovery']].filter(n => n[1].toLowerCase().includes(this.commandQuery.toLowerCase()));
    }
  },methods:{
runQualityValidation() {
  const name = this.qualitySkillName.trim().toLowerCase();
  const scope = this.qualityScope;
  const root = scope === 'Codex' ? '~/.codex/skills/' : '~/.claude/skills/';
  const path = root + name + '/SKILL.md';
  const available = this.qualityState !== 'Empty' &&
    !(this.qualityState === 'Partial' && scope === 'Claude Code') &&
    this.qualitySizeRows.some(s => s.name === name && s.scope === scope);
  if (!available) {
    this.qualityValidation = {
      path, status: 'Unavailable', checks: [
        ['Instance', 'No readable sample instance found for this name and scope.', 'Unknown']
      ]
    };
  } else if (name === 'incident-notes') {
    this.qualityValidation = {
      path, status: 'Invalid', checks: [
        ['File', 'The sample file is readable.', 'Pass'],
        ['Frontmatter', 'Line 4 has a missing closing quote.', 'Error'],
        ['Required fields', 'Cannot evaluate fields until frontmatter parses.', 'Unknown']
      ]
    };
  } else {
    this.qualityValidation = {
      path, status: 'Valid structure', checks: [
        ['File', 'The sample file is readable.', 'Pass'],
        ['Frontmatter', 'The sample frontmatter parses.', 'Pass'],
        ['Required fields', 'Name and description are present.', 'Pass']
      ]
    };
  }
},
    go(p){
      location.hash='#/'+p
    },route(){
      let parts=location.hash.slice(2).split('/');
      const next = parts[0]==='tools'?(parts[1]||'tools'):(parts[0]||'tools');
      if (this.editSkill && next !== 'skills' && !window.confirm('Discard the unsaved sample skill?')) {
        location.hash = '#/skills'; return;
      }
      this.editSkill = false;
      this.page = [...this.mainNav, ...this.toolNav, ['tools']].some(n => n[0] === next) ? next : 'tools';
      this.mobileMenu = false;
      document.title = (this.page === 'tools' ? 'Tools & settings' : [...this.mainNav,...this.toolNav].find(n=>n[0]===this.page)?.[1]) + ' · Skills Manager design preview';
      this.$nextTick(() => { window.scrollTo(0, 0); document.querySelector('h1')?.focus({preventScroll: true}); });
    },announce(s){
      this.message=s;
      clearTimeout(this.timer);
      this.timer=setTimeout(()=>this.message='',5000)
    },openDialog(title,text,detail,action,check=false,blocked=''){
      this.pendingEffect = null; this.reviewFacts = []; this.reviewDiff = false; this.dialogKind = '';
      this.opener=document.activeElement;
      this.dialogTitle=title;
      this.dialogText=text;
      this.dialogDetail=detail;
      this.dialogAction=action;
      this.dialogNeedsCheck=check;
      this.dialogBlocked=blocked;
      this.confirmed=false;
      this.$nextTick(()=>this.$refs.dialog.showModal())
    },closeDialog(){
      this.$refs.dialog.close()
    },dialogClosed(){
      if(this.opener?.isConnected&&!this.opener.disabled)this.opener.focus();
      else document.querySelector('h1')?.focus({preventScroll:true});
    },finishDialog(){
      if (this.dialogBlocked || (this.dialogNeedsCheck && !this.confirmed)) return;
      let title=this.dialogTitle;
      if(this.dialogKind==='Sync'&&!this.bulkReviewed)return;
      const failedId=this.batchState==='Partial'?this.reviewRows[this.reviewRows.length-1]:null;
      if(title==='Delete profile'){
        this.profiles=this.profiles.filter(p=>p!==this.profile);
        this.profile=this.profiles[0]||''
      }if(title==='Review enable')this.skills.forEach(s=>{
        if(this.reviewRows.includes(s.id)&&s.id!==failedId&&s.state!=='Invalid')s.state='Enabled'
      });
      if(title==='Review disable')this.skills.forEach(s=>{
        if(this.reviewRows.includes(s.id)&&s.id!==failedId&&s.state!=='Invalid')s.state='Disabled'
      });
      if(title==='Review remove')this.skills=this.skills.filter(s=>!this.reviewRows.includes(s.id)||s.id===failedId);
      if(title==='Review tag')this.skills.forEach(s=>{
        if(this.reviewRows.some(id=>this.skills.find(x=>x.id===id)?.name===s.name)){
          if(this.tagOperation==='Add'&&!s.tags.includes(this.tagName))s.tags.push(this.tagName);
          if(this.tagOperation==='Remove')s.tags=s.tags.filter(t=>t!==this.tagName)
        }
      });
      this.resultRows = [];
      this.result = this.dialogAction + ' completed in sample data. No files changed.';
      if (this.pendingEffect) this.pendingEffect();
      if (['Review enable', 'Review disable', 'Review remove'].includes(title)) this.selected = [];
      this.closeDialog()
    },reviewInstall(name,source='registry'){
      let blocked=this.installState==='Blocked'?'Blocked: the target is outside the allowed root.':this.installState==='Expired'?'Review expired. Refresh the source before continuing.':'';
      this.openDialog('Review '+name,'Review this sample artifact and its destination. Instructions and scripts in a source are untrusted.', 'Add SKILL.md\nAdd references/checklist.md\n\nValidation: readable frontmatter; canonical name.\nAdvisory risk: includes instructions and reference files. No safety guarantee.', 'Simulate install',true,blocked);
      this.reviewFacts = [['Source', source === 'registry' ? 'github.com/example/skills (sample)' : 'Local folder · filename preview only'], ['Destination', this.installTarget + ' · ' + this.scopeRoot(this.installTarget) + '/' + name], ['Artifact', 'SHA-256 9e3d…c72a · example identifier'], ['Review', 'a84c129 · expires in 10 minutes (sample)']];
      this.pendingEffect = () => {
        this.result = name + ' installed into the sample ' + this.installTarget + ' folder.';
        if (!this.skills.some(s => s.name === name && s.scope === this.installTarget)) this.skills.push({id:String(Date.now()),name,desc:'Imported sample skill.',scope:this.installTarget,path:this.scopeRoot(this.installTarget)+'/'+name+'/SKILL.md',state:'Enabled',tags:[]});
      };
    },copyCommand(){
      if(navigator.clipboard)navigator.clipboard.writeText(this.command).then(()=>this.announce('Command copied.')).catch(()=>this.announce('Copy unavailable; select the command above.'));
      else this.announce('Copy unavailable; select the command above.')
    },newProfile(){
      let n=this.profileName.trim();
      if (!n || (this.profiles.includes(n) && !this.profileEdit)) { this.formError = 'Choose a unique profile name.'; return; }
      if(n){
        const desired=[...new Set([...this.profilePicked,...this.profileAdditional.split(',').map(n=>n.trim()).filter(Boolean)])];
        if(desired.some(name=>!/^[a-z0-9][a-z0-9-]*$/.test(name))){this.formError='Skill names use lowercase letters, numbers and hyphens.';return;}
        if (!this.profiles.includes(n)) this.profiles.push(n);
        this.profileMembers[n] = desired.map(name => {
          const copies = this.skills.filter(s => s.name === name && this.profileTargets.includes(s.scope));
          return [name, this.profileTargets.join(', ') || 'No targets', copies.length ? 'Observed' : 'Missing'];
        });
        this.profileDescriptions[n] = this.profileDescription; this.profileScopeMap[n]=[...this.profileTargets];
        this.profile=n;
        this.profileName='';
        this.profileForm=false;
        this.profileEdit=false; this.formError='';
        this.result='Profile '+n+' added to sample data.'
      }
    },deleteProfile(){
      this.openDialog('Delete profile','This removes the sample profile only, not its skills.',this.profile,'Simulate delete')
    },reviewProfile(){
      const names = new Set(this.currentMembers.map(m=>m[0]));
      const targets = this.skills.filter(s => names.has(s.name) && (this.profileScopeMap[this.profile]||[]).includes(s.scope));
      this.openDialog('Review enable-only set','Only observed copies are included. Missing skills are not installed; other skills are not disabled. This is a per-target operation, not a transaction.',targets.map(s=>s.name+' · '+s.scope+'\n'+s.path+'\n'+(s.state==='Enabled'?'Already enabled':'Will enable')).join('\n\n'), 'Simulate enable');
      this.pendingEffect = () => {
        this.resultRows = targets.map((s,i) => ({name:s.name+' · '+s.scope, state:this.profileState==='Partial'&&i===targets.length-1?'Failed · target changed':s.state==='Enabled'?'Already enabled':'Enabled'}));
        targets.forEach((s,i) => {if (!(this.profileState==='Partial'&&i===targets.length-1)) s.state='Enabled';});
        this.result='Profile result · '+(this.profileState==='Partial'?'partially applied. Review failed targets below.':'all observed targets processed. Missing members were skipped.');
      };
    },inspectWorkspace(){
      this.workspaceState=this.workspacePath.startsWith('/projects/')&&!this.workspacePath.split('/').includes('..')?'Ready':'Outside root'
    },saveTemplate(){
      if (!this.newTemplate.trim() || this.templates.includes(this.newTemplate.trim())) { this.formError='Choose a unique template name.'; return; }
      this.newTemplate=this.newTemplate.trim(); this.templateBodies[this.newTemplate]=this.templateMarkdown;
      this.templates.push(this.newTemplate);
      this.template=this.newTemplate;
      this.newTemplate='';
      this.templateCreate=false;
      this.announce('Stored template added to sample data.')
    },previewCreate(){
      this.reviewSkill();
    },maintenance(action){
      this.openDialog(action+' index',action+' affects the rebuildable global library index. Skill files are not modified.','Scope: global library','Simulate '+action.toLowerCase())
    },reviewBulk(action){
      let rows=this.skills.filter(s=>this.selected.includes(s.id));
      const prior=Object.fromEntries(rows.map(s=>[s.id,s.state]));
      this.reviewRows=rows.map(s=>s.id);
      let note=action==='Tag'?`Tags apply to every copy of these ${new Set(rows.map(s=>s.name)).size} skill names.`:'Targets and options are fixed for this review; source contents and before-state are not frozen. Results may be partial.';
      if(action==='Remove') note+=' Agent-scope trash cannot be restored in-app; there is no automatic Undo for this removal.';
      this.openDialog('Review '+action.toLowerCase(),note,rows.map(s=>`${s.name} · ${s.scope}\n${s.path}${action==='Enable'&&s.state==='Enabled'?' — already enabled':''}`).join('\n\n'),'Simulate '+action.toLowerCase());
      this.dialogKind=action;
      this.bulkReviewed=false;
      if(this.batchState==='Stale')this.dialogBlocked='One of the reviewed target identities is no longer available. Close and review the selection again.';
      if(action==='Sync'&&new Set(rows.map(s=>s.name)).size!==rows.length)this.dialogBlocked='More than one selected source has the same skill name. Select one source copy per name before syncing.';
      this.pendingEffect=()=>{
        if(action==='Sync')this.result='Sync simulated for '+rows.length+' selected source copies to '+this.bulkTargets.join(', ')+'. Existing targets: '+(this.bulkOverwrite?'overwrite reviewed':'skip')+'.';
        else this.result=action+' simulated for '+rows.length+' exact copies.';
        this.resultRows=rows.map(s=>({name:s.name+' · '+s.scope,state:action!=='Tag'&&this.batchState==='Partial'&&s.id===rows[rows.length-1]?.id?'Failed · target unavailable':action==='Tag'?'Logical-name tag updated':action==='Remove'?'Removed · no in-app agent restore':prior[s.id]==='Invalid'?'File state changed; invalid document remains':action==='Enable'&&prior[s.id]==='Enabled'?'Already enabled':action==='Disable'&&prior[s.id]==='Disabled'?'Already disabled':action+' processed'}));
        if(action!=='Tag'&&this.batchState==='Partial')this.result='Partial sample result. Successful changes remain; inspect the failed target below.';
      };
    },saveSelectionProfile(){
      let name='Selection '+(Object.keys(this.profileMembers).length+1);
      this.profiles.push(name);
      const rows=this.skills.filter(s=>this.selected.includes(s.id)); this.profileMembers[name]=[...new Set(rows.map(s=>s.name))].map(n=>[n,[...new Set(rows.filter(s=>s.name===n).map(s=>s.scope))].join(', '),'Observed']); this.profileScopeMap[name]=[...new Set(rows.map(s=>s.scope))];
      this.profile=name;
      this.result='Saved '+this.profileMembers[name].length+' desired skill names as '+name+'.';
      this.go('tools/profiles')
    },reviewSource(s){
      this.sourceScenario='Ready';
      this.openDialog('Review source update','Compare the incoming sample tree with this exact copy. This is a whole-tree source review.', '- Review the change.\n+ Review the change and record evidence.', 'Simulate update',true);
      this.dialogKind='source'; this.reviewDiff=true;
      this.reviewFacts=[['Target', s.scope+' · '+s.path],['Files','SKILL.md changed · references/checklist.md added'],['Validation','Frontmatter readable · name matches target'],['Advisory','Inspect instructions and companion files; checks are not a safety guarantee.'],['Recovery','A retained whole-tree snapshot; text Undo alone cannot restore binary or companion files.']];
    },importPreview(){
      this.openDialog('Review sample import',`Mode: ${this.importType}. Global store only. Overwrite: ${this.overwrite?'yes':'no'}. A selected archive name is shown; archive contents are not read in this preview.`,this.archiveName||'library-backup.zip · supplied example', 'Simulate import');
      this.pendingEffect=()=>{this.result='Import simulated · 2 added, 1 skipped.';this.resultRows=[{name:'code-review',state:'Added'},{name:'incident-notes',state:'Added'},{name:'meeting-notes',state:'Skipped · already exists'}];};
    },scopeRoot(scope){
      return {'Codex':'~/.codex/skills','Claude Code':'~/.claude/skills','Global library':'~/.local/share/skills-manager/skills'}[scope] || '/projects/skills-manager/.agents/skills';
    },chooseFolder(event){
      this.chosenFolderFiles=Array.from(event.target.files).map(f=>f.webkitRelativePath||f.name); this.folderPicked=!!this.chosenFolderFiles.length;
    },openSkill(s=null){
      this.formError='';this.editingId=s?.id||null;this.newSkillName=s?.name||'';this.newSkillDescription=s?.desc||'';this.newSkillTarget=s?.scope||'Global library';
      this.skillBody=s?.body||this.templateContent; for(const field of ['category','version','license','compatibility','allowedTools'])this[field]=s?.[field]||''; this.editSkill=true;
      this.$nextTick(()=>document.querySelector('.editor input')?.focus());
    },reviewSkill(){
      if (!/^[a-z0-9][a-z0-9-]*$/.test(this.newSkillName)) {this.formError='Use lowercase letters, numbers and hyphens for the skill name.';return;}
      if(this.skills.some(s=>s.id!==this.editingId && s.name===this.newSkillName && s.scope===this.newSkillTarget)){this.formError='This sample destination already has that skill. Edit its exact copy instead.';return;}
      this.openDialog('Review skill', 'Review the document and destination before saving.',this.skillBody,'Simulate save');
      this.reviewFacts=[['Name',this.newSkillName],['Destination',this.newSkillTarget+' · '+this.scopeRoot(this.newSkillTarget)],['Metadata',[this.category,this.version,this.license,this.compatibility,this.allowedTools].filter(Boolean).join(' · ')||'Optional fields not set']];
      this.pendingEffect=()=>{const old=this.skills.find(s=>s.id===this.editingId);const item={id:old?.id||String(Date.now()),name:this.newSkillName,desc:this.newSkillDescription,scope:this.newSkillTarget,path:this.scopeRoot(this.newSkillTarget)+'/'+this.newSkillName+'/SKILL.md',body:this.skillBody,category:this.category,version:this.version,license:this.license,compatibility:this.compatibility,allowedTools:this.allowedTools,state:old?.state||'Enabled',tags:old?.tags||[]};if(old)Object.assign(old,item);else this.skills.push(item);this.editSkill=false;this.templateUse=false;this.result='Saved '+item.name+' to sample '+item.scope+'.';};
    },restoreSample(name){
      this.openDialog('Restore '+name,'Restore this item to the sample global library.',name,'Simulate restore');
      this.pendingEffect=()=>{this.trashItems=this.trashItems.filter(n=>n!==name);this.result=name+' restored in sample data.';};
    },emptySampleTrash(){
      this.openDialog('Empty global trash','Permanently remove every item in the sample global trash. No Undo would be available.',this.trashItems.length+' items · global store only','Simulate empty trash');
      this.pendingEffect=()=>{this.trashItems=[];this.result='Global sample trash emptied.';};
    },rollbackSource(){
      this.reviewSource(this.skills.find(s=>s.name==='code-review')||this.skills[0]||{scope:'Codex',path:'~/.codex/skills/code-review'});
      this.dialogTitle='Review source-snapshot rollback';this.dialogAction='Simulate rollback';
    },openCommands(){
      this.openDialog('Go to a tool','Search screens and actions in this design preview.','', 'Close');this.dialogKind='commands';
    },openCommand(page){
      this.closeDialog();this.go(this.toolNav.some(n=>n[0]===page)?'tools/'+page:page);
    }
  },mounted(){
    window.addEventListener('hashchange',this.route);
    this.skills.forEach(s=>{s.body=s.scope==='Codex'?'# Instructions\n\nReview the change.':'# Instructions\n\nReview the change and record evidence.';});
    this.route();
    document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();this.openCommands();}});
    this.$watch('qualityState',()=>{this.qualityValidation=null;});
      this.skills.push({id:'4',name:'frontend-patterns',desc:'Build maintainable web interfaces.',scope:'Claude Code',path:'~/.claude/skills/frontend-patterns/SKILL.md',state:'Enabled',tags:['frontend']},{id:'5',name:'incident-notes',desc:'Capture evidence during an incident.',scope:'Codex',path:'~/.codex/skills/incident-notes/SKILL.md',state:'Invalid',tags:[]});
      this.qualitySizeRows.push({name:'frontend-patterns',scope:'Codex',path:'~/.codex/skills/frontend-patterns/SKILL.md',characters:4100});
      this.$watch('sourceScenario', value=>{if(this.dialogKind==='source')this.dialogBlocked=value==='Ready'?'':value==='Stale'?'The target changed after review. Close this review and start again.':'Validation blocked this candidate. Choose a corrected source.';});
  }
}).mount('#app');

