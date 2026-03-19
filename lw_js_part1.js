

// ── LIVING WRITER ─────────────────────────────────────────────────────────────

async function loadLwDashboard() {
  try {
    const storiesRes = await GET('/api/lw/stories');
    state.lwStories = storiesRes.stories || [];
    const levRes = await GET('/api/lw/leviathan/questions');
    state.lwLeviathanQuestions = levRes.questions || [];
    renderLwPipeline();
  } catch (e) {
    console.error('Failed to load Living Writer dashboard', e);
    toast('Error loading dashboard', 'error');
  }
}

function renderLwPipeline() {
  document.getElementById('lw-pipeline-view').style.display = 'block';
  document.getElementById('lw-story-view').style.display = 'none';
  const list = document.getElementById('lw-pipeline-list');
  list.innerHTML = '';
  
  if (!state.lwStories || state.lwStories.length === 0) {
    list.innerHTML = '<p class="muted">No stories in the pipeline yet. Click + New Story to begin.</p>';
    return;
  }
  
  const stages = {
    1: 'Initial Concept Note',
    2: 'World & Story Outliner',
    3: 'Four Episode Grid',
    4: 'Chapter & Beat Cruxes',
    5: 'Treatment + Descriptionary',
    6: 'Internalization',
    7: 'Drafting in Flow'
  };
  
  state.lwStories.forEach(story => {
    const stageNum = story.current_stage || 1;
    let badgeHtml = '';
    if (story.draft_complete) {
      badgeHtml = '<span class="lw-draft-complete-badge promo-badge" style="background:var(--success-color, #2eb82e);">Draft Complete</span>';
    }
    const pc = ((stageNum - 1) / 6) * 100;
    
    let dateStr = 'Unknown';
    if (story.updated_at) {
      try {
        const d = new Date(story.updated_at);
        dateStr = d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
      } catch(e){}
    }
    
    list.innerHTML += `
      <div class="card lw-pipeline-card" style="margin-bottom: 1rem; cursor:pointer;" onclick="openLwStory('${story.id}')">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <div>
            <h3 style="margin:0 0 0.5rem 0;">${escapeHTML(story.title)} ${badgeHtml}</h3>
            <p class="muted" style="margin:0 0 0.5rem 0; font-size:0.9em;">Stage ${stageNum}: ${stages[stageNum]}</p>
          </div>
          <div style="display:flex; gap:0.5rem;">
            <button class="btn" onclick="event.stopPropagation(); openLwStory('${story.id}')">Open</button>
            <button class="btn-danger" onclick="event.stopPropagation(); confirmDeleteLwStory('${story.id}')">Delete</button>
          </div>
        </div>
        <div class="lw-progress-track" style="background: var(--border-color); width:100%; height:8px; border-radius:4px; margin-top:0.5rem;">
          <div class="lw-progress-bar" style="background: var(--accent-color); width:${pc}%; height:100%; border-radius:4px; transition: width 0.3s ease;"></div>
        </div>
        <div class="muted" style="font-size:0.8em; margin-top:0.5rem; text-align:right;">Last updated: ${dateStr}</div>
      </div>
    `;
  });
}

function newLwStoryModal() {
  const c = `
    <h3>New Story</h3>
    <div class="input-group">
      <label>Story Title *</label>
      <input type="text" id="lw-new-title" class="input" placeholder="Enter title..."/>
    </div>
    <div style="display:flex; justify-content:flex-end; gap:0.5rem; margin-top:1rem;">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="submitNewLwStory()">Save</button>
    </div>
  `;
  showModal(c);
  requestAnimationFrame(() => document.getElementById('lw-new-title').focus());
}

async function submitNewLwStory() {
  const title = document.getElementById('lw-new-title').value.trim();
  if (!title) {
    alert("Title is required");
    return;
  }
  try {
    const res = await POST('/api/lw/stories', { title });
    closeModal();
    toast('Story created');
    await loadLwDashboard();
    openLwStory(res.id);
  } catch (e) {
    if (e.message.includes('409')) {
      toast('Maximum stories in pipeline reached', 'error');
    } else {
      toast('Failed to create story', 'error');
    }
  }
}

