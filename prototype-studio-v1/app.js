(() => {
  'use strict';
  const seed = [
    ['api-conventions','Rules for naming, versioning, and documenting partner APIs.','review',8420,['codex','cursor','claude']],
    ['deploy-checklist','Checks to complete before a service reaches production.','invalid',3260,['global','codex']],
    ['release-notes','Turn merged changes into clear notes for users and operators.','review',18400,['codex','claude']],
    ['research-synthesis','Weigh evidence across papers and report uncertainty.','active',6180,['global','claude']],
    ['accessibility-review','Audit keyboard, focus, contrast, and screen-reader flows.','active',9140,['codex','cursor']],
    ['architecture-decision','Record the context, tradeoffs, and consequences of a decision.','active',4840,['global','codex']],
    ['backend-auth-patterns','Review session, token, and authorization boundaries.','active',7350,['codex']],
    ['content-editing','Revise product copy for clarity, tone, and accessibility.','active',2990,['claude','cursor']],
    ['database-migration','Plan reversible schema changes and deployment sequencing.','active',7720,['codex','cursor']],
    ['design-critique','Review interfaces against the local design system.','active',5480,['claude']],
    ['incident-response','Triage production events and capture a clear timeline.','active',6720,['global','codex']],
    ['integration-testing','Choose meaningful integration checks for changed behavior.','active',5280,['codex','claude']],
    ['localization','Review copy and layout for translation and regional formats.','active',3820,['cursor']],
    ['meeting-notes','Extract decisions, owners, and unanswered questions.','disabled',1880,['global']],
    ['onboarding-guide','Create a practical first-week path for new engineers.','active',4180,['claude']],
    ['performance-review','Profile slow paths and explain measured bottlenecks.','active',7990,['codex']],
    ['privacy-check','Check collection, retention, and deletion of personal data.','active',5110,['global','cursor']],
    ['product-brief','Shape a feature brief around user needs and constraints.','active',4740,['claude']],
    ['pull-request-review','Review a diff for correctness and maintainability.','active',3820,['codex','cursor']],
    ['security-threat-model','Map trust boundaries and likely abuse paths.','active',10620,['codex']],
    ['sql-query-review','Inspect query plans, indexes, and unsafe assumptions.','active',5660,['global']],
    ['support-reply','Draft clear responses for support tickets and handoffs.','disabled',2190,['claude']],
    ['test-data-design','Create realistic fixtures for edge cases and large data.','active',4330,['cursor']],
    ['technical-writing','Write concise, accurate developer documentation.','active',6010,['global','codex']]
  ];
  const records = seed.map(([name,description,state,tokens,scopes]) => ({name,description,state,tokens,scopes}));
  const scopeMeta = [{id:'codex',label:'Codex',mark:'C',count:13},{id:'claude',label:'Claude Code',mark:'A',count:9},{id:'cursor',label:'Cursor',mark:'↗',count:8},{id:'global',label:'Global',mark:'G',count:8}];
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const stateLabel = {active:'Active',review:'Review',invalid:'Malformed',disabled:'Disabled'};
  const state = {view:'overview',scope:'all',filter:'all',query:'',selected:null,detailTab:'document',commandIndex:0,commandResults:[],demo:'normal',lastFocus:null};
  const icon = (name) => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  let toastTimer;

  function toast(message) {
    const el = $('#toast'); el.textContent = message; el.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => {el.hidden = true;}, 4300);
  }
  function renderScopes() {
    scopeMeta.forEach(scope => { scope.count = records.filter(record => record.scopes.includes(scope.id)).length; });
    $('#scope-list').innerHTML = scopeMeta.map(scope => `<button type="button" class="scope-item${state.scope===scope.id?' active':''}" data-scope="${scope.id}" aria-pressed="${state.scope===scope.id}"><span class="scope-symbol">${scope.mark}</span><span>${scope.label}</span><strong>${scope.count}</strong></button>`).join('');
    $('.nav-count').textContent = records.length;
    $('#snapshot-title').textContent = `${records.length} skills across ${scopeMeta.length} skill roots`;
    $('.metric-line strong').textContent = records.filter(record => record.state === 'active').length;
  }
  function setView(view, focus=true) {
    state.view=view;
    $$('.view').forEach(el=>el.classList.toggle('is-visible',el.id===`view-${view}`));
    $$('[data-view]').forEach(el=>{const on=el.dataset.view===view;el.classList.toggle('is-current',on);el.classList.toggle('active',on);if(el.classList.contains('nav-item')) el.setAttribute('aria-current',on?'page':'false');});
    $('#crumb-current').textContent={overview:'Overview',library:'Library',quality:'Quality'}[view];
    $('#sidebar').classList.remove('open');$('#sidebar-scrim').classList.remove('open');
    if(view==='library') renderLibrary();
    if(focus) $(`#${view==='library'?'library-title':view==='overview'?'overview-title':'quality-title'}`).setAttribute('tabindex','-1'),$(`#${view==='library'?'library-title':view==='overview'?'overview-title':'quality-title'}`).focus({preventScroll:true});
    window.scrollTo({top:0,behavior:'instant'});
  }
  function visibleRecords() {
    const query=state.query.trim().toLowerCase();
    return records.filter(record => (state.scope==='all'||record.scopes.includes(state.scope)) && (state.filter==='all'||(state.filter==='review'?['review','invalid'].includes(record.state):record.state==='active')) && (!query||`${record.name} ${record.description}`.toLowerCase().includes(query)));
  }
  function renderLibrary() {
    const items=visibleRecords();
    $('#library-count').textContent=records.length;
    $('#results-caption').textContent=`${items.length} ${items.length===1?'skill':'skills'}`;
    const list=$('#skill-list');
    list.innerHTML=items.length ? items.map(record => `<button class="skill-row${state.selected===record.name?' selected':''}" type="button" data-record="${escapeHtml(record.name)}" aria-current="${state.selected===record.name?'true':'false'}"><span class="skill-row-main"><span class="skill-row-title"><strong>${escapeHtml(record.name)}</strong><span class="status ${record.state}">${stateLabel[record.state]}</span></span><small>${escapeHtml(record.description)}</small></span>${icon('chevron')}</button>`).join('') : `<div class="list-empty"><strong>No matching skills</strong><p>Try a different search term or scope.</p><button class="inline-action" type="button" id="clear-filters">Clear filters ${icon('arrow')}</button></div>`;
    renderDetail();
  }
  function selectRecord(name) {
    if(!records.some(record=>record.name===name)) return;
    state.selected=name; state.detailTab='document'; state.demo='normal';
    if(state.view!=='library') setView('library',false);
    state.scope='all';$('#scope-select').value='all';state.filter='all';state.query='';$('#library-search').value='';
    $$('[data-filter]').forEach(el=>el.classList.toggle('active',el.dataset.filter==='all'));
    renderScopes();renderLibrary();
    $('.library-layout').classList.add('detail-open');
    if(window.innerWidth<=760) $('#detail-heading')?.focus();
  }
  function renderDetail() {
    const record=records.find(item=>item.name===state.selected);
    $('#detail-empty').hidden=!!record;$('#detail-content').hidden=!record;
    if(!record) return;
    const scope=record.scopes[0];
    const tab=state.detailTab;
    const body=tab==='document' ? `<article class="doc-sheet"><div class="doc-kicker">SKILL.md · illustrative content</div><h2>${escapeHtml(record.name.replace(/-/g,' ').replace(/^./,c=>c.toUpperCase()))}</h2><p>${escapeHtml(record.description)}</p><h3>When to use</h3><p>Use this skill when a task involves ${escapeHtml(record.name.replace(/-/g,' '))} and the agent needs a repeatable set of checks grounded in the project.</p><h3>Working method</h3><ul><li>Read the relevant project instructions and confirm the exact files or systems involved.</li><li>Separate observations from assumptions. Record missing evidence before changing anything.</li><li>Make the smallest reviewable change, then check the affected behavior and edge cases.</li></ul><h3>Output</h3><p>Give the user a concise result, the checks performed, and any meaningful limitation.</p></article>` : tab==='copies' ? `<p class="instance-note">These are physical instances observed in the sample workspace. Scope labels describe location, not precedence.</p><div class="instance-list">${record.scopes.map((scope,index)=>`<div class="instance-row"><strong>${escapeHtml(scope==='claude'?'Claude Code':scope[0].toUpperCase()+scope.slice(1))}</strong><code>~/.${escapeHtml(scope==='claude'?'claude':scope)}/skills/${escapeHtml(record.name)}/SKILL.md</code><span class="status ${record.state==='review'&&index>0?'review':record.state}">${record.state==='review'&&index>0?'Different copy':stateLabel[record.state]}</span></div>`).join('')}</div>` : `<dl class="evidence-list"><div><dt>Observed state</dt><dd>${stateLabel[record.state]}</dd></div><div><dt>Physical copies</dt><dd>${record.scopes.length}</dd></div><div><dt>Estimated size</dt><dd>${(record.tokens/1000).toFixed(1)}k tokens</dd></div><div><dt>Selected source</dt><dd>~/.${escapeHtml(scope==='claude'?'claude':scope)}/skills/${escapeHtml(record.name)}/SKILL.md</dd></div><div><dt>Index authority</dt><dd>Filesystem observation</dd></div></dl>`;
    $('#detail-content').innerHTML=`<div class="detail-body"><button type="button" class="detail-back" id="detail-back">${icon('arrow')} Back to Library</button><div class="detail-topline"><span class="detail-path">Library / ${escapeHtml(record.name)}</span><span class="status ${record.state}">${stateLabel[record.state]}</span></div><h1 id="detail-heading" tabindex="-1">${escapeHtml(record.name)}</h1><p class="detail-summary">${escapeHtml(record.description)}</p><div class="detail-facts"><span><b>${record.scopes.length}</b> ${record.scopes.length===1?'copy':'copies'}</span><span><b>${(record.tokens/1000).toFixed(1)}k</b> tokens</span><span>Primary: <b>${escapeHtml(scope==='claude'?'Claude Code':scope[0].toUpperCase()+scope.slice(1))}</b></span></div><div class="detail-tabs" role="tablist" aria-label="Skill information"><button type="button" role="tab" aria-selected="${tab==='document'}" class="${tab==='document'?'active':''}" data-tab="document">Document</button><button type="button" role="tab" aria-selected="${tab==='copies'}" class="${tab==='copies'?'active':''}" data-tab="copies">Copies ${record.scopes.length}</button><button type="button" role="tab" aria-selected="${tab==='evidence'}" class="${tab==='evidence'?'active':''}" data-tab="evidence">Evidence</button></div>${body}</div>`;
  }
  function openOverlay(which) {
    state.lastFocus=document.activeElement;
    $(`#${which}-overlay`).hidden=false;
    document.body.style.overflow='hidden';
    setTimeout(()=>$(which==='command'?'#command-query':'#skill-name').focus(),0);
    if(which==='command'){ $('#command-query').value='';renderCommands(); }
  }
  function closeOverlay(which) {
    $(`#${which}-overlay`).hidden=true;
    document.body.style.overflow='';
    state.lastFocus?.focus();
  }
  function commandItems() {
    const actions=[{label:'Overview',description:'Open workspace summary',view:'overview',icon:'grid'},{label:'Library',description:'Browse observed skills',view:'library',icon:'layers'},{label:'Quality',description:'Inspect hygiene evidence',view:'quality',icon:'pulse'},{label:'Create a skill',description:'Draft a sample document',action:'create',icon:'plus'}];
    const skills=records.map(record=>({label:record.name,description:record.description,record:record.name,icon:'file'}));
    return [...actions,...skills];
  }
  function renderCommands() {
    const query=$('#command-query').value.toLowerCase().trim();
    state.commandResults=commandItems().filter(item=>!query||`${item.label} ${item.description}`.toLowerCase().includes(query)).slice(0,9);
    state.commandIndex=0;
    $('#command-results').innerHTML=state.commandResults.length?`<div class="command-group">${query?'Results':'Quick actions'}</div>${state.commandResults.map((item,i)=>`<button type="button" class="command-item${i===0?' active':''}" data-command-index="${i}">${icon(item.icon)}<span>${escapeHtml(item.label)}</span><small>${escapeHtml(item.description)}</small></button>`).join('')}`:'<div class="list-empty"><strong>No results</strong><p>Try a skill name or an action such as “Quality”.</p></div>';
  }
  function runCommand(index) {
    const item=state.commandResults[index];if(!item)return;
    closeOverlay('command');
    if(item.view)setView(item.view);
    if(item.record)selectRecord(item.record);
    if(item.action==='create')openOverlay('create');
  }
  function setDemo(mode) {
    state.demo=mode;$('#demo-menu').hidden=true;
    $('#overview-content').hidden=mode!=='normal';
    const panel=$('#overview-special');panel.hidden=mode==='normal';
    if(mode==='empty')panel.innerHTML=`<div class="empty-glyph">${icon('file')}</div><h2>Start with a local skill library</h2><p>No skill documents are observed yet. Create one here, or add folders you already trust.</p><button type="button" class="button button-primary" data-special="create">Create a skill</button>`;
    if(mode==='loading')panel.innerHTML='<div class="spinner" aria-hidden="true"></div><h2>Reading local skill roots…</h2><p>Loading the observed documents and their state.</p>';
    if(mode==='error')panel.innerHTML='<div class="issue-mark error" style="margin:0 auto 17px">×</div><h2>Could not read the library</h2><p>The local data could not be loaded. Check the service and try again.</p><button type="button" class="button button-secondary" data-special="retry">Try again</button>';
  }
  function handleCreate(event) {
    event.preventDefault();
    const name=$('#skill-name').value.trim();const description=$('#skill-description').value.trim();
    const error=$('#name-error');
    if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name)){error.textContent='Use lowercase letters, numbers, and single hyphens.';error.hidden=false;$('#skill-name').focus();return;}
    if(records.some(record=>record.name===name)){error.textContent='That skill name already exists in this sample library.';error.hidden=false;$('#skill-name').focus();return;}
    if(!description){$('#skill-description').focus();return;}
    const submit=$('#create-submit');submit.disabled=true;submit.textContent='Creating…';
    setTimeout(()=>{
      records.push({name,description,state:'active',tokens:420,scopes:['global']});
      $('#create-form').reset();error.hidden=true;submit.disabled=false;submit.textContent='Create sample skill';
      closeOverlay('create');selectRecord(name);toast('Sample skill created for this page. Refresh to reset.');
    },420);
  }
  document.addEventListener('click',event=>{
    const view=event.target.closest('[data-view]');if(view){setView(view.dataset.view);return;}
    const go=event.target.closest('[data-go]');if(go){setView(go.dataset.go);return;}
    const select=event.target.closest('[data-select]');if(select){selectRecord(select.dataset.select);return;}
    const scope=event.target.closest('[data-scope]');if(scope){state.scope=scope.dataset.scope;$('#scope-select').value=state.scope;renderScopes();setView('library');return;}
    const row=event.target.closest('[data-record]');if(row){state.selected=row.dataset.record;state.detailTab='document';renderLibrary();$('.library-layout').classList.add('detail-open');if(window.innerWidth<=760)$('#detail-heading')?.focus();return;}
    const filter=event.target.closest('[data-filter]');if(filter){state.filter=filter.dataset.filter;$$('[data-filter]').forEach(el=>el.classList.toggle('active',el===filter));renderLibrary();return;}
    const tab=event.target.closest('[data-tab]');if(tab){state.detailTab=tab.dataset.tab;renderDetail();$(`[data-tab="${state.detailTab}"]`)?.focus();return;}
    const command=event.target.closest('[data-command-index]');if(command){runCommand(Number(command.dataset.commandIndex));return;}
    const demo=event.target.closest('[data-demo]');if(demo){setDemo(demo.dataset.demo);return;}
    const special=event.target.closest('[data-special]');if(special){if(special.dataset.special==='create')openOverlay('create');else setDemo('normal');return;}
    if(event.target.id==='clear-filters'){state.filter='all';state.scope='all';state.query='';$('#library-search').value='';$('#scope-select').value='all';$$('[data-filter]').forEach(el=>el.classList.toggle('active',el.dataset.filter==='all'));renderScopes();renderLibrary();return;}
    if(event.target.closest('#detail-back')){$('.library-layout').classList.remove('detail-open');$(`[data-record="${state.selected}"]`)?.focus();return;}
    if(event.target.closest('#mobile-menu')){$('#sidebar').classList.add('open');$('#sidebar-scrim').classList.add('open');return;}
    if(event.target.closest('#sidebar-scrim')){$('#sidebar').classList.remove('open');$('#sidebar-scrim').classList.remove('open');return;}
    if(event.target.closest('#search-open')||event.target.closest('#command-open')){openOverlay('command');return;}
    if(event.target.closest('#create-open')){openOverlay('create');return;}
    if(event.target.closest('#create-close')||event.target.closest('#create-cancel')){closeOverlay('create');return;}
    if(event.target.closest('#all-scopes')){state.scope='all';$('#scope-select').value='all';renderScopes();setView('library');return;}
    if(event.target.closest('#demo-states')){$('#demo-menu').hidden=!$('#demo-menu').hidden;return;}
    if(event.target.closest('#quality-refresh')){const button=$('#quality-refresh');button.disabled=true;button.textContent='Refreshing…';setTimeout(()=>{button.disabled=false;button.textContent='Refresh report';$('#quality-updated').textContent='Observed just now';toast('Sample report refreshed.');},500);return;}
    if(event.target.id==='command-overlay')closeOverlay('command');
    if(event.target.id==='create-overlay')closeOverlay('create');
    if(!event.target.closest('#demo-menu'))$('#demo-menu').hidden=true;
  });
  $('#library-search').addEventListener('input',event=>{state.query=event.target.value;renderLibrary();});
  $('#scope-select').addEventListener('change',event=>{state.scope=event.target.value;renderScopes();renderLibrary();});
  $('#command-query').addEventListener('input',renderCommands);
  $('#command-query').addEventListener('keydown',event=>{
    if((event.key==='ArrowDown'||event.key==='ArrowUp')&&state.commandResults.length){event.preventDefault();const delta=event.key==='ArrowDown'?1:-1;state.commandIndex=(state.commandIndex+delta+state.commandResults.length)%state.commandResults.length;$$('[data-command-index]').forEach((el,index)=>el.classList.toggle('active',index===state.commandIndex));}
    if(event.key==='Enter'){event.preventDefault();runCommand(state.commandIndex);}
  });
  $('#skill-name').addEventListener('input',()=>{$('#name-error').hidden=true;});
  $('#create-form').addEventListener('submit',handleCreate);
  document.addEventListener('keydown',event=>{
    const activeOverlay = !$('#command-overlay').hidden ? $('#command-overlay') : !$('#create-overlay').hidden ? $('#create-overlay') : null;
    if(event.key==='Tab' && activeOverlay){
      const focusable = Array.from(activeOverlay.querySelectorAll('button:not([disabled]), input:not([disabled]), textarea:not([disabled])')).filter(el=>el.getClientRects().length);
      if(focusable.length){const first=focusable[0],last=focusable[focusable.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}
    }
    if(event.key==='Escape'){
      if(!$('#command-overlay').hidden)closeOverlay('command');else if(!$('#create-overlay').hidden)closeOverlay('create');else if(!$('#demo-menu').hidden)$('#demo-menu').hidden=true;else if($('#sidebar').classList.contains('open')){$('#sidebar').classList.remove('open');$('#sidebar-scrim').classList.remove('open');}return;
    }
    if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){event.preventDefault();if($('#command-overlay').hidden&&$('#create-overlay').hidden)openOverlay('command');return;}
    if(event.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)&&$('#command-overlay').hidden&&$('#create-overlay').hidden){event.preventDefault();openOverlay('command');}
  });
  renderScopes();renderLibrary();
})();
