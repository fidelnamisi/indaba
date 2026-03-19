with open('/Users/fidelnamisi/Indaba/lw_js_part3.js', 'w') as f: f.write(r'''

// ---- STAGE 6 ----
function renderLwStage6(story) {
   const container = document.getElementById('lw-stage-content');
   const s6 = story.stage6 || {};
   const sessions = s6.reconstruction_sessions || [];
   
   let html = `
     <h3 class="lw-stage-heading">Stage 6 &mdash; Internalization</h3>
     
     <div style="margin-bottom:2rem;">
        <h4>Narrative Summary</h4>
        <p class="muted">A vivid prose retelling of the entire story by thread. Present tense. Read twice daily for two days. Do not analyse &mdash; absorb.</p>
        <textarea id="lw-s6-ns" class="input" style="width:100%; height:200px;">${escapeHTML(s6.narrative_summary||'')}</textarea>
        <div id="lw-s6-ns-wc" class="muted" style="font-size:0.8em; text-align:right;">Words: 0</div>
     </div>
     
     <div style="margin-bottom:2rem; border-top:1px solid var(--border-color); padding-top:1rem;">
        <h4>Anki Deck</h4>
        <p class="muted">Flashcards on concrete action beats only. Exported as .apkg for import to Anki on your phone.</p>
        ${s6.anki_deck_exported ? `
           <div style="color:var(--success-color, #2eb82e); font-weight:bold; margin-bottom:1rem;">✓ Deck exported</div>
           <button class="btn" onclick="exportLwAnki('${story.id}')">Re-export Deck</button>
        ` : `
           <button class="btn-primary" id="btn-export-anki" onclick="exportLwAnki('${story.id}')">Export Anki Deck</button>
        `}
     </div>
     
     <div style="margin-bottom:2rem; border-top:1px solid var(--border-color); padding-top:1rem;">
        <h4>Reconstruction Log</h4>
        <p class="muted">After each reconstruction session, log what you remembered and what you missed.</p>
        
        <button class="btn" style="margin-bottom:1rem;" onclick="openLwLogSessionModal('${story.id}')">+ Log Session</button>
        <div id="lw-s6-sessions"></div>
     </div>
   `;
   
   container.innerHTML = html;
   
   const ta = document.getElementById('lw-s6-ns');
   const wc = document.getElementById('lw-s6-ns-wc');
   const updWc = () => {
       const w = ta.value.trim().split(/\s+/).filter(x=>x).length;
       wc.textContent = 'Words: ' + w;
   };
   ta.addEventListener('keyup', updWc);
   ta.addEventListener('blur', () => {
       PUT('/api/lw/stories/'+story.id, { stage6: { narrative_summary: ta.value } });
   });
   updWc();
   
   const slist = document.getElementById('lw-s6-sessions');
   sessions.sort((a,b)=>new Date(b.timestamp)-new Date(a.timestamp)).forEach(s => {
       const d = new Date(s.timestamp).toLocaleString();
       slist.innerHTML += `
         <div class="card lw-reconstruction-session" style="margin-bottom:0.5rem;">
           <div class="muted" style="font-size:0.8em; margin-bottom:0.5rem;">${d}</div>
           <p style="margin:0; white-space:pre-wrap;">${escapeHTML(s.notes)}</p>
         </div>
       `;
   });
}

window.exportLwAnki = async function(storyId) {
    const btn = document.getElementById('btn-export-anki');
    if(btn) btn.textContent = 'Exporting...';
    try {
        const res = await POST(`/api/lw/stories/${storyId}/stage6/export_anki`);
        if(res.download_url) {
            window.location.href = res.download_url;
            toast("Deck exported");
            openLwStory(storyId); // refresh
        }
    } catch(e) { toast("Error exporting deck or genanki not installed", "error"); if(btn) btn.textContent = 'Export Anki Deck'; }
}

window.openLwLogSessionModal = function(storyId) {
    const html = `
      <h3>Log Reconstruction Session</h3>
      <div class="input-group">
        <label>Notes (What you remembered vs missed)</label>
        <textarea id="log-s-notes" class="input" style="height:120px;"></textarea>
      </div>
      <div style="margin-top:1rem; text-align:right;">
        <button class="btn" onclick="closeModal()">Cancel</button>
        <button class="btn-primary" onclick="submitLwLogSession('${storyId}')">Save</button>
      </div>
    `;
    showModal(html);
}

window.submitLwLogSession = async function(storyId) {
    const notes = document.getElementById('log-s-notes').value.trim();
    if(!notes){ alert("Notes required"); return; }
    try {
        const story = await GET('/api/lw/stories/'+storyId);
        const s6 = story.stage6 || {};
        const sess = s6.reconstruction_sessions || [];
        sess.push({ id:'r_'+Date.now(), timestamp: new Date().toISOString(), notes: notes });
        await PUT('/api/lw/stories/'+storyId, { stage6: { reconstruction_sessions: sess } });
        closeModal();
        toast("Session logged");
        openLwStory(storyId);
    } catch(e) { }
}

// ---- STAGE 7 ----
function renderLwStage7(story) {
   const container = document.getElementById('lw-stage-content');
   const s7 = story.stage7 || {};
   
   let html = `
     <h3 class="lw-stage-heading">Stage 7 &mdash; Drafting in Flow</h3>
     <div class="card" style="background:var(--bg-secondary); border-left:4px solid var(--border-color); margin-bottom:2rem;">
        <p style="margin:0;"><strong>Before each session:</strong> review the crux list for today's scenes.<br>
        <strong>During the session:</strong> write freely. Do not consult the Treatment.<br>
        <strong>After each session:</strong> review the crux list to confirm coverage.</p>
     </div>
     
     <div style="margin-bottom:2rem;">
       <h4>Export Treatment / Cruxes</h4>
       <div style="display:flex; gap:1rem; align-items:center;">
         <label><input type="radio" name="export-fmt" value="treatment" checked> Treatment</label>
         <label><input type="radio" name="export-fmt" value="cruxes"> Cruxes Only</label>
       </div>
       <div style="margin-top:0.5rem; display:flex; gap:0.5rem; flex-wrap:wrap;">
         ${['final_draft', 'scrivener', 'novelwriter', 'ulysses', 'freewrite'].map(t => 
            `<button class="btn" onclick="doLwExport('${story.id}', '${t}')">Export for ${t.replace('_',' ')}</button>`
         ).join('')}
       </div>
     </div>
     
     <div style="margin-bottom:2rem; border-top:1px solid var(--border-color); padding-top:1rem;">
       <h4>Today's Crux Reference</h4>
       <div id="lw-s7-crux-list" class="lw-crux-list"><span class="muted">Loading cruxes...</span></div>
     </div>
     
     <div style="margin-bottom:2rem; border-top:1px solid var(--border-color); padding-top:1rem;">
       <h4>Session Notes</h4>
       <textarea id="lw-s7-notes" class="input" style="width:100%; height:120px;">${escapeHTML(s7.session_notes||'')}</textarea>
     </div>
   `;
   
   if (!story.draft_complete) {
       html += `
         <div style="margin-top:2rem; padding-top:1rem; border-top:1px solid var(--border-color);">
            <button class="btn-primary" style="width:100%; padding:1rem; font-size:1.1em;" onclick="completeLwStory('${story.id}')">Mark Draft Complete</button>
         </div>
       `;
   } else {
       html += `
         <div class="card" style="margin-top:2rem; background:var(--success-color, #2eb82e); color:white;">
            <h4 style="margin:0 0 0.5rem 0;">✓ Draft complete as of ${new Date(story.draft_complete_at).toLocaleString()}</h4>
            <p style="margin:0;">Indaba has been notified.</p>
         </div>
       `;
   }
   
   container.innerHTML = html;
   
   const ta = document.getElementById('lw-s7-notes');
   ta.addEventListener('blur', () => {
       PUT('/api/lw/stories/'+story.id, { stage7: { session_notes: ta.value } });
   });
   
   // Fetch cruxes
   GET('/api/lw/stories/'+story.id+'/cruxes').then(cruxes => {
       const clist = document.getElementById('lw-s7-crux-list');
       if(!cruxes || cruxes.length === 0) {
           clist.innerHTML = '<span class="muted">No scenes in treatment yet. Complete Stage 5 first.</span>';
       } else {
           clist.innerHTML = '';
           cruxes.forEach((c, idx) => {
               clist.innerHTML += `<div class="lw-crux-list-item"><strong>${idx+1}. ${escapeHTML(c.slug_line||'')}</strong> &mdash; ${escapeHTML(c.crux||'')}</div>`;
           });
       }
   }).catch(e => {
       document.getElementById('lw-s7-crux-list').innerHTML = '<span class="muted">Failed to load cruxes</span>';
   });
}

window.doLwExport = async function(storyId, target) {
    const fmt = document.querySelector('input[name="export-fmt"]:checked').value;
    try {
        const res = await POST(`/api/lw/stories/${storyId}/stage7/export`, { target, format: fmt });
        if(res.download_url) {
            window.location.href = res.download_url;
            toast("Export ready");
        }
    } catch(e) { toast("Error exporting", "error"); }
}

''')