function confirmDeleteLwStory(storyId) {
  if (confirm("Delete this story and all its content? This cannot be undone.")) {
    DEL('/api/lw/stories/' + storyId)
      .then(() => {
        toast('Story deleted');
        loadLwDashboard();
      })
      .catch((e) => toast('Failed to delete story', 'error'));
  }
}

async function openLwStory(storyId) {
  try {
    const story = await GET('/api/lw/stories/' + storyId);
    state.lwCurrentStoryId = storyId;
    state.lwCurrentStage = story.current_stage || 1;
    document.getElementById('lw-pipeline-view').style.display = 'none';
    document.getElementById('lw-story-view').style.display = 'block';
    renderLwStageSidebar(story);
    renderLwStageContent(story);
  } catch (e) {
    console.error('Failed to open story', e);
    toast('Could not open story', 'error');
  }
}

function renderLwStageSidebar(story) {
  const sbar = document.getElementById('lw-stage-sidebar');
  let html = `
    <button class="btn" style="width:100%; margin-bottom:1rem;" onclick="loadLwDashboard()">← All Stories</button>
    <h3 style="margin-top:0; word-break:break-word;">${escapeHTML(story.title)}</h3>
    <div style="display:flex; flex-direction:column; gap:0.25rem; margin-top:1rem;">
  `;
  const stages = [
    'Initial Concept Note', 'World & Story Outliner', 'Four Episode Grid',
    'Chapter & Beat Cruxes', 'Treatment + Descriptionary', 'Internalization', 'Drafting in Flow'
  ];
  
  stages.forEach((name, i) => {
    const stageNum = i + 1;
    let cls = 'lw-stage-item';
    let icon = '';
    
    if (stageNum < story.current_stage) {
      cls += ' completed';
      icon = '✓ ';
    } else if (stageNum === state.lwCurrentStage) {
      cls += ' active';
    } else if (stageNum > story.current_stage) {
      cls += ' locked';
    }
    
    html += `
      <div class="${cls}" onclick="switchLwStage('${story.id}', ${stageNum})" style="padding:0.5rem; border-radius:4px; cursor:pointer;">
        ${icon}Stage ${stageNum}: ${name}
      </div>
    `;
  });
  
  html += `</div>`;
  
  html += `<div style="margin-top:1.5rem; border-top:1px solid var(--border-color); padding-top:1rem;">`;
  if (story.current_stage < 7) {
    html += `<button class="btn-primary" style="width:100%;" onclick="advanceLwStage('${story.id}', ${story.current_stage})">Mark Stage Complete</button>`;
  } else if (story.current_stage === 7 && !story.draft_complete) {
    html += `<button class="btn-primary" style="width:100%;" onclick="completeLwStory('${story.id}')">Mark Draft Complete</button>`;
  } else if (story.draft_complete) {
    html += `<div style="color:var(--success-color, #2eb82e); font-weight:bold; text-align:center;">✓ Draft Complete</div>`;
  }
  html += `</div>`;
  
  sbar.innerHTML = html;
}

async function switchLwStage(storyId, stageNumber) {
  state.lwCurrentStage = stageNumber;
  try {
    const story = await GET('/api/lw/stories/' + storyId);
    renderLwStageSidebar(story);
    renderLwStageContent(story);
  } catch(e) { console.error('switchLwStage load fail', e); }
}

async function advanceLwStage(storyId, currentStage) {
  try {
    await POST(`/api/lw/stories/${storyId}/advance`);
    toast(`Stage complete! Moving to Stage ${currentStage + 1}`);
    openLwStory(storyId);
  } catch (e) {
    toast('Error advancing: check requirements', 'error');
  }
}

