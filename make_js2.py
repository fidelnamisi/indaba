import os
js_append = """

// ---- STAGE 4 ----
function renderLwStage4(story) {
   const container = document.getElementById('lw-stage-content');
   const files = story.stage4?.treesheets_files || [];
   
   let html = `
      <h3 class="lw-stage-heading">Stage 4 &mdash; Chapter & Beat Cruxes</h3>
      <p class="muted">Link your TreeSheets files for this story.</p>
      
      <div style="margin-bottom:1rem;">
         <button class="btn" onclick="openLwLinkFileModal('${story.id}')">+ Link File</button>
      </div>
   `;
   
   if(files.length === 0) {
      html += `<p class="muted">No TreeSheets files linked yet.</p>`;
   } else {
      files.forEach(f => {
         const trunc = f.filepath.length > 50 ? '...' + f.filepath.slice(-47) : f.filepath;
         html += `
           <div class="card" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem; padding:0.5rem 1rem;">
             <div>
               <strong>${escapeHTML(f.label)}</strong>
               <div class="muted" style="font-size:0.8em;">${escapeHTML(trunc)}</div>
             </div>
             <div style="display:flex; gap:0.5rem;">
               <button class="btn btn-sm" onclick="lwOpenLinkedFile('${story.id}', '${f.filepath}', '${f.label}')">Open</button>
               <button class="btn-danger btn-sm" onclick="lwRemoveLinkedFile('${story.id}', '${f.id}')">Remove</button>
             </div>
           </div>
         `;
      });
   }
   
   container.innerHTML = html;
}

window.openLwLinkFileModal = function(storyId) {
   const html = `
     <h3>Link TreeSheets File</h3>
     <div class="input-group"><label>Label *</label><input type="text" id="add-f-lbl" class="input"/></div>
     <div class="input-group"><label>File path *</label><input type="text" id="add-f-path" class="input" placeholder="/Users/yourname/Documents/story-outline.tsv"/></div>
     <div style="margin-top:1rem; text-align:right;">
       <button class="btn" onclick="closeModal()">Cancel</button>
       <button class="btn-primary" onclick="submitLwLinkFile('${storyId}')">Save</button>
     </div>
   `;
   showModal(html);
}

window.submitLwLinkFile = async function(storyId) {
    const lbl = document.getElementById('add-f-lbl').value.trim();
    const path = document.getElementById('add-f-path').value.trim();
    if(!lbl || !path) { alert("Both are required"); return; }
    
    try {
        const story = await GET('/api/lw/stories/'+storyId);
        const files = story.stage4?.treesheets_files || [];
        files.push({ id:'f_'+Date.now(), label:lbl, filepath:path });
        await PUT('/api/lw/stories/'+storyId, { stage4: { treesheets_files: files } });
        closeModal();
        toast("File linked");
        openLwStory(storyId);
    } catch(e) { }
}

window.lwOpenLinkedFile = async function(storyId, path, lbl) {
   toast("Opening " + lbl + "...");
   try {
       await POST(`/api/lw/stories/${storyId}/stage4/open_file`, { filepath: path });
   } catch(e) { toast("Error opening file", "error"); }
}

window.lwRemoveLinkedFile = async function(storyId, fId) {
   try {
       const story = await GET('/api/lw/stories/'+storyId);
       const files = (story.stage4?.treesheets_files || []).filter(f=>f.id !== fId);
       await PUT('/api/lw/stories/'+storyId, { stage4: { treesheets_files: files } });
       openLwStory(storyId);
   } catch(e) { }
}


// ---- STAGE 5 ----
function renderLwStage5(story) {
   const container = document.getElementById('lw-stage-content');
   const scenes = story.stage5?.treatment_scenes || [];
   const desc = story.stage5?.descriptionary || [];
   
   let html = `
      <h3 class="lw-stage-heading">Stage 5 &mdash; Treatment & Descriptionary</h3>
      <div style="margin-bottom:1rem; display:flex; gap:0.5rem; border-bottom:1px solid var(--border-color); padding-bottom:1rem;">
         <button class="btn active" id="btn-t-view" onclick="lwToggleS5('t')">Treatment</button>
         <button class="btn" id="btn-d-view" onclick="lwToggleS5('d')">Descriptionary</button>
      </div>
      
      <div id="lw-s5-t">
        <div style="display:flex; justify-content:space-between; margin-bottom:1rem;">
           <strong>Treatment</strong>
           <button class="btn btn-sm" onclick="lwToggleCruxView()">Toggle Full/Crux View</button>
        </div>
        <div id="lw-s5-t-list"></div>
        <button class="btn" onclick="openLwAddSceneModal('${story.id}')">+ Add Scene</button>
      </div>
      
      <div id="lw-s5-d" style="display:none;">
        <div style="margin-bottom:1rem;">
           <strong>Descriptionary</strong>
           <p class="muted">50-100 words of sensory detail per entry. Fragments, not full sentences.</p>
        </div>
        <div id="lw-s5-d-list"></div>
        <button class="btn" onclick="openLwAddDescModal('${story.id}')">+ Add Entry</button>
      </div>
   `;
   
   container.innerHTML = html;
   
   const tlist = document.getElementById('lw-s5-t-list');
   // Render scenes
   scenes.sort((a,b)=>(parseInt(a.order)||0)-(parseInt(b.order)||0)).forEach(s => {
       tlist.innerHTML += `
          <div class="lw-treatment-scene card" style="margin-bottom:0.5rem; border-left:4px solid var(--accent-color);">
             <div style="display:flex; justify-content:space-between;">
               <div>
                 <strong>${escapeHTML(s.slug_line)}</strong> &mdash; 
                 <span style="color:var(--accent-color); font-weight:bold;">${escapeHTML(s.crux)}</span>
               </div>
               <button class="btn-danger btn-sm" onclick="lwDelScene('${story.id}', '${s.id}')">X</button>
             </div>
             <div class="s5-scene-desc" style="margin-top:0.5rem; white-space:pre-wrap;">${escapeHTML(s.scene_description || '')}</div>
          </div>
       `;
   });
   
   const dlist = document.getElementById('lw-s5-d-list');
   desc.forEach(d => {
       dlist.innerHTML += `
          <div class="lw-descriptionary-entry card" style="margin-bottom:0.5rem;">
             <div style="display:flex; justify-content:space-between;">
               <strong>${escapeHTML(d.header)}</strong>
               <button class="btn-danger btn-sm" onclick="lwDelDesc('${story.id}', '${d.header}')">X</button>
             </div>
             <p style="white-space:pre-wrap; margin:0.5rem 0 0 0;">${escapeHTML(d.body||'')}</p>
          </div>
       `;
   });
}

window.lwToggleS5 = function(mode) {
    document.getElementById('lw-s5-t').style.display = mode === 't' ? 'block' : 'none';
    document.getElementById('lw-s5-d').style.display = mode === 'd' ? 'block' : 'none';
    document.getElementById('btn-t-view').classList.toggle('active', mode === 't');
    document.getElementById('btn-d-view').classList.toggle('active', mode === 'd');
}

window.lwToggleCruxView = function() {
    const descs = document.querySelectorAll('.s5-scene-desc');
    descs.forEach(d => { d.style.display = d.style.display === 'none' ? 'block' : 'none'; });
}

window.openLwAddSceneModal = function(storyId) {
    const html = `
      <h3>Add Scene</h3>
      <div class="input-group"><label>Slug Line</label><input type="text" id="add-s-slug" class="input"/></div>
      <div class="input-group"><label>Crux *</label><input type="text" id="add-s-crux" class="input"/></div>
      <div class="input-group"><label>Description</label><textarea id="add-s-desc" class="input" style="height:120px"></textarea></div>
      <div style="margin-top:1rem; text-align:right;">
        <button class="btn" onclick="closeModal()">Cancel</button>
        <button class="btn-primary" onclick="submitLwAddScene('${storyId}')">Save</button>
      </div>
    `;
    showModal(html);
}

window.submitLwAddScene = async function(storyId) {
    const slug = document.getElementById('add-s-slug').value.trim();
    const crux = document.getElementById('add-s-crux').value.trim();
    const desc = document.getElementById('add-s-desc').value.trim();
    if(!crux) { alert("Crux is required"); return; }
    
    try {
        const story = await GET('/api/lw/stories/'+storyId);
        const scs = story.stage5?.treatment_scenes || [];
        const nextO = scs.length > 0 ? Math.max(...scs.map(s=>parseInt(s.order)||0)) + 1 : 1;
        scs.push({id:'s_'+Date.now(), order:nextO, slug_line:slug, crux:crux, scene_description:desc});
        await PUT('/api/lw/stories/'+storyId, { stage5: { treatment_scenes: scs } });
        closeModal();
        openLwStory(storyId);
    } catch(e) {}
}

window.lwDelScene = async function(storyId, sId) {
    if(!confirm("Delete scene?")) return;
    try {
        const story = await GET('/api/lw/stories/'+storyId);
        const scs = (story.stage5?.treatment_scenes || []).filter(s=>s.id!==sId);
        await PUT('/api/lw/stories/'+storyId, { stage5: { treatment_scenes: scs } });
        openLwStory(storyId);
    } catch(e) {}
}

window.openLwAddDescModal = function(storyId) {
    const html = `
      <h3>Add Descriptionary Entry</h3>
      <div class="input-group"><label>Header (All Caps) *</label><input type="text" id="add-d-head" class="input" style="text-transform:uppercase"/></div>
      <div class="input-group">
        <label>Body</label>
        <textarea id="add-d-body" class="input" style="height:120px"></textarea>
        <div id="add-d-wc" class="muted" style="font-size:0.8em;">0 words</div>
      </div>
      <div style="margin-top:1rem; text-align:right;">
        <button class="btn" onclick="closeModal()">Cancel</button>
        <button class="btn-primary" onclick="submitLwAddDesc('${storyId}')">Save</button>
      </div>
    `;
    showModal(html);
    
    document.getElementById('add-d-body').addEventListener('keyup', e => {
        const text = e.target.value.trim();
        const words = text ? text.split(/\\s+/).length : 0;
        const wcEl = document.getElementById('add-d-wc');
        wcEl.textContent = words + ' words';
        if(words < 50 || words > 100) wcEl.style.color = 'var(--text-danger, orange)';
        else wcEl.style.color = 'var(--text-muted, #888)';
    });
}

window.submitLwAddDesc = async function(storyId) {
    const head = document.getElementById('add-d-head').value.trim().toUpperCase();
    const body = document.getElementById('add-d-body').value.trim();
    if(!head) { alert("Header is required"); return; }
    
    try {
        const story = await GET('/api/lw/stories/'+storyId);
        const descs = story.stage5?.descriptionary || [];
        descs.push({header:head, body:body});
        await PUT('/api/lw/stories/'+storyId, { stage5: { descriptionary: descs } });
        closeModal();
        openLwStory(storyId);
    } catch(e) {}
}

window.lwDelDesc = async function(storyId, head) {
    if(!confirm("Delete entry?")) return;
    try {
        const story = await GET('/api/lw/stories/'+storyId);
        const descs = (story.stage5?.descriptionary || []).filter(d=>d.header!==head);
        await PUT('/api/lw/stories/'+storyId, { stage5: { descriptionary: descs } });
        openLwStory(storyId);
    } catch(e) {}
}

"""
try:
    with open("/Users/fidelnamisi/Indaba/script_js2.py", "w") as f:
        f.write("with open('/Users/fidelnamisi/Indaba/lw_js_part2.js', 'w') as f: f.write(r'''" + js_append + "''')")
except Exception as e:
    print(e)