async function completeLwStory(storyId) {
  if (confirm("Mark this story as draft complete? This will signal Indaba that the project is ready.")) {
    try {
      await POST(`/api/lw/stories/${storyId}/complete`);
      toast('Draft complete! Indaba has been notified.');
      openLwStory(storyId);
    } catch (e) {
      toast('Error completing draft', 'error');
    }
  }
}

function renderLwStageContent(story) {
  const container = document.getElementById('lw-stage-content');
  if (state.lwCurrentStage > story.current_stage) {
    container.innerHTML = `
      <div class="coming-soon-panel" style="margin-top:2rem;">
        <h3 class="lw-stage-heading">Stage ${state.lwCurrentStage}</h3>
        <p class="muted">Complete earlier stages to unlock this stage.</p>
      </div>
    `;
    return;
  }
  
  // Handlers
  if (state.lwCurrentStage === 1) renderLwStage1(story);
  else if (state.lwCurrentStage === 2) renderLwStage2(story);
  else if (state.lwCurrentStage === 3) renderLwStage3(story);
  else if (state.lwCurrentStage === 4) renderLwStage4(story);
  else if (state.lwCurrentStage === 5) renderLwStage5(story);
  else if (state.lwCurrentStage === 6) renderLwStage6(story);
  else if (state.lwCurrentStage === 7) renderLwStage7(story);
}

// ---- STAGE 1 ----
function renderLwStage1(story) {
  const container = document.getElementById('lw-stage-content');
  let html = `
    <h3 class="lw-stage-heading">Stage 1 &mdash; Initial Concept Note</h3>
    <textarea id="lw-s1-note" class="input" style="width:100%; height:300px; resize:vertical;">${escapeHTML(story.stage1?.concept_note || '')}</textarea>
    <div id="lw-s1-wc" class="lw-word-count">Words: 0</div>
  `;
  container.innerHTML = html;
  
  const ta = document.getElementById('lw-s1-note');
  const wc = document.getElementById('lw-s1-wc');
  
  const updateWc = () => {
    const text = ta.value.trim();
    wc.textContent = 'Words: ' + (text ? text.split(/\s+/).length : 0);
  };
  
  ta.addEventListener('keyup', updateWc);
  ta.addEventListener('blur', () => {
    PUT(`/api/lw/stories/${story.id}`, { stage1: { concept_note: ta.value } }).catch(e => console.error(e));
  });
  updateWc();
  
  if (!story.stage1?.devonthink_nudge_shown) {
    const c = `
      <h3>Before you begin</h3>
      <p>Do you have existing material on this concept in DEVONthink? Notes, research, prior drafts, clippings?<br><br>Retrieve any relevant material before developing this story further.</p>
      <div style="text-align:right; margin-top:1rem;">
        <button class="btn-primary" onclick="closeModal(); dismissDevonthinkNudge('${story.id}')">Got it, I've checked</button>
      </div>
    `;
    showModal(c);
  }
}

function dismissDevonthinkNudge(storyId) {
  PUT(`/api/lw/stories/${storyId}`, { stage1: { devonthink_nudge_shown: true } });
}

// ---- STAGE 2 ----
function renderLwStage2(story) {
  const container = document.getElementById('lw-stage-content');
  const s2 = story.stage2 || {};
  const chars = s2.characters || [];
  const frags = s2.fragments || [];
  
  let html = `<h3 class="lw-stage-heading">Stage 2 &mdash; World & Story Outliner</h3>`;
  
  // A. Characters
  html += `
    <div style="margin-bottom:2rem;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h4 class="lw-section-header">Characters (${chars.length}/6) <span class="lw-compulsory-badge">COMPULSORY</span></h4>
        <button class="btn" onclick="openLwAddCharacterModal('${story.id}')" ${chars.length>=6?'disabled title="Maximum 6 characters reached"':''}>+ Add Character</button>
      </div>
      <div id="lw-s2-chars" style="margin-top:1rem;"></div>
    </div>
  `;
  
  // B. Thematic Values
  const tv = escapeHTML(s2.thematic_values || '');
  html += `
    <div style="margin-bottom:2rem; padding:1rem; border:1px solid var(--border-color); border-radius:4px; background:var(--bg-secondary);">
      <h4 class="lw-section-header">Thematic Values in Conflict</h4>
      ${!tv ? `
        <button id="btn-derive-tv" class="btn" onclick="deriveLwThematicValues('${story.id}')" style="margin-bottom:1rem;">Derive Thematic Values</button>
      ` : ''}
      <textarea id="lw-s2-tv" class="input" style="width:100%; height:80px; resize:vertical;">${tv}</textarea>
    </div>
  `;
  
  container.innerHTML = html;
  
  // Render chars
  const charDiv = document.getElementById('lw-s2-chars');
  chars.forEach((c, idx) => {
    const headText = c.character_in_one_line ? c.character_in_one_line.substring(0, 40) + '...' : 'New Character';
    charDiv.innerHTML += `
      <div class="card lw-character-card" style="margin-bottom:0.5rem;">
        <div class="lw-character-card-header" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display==='none'?'block':'none'">
          <strong>${escapeHTML(headText)}</strong>
          <span style="float:right;">▼</span>
        </div>
        <div class="lw-character-card-body" style="display:none; padding-top:1rem; border-top:1px solid var(--border-color);">
           <div style="text-align:right; margin-bottom:1rem;">
             <button class="btn-danger btn-sm" onclick="delLwCharacter('${story.id}', '${c.id}')">Remove</button>
           </div>
           
           ${renderLwTextInput(c, idx, 'character_in_one_line', 'Character in One Line')}
           ${renderLwTextArea(c, idx, 'wound', 'The Wound')}
           ${renderLwTextArea(c, idx, 'lie', 'The Lie They\'re Living')}
           ${renderLwTextInput(c, idx, 'crucible', 'The Crucible')}
           ${renderLwTextArea(c, idx, 'terrain', 'The Terrain')}
           ${renderLwTextArea(c, idx, 'transformation', 'The Transformation')}
           ${renderLwTextArea(c, idx, 'what_they_leave_behind', 'What They Leave Behind')}
        </div>
      </div>
    `;
  });
  
  // Need to bind events for auto-saving chars inside! 
  // Let's defer full s2 binding logic to an external function.
  
  // ... (truncating S2 for now, building it iteratively)
}

function renderLwTextInput(c, cIdx, field, label) {
    return `<div class="input-group">
      <label>${escapeHTML(label)}</label>
      <input type="text" class="input s2-char-input" data-cidx="${cIdx}" data-field="${field}" value="${escapeHTML(c[field]||'')}"/>
    </div>`;
}
function renderLwTextArea(c, cIdx, field, label) {
    return `<div class="input-group">
      <label>${escapeHTML(label)}</label>
      <textarea class="input s2-char-input" data-cidx="${cIdx}" data-field="${field}" style="height:60px; resize:vertical;">${escapeHTML(c[field]||'')}</textarea>
    </div>`;
}

function delLwCharacter(storyId, charId) {
    if(confirm("Remove this character?")) {
       // get story, filter chars, PUT
       GET('/api/lw/stories/'+storyId).then(story=>{
           const s2 = story.stage2 || {};
           const chars = (s2.characters || []).filter(c=>c.id !== charId);
           PUT('/api/lw/stories/'+storyId, { stage2: { characters: chars } }).then(()=>openLwStory(storyId));
       });
    }
}

async function deriveLwThematicValues(storyId) {
    const btn = document.getElementById('btn-derive-tv');
    if(btn) btn.textContent = 'Generating...';
    try {
        const res = await POST(`/api/lw/stories/${storyId}/stage2/derive_thematic_values`);
        openLwStory(storyId);
    } catch(e) { toast('Error or AI unavailable', 'error'); if(btn) btn.textContent = 'Derive Thematic Values'; }
}

function openLwAddCharacterModal(storyId) {
   let html = `
     <h3>Add Character</h3>
     <div class="input-group"><label>Character in One Line *</label><input type="text" id="add-c-line" class="input"/></div>
     <div class="input-group"><label>The Wound</label><textarea id="add-c-wound" class="input" style="height:60px"></textarea></div>
     <div class="input-group"><label>The Crucible</label><input type="text" id="add-c-cruc" class="input"/></div>
     <div style="margin-top:1rem; text-align:right;">
       <button class="btn" onclick="closeModal()">Cancel</button>
       <button class="btn-primary" onclick="submitLwAddChar('${storyId}')">Save</button>
     </div>
   `;
   showModal(html);
}

async function submitLwAddChar(storyId) {
    const line = document.getElementById('add-c-line').value.trim();
    if(!line){ alert("Character in One Line is required"); return; }
    const wc = document.getElementById('add-c-wound').value;
    const cc = document.getElementById('add-c-cruc').value;
    
    // We will do a full load, put, reload
    try {
        const story = await GET('/api/lw/stories/'+storyId);
        const chars = story.stage2?.characters || [];
        chars.push({
            id: 'c_'+Date.now(),
            character_in_one_line: line,
            wound: wc,
            crucible: cc
        });
        await PUT('/api/lw/stories/'+storyId, {stage2: {characters: chars}});
        closeModal();
        toast("Character added");
        openLwStory(storyId);
    } catch(e) { }
}

// ---- STAGE 3 ----
function renderLwStage3(story) {
   const container = document.getElementById('lw-stage-content');
   const chars = story.stage2?.characters || [];
   const bss = story.stage3?.arc_brainstorms || [];
   const ll = story.stage3?.four_episode_loglines || [];
   
   let html = `<h3 class="lw-stage-heading">Stage 3 &mdash; Four Episode Grid</h3>`;
   
   html += `<div style="margin-bottom:2rem; padding:1rem; border:1px solid var(--border-color); background:var(--bg-secondary);">
      <h4>Arc Brainstorm</h4>
      <div style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-bottom:1rem;">
        <select id="lw-s3-char" class="input" style="flex:1;">
          <option value="">-- Select Character --</option>
          ${chars.map(c=>`<option value="${c.id}">${escapeHTML(c.character_in_one_line)}</option>`).join('')}
        </select>
        <button id="btn-gen-arc" class="btn" onclick="genLwArcBrainstorm('${story.id}')">Generate Arc Brainstorm</button>
      </div>
   </div>`;
   
   if(bss.length > 0) {
      bss.forEach(b => {
         html += `
           <div class="card" style="margin-bottom:1rem;">
             <h5>Primary: ${escapeHTML(b.primary_arc_type)}</h5>
             <p>${escapeHTML(b.arc_summary)}</p>
             <button class="btn btn-sm" onclick="genLwLoglines('${story.id}', '${b.id}', this)">Generate Loglines from this Arc</button>
           </div>
         `;
      });
   }
   
   container.innerHTML = html;
}

window.genLwArcBrainstorm = async function(storyId) {
   const val = document.getElementById('lw-s3-char').value;
   if(!val) { toast("Select a character first", "error"); return; }
   const btn = document.getElementById('btn-gen-arc');
   const oldText = btn.textContent;
   btn.textContent = "Generating 3 arc possibilities...";
   try {
       await POST(`/api/lw/stories/${storyId}/stage3/arc_brainstorm`, { character_id: val });
       openLwStory(storyId);
   } catch(e) { toast("AI unavailable.", "error"); btn.textContent = oldText; }
}

window.genLwLoglines = async function(storyId, bsId, btn) {
    const oldText = btn.textContent;
    btn.textContent = "Generating...";
    try {
        await POST(`/api/lw/stories/${storyId}/stage3/generate_loglines`, { brainstorm_id: bsId });
        openLwStory(storyId);
    } catch(e) { toast("AI unavailable.", "error"); btn.textContent = oldText; }
}

