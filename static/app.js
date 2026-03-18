/**
 * Indaba — Frontend Application
 * Vanilla JS, state-driven rendering.
 */

// ── State ─────────────────────────────────────────────────────────────────────

const state = {
  projects:        [],
  settings:        {},
  contentPipeline: [],
  leadMeasures:    {},
  windowRemaining: '',
  windowActive:    true,
  plugins:         [],
  today:           '',
  weekday:         '',
  todayLog:        { commitment: '', session_notes: [] },
  p4Expanded:      false,
  completedExpanded: false,
  currentTopTab:   'hub',
  currentView:     'dashboard',
  inbox:           [],
  inboxUrgent:     0,
  caps:            { total_active: 0, total_cap: 8, zone_counts: {}, zone_caps: {morning:3,paid_work:3,evening:2}, inbox_count: 0, inbox_max: 15, dormant_count: 0, dormant_max: 25 },
  triageQuestion:  'If you had one more year of productive work left, would you spend any of it on this?',
  postingToday:    { patreon: false, website: false, vip_group: false, wa_channel: false },
  postingStreaks:  { patreon: 0, website: 0, vip_group: 0, wa_channel: 0 },
  zonePriorities:  { morning: null, paid_work: null, evening: null },
  
  // Promotion Machine State
  currentPromoTab:   "contacts",
  promoContacts:     [],
  promoLeads:        [],
  promoMessages:     [],
  promoProverbs:     [],
  promoBooks:        [],
  promoSettings:     {},
  selectedBookId:    null,
  selectedContactId: null,
  selectedLeadId:    null,
  promoOverdueCount: 0,
  promoDispatchedCount: 0,
  promoInstruction: null,
  currentMessageFilter: "all"
};

// ── API helpers ───────────────────────────────────────────────────────────────

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`API ${method} ${path} → ${res.status}`);
  return res.json();
}
const GET  = p      => api('GET',    p);
const POST = (p, b) => api('POST',   p, b);
const PUT  = (p, b) => api('PUT',    p, b);
const DEL  = p      => api('DELETE', p);

// ── View Switching ────────────────────────────────────────────────────────────

function switchView(view) {
  if (state.currentView === view) return;
  state.currentView = view;
  
  // Update sub-tab button active states within TO-DO
  document.querySelectorAll('#view-todo .tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === view);
  });

  renderAll();
}

function switchTopTab(tabName) {
  state.currentTopTab = tabName;
  
  // Update top tab buttons active state
  document.querySelectorAll('.top-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });

  // Toggle visibility of top view containers
  document.querySelectorAll('.top-view-container').forEach(el => {
    el.style.display = el.id === `view-${tabName}` ? 'block' : 'none';
  });

  if (tabName === 'hub') {
    loadHubSummary();
  } else if (tabName === 'promotion-machine') {
    switchPromoTab('contacts');
  }

  renderAll();
}

function switchPromoTab(tabName) {
  state.currentPromoTab = tabName;
  
  // Hide all promo views
  document.querySelectorAll('.promo-view-container').forEach(el => {
    el.style.display = 'none';
  });
  
  // Show selected promo view
  const target = document.getElementById(`promo-view-${tabName}`);
  if (target) target.style.display = 'block';
  
  // Update tab button active state
  document.querySelectorAll('.promo-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.promoTab === tabName);
  });
  
  // Load data if needed
  if (tabName === 'contacts')       loadPromoContacts();
  else if (tabName === 'leads')     loadPromoLeads();
  else if (tabName === 'message-maker') renderPromoMessageMaker();
  else if (tabName === 'book-serializer') loadPromoBooks();
  else if (tabName === 'wa-post-maker') loadPromoProverbs();
  else if (tabName === 'sender')    loadPromoMessages();
  else if (tabName === 'promo-settings') loadPromoSettings();
}

async function loadHubSummary() {
  try {
    const data = await GET('/api/hub/summary');
    renderHubCards(data);
  } catch (e) {
    console.error('Hub load failed:', e);
    toast('Could not load hub summary', 'error');
  }
}

function renderHubCards(data) {
  const grid = document.getElementById('hub-cards-grid');
  if (!grid) return;

  const cards = [
    {
      id: 'todo',
      title: 'To-Do',
      stats: [
        `${data.todo.active_projects} active projects`,
        `${data.todo.inbox_count} inbox items`,
        `${data.todo.overdue_projects} overdue`
      ],
      target: 'todo'
    },
    {
      id: 'living_writer',
      title: 'Living Writer',
      stats: [
        `${data.living_writer.stories_in_pipeline} stories in pipeline`,
        `Furthest stage: ${data.living_writer.furthest_stage}`,
        `${data.living_writer.draft_complete_count} draft complete`
      ],
      target: 'living-writer'
    },
    {
      id: 'publishing_central',
      title: 'Publishing Central',
      stats: [
        `${data.publishing_central.chapters_live} chapters live`,
        `${data.publishing_central.chapters_pending} pending`
      ],
      target: 'publishing-central'
    },
    {
      id: 'promotion_machine',
      title: 'Promotion Machine',
      stats: [
        `${data.promotion_machine.contacts_count} contacts`,
        `${data.promotion_machine.open_leads} open leads`,
        `${data.promotion_machine.messages_queued} messages queued`
      ],
      target: 'promotion-machine'
    }
  ];

  grid.innerHTML = cards.map(c => `
    <div class="hub-card">
      <h3>${c.title}</h3>
      <div class="hub-stats">
        ${c.stats.map(s => `<div class="hub-stat">${s}</div>`).join('')}
      </div>
      <button class="hub-open-btn" onclick="switchTopTab('${c.target}')">Open</button>
    </div>
  `).join('');
}

// ── Boot ──────────────────────────────────────────────────────────────────────

async function loadDashboard() {
  try {
    const d = await GET('/api/dashboard');
    state.projects        = d.projects;
    state.settings        = d.settings;
    state.contentPipeline = d.content_pipeline;
    state.leadMeasures    = d.lead_measures;
    state.windowRemaining = d.window_remaining;
    state.windowActive    = d.window_active;
    state.plugins         = d.plugins || [];
    state.today           = d.today;
    state.weekday         = d.weekday;
    state.todayLog        = d.today_log || { commitment: '', session_notes: [] };
    state.inbox           = d.inbox || [];
    state.inboxUrgent     = d.inbox_urgent || 0;
    state.caps            = d.caps || state.caps;
    state.postingToday    = d.posting_today   || state.postingToday;
    state.postingStreaks  = d.posting_streaks  || state.postingStreaks;
    state.zonePriorities  = d.zone_priorities  || state.zonePriorities;
    if (d.settings && d.settings.inbox_triage_question) {
      state.triageQuestion = d.settings.inbox_triage_question;
    }
    renderAll();
  } catch (e) {
    console.error('Dashboard load failed:', e);
    toast('Could not load dashboard data', 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
  startClock();
  applyStoredTheme();
  document.getElementById('btn-new-project').onclick = openNewProjectModal;
  // document.getElementById('btn-settings').onclick    = openSettingsModal; // Removed from top-right
  document.getElementById('btn-plugins').onclick     = openPluginsModal;
  document.getElementById('btn-theme').onclick       = toggleTheme;
  document.getElementById('btn-notes').onclick       = openNotesModal;
  document.getElementById('btn-help').onclick        = openHelpModal;
  
  // Top Tab navigation
  document.querySelectorAll('.top-tab-btn').forEach(btn => {
    btn.onclick = () => switchTopTab(btn.dataset.tab);
  });

  // Sub Tab navigation
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.onclick = () => switchView(btn.dataset.view);
  });

  // Promo Tab navigation
  document.querySelectorAll('.promo-tab-btn').forEach(btn => {
    btn.onclick = () => switchPromoTab(btn.dataset.promoTab);
  });

  switchTopTab('hub'); // Default view
  
  setInterval(loadDashboard, 5 * 60 * 1000);
});

// ── Clock ─────────────────────────────────────────────────────────────────────

function startClock() {
  const tick = () => {
    const now = new Date();
    document.getElementById('clock').textContent =
      `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  };
  tick();
  setInterval(tick, 30000);
}

// ── Render: All ───────────────────────────────────────────────────────────────

function renderAll() {
  renderTopBar();
  
  // Logic for top-level views
  if (state.currentTopTab === 'hub') {
    // Hub rendering is handled by renderHubCards which is called by loadHubSummary
  } else if (state.currentTopTab === 'todo') {
    renderTodoView();
  } else if (state.currentTopTab === 'living-writer') {
    // Coming soon
  } else if (state.currentTopTab === 'publishing-central') {
    renderPublishingDashboard();
  } else if (state.currentTopTab === 'promotion-machine') {
    // Coming soon
  } else if (state.currentTopTab === 'settings') {
    renderSettingsView();
  }
}

function renderTodoView() {
  // Hide all internal containers
  document.querySelectorAll('#view-todo .view-container').forEach(el => el.classList.add('hidden'));
  document.getElementById('feed').classList.add('hidden');
  document.getElementById('sidebar').classList.add('hidden');
  
  if (state.currentView === 'dashboard') {
    document.getElementById('feed').classList.remove('hidden');
    document.getElementById('sidebar').classList.remove('hidden');
    renderCommitment();
    renderFeed();
    renderPostingTracker();
    renderInbox();
    renderLeadMeasures();
    renderPipeline();
    renderQuickProjects();
  } else if (state.currentView === 'earnings') {
    const ec = document.getElementById('earnings-container');
    if (ec) {
      ec.classList.remove('hidden');
      renderEarningsDashboard();
    }
  }
}

// ── Render: Publishing Dashboard ──────────────────────────────────────────────

function renderPublishingDashboard() {
  const container = document.getElementById('publishing-container');
  const pipeline = state.contentPipeline || [];
  
  const rows = pipeline.map(entry => {
    const platforms = [
      { key: 'vip_group', label: 'VIP Group', status: entry.vip_group_status, rev: entry.vip_group_revision || 0 },
      { key: 'patreon', label: 'Patreon', status: entry.patreon_status, rev: entry.patreon_revision || 0 },
      { key: 'website', label: 'Website', status: entry.website_status, rev: entry.website_revision || 0 },
      { key: 'wa_channel', label: 'WA Channel', status: entry.wa_channel_status, rev: entry.wa_channel_revision || 0 },
    ];
    const platformCells = platforms.map(p => `
      <div class="platform-cell">
        <div class="platform-label">${p.label}</div>
        <div class="platform-status ${p.status}">${p.status}</div>
        <div class="platform-rev">
          <button class="rev-btn" onclick="incrementRevision('${entry.id}', '${p.key}_revision')">+</button>
          <span class="rev-count">${p.rev}</span>
          <button class="rev-btn" onclick="decrementRevision('${entry.id}', '${p.key}_revision')">−</button>
        </div>
      </div>
    `).join('');
    
    return `
      <div class="pipeline-row">
        <div class="pipeline-chapter">
          <strong>${esc(entry.book)} Ch${entry.chapter_number}: ${esc(entry.chapter)}</strong>
          <div class="chapter-title">${esc(entry.title || '')}</div>
        </div>
        <div class="pipeline-platforms">
          ${platformCells}
        </div>
      </div>
    `;
  }).join('');
  
  container.innerHTML = `
    <div class="publishing-header">
      <h2>Publishing Dashboard</h2>
      <p>Revision tracking and pipeline management.</p>
      <button onclick="openAddChapterModal()" class="btn-capture">+ Add Chapter</button>
    </div>
    <div class="publishing-pipeline">
      ${rows}
    </div>
  `;
}

async function incrementRevision(entryId, field) {
  await POST(`/api/content-pipeline/${entryId}/increment-revision`, { field, delta: 1 });
  await loadDashboard();
}

async function decrementRevision(entryId, field) {
  await POST(`/api/content-pipeline/${entryId}/increment-revision`, { field, delta: -1 });
  await loadDashboard();
}

// ── Render: Earnings Dashboard ───────────────────────────────────────────────

async function renderEarningsDashboard() {
  const container = document.getElementById('earnings-container');
  container.innerHTML = `<div style="padding:20px;"><h2>Earnings Dashboard</h2><p>Loading…</p></div>`;
  
  try {
    const [entries, monthly] = await Promise.all([
      GET('/api/earnings'),
      GET('/api/earnings/monthly')
    ]);
    
    const totalThisMonth = monthly.length > 0 ? monthly[0].total : 0;
    const totalLastMonth = monthly.length > 1 ? monthly[1].total : 0;
    
    const entriesHtml = entries.map(e => `
      <tr>
        <td>${e.date}</td>
        <td>${esc(e.platform)}</td>
        <td>R${e.amount.toFixed(2)}</td>
        <td>${esc(e.notes)}</td>
        <td><button class="badge badge-reopen" onclick="deleteEarning('${e.id}')">Delete</button></td>
      </tr>
    `).join('');
    
    const monthlyHtml = monthly.map(m => `
      <div class="month-bar" style="width: ${Math.min(m.total / 100, 100)}%;">
        <span class="month-label">${m.month}</span>
        <span class="month-total">R${m.total.toFixed(2)}</span>
      </div>
    `).join('');
    
    container.innerHTML = `
      <div class="earnings-header">
        <h2>Earnings Dashboard</h2>
        <p>Total this month: <strong>R${totalThisMonth.toFixed(2)}</strong> | Last month: R${totalLastMonth.toFixed(2)}</p>
        <button onclick="openAddEarningModal()" class="btn-capture">+ Add Manual Entry</button>
      </div>
      <div class="earnings-chart">
        <h3>Monthly Earnings</h3>
        <div class="chart-bars">${monthlyHtml}</div>
      </div>
      <div class="earnings-table">
        <h3>All Entries</h3>
        <table>
          <thead>
            <tr><th>Date</th><th>Platform</th><th>Amount</th><th>Notes</th><th>Actions</th></tr>
          </thead>
          <tbody>${entriesHtml}</tbody>
        </table>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="error">Failed to load earnings data.</div>`;
    console.error(e);
  }
}

async function openAddEarningModal() {
  // Simple inline form for now; could be a modal later
  const container = document.getElementById('earnings-container');
  const formHtml = `
    <div class="modal-overlay" style="position:fixed;inset:0;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;z-index:1000;">
      <div class="modal-box" style="background:var(--surface);padding:30px;border-radius:8px;max-width:400px;">
        <h3>Add Earnings Entry</h3>
        <form id="add-earning-form">
          <label>Date <input type="date" id="earning-date" required value="${new Date().toISOString().split('T')[0]}"></label>
          <label>Platform <input type="text" id="earning-platform" placeholder="Patreon, VIP Group, etc." required></label>
          <label>Amount (R) <input type="number" step="0.01" id="earning-amount" required></label>
          <label>Notes <textarea id="earning-notes" rows="2"></textarea></label>
          <div style="display:flex;gap:10px;margin-top:20px;">
            <button type="submit" class="btn-capture">Save</button>
            <button type="button" onclick="closeAddEarningModal()">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  `;
  container.insertAdjacentHTML('beforeend', formHtml);
  document.getElementById('add-earning-form').onsubmit = async (e) => {
    e.preventDefault();
    const date = document.getElementById('earning-date').value;
    const platform = document.getElementById('earning-platform').value;
    const amount = parseFloat(document.getElementById('earning-amount').value);
    const notes = document.getElementById('earning-notes').value;
    await POST('/api/earnings', { date, platform, amount, notes });
    closeAddEarningModal();
    renderEarningsDashboard();
  };
}

function closeAddEarningModal() {
  const overlay = document.querySelector('.modal-overlay');
  if (overlay) overlay.remove();
}

async function deleteEarning(id) {
  if (!confirm('Delete this earnings entry?')) return;
  await DEL(`/api/earnings/${id}`);
  renderEarningsDashboard();
}

// ── Render: Top Bar ───────────────────────────────────────────────────────────

function renderTopBar() {
  const dateEl = document.getElementById('topbar-date');
  if (state.today) {
    const d = new Date(state.today + 'T00:00:00');
    dateEl.textContent = d.toLocaleDateString('en-ZA', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
    });
  }
  const pill = document.getElementById('window-pill');
  pill.className = 'window-pill';
  if (!state.windowActive) {
    pill.textContent = 'Window closed';
    pill.classList.add('closed');
  } else {
    const rem   = state.windowRemaining || '';
    const match = rem.match(/^0h (\d+)m/);
    if (match && parseInt(match[1]) <= 30) pill.classList.add('warning');
    const wend = state.settings.window_end || '11:30';
    pill.innerHTML =
      `<span style="color:var(--muted);margin-right:5px;">window closes</span>${wend} &nbsp;·&nbsp; ${rem}`;
  }
}

// ── Gap 1: Commitment Declaration ─────────────────────────────────────────────

function renderCommitment() {
  const el = document.getElementById('commitment-block');
  if (!el) return;
  const val = state.todayLog.commitment || '';
  el.innerHTML = `
    <div class="commitment-wrap">
      <div class="commitment-label">Today I will focus on</div>
      <textarea id="commitment-input" class="commitment-input"
        placeholder="Write your intention for this morning's session…"
        rows="2" onblur="saveCommitment()">${esc(val)}</textarea>
    </div>`;
}

async function saveCommitment() {
  const val = document.getElementById('commitment-input')?.value || '';
  if (val === state.todayLog.commitment) return;
  try {
    const updated = await PUT('/api/daily-log', { date: state.today, commitment: val });
    state.todayLog.commitment = updated.commitment;
  } catch (e) { /* silent */ }
}

// ── Gap 2: Priority Feed — P4 collapsible ────────────────────────────────────

function renderFeed() {
  const feed = document.getElementById('priority-feed');
  const active    = state.projects.filter(p => !p.completed);
  const completed = state.projects.filter(p => p.completed);

  // Group by energy zone
  const zones = { morning: [], flexible: [], evening: [] };
  active.forEach(p => {
    const z = p.energy_zone || 'flexible';
    (zones[z] = zones[z] || []).push(p);
  });

  // Within each zone, sort by priority then deadline
  const sortFn = (a, b) => {
    if ((a.priority||4) !== (b.priority||4)) return (a.priority||4) - (b.priority||4);
    return (a.deadline||'9999-12-31') < (b.deadline||'9999-12-31') ? -1 : 1;
  };

  const ZONES = [
    { key: 'morning',   icon: '☀',  title: 'Morning Block',  subtitle: 'Peak intellect + will · 08:30–10:30' },
    { key: 'paid_work', icon: '◈',  title: 'Paid Work',      subtitle: 'Client & commissioned · 11:00–13:00' },
    { key: 'evening',   icon: '◑',  title: 'Evening Block',  subtitle: 'Outreach & sales · End of day' },
  ];

  const zoneHtml = ZONES.map(({ key, icon, title, subtitle }) => {
    const items = (zones[key] || []).sort(sortFn);
    if (!items.length) return '';
    const focusId = state.zonePriorities[key] || null;
    const focusProject = focusId ? items.find(p => p.id === focusId) : null;
    const rest = focusProject ? items.filter(p => p.id !== focusId) : items;
    const focusHtml = focusProject
      ? `<div class="zone-focus-slot">${renderCard(focusProject)}</div>`
      : `<div class="zone-focus-empty">
           <span class="zone-focus-empty-label">No focus set — tap a project's ⊙ to set zone focus</span>
         </div>`;
    return `
      <div class="zone-section zone-${key}">
        <div class="section-header">
          <div class="zone-icon">${icon}</div>
          <div style="flex:1;">
            <div class="section-title">${title}</div>
            <div class="zone-subtitle">${subtitle}</div>
          </div>
          <div class="section-count">${items.length} item${items.length !== 1 ? 's' : ''}</div>
        </div>
        <div class="zone-focus-label-row"><span class="zone-focus-header-tag">⊙ Focus</span></div>
        ${focusHtml}
        ${rest.length > 0 ? `
          <div class="zone-queue-label">Queue</div>
          ${rest.map(renderCard).join('')}` : ''}
      </div>`;
  }).join('');

  const completedCount = completed.length;
  const completedHtml = completedCount === 0 ? '' : `
    <div class="completed-toggle" onclick="toggleCompleted()">
      <span class="completed-toggle-label">${state.completedExpanded
        ? '▾ Hide completed'
        : `▸ Completed (${completedCount})`}</span>
    </div>
    ${state.completedExpanded ? `
      <div class="priority-section completed">
        <div class="section-header">
          <div class="section-dot"></div>
          <div class="section-title">Completed Projects</div>
          <div class="section-count">${completedCount} item${completedCount !== 1 ? 's' : ''}</div>
        </div>
        ${completed.map(renderCard).join('')}
      </div>` : ''}`;

  feed.innerHTML = zoneHtml + completedHtml;
}

function toggleP4() {
  state.p4Expanded = !state.p4Expanded;
  renderFeed();
}

function toggleCompleted() {
  state.completedExpanded = !state.completedExpanded;
  renderFeed();
}

async function completeProject(id) {
  await PUT(`/api/projects/${id}`, { completed: true, completed_at: new Date().toISOString() });
  await loadDashboard();
}

async function reopenProject(id) {
  await PUT(`/api/projects/${id}`, { completed: false, completed_at: null });
  await loadDashboard();
}

async function setZonePriority(id) {
  try {
    const res = await fetch(`/api/projects/${id}/set-zone-priority`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      toast(err.error || 'Could not set focus', 'error');
      return;
    }
    const p = state.projects.find(x => x.id === id);
    if (p) {
      // Clear any existing focus in this zone from state
      const zone = p.energy_zone;
      state.projects.forEach(x => {
        if (x.energy_zone === zone) x.zone_priority = false;
      });
      p.zone_priority = true;
      state.zonePriorities[zone] = id;
    }
    renderFeed();
    toast('Focus set', 'success');
  } catch (e) { toast('Could not set focus', 'error'); }
}

async function releaseZonePriority(id) {
  try {
    await POST(`/api/projects/${id}/release-zone-priority`, {});
    const p = state.projects.find(x => x.id === id);
    if (p) {
      p.zone_priority = false;
      state.zonePriorities[p.energy_zone] = null;
    }
    renderFeed();
    toast('Focus released', 'success');
  } catch (e) { toast('Could not release focus', 'error'); }
}

async function cyclePhase(id) {
  const project = state.projects.find(p => p.id === id);
  if (!project || !project.phases || project.phases.length === 0) return;
  const idx = project.phases.indexOf(project.phase);
  // If current phase is the last in the array, prompt to complete
  if (idx === project.phases.length - 1) {
    if (!confirm('You are on the last phase. Mark this project as complete?')) return;
    await completeProject(id);
    return;
  }
  const nextIdx = idx === -1 ? 0 : (idx + 1) % project.phases.length;
  const nextPhase = project.phases[nextIdx];
  await PUT(`/api/projects/${id}`, { phase: nextPhase });
  await loadDashboard();
}

async function cyclePhaseBack(id) {
  const project = state.projects.find(p => p.id === id);
  if (!project || !project.phases || project.phases.length === 0) return;
  const idx = project.phases.indexOf(project.phase);
  if (idx <= 0) return; // already at first phase or not found
  const prevPhase = project.phases[idx - 1];
  await PUT(`/api/projects/${id}`, { phase: prevPhase });
  await loadDashboard();
}

// ── Card ──────────────────────────────────────────────────────────────────────

function renderCard(p) {
  const deadlinePill = p.deadline_label
    ? `<div class="deadline-pill dl-${p.deadline_urgency||'ok'}">${esc(p.deadline_label)}</div>`
    : '';
  const badges = [];
  if (p.blocked) badges.push(`<span class="badge badge-blocked">BLOCKED</span>`);
  if (p.phase && p.phase.toLowerCase().includes('intake'))
    badges.push(`<span class="badge badge-new">NEW</span>`);

  let phaseDisplay = p.phase || '';
  if (p.phases && Array.isArray(p.phases) && p.phases.length > 0 && p.phase) {
    const idx = p.phases.indexOf(p.phase);
    if (idx !== -1) {
      phaseDisplay = `Phase ${idx + 1} of ${p.phases.length} — ${p.phase}`;
    }
  }
  const meta = [TYPE_LABELS[p.type]||'', PIPELINE_LABELS[p.pipeline]||'', phaseDisplay]
    .filter(Boolean).join(' · ');

  // Gap 3: last session note snippet on card
  const sessionSnip = p.last_session_note
    ? `<div class="card-session-note">
         <span class="session-note-date">${formatDateShort(p.last_session_at)}</span>
         ${esc(p.last_session_note)}
       </div>`
    : '';

  // Gap 5: ghostwriting lifecycle bar
  const gwBar = p.type === 'ghostwriting' ? renderGwBar(p.gw_lifecycle || {}) : '';

  // Mission badge
  const missionBadge = p.mission_critical
    ? `<span class="badge badge-mission">⭐ MISSION</span>`
    : '';

  // Complete/Reopen button
  let actionButton = '';
  if (p.completed) {
    actionButton = `<button class="badge badge-reopen" onclick="event.stopPropagation(); reopenProject('${p.id}')">Reopen</button>`;
  } else {
    actionButton = `<button class="badge badge-complete" onclick="event.stopPropagation(); completeProject('${p.id}')">Complete</button>`;
  }

  // Zone focus button (only for active projects in a named zone)
  let focusButton = '';
  if (!p.completed && p.energy_zone && p.energy_zone !== '') {
    if (p.zone_priority) {
      focusButton = `<button class="badge badge-focus-release" title="Release zone focus" onclick="event.stopPropagation(); releaseZonePriority('${p.id}')">⊙ Release</button>`;
    } else {
      focusButton = `<button class="badge badge-focus-set" title="Set as zone focus" onclick="event.stopPropagation(); setZonePriority('${p.id}')">⊙</button>`;
    }
  }

  // Next/Prev phase buttons
  let nextPhaseButton = '';
  let prevPhaseButton = '';
  if (p.phases && p.phases.length > 0) {
    const idx = p.phases.indexOf(p.phase);
    if (idx > 0) {
      prevPhaseButton = `<button class="badge badge-phase-prev" onclick="event.stopPropagation(); cyclePhaseBack('${p.id}')">Prev</button>`;
    }
    nextPhaseButton = `<button class="badge badge-phase-next" onclick="event.stopPropagation(); cyclePhase('${p.id}')">Next</button>`;
  }

  return `
    <div class="card card-p${p.priority||4}" onclick="openContextModal('${p.id}')">
      <div class="card-top">
        <div>
          <div class="card-title">${esc(p.name)}</div>
          <div class="card-meta">${esc(meta)}</div>
        </div>
        <div style="display:flex;gap:6px;align-items:center;flex-shrink:0;flex-wrap:wrap;justify-content:flex-end;">
          ${focusButton}${missionBadge}${badges.join('')}${deadlinePill}${actionButton}${prevPhaseButton}${nextPhaseButton}
        </div>
      </div>
      ${p.next_action ? `<div class="card-action">${esc(p.next_action)}</div>` : ''}
      ${gwBar}
      ${sessionSnip}
    </div>`;
}

// ── Gap 5: Ghostwriting lifecycle bar ────────────────────────────────────────

const GW_STAGES = [
  { key: 'commission_confirmed', label: 'Commission' },
  { key: 'draft_delivered',      label: 'Draft' },
  { key: 'revision_complete',    label: 'Revision' },
  { key: 'final_delivered',      label: 'Final' },
  { key: 'invoice_sent',         label: 'Invoice' },
  { key: 'payment_received',     label: 'Paid ✓' },
];

function renderGwBar(lifecycle) {
  return `<div class="gw-bar">${GW_STAGES.map(s => `
    <div class="gw-stage ${lifecycle[s.key] ? 'gw-done' : 'gw-pending'}" title="${s.label}">
      ${lifecycle[s.key] ? '✓' : '·'} <span class="gw-stage-label">${s.label}</span>
    </div>`).join('')}</div>`;
}

// ── Gap 4: Project Context Modal ──────────────────────────────────────────────

function openContextModal(id) {
  const p = state.projects.find(x => x.id === id);
  if (!p) return;

  const sessionHistory = (state.todayLog.session_notes || [])
    .filter(n => n.project_id === id)
    .map(n => `<div class="session-history-item">
      <span class="session-note-date">${formatTimeShort(n.at)}</span> ${esc(n.note)}
    </div>`).join('');

  const lastNote = p.last_session_note
    ? `<div class="context-block">
         <div class="context-section-label">Last session</div>
         <div class="context-last-note">${esc(p.last_session_note)}</div>
         <div class="session-note-date">${formatDateShort(p.last_session_at)}</div>
       </div>`
    : '';

  const blockedHtml = p.blocked
    ? `<div class="context-blocked">
         <span class="badge badge-blocked">BLOCKED</span>
         <span style="margin-left:8px;font-size:13px;color:var(--p1);">${esc(p.blocked_reason||'')}</span>
       </div>`
    : '';

  const gwSection = p.type === 'ghostwriting'
    ? `<div class="context-block">
         <div class="context-section-label">Commercial lifecycle</div>
         ${renderGwBar(p.gw_lifecycle||{})}
       </div>` : '';

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">${esc(p.name)}</div>
    <div class="modal-subtitle">${esc(TYPE_LABELS[p.type]||p.type)} · ${esc(PIPELINE_LABELS[p.pipeline]||p.pipeline)}</div>

    ${blockedHtml}

    <div class="context-block">
      <div class="context-section-label">Current phase</div>
      <div class="context-val">${esc(p.phase||'—')}</div>
    </div>

    <div class="context-block">
      <div class="context-section-label">Next action</div>
      <div class="context-val context-next-val">${esc(p.next_action||'—')}</div>
    </div>

    ${lastNote}
    ${gwSection}

    ${sessionHistory ? `
      <div class="context-block">
        <div class="context-section-label">Today's notes</div>
        <div class="session-history">${sessionHistory}</div>
      </div>` : ''}

    <div class="context-block">
      <div class="context-section-label">Log a session note</div>
      <textarea class="form-textarea" id="ctx-session-note"
        placeholder="What happened? What's stuck? What's the next crux?"
        rows="2"></textarea>
    </div>

    <div class="modal-actions">
      <button class="btn-danger"    onclick="deleteProject('${p.id}')">Delete</button>
      <button class="btn-secondary" onclick="openEditModal('${p.id}')">Edit</button>
      <button class="btn-secondary" onclick="logSessionNoteFromContext('${p.id}')">Log note</button>
      <button class="btn-primary"   onclick="closeModal()">Done</button>
    </div>`;
  showModal();
}

async function logSessionNoteFromContext(id) {
  const note = document.getElementById('ctx-session-note')?.value?.trim();
  if (!note) { toast('Nothing to log', 'error'); return; }
  try {
    const updated = await POST(`/api/projects/${id}/session-note`, { note });
    const i = state.projects.findIndex(p => p.id === id);
    if (i >= 0) state.projects[i] = { ...state.projects[i], ...updated };
    state.todayLog.session_notes = state.todayLog.session_notes || [];
    state.todayLog.session_notes.push({
      project_id: id, note,
      project_name: state.projects[i]?.name || '',
      at: new Date().toISOString(),
    });
    toast('Session note logged', 'success');
    renderFeed();
    openContextModal(id);
  } catch (e) { toast('Could not log note', 'error'); }
}

// ── Edit Project Modal ────────────────────────────────────────────────────────

function openEditModal(id) {
  const p   = state.projects.find(x => x.id === id);
  if (!p) return;
  const gwl = p.gw_lifecycle || {};

  const gwSection = p.type === 'ghostwriting' ? `
    <div class="sidebar-title" style="margin:20px 0 12px;">Ghostwriting Lifecycle</div>
    <div class="gw-checklist">
      ${GW_STAGES.map(s => `
        <label class="check-row" style="margin-bottom:10px;">
          <input type="checkbox" id="gw-${s.key}" ${gwl[s.key]?'checked':''}/>
          ${s.label}
        </label>`).join('')}
    </div>` : '';

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Edit — ${esc(p.name)}</div>
    <div class="form-group">
      <label class="form-label">Project Name</label>
      <input class="form-input" id="ed-name" value="${esc(p.name)}"/>
    </div>
    <div class="form-group">
      <label class="form-label">Phase</label>
      <input class="form-input" id="ed-phase" value="${esc(p.phase||'')}"/>
    </div>
    <div class="form-group">
      <label class="form-label">Next Action</label>
      <input class="form-input" id="ed-action" value="${esc(p.next_action||'')}"/>
    </div>
    <div class="form-group">
      <label class="form-label">Deadline</label>
      <input class="form-input" id="ed-deadline" type="date" value="${p.deadline||''}"/>
    </div>
    <div class="form-group">
      <label class="form-label">Priority</label>
      <div class="priority-grid" id="ed-priority-grid">
        ${[1,2,3,4].map(n => `
          <button class="pri-btn ${(p.priority||3)===n?'selected':''}"
            data-p="${n}" onclick="selectEditPriority(${n})">
            P${n}<br><span style="font-size:10px;font-weight:normal">${
              ['Hard deadline','Revenue','Audience','Infra'][n-1]}</span>
          </button>`).join('')}
      </div>
    </div>
    <div class="form-group">
      <label class="check-row">
        <input type="checkbox" id="ed-blocked" ${p.blocked?'checked':''}
          onchange="toggleBlockedReason(this.checked)"/>
        Project is blocked
      </label>
    </div>
    <div class="form-group" id="ed-blocked-reason-group" style="${p.blocked?'':'display:none'}">
      <label class="form-label">Blocked reason / smallest unblocking action</label>
      <input class="form-input" id="ed-blocked-reason" value="${esc(p.blocked_reason||'')}"/>
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <textarea class="form-textarea" id="ed-notes">${esc(p.notes||'')}</textarea>
    </div>
    <div class="form-group">
      <label class="check-row">
        <input type="checkbox" id="ed-money" ${p.money_attached?'checked':''}/>
        Money attached
      </label>
    </div>
    <div class="form-group">
      <label class="form-label">Energy Zone</label>
      <select class="form-select" id="ed-energy-zone">
        <option value="morning"   ${(p.energy_zone||'paid_work')==='morning'   ?'selected':''}>☀ Morning Block — Peak intellect + will · 08:30–10:30</option>
        <option value="paid_work" ${(p.energy_zone||'paid_work')==='paid_work' ?'selected':''}>◈ Paid Work — Client & commissioned · 11:00–13:00</option>
        <option value="evening"   ${(p.energy_zone||'paid_work')==='evening'   ?'selected':''}>◑ Evening Block — Outreach & sales</option>
      </select>
    </div>
    <div class="form-group">
      <label class="check-row">
        <input type="checkbox" id="ed-mission" ${p.mission_critical?'checked':''}/>
        ⭐ Mission-critical — core to long-term financial independence
      </label>
    </div>
    ${gwSection}
    ${buildPhaseTemplateSection(p)}
    <div class="modal-actions">
      <button class="btn-danger"    onclick="deleteProject('${p.id}')">Delete</button>
      <button class="btn-secondary" onclick="openContextModal('${p.id}')">← Back</button>
      <button class="btn-primary"   onclick="saveEditModal('${p.id}')">Save</button>
    </div>`;
  window._editPriority = p.priority || 3;
  showModal();
}

function selectEditPriority(n) {
  window._editPriority = n;
  document.querySelectorAll('#ed-priority-grid .pri-btn')
    .forEach(b => b.classList.toggle('selected', parseInt(b.dataset.p) === n));
}
function toggleBlockedReason(show) {
  document.getElementById('ed-blocked-reason-group').style.display = show ? '' : 'none';
}

async function saveEditModal(id) {
  const p   = state.projects.find(x => x.id === id);
  let gwl   = p?.gw_lifecycle || {};
  if (p?.type === 'ghostwriting') {
    gwl = {};
    GW_STAGES.forEach(s => { gwl[s.key] = document.getElementById(`gw-${s.key}`)?.checked || false; });
  }
  const payload = {
    name:           document.getElementById('ed-name').value.trim(),
    phase:          document.getElementById('ed-phase').value.trim(),
    next_action:    document.getElementById('ed-action').value.trim(),
    deadline:       document.getElementById('ed-deadline').value || null,
    priority:       window._editPriority || 3,
    blocked:        document.getElementById('ed-blocked').checked,
    blocked_reason: document.getElementById('ed-blocked-reason')?.value.trim() || null,
    notes:          document.getElementById('ed-notes').value.trim(),
    money_attached:  document.getElementById('ed-money').checked,
    energy_zone:     document.getElementById('ed-energy-zone')?.value || 'paid_work',
    mission_critical: document.getElementById('ed-mission')?.checked || false,
    gw_lifecycle:    gwl,
  };
  try {
    const updated = await PUT(`/api/projects/${id}`, payload);
    const i = state.projects.findIndex(p => p.id === id);
    if (i >= 0) state.projects[i] = updated;
    state.projects.sort((a,b) => (a.priority||4) - (b.priority||4));
    closeModal(); renderAll();
    toast('Project updated', 'success');
  } catch (e) { toast('Could not save', 'error'); }
}

function buildPhaseTemplateSection(p) {
  const templates = state.settings.phase_templates || {};
  const keys = Object.keys(templates);
  if (keys.length === 0) return '';
  const options = keys.map(k =>
    `<option value="${esc(k)}">${esc(k)} (${templates[k].length} phases)</option>`
  ).join('');
  return `
    <div class="form-group phase-template-section">
      <div class="sidebar-title" style="margin:20px 0 8px;font-size:11px;">Apply Phase Template</div>
      <div style="display:flex;gap:8px;align-items:center;">
        <select class="form-select" id="ed-template-select" style="flex:1;">
          <option value="">— select template —</option>
          ${options}
        </select>
        <button class="btn-secondary" style="white-space:nowrap;"
          onclick="openApplyTemplateConfirm('${p.id}')">Apply</button>
      </div>
      <div style="font-size:11px;color:var(--muted);margin-top:4px;">
        Replaces current phases. Current: ${p.phases && p.phases.length ? p.phases.join(' → ') : 'none'}
      </div>
    </div>`;
}

function openApplyTemplateConfirm(projectId) {
  const key = document.getElementById('ed-template-select')?.value;
  if (!key) { toast('Select a template first', 'error'); return; }
  const templates = state.settings.phase_templates || {};
  const phases    = templates[key] || [];
  const p         = state.projects.find(x => x.id === projectId);
  if (!p) return;
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Apply Template: ${esc(key)}</div>
    <p style="margin:12px 0;color:var(--muted);font-size:13px;">
      This will replace "${esc(p.name)}"'s current phases with:<br/>
      <strong style="color:var(--text);">${phases.join(' → ')}</strong>
    </p>
    <div class="form-group">
      <label class="form-label">Jot down anything from the current phases you want to keep</label>
      <textarea class="form-textarea" id="template-notes-scratch" rows="3"
        placeholder="Optional — scratch pad before you confirm…"></textarea>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="openEditModal('${projectId}')">← Back</button>
      <button class="btn-primary"   onclick="confirmApplyTemplate('${projectId}', '${esc(key)}')">Confirm Replace</button>
    </div>`;
}

async function confirmApplyTemplate(projectId, templateKey) {
  const templates = state.settings.phase_templates || {};
  const phases    = templates[templateKey];
  if (!phases) { toast('Template not found', 'error'); return; }
  try {
    const updated = await PUT(`/api/projects/${projectId}`, { phases, phase: phases[0] || '' });
    const i = state.projects.findIndex(p => p.id === projectId);
    if (i >= 0) state.projects[i] = updated;
    closeModal(); renderAll();
    toast(`Template "${templateKey}" applied`, 'success');
  } catch (e) { toast('Could not apply template', 'error'); }
}

async function deleteProject(id) {
  const p = state.projects.find(x => x.id === id);
  if (!p || !confirm(`Delete "${p.name}"? This cannot be undone.`)) return;
  try {
    await DEL(`/api/projects/${id}`);
    state.projects = state.projects.filter(x => x.id !== id);
    closeModal(); renderAll();
    toast('Project deleted', 'success');
  } catch (e) { toast('Could not delete', 'error'); }
}

// ── Posting Tracker ────────────────────────────────────────────────────────────

const POSTING_PLATFORMS = [
  { key: 'patreon',    label: 'Patreon',    note: 'Pays first' },
  { key: 'website',    label: 'Website',    note: 'SEO anchor' },
  { key: 'vip_group',  label: 'VIP Group',  note: 'Community' },
  { key: 'wa_channel', label: 'WA Channel', note: 'Broadcast' },
];

function renderPostingTracker() {
  const panel   = document.getElementById('posting-tracker-panel');
  if (!panel) return;
  const posting = state.postingToday || {};
  const streaks = state.postingStreaks || {};
  const today   = state.today || new Date().toISOString().slice(0,10);

  const rows = POSTING_PLATFORMS.map(p => {
    const done   = posting[p.key] || false;
    const streak = streaks[p.key] || 0;
    return `
      <div class="posting-row ${done ? 'posting-done' : ''}">
        <label class="posting-check-wrap">
          <input type="checkbox" class="posting-check" ${done ? 'checked' : ''}
            onchange="togglePosting('${p.key}', '${today}')"/>
          <span class="posting-platform-name">${p.label}</span>
          <span class="posting-platform-note">${p.note}</span>
        </label>
        <span class="posting-streak ${streak > 0 ? 'streak-active' : ''}">${streak > 0 ? `${streak}d` : '—'}</span>
      </div>`;
  }).join('');

  panel.innerHTML = `
    <div class="sidebar-section posting-section">
      <div class="sidebar-title">Today's Posts</div>
      ${rows}
    </div>`;
}

async function togglePosting(platform, dateStr) {
  try {
    const result = await POST('/api/posting-log/toggle', { platform, date: dateStr });
    state.postingToday   = result.posting;
    state.postingStreaks  = result.streaks;
    renderPostingTracker();
  } catch (e) { toast('Could not save', 'error'); }
}

// ── Inbox ──────────────────────────────────────────────────────────────────────

function inboxExpiryLabel(expiresAt) {
  if (!expiresAt) return '';
  const diffMs  = new Date(expiresAt) - new Date();
  const diffH   = diffMs / 3600000;
  const diffD   = diffMs / 86400000;
  if (diffH < 0)  return `<span class="inbox-expiry expiry-gone">expired</span>`;
  if (diffH < 12) return `<span class="inbox-expiry expiry-critical">⚠ ${Math.ceil(diffH)}h left</span>`;
  if (diffH < 24) return `<span class="inbox-expiry expiry-urgent">⚠ &lt;24h left</span>`;
  if (diffD < 3)  return `<span class="inbox-expiry expiry-soon">${Math.ceil(diffD)}d left</span>`;
  return `<span class="inbox-expiry expiry-ok">${Math.ceil(diffD)}d left</span>`;
}

function renderInbox() {
  const panel  = document.getElementById('inbox-panel');
  const items  = state.inbox || [];
  const caps   = state.caps;
  const urgent = state.inboxUrgent || 0;

  const urgentBanner = urgent > 0
    ? `<div class="inbox-urgent-banner">⚠ ${urgent} item${urgent !== 1 ? 's' : ''} expire within 24 hours — triage now or lose them forever.</div>`
    : '';

  const capBar = `<div class="inbox-cap-bar">
    <span class="inbox-cap-item">Inbox ${caps.inbox_count||items.length}/${caps.inbox_max}</span>
    <span class="inbox-cap-sep">·</span>
    <span class="inbox-cap-item">Projects ${caps.total_active}/${caps.total_cap}</span>
    <span class="inbox-cap-sep">·</span>
    <button class="inbox-dormant-link" onclick="openDormantModal()">Dormant ${caps.dormant_count}/${caps.dormant_max}</button>
  </div>`;

  const rows = items.length === 0
    ? `<div class="inbox-empty">Nothing in the inbox. Add an idea below.</div>`
    : items.map(item => `
      <div class="inbox-item">
        <div class="inbox-item-title">${esc(item.title)}</div>
        <div class="inbox-item-footer">
          ${inboxExpiryLabel(item.expires_at)}
          <button class="inbox-triage-btn" onclick="openTriageModal('${item.id}')">Triage →</button>
        </div>
      </div>`).join('');

  panel.innerHTML = `
    <div class="sidebar-section inbox-section">
      <div class="sidebar-title">
        Inbox
        ${items.length > 0 ? `<span class="inbox-count-badge ${urgent > 0 ? 'urgent' : ''}">${items.length}</span>` : ''}
      </div>
      ${urgentBanner}
      ${capBar}
      ${rows}
      <div class="inbox-capture-row">
        <input class="inbox-capture-input" id="inbox-capture-input"
          placeholder="New idea — one line, no friction…"
          onkeydown="if(event.key==='Enter')submitInboxCapture()"/>
        <button class="inbox-capture-btn" onclick="submitInboxCapture()">+</button>
      </div>
    </div>`;
}

async function submitInboxCapture() {
  const input = document.getElementById('inbox-capture-input');
  const title = input?.value?.trim();
  if (!title) return;
  const caps = state.caps;
  if ((caps.inbox_count || state.inbox.length) >= (caps.inbox_max || 15)) {
    toast(`Inbox full (${caps.inbox_max} items). Triage something first.`, 'error');
    return;
  }
  try {
    const item = await POST('/api/inbox', { title });
    state.inbox.push(item);
    state.caps.inbox_count = (state.caps.inbox_count || 0) + 1;
    input.value = '';
    renderInbox();
    toast('Captured', 'success');
  } catch (e) {
    const msg = e.message || '';
    toast(msg.includes('full') ? 'Inbox full — triage first' : 'Could not capture', 'error');
  }
}

// ── Triage Modal ───────────────────────────────────────────────────────────────

let _triageItemId = null;

function openTriageModal(id) {
  const item = state.inbox.find(i => i.id === id);
  if (!item) return;
  _triageItemId = id;
  const q = state.triageQuestion;
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Triage</div>
    <div class="triage-item-title">"${esc(item.title)}"</div>
    <div class="triage-question">${esc(q)}</div>
    ${item.notes ? `<div class="triage-notes">${esc(item.notes)}</div>` : ''}
    <div class="triage-actions">
      <button class="btn-primary triage-btn-promote" onclick="openPromoteFromTriage('${id}')">
        ↑ Promote to Project
      </button>
      <button class="btn-secondary triage-btn-archive" onclick="archiveFromTriage('${id}')">
        ◎ Archive (Dormant)
      </button>
      <button class="btn-danger triage-btn-delete" onclick="deleteFromTriage('${id}')">
        ✕ Delete Forever
      </button>
    </div>
    <div class="triage-footer">
      ${inboxExpiryLabel(item.expires_at)}
      <span class="triage-caps-hint">Projects: ${state.caps.total_active}/${state.caps.total_cap} · Dormant: ${state.caps.dormant_count}/${state.caps.dormant_max}</span>
    </div>
    <div style="margin-top:16px;border-top:1px solid var(--border);padding-top:12px;">
      <div style="font-size:11px;color:var(--muted);font-family:var(--font-mono);margin-bottom:6px;text-transform:uppercase;letter-spacing:.06em;">Edit triage question</div>
      <input class="form-input" id="triage-q-edit" value="${esc(q)}" style="font-size:13px;"/>
      <button class="btn-secondary" style="margin-top:6px;font-size:12px;" onclick="saveTriageQuestion()">Save question</button>
    </div>
    <div class="modal-actions"><button class="btn-secondary" onclick="closeModal()">Cancel</button></div>`;
  showModal();
}

async function saveTriageQuestion() {
  const q = document.getElementById('triage-q-edit')?.value?.trim();
  if (!q) return;
  try {
    await PUT('/api/settings/triage-question', { question: q });
    state.triageQuestion = q;
    toast('Triage question updated', 'success');
  } catch (e) { toast('Could not save', 'error'); }
}

async function archiveFromTriage(id) {
  if (state.caps.dormant_count >= state.caps.dormant_max) {
    toast(`Dormant archive full (${state.caps.dormant_max}). Delete a dormant idea to make room.`, 'error');
    return;
  }
  try {
    await POST(`/api/inbox/${id}/archive`);
    state.inbox = state.inbox.filter(i => i.id !== id);
    state.caps.inbox_count = Math.max(0, (state.caps.inbox_count||1) - 1);
    state.caps.dormant_count = (state.caps.dormant_count||0) + 1;
    closeModal(); renderInbox();
    toast('Archived to Dormant', 'success');
  } catch (e) { toast('Could not archive', 'error'); }
}

async function deleteFromTriage(id) {
  const item = state.inbox.find(i => i.id === id);
  if (!item) return;
  if (!confirm(`Delete "${item.title}" permanently?\n\nThis cannot be undone and cannot be recovered. Ever.`)) return;
  try {
    await DEL(`/api/inbox/${id}`);
    state.inbox = state.inbox.filter(i => i.id !== id);
    state.caps.inbox_count = Math.max(0, (state.caps.inbox_count||1) - 1);
    closeModal(); renderInbox();
    toast('Deleted permanently', 'success');
  } catch (e) { toast('Could not delete', 'error'); }
}

// ── Promote Flow ───────────────────────────────────────────────────────────────

let _promoteState = {};

function openPromoteFromTriage(id) {
  const item = state.inbox.find(i => i.id === id);
  if (!item) return;
  _promoteState = { id, name: item.title, energy_zone: 'paid_work', priority: 3, mission_critical: false };
  renderPromoteStep();
}

function renderPromoteStep() {
  const s    = _promoteState;
  const caps = state.caps;
  const zoneInfo = [
    { key: 'morning',   icon: '☀', label: 'Morning Block',  sub: '08:30–10:30',     used: caps.zone_counts?.morning   || 0, cap: caps.zone_caps?.morning   || 3 },
    { key: 'paid_work', icon: '◈', label: 'Paid Work',      sub: '11:00–13:00',     used: caps.zone_counts?.paid_work || 0, cap: caps.zone_caps?.paid_work || 3 },
    { key: 'evening',   icon: '◑', label: 'Evening Block',  sub: 'End of day',      used: caps.zone_counts?.evening   || 0, cap: caps.zone_caps?.evening   || 2 },
  ];
  const zoneButtons = zoneInfo.map(z => {
    const full    = z.used >= z.cap;
    const sel     = s.energy_zone === z.key;
    return `<button class="zone-pick-btn ${sel ? 'selected' : ''} ${full ? 'full' : ''}"
      onclick="${full ? '' : `selectPromoteZone('${z.key}')`}" ${full ? 'disabled title="Zone full"' : ''}>
      <span class="zone-pick-icon">${z.icon}</span>
      <span class="zone-pick-name">${z.label}</span>
      <span class="zone-pick-sub">${z.sub}</span>
      <span class="zone-pick-cap ${full ? 'cap-full' : ''}">${z.used}/${z.cap}</span>
    </button>`;
  }).join('');

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Promote to Project</div>
    <div class="triage-item-title">"${esc(s.name)}"</div>
    <div class="form-group" style="margin-top:16px;">
      <label class="form-label">Name (optional edit)</label>
      <input class="form-input" id="prm-name" value="${esc(s.name)}"/>
    </div>
    <div class="form-group">
      <label class="form-label">Zone — total active: ${caps.total_active}/${caps.total_cap}</label>
      <div class="zone-pick-grid">${zoneButtons}</div>
    </div>
    <div class="form-group">
      <label class="form-label">Priority within zone</label>
      <div class="priority-grid">
        ${[1,2,3,4].map(n => `
          <button class="pri-btn ${s.priority===n?'selected':''}" data-p="${n}" onclick="selectPromotePriority(${n})">
            P${n}<br><span style="font-size:10px;font-weight:normal">${['Hard deadline','Revenue','Audience','Infra'][n-1]}</span>
          </button>`).join('')}
      </div>
    </div>
    <div class="form-group">
      <label class="check-row">
        <input type="checkbox" id="prm-mission" ${s.mission_critical?'checked':''}/>
        ⭐ Mission-critical
      </label>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="openTriageModal('${s.id}')">← Back</button>
      <button class="btn-primary"   onclick="confirmPromote()">Add to Projects →</button>
    </div>`;
}

function selectPromoteZone(z) {
  _promoteState.energy_zone = z;
  renderPromoteStep();
}
function selectPromotePriority(n) {
  _promoteState.priority = n;
  renderPromoteStep();
}

async function confirmPromote() {
  const s    = _promoteState;
  s.name     = document.getElementById('prm-name')?.value?.trim() || s.name;
  s.mission_critical = document.getElementById('prm-mission')?.checked || false;
  try {
    const project = await POST(`/api/inbox/${s.id}/promote`, {
      name: s.name, energy_zone: s.energy_zone,
      priority: s.priority, mission_critical: s.mission_critical,
    });
    state.inbox    = state.inbox.filter(i => i.id !== s.id);
    state.projects.push(project);
    state.projects.sort((a,b) => (a.priority||4) - (b.priority||4));
    state.caps.total_active  = (state.caps.total_active||0) + 1;
    state.caps.inbox_count   = Math.max(0, (state.caps.inbox_count||1) - 1);
    if (state.caps.zone_counts) state.caps.zone_counts[s.energy_zone] = (state.caps.zone_counts[s.energy_zone]||0) + 1;
    closeModal(); renderAll();
    toast(`"${s.name}" added to projects`, 'success');
  } catch (e) {
    const body = e.message || '';
    toast(body.includes('cap') || body.includes('full') ? `Cap reached — complete a project first` : 'Could not promote', 'error');
  }
}

// ── Dormant Browser ────────────────────────────────────────────────────────────

async function openDormantModal() {
  let dormant = [];
  try { dormant = await GET('/api/dormant'); } catch (e) { toast('Could not load dormant', 'error'); return; }
  const caps = state.caps;
  const rows = dormant.length === 0
    ? `<div style="color:var(--muted);font-size:13px;padding:10px 0;">No dormant ideas yet.</div>`
    : dormant.map(item => `
      <div class="dormant-item">
        <div class="dormant-item-title">${esc(item.title)}</div>
        ${item.notes ? `<div class="dormant-item-notes">${esc(item.notes)}</div>` : ''}
        <div class="dormant-item-footer">
          <span class="dormant-date">Archived ${item.archived_at ? item.archived_at.slice(0,10) : '—'}</span>
          <div style="display:flex;gap:6px;">
            <button class="badge badge-phase-next" onclick="reviveDormant('${item.id}')">↑ Revive</button>
            <button class="badge badge-reopen" style="background:var(--p1-bg);color:var(--p1);border-color:var(--p1-border);"
              onclick="deleteDormant('${item.id}')">✕ Delete</button>
          </div>
        </div>
      </div>`).join('');

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Dormant Ideas</div>
    <div class="modal-subtitle">${dormant.length}/${caps.dormant_max} slots used · Reviving an idea sends it back to your inbox (7-day clock restarts)</div>
    ${rows}
    <div class="modal-actions"><button class="btn-secondary" onclick="closeModal()">Close</button></div>`;
  showModal();
}

async function reviveDormant(id) {
  if ((state.caps.inbox_count||0) >= (state.caps.inbox_max||15)) {
    toast('Inbox full — triage something first', 'error'); return;
  }
  try {
    await POST(`/api/dormant/${id}/revive`);
    const dormantItems = document.querySelectorAll('.dormant-item');
    state.caps.inbox_count = (state.caps.inbox_count||0) + 1;
    state.caps.dormant_count = Math.max(0, (state.caps.dormant_count||1) - 1);
    await loadDashboard();
    openDormantModal();
    toast('Revived to inbox', 'success');
  } catch (e) { toast('Could not revive', 'error'); }
}

async function deleteDormant(id) {
  if (!confirm('Delete this idea permanently? It cannot be recovered.')) return;
  try {
    await DEL(`/api/dormant/${id}`);
    state.caps.dormant_count = Math.max(0, (state.caps.dormant_count||1) - 1);
    openDormantModal();
    toast('Deleted permanently', 'success');
  } catch (e) { toast('Could not delete', 'error'); }
}

// ── Lead Measures — prominent actuals ────────────────────────────────────────

function renderLeadMeasures() {
  const panel = document.getElementById('lead-measures-panel');
  const m     = state.leadMeasures || {};
  const t     = state.settings.lead_measure_targets || {};
  const monthLabel = new Date().toLocaleDateString('en-ZA', { month: 'long', year: 'numeric' });

  const rows = [
    { key: 'pitches_sent',     label: 'Pitches sent' },
    { key: 'pitch_meetings',   label: 'Pitch meetings' },
    { key: 'in_active_review', label: 'In active review' },
    { key: 'patreon_leads',    label: 'Patreon leads' },
    { key: 'follow_ups',       label: 'Follow-ups done' },
  ].map(({ key, label }) => {
    const val    = m[key] ?? 0;
    const target = t[key];
    const cls    = val === 0 ? 'measure-zero'
                 : (target != null && val >= target) ? 'measure-ok' : 'measure-good';
    const targetStr = target != null
      ? `<span class="measure-of">/ ${target}</span>`
      : `<span class="measure-of">/ —</span>`;
    return `
      <div class="measure-row">
        <div class="measure-label">${label}</div>
        <div class="measure-right">
          <button class="measure-btn-large" onclick="incrementMeasure('${key}',1)" title="Log one">+1</button>
          <div class="measure-val-block">
            <span class="measure-val ${cls}">${val}</span>${targetStr}
          </div>
          <button class="measure-btn-sm" onclick="incrementMeasure('${key}',-1)" title="Undo one">−</button>
        </div>
      </div>`;
  }).join('');

  panel.innerHTML = `
    <div class="sidebar-section">
      <div class="sidebar-title">Lead Measures — ${monthLabel}
        <span class="lead-hint">tap +1 to log</span>
      </div>
      ${rows}
      <button class="btn-card" style="width:100%;text-align:center;margin-top:10px;"
        onclick="openSettingsModal()">Set monthly targets →</button>
    </div>`;
}

async function incrementMeasure(key, delta) {
  try {
    const updated = await PUT('/api/lead-measures', { [key]: delta > 0 ? '+1' : '-1' });
    state.leadMeasures = updated;
    renderLeadMeasures();
    toast(delta > 0 ? `+1 logged` : 'Undone', 'success');
  } catch (e) { toast('Could not update measure', 'error'); }
}

// ── Content Pipeline ──────────────────────────────────────────────────────────

const STATUS_LABELS  = { live: '✓ Live', in_progress: '~ In progress', pending: '↻ Pending', not_started: '—' };
const STATUS_CLASSES = { live: 'ps-live', in_progress: 'ps-in_progress', pending: 'ps-pending', not_started: 'ps-not_started' };
const STATUS_CYCLE   = ['not_started', 'in_progress', 'pending', 'live'];

// Track which chapter's assets are expanded
let _expandedChapterId = null;

function renderPipeline() {
  const panel = document.getElementById('pipeline-panel');

  // Group chapters by book (preserve order)
  const groups = [];
  const groupMap = {};
  state.contentPipeline.forEach(e => {
    const book = e.book || '—';
    if (!groupMap[book]) { groupMap[book] = []; groups.push(book); }
    groupMap[book].push(e);
  });

  const BOOK_LABELS = { ROTRQ: 'Rise of the Rain Queen', OAO: 'Outlaws and Outcasts', MOSAS: 'Man of Stone and Shadow' };

  const renderRow = e => {
    const vip = e.vip_group_status || 'not_started';
    const pat = e.patreon_status  || 'not_started';
    const wst = e.website_status  || 'not_started';
    const wa  = e.wa_channel_status || 'not_started';
    const isExpanded = _expandedChapterId === e.id;
    const assets = e.assets || {};
    const hasAssets = assets.tagline || assets.blurb || assets.synopsis || assets.image_prompt;
    const assetRow = isExpanded && hasAssets ? `
      <tr class="pipeline-assets-row">
        <td colspan="5">
          <div class="pipeline-assets-drawer">
            <div class="pipeline-assets-label">Assets</div>
            ${assets.tagline  ? `<div class="pipeline-asset-field"><span class="pipeline-asset-key">Tagline</span><span>${esc(assets.tagline)}</span></div>` : ''}
            ${assets.blurb    ? `<div class="pipeline-asset-field"><span class="pipeline-asset-key">Blurb</span><span>${esc(assets.blurb)}</span></div>` : ''}
            ${assets.synopsis ? `<div class="pipeline-asset-field"><span class="pipeline-asset-key">Synopsis</span><span class="pipeline-synopsis-text">${esc(assets.synopsis)}</span></div>` : ''}
            ${assets.image_prompt ? `<div class="pipeline-asset-field"><span class="pipeline-asset-key">Image Prompt</span><span class="pipeline-synopsis-text">${esc(assets.image_prompt)}</span></div>` : ''}
            <div style="margin-top:8px;display:flex;gap:6px;">
              <button class="btn-card" onclick="openEditChapterModal('${e.id}')">Edit assets</button>
              <button class="btn-card" onclick="toggleChapterAssets('${e.id}')">Hide</button>
            </div>
          </div>
        </td>
      </tr>` : '';
    const chevron = hasAssets ? (isExpanded ? '▾' : '▸') : '';
    return `<tr class="pipeline-row" onclick="${hasAssets ? `toggleChapterAssets('${e.id}')` : ''}">
      <td>${chevron ? `<span style="cursor:pointer;width:14px;display:inline-block;">${chevron}</span>` : ''} ${esc(e.chapter)}</td>
      <td><span class="${STATUS_CLASSES[vip]}" style="cursor:pointer" onclick="event.stopPropagation();cyclePipelineStatus('${e.id}','vip_group_status')">${STATUS_LABELS[vip]}</span></td>
      <td><span class="${STATUS_CLASSES[pat]}" style="cursor:pointer" onclick="event.stopPropagation();cyclePipelineStatus('${e.id}','patreon_status')">${STATUS_LABELS[pat]}</span></td>
      <td><span class="${STATUS_CLASSES[wst]}" style="cursor:pointer" onclick="event.stopPropagation();cyclePipelineStatus('${e.id}','website_status')">${STATUS_LABELS[wst]}</span></td>
      <td><span class="${STATUS_CLASSES[wa]}" style="cursor:pointer" onclick="event.stopPropagation();cyclePipelineStatus('${e.id}','wa_channel_status')">${STATUS_LABELS[wa]}</span>
        ${e.notes ? `<span class="pipeline-action">${esc(e.notes)}</span>` : ''}</td>
    </tr>${assetRow}`;
  };

  const tableBody = groups.length > 1
    ? groups.map(book => `
        <tr class="pipeline-book-header">
          <td colspan="5">${esc(BOOK_LABELS[book] || book)}<span class="pipeline-book-count">${groupMap[book].length} chapters</span></td>
        </tr>
        ${groupMap[book].map(renderRow).join('')}`).join('')
    : state.contentPipeline.map(renderRow).join('');

  panel.innerHTML = `
    <div class="sidebar-section">
      <div class="sidebar-title">Content Pipeline</div>
      <table class="pipeline-table">
        <thead><tr><th>Chapter</th><th>VIP Group</th><th>Patreon</th><th>Website</th><th>WA Channel</th></tr></thead>
        <tbody>${tableBody}</tbody>
      </table>
      <button class="btn-pipeline-add" onclick="openAddChapterModal()">+ Add chapter</button>
    </div>`;
}

function toggleChapterAssets(id) {
  _expandedChapterId = _expandedChapterId === id ? null : id;
  renderPipeline();
}

function openEditChapterModal(id) {
  const e = state.contentPipeline.find(x => x.id === id);
  if (!e) return;
  const assets = e.assets || {};
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Edit Assets — ${esc(e.chapter)}</div>
    ${e.book ? `<div style="font-size:12px;color:var(--muted);margin-bottom:14px;">${esc(e.book)}</div>` : ''}
    <div class="form-group"><label class="form-label">Tagline</label>
      <input class="form-input" id="edit-ch-tagline" value="${esc(assets.tagline||'')}" placeholder="One-sentence Hollywood logline…"/></div>
    <div class="form-group"><label class="form-label">Blurb</label>
      <textarea class="form-textarea" id="edit-ch-blurb" rows="4" placeholder="4-sentence marketing blurb…">${esc(assets.blurb||'')}</textarea></div>
    <div class="form-group"><label class="form-label">Synopsis</label>
      <textarea class="form-textarea" id="edit-ch-synopsis" rows="7" placeholder="500–600 word working synopsis…">${esc(assets.synopsis||'')}</textarea></div>
    <div class="form-group"><label class="form-label">Excerpt <span style="color:var(--muted);font-size:11px;">(optional — curated passage for marketing)</span></label>
      <textarea class="form-textarea" id="edit-ch-excerpt" rows="3" placeholder="Paste a short excerpt…">${esc(assets.excerpt||'')}</textarea></div>
    <div class="form-group"><label class="form-label">Image Prompt</label>
      <textarea class="form-textarea" id="edit-ch-image-prompt" rows="4" placeholder="Image generation prompt for the chapter banner…">${esc(assets.image_prompt||'')}</textarea></div>
    <div class="modal-actions">
      <button class="btn-danger"    onclick="deleteChapter('${e.id}')">Delete chapter</button>
      <button class="btn-secondary" onclick="renderPipeline();closeModal();">Cancel</button>
      <button class="btn-primary"   onclick="saveChapterAssets('${e.id}')">Save</button>
    </div>`;
  showModal();
}

async function saveChapterAssets(id) {
  try {
    const updated = await PUT(`/api/content-pipeline/${id}`, {
      assets: {
        tagline:      document.getElementById('edit-ch-tagline').value.trim()      || null,
        blurb:        document.getElementById('edit-ch-blurb').value.trim()        || null,
        synopsis:     document.getElementById('edit-ch-synopsis').value.trim()     || null,
        excerpt:      document.getElementById('edit-ch-excerpt').value.trim()      || null,
        image_prompt: document.getElementById('edit-ch-image-prompt').value.trim() || null,
      }
    });
    const i = state.contentPipeline.findIndex(x => x.id === id);
    if (i >= 0) state.contentPipeline[i] = updated;
    closeModal(); renderPipeline();
    toast('Assets updated', 'success');
  } catch (e) { toast('Could not save', 'error'); }
}

async function deleteChapter(id) {
  const e = state.contentPipeline.find(x => x.id === id);
  if (!e || !confirm(`Delete "${e.chapter}"?`)) return;
  try {
    await DEL(`/api/content-pipeline/${id}`);
    state.contentPipeline = state.contentPipeline.filter(x => x.id !== id);
    closeModal(); renderPipeline();
    toast('Chapter deleted', 'success');
  } catch (e) { toast('Could not delete', 'error'); }
}

async function cyclePipelineStatus(id, field) {
  const e    = state.contentPipeline.find(x => x.id === id);
  if (!e) return;
  const next = STATUS_CYCLE[(STATUS_CYCLE.indexOf(e[field]||'not_started') + 1) % STATUS_CYCLE.length];
  try {
    const updated = await PUT(`/api/content-pipeline/${id}`, { [field]: next });
    const i = state.contentPipeline.findIndex(x => x.id === id);
    if (i >= 0) state.contentPipeline[i] = updated;
    renderPipeline();
  } catch (e) { toast('Could not update', 'error'); }
}

// ── Quick Projects ────────────────────────────────────────────────────────────

function renderQuickProjects() {
  const panel = document.getElementById('quick-projects-panel');
  const rows  = state.projects.map(p => {
    let cls  = 'qp-meta';
    let meta = [PIPELINE_LABELS[p.pipeline], p.phase].filter(Boolean).join(' · ');
    if (p.blocked) { cls = 'qp-meta qp-meta-blocked'; meta = 'BLOCKED' + (p.blocked_reason ? ': ' + p.blocked_reason : ''); }
    const pri = p.priority || 4;
    return `<div class="qp-row" onclick="openContextModal('${p.id}')">
      <div class="qp-dot qp-dot-${pri}"></div>
      <div class="qp-content">
        <div class="qp-name">${esc(p.name)}</div>
        <div class="${cls}">${esc(meta)}</div>
      </div>
    </div>`;
  }).join('');
  panel.innerHTML = `
    <div class="sidebar-section">
      <div class="sidebar-title">All Projects</div>
      ${rows || '<div style="color:var(--muted);font-size:13px;">No projects yet.</div>'}
    </div>`;
}

// ── New Project Capture ───────────────────────────────────────────────────────

let captureState = {};

function openNewProjectModal() {
  captureState = { step: 1, type: null, priority: 3, money_attached: false, phaseTemplate: '', energy_zone: 'paid_work', mission_critical: false };
  renderCaptureStep();
  showModal();
}

function renderCaptureStep() {
  const s = captureState;
  let html = '';
  if (s.step === 1) {
    html = `
      <div class="modal-title">Capture Incoming Work</div>
      <div class="modal-subtitle">What kind of project is this?</div>
      <div class="type-grid">
        ${[['tv_script','TV Script','Paid episodic — outline in, script due'],
           ['ghostwriting','Ghostwriting','Commissioned for someone else'],
           ['tv_series','TV Series','Original series development'],
           ['original_fiction','Original Novel','Long fiction from scratch'],
           ['original_screenplay','Original Screenplay','Feature or short film'],
           ['podcast','Podcast','Episode series — audio or video'],
           ['other','Other','Everything else']
          ].map(([val,label,sub]) => `
          <button class="type-btn ${s.type===val?'selected':''}" onclick="selectType('${val}')">
            <div style="font-weight:bold">${label}</div>
            <div style="font-size:11px;margin-top:3px;color:var(--muted)">${sub}</div>
          </button>`).join('')}
      </div>
      <div class="modal-actions">
        <button class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn-primary" onclick="captureNext()" ${s.type?'':'disabled'}>Next →</button>
      </div>`;
  } else if (s.step === 2) {
    html = `
      <div class="modal-step-indicator">Step 2 of 3 — Details</div>
      <div class="modal-title">Project Details</div>
      <div class="form-group">
        <label class="form-label">Project Name *</label>
        <input class="form-input" id="cap-name" placeholder="What do you call it?" value="${esc(s.name||'')}"/>
      </div>
      <div class="form-group">
        <label class="form-label">Source</label>
        <input class="form-input" id="cap-source" placeholder="Phone call, email, own idea…" value="${esc(s.source||'')}"/>
      </div>
      <div class="form-group">
        <label class="form-label">Deadline (if known)</label>
        <input class="form-input" id="cap-deadline" type="date" value="${s.deadline||''}"/>
      </div>
      <div class="form-group">
        <label class="form-label">Pipeline</label>
        <select class="form-select" id="cap-pipeline">
          <option value="creative_development" ${s.pipeline==='creative_development'?'selected':''}>Creative Development</option>
          <option value="sales_funding"        ${s.pipeline==='sales_funding'?'selected':''}>Sales & Funding</option>
          <option value="publishing_engine"    ${s.pipeline==='publishing_engine'?'selected':''}>Publishing Engine</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Phase Template (optional)</label>
        <select class="form-select" id="cap-phase-template">
          <option value="">— No template —</option>
          ${Object.keys(state.settings.phase_templates || {}).map(key => `
            <option value="${key}" ${s.phaseTemplate===key?'selected':''}>${key}</option>`).join('')}
        </select>
      </div>
      <div class="modal-actions">
        <button class="btn-secondary" onclick="captureBack()">← Back</button>
        <button class="btn-primary"   onclick="captureNext()">Next →</button>
      </div>`;
  } else if (s.step === 3) {
    html = `
      <div class="modal-step-indicator">Step 3 of 3 — Priority & First Action</div>
      <div class="modal-title">Priority & First Action</div>
      <div class="form-group">
        <label class="form-label">Priority</label>
        <div class="priority-grid">
          ${[1,2,3,4].map(n => `
            <button class="pri-btn ${s.priority===n?'selected':''}" data-p="${n}" onclick="selectPriority(${n})">
              P${n}<br><span style="font-size:10px;font-weight:normal">${['Hard deadline','Revenue','Audience','Infra'][n-1]}</span>
            </button>`).join('')}
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">First Next Action</label>
        <input class="form-input" id="cap-action" placeholder="Smallest concrete next step?" value="${esc(s.next_action||'')}"/>
      </div>
      <div class="form-group">
        <label class="form-label">Notes (optional)</label>
        <textarea class="form-textarea" id="cap-notes" placeholder="Any context…">${esc(s.notes||'')}</textarea>
      </div>
      <div class="form-group">
        <label class="check-row">
          <input type="checkbox" id="cap-money" ${s.money_attached?'checked':''}/>
          Money attached to this project
        </label>
      </div>
      <div class="form-group">
        <label class="form-label">Energy Zone</label>
        <select class="form-select" id="cap-energy-zone">
          <option value="morning"   ${s.energy_zone==='morning'   ?'selected':''}>☀ Morning Block — Peak intellect + will · 08:30–10:30</option>
          <option value="paid_work" ${s.energy_zone==='paid_work'||!s.energy_zone?'selected':''}>◈ Paid Work — Client & commissioned · 11:00–13:00</option>
          <option value="evening"   ${s.energy_zone==='evening'   ?'selected':''}>◑ Evening Block — Outreach & sales</option>
        </select>
      </div>
      <div class="form-group">
        <label class="check-row">
          <input type="checkbox" id="cap-mission" ${s.mission_critical?'checked':''}/>
          ⭐ Mission-critical — core to long-term financial independence
        </label>
      </div>
      <div class="modal-actions">
        <button class="btn-secondary" onclick="captureBack()">← Back</button>
        <button class="btn-primary"   onclick="captureSubmit()">Add Project</button>
      </div>`;
  }
  document.getElementById('modal-content').innerHTML = html;
}

function selectType(val) {
  captureState.type = val;
  if (['tv_script','ghostwriting','tv_series','original_fiction','original_screenplay','podcast'].includes(val))
    captureState.pipeline = 'creative_development';
  renderCaptureStep();
}
function selectPriority(n) { captureState.priority = n; renderCaptureStep(); }
function captureNext() {
  if (captureState.step === 2) {
    captureState.name     = document.getElementById('cap-name').value.trim();
    captureState.source   = document.getElementById('cap-source').value.trim();
    captureState.deadline = document.getElementById('cap-deadline').value || null;
    captureState.pipeline = document.getElementById('cap-pipeline').value;
    captureState.phaseTemplate = document.getElementById('cap-phase-template').value;
    if (!captureState.name) { toast('Project name is required', 'error'); return; }
  }
  captureState.step++;
  renderCaptureStep();
}
function captureBack() { captureState.step = Math.max(1, captureState.step - 1); renderCaptureStep(); }

async function captureSubmit() {
  captureState.next_action     = document.getElementById('cap-action').value.trim();
  captureState.notes           = document.getElementById('cap-notes').value.trim();
  captureState.money_attached  = document.getElementById('cap-money').checked;
  captureState.energy_zone     = document.getElementById('cap-energy-zone')?.value || 'flexible';
  captureState.mission_critical = document.getElementById('cap-mission')?.checked || false;
  // Use phase template if defined, otherwise default logic
  const phaseTemplates = state.settings.phase_templates || {};
  let phases = [];
  let phase = '';

  // 1. Check if a specific template was selected in the dropdown
  if (captureState.phaseTemplate && phaseTemplates[captureState.phaseTemplate]) {
    phases = Array.isArray(phaseTemplates[captureState.phaseTemplate]) 
      ? phaseTemplates[captureState.phaseTemplate] 
      : [phaseTemplates[captureState.phaseTemplate]];
    phase = phases[0] || '';
  }

  // 2. Fall back to type default if no phase set yet
  if (!phase && phaseTemplates[captureState.type]) {
    phases = Array.isArray(phaseTemplates[captureState.type])
      ? phaseTemplates[captureState.type]
      : [phaseTemplates[captureState.type]];
    phase = phases[0] || '';
  }

  // 3. Last resort hardcoded defaults
  if (!phase) {
    phase = captureState.pipeline === 'creative_development' ? 'Phase 1 — World & Bible' : 'New';
    phases = []; // No full array for hardcoded defaults
  }
  try {
    const project = await POST('/api/projects', {
      name: captureState.name, type: captureState.type,
      pipeline: captureState.pipeline,
      phase: phase,
      phases: phases,
      next_action: captureState.next_action || 'Define scope and first step',
      deadline: captureState.deadline, priority: captureState.priority,
      money_attached:  captureState.money_attached,
      energy_zone:     captureState.energy_zone || 'flexible',
      mission_critical: captureState.mission_critical || false,
      notes: captureState.notes, source: captureState.source,
    });
    state.projects.push(project);
    state.projects.sort((a,b) => (a.priority||4) - (b.priority||4));
    const isCD = captureState.pipeline === 'creative_development';
    const isSF = captureState.pipeline === 'sales_funding';
    if (isCD || isSF) {
      document.getElementById('modal-content').innerHTML = `
        <div class="modal-title">"${esc(project.name)}" added</div>
        ${isCD ? `<div class="prompt-box" onclick="activateLivingWriterStub('${esc(project.id)}', '${esc(project.name)}')" style="cursor:pointer;"><div class="prompt-box-title">Start a LivingWriter record?</div>
          <div class="prompt-box-body">Open the Living Writer module and start tracking this story's development.</div></div>` : ''}
        ${isSF ? `<div class="prompt-box" onclick="activateCrmStub('${esc(project.id)}', '${esc(project.name)}')" style="cursor:pointer;margin-top:12px;"><div class="prompt-box-title">Add to the CRM?</div>
          <div class="prompt-box-body">Create a contact in the Promotion Machine for this project relationship.</div></div>` : ''}
        <div class="modal-actions"><button class="btn-primary" onclick="closeModal();renderAll();">Done</button></div>`;
    } else {
      closeModal(); renderAll();
      toast(`"${project.name}" added`, 'success');
    }
  } catch (e) { toast('Could not save project', 'error'); }
}

// ── Add Chapter Modal ─────────────────────────────────────────────────────────

function openAddChapterModal() {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Add Chapter</div>
    <div class="form-group"><label class="form-label">Label</label>
      <input class="form-input" id="ch-label" placeholder="e.g. Ch. 4"/></div>
    <div class="sidebar-title" style="margin:20px 0 12px;">Publication Status</div>
    <div class="form-group"><label class="form-label">VIP Group</label>
      <select class="form-select" id="ch-vip">
        <option value="not_started">Not started</option><option value="in_progress">In progress</option>
        <option value="pending">Pending</option><option value="live">Live</option>
      </select></div>
    <div class="form-group"><label class="form-label">Patreon</label>
      <select class="form-select" id="ch-patreon">
        <option value="not_started">Not started</option><option value="in_progress">In progress</option>
        <option value="pending">Pending</option><option value="live">Live</option>
      </select></div>
    <div class="form-group"><label class="form-label">Website</label>
      <select class="form-select" id="ch-website">
        <option value="not_started">Not started</option><option value="in_progress">In progress</option>
        <option value="pending">Pending</option><option value="live">Live</option>
      </select></div>
    <div class="form-group"><label class="form-label">WhatsApp Channel</label>
      <select class="form-select" id="ch-wa">
        <option value="not_started">Not started</option><option value="in_progress">In progress</option>
        <option value="pending">Pending</option><option value="live">Live</option>
      </select></div>
    <div class="sidebar-title" style="margin:20px 0 12px;">Assets (Optional)</div>
    <div class="form-group"><label class="form-label">Tagline</label>
      <input class="form-input" id="ch-tagline" placeholder="Short hook…"/></div>
    <div class="form-group"><label class="form-label">Blurb</label>
      <textarea class="form-textarea" id="ch-blurb" placeholder="Plot summary…" rows="2"></textarea></div>
    <div class="form-group"><label class="form-label">Excerpt</label>
      <textarea class="form-textarea" id="ch-excerpt" placeholder="Key passage…" rows="2"></textarea></div>
    <div class="form-group"><label class="form-label">Image Prompt</label>
      <input class="form-input" id="ch-image-prompt" placeholder="For AI generation or search…"/></div>
    <div class="form-group"><label class="form-label">Notes</label>
      <input class="form-input" id="ch-notes" placeholder="Optional…"/></div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary"   onclick="submitAddChapter()">Add</button>
    </div>`;
  showModal();
}

async function submitAddChapter() {
  const label = document.getElementById('ch-label').value.trim();
  if (!label) { toast('Label required', 'error'); return; }
  try {
    const entry = await POST('/api/content-pipeline', {
      chapter: label,
      vip_group_status: document.getElementById('ch-vip').value,
      patreon_status: document.getElementById('ch-patreon').value,
      website_status: document.getElementById('ch-website').value,
      wa_channel_status: document.getElementById('ch-wa').value,
      assets: {
        tagline: document.getElementById('ch-tagline').value.trim() || null,
        blurb: document.getElementById('ch-blurb').value.trim() || null,
        excerpt: document.getElementById('ch-excerpt').value.trim() || null,
        image_prompt: document.getElementById('ch-image-prompt').value.trim() || null,
      },
      notes: document.getElementById('ch-notes').value.trim(),
    });
    state.contentPipeline.push(entry);
    closeModal(); renderPipeline();
    toast(`${label} added`, 'success');
  } catch (e) { toast('Could not add chapter', 'error'); }
}

// ── Notes Modal ───────────────────────────────────────────────────────────────

async function openNotesModal() {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Concept Notes</div>
    <div class="modal-subtitle">~/Indaba/notes/ — plain markdown files</div>
    <div id="notes-list"><div style="color:var(--muted);">Loading…</div></div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Close</button>
      <button class="btn-primary"   onclick="openNewNoteForm()">+ New Note</button>
    </div>`;
  showModal();
  try {
    const notes = await GET('/api/notes');
    const el = document.getElementById('notes-list');
    el.innerHTML = notes.length
      ? notes.map(n => `<div class="note-row" onclick="openNoteView('${n.filename}')">
          <div class="note-title">${esc(n.title)}</div>
          <div class="note-meta">${formatDateShort(n.modified)}</div>
        </div>`).join('')
      : `<div style="color:var(--muted);font-size:13px;">No notes yet. Ideas, character concepts, themes — capture them here.</div>`;
  } catch (e) { toast('Could not load notes', 'error'); }
}

function openNewNoteForm() {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">New Concept Note</div>
    <div class="form-group"><label class="form-label">Title</label>
      <input class="form-input" id="note-title" placeholder="Story idea, character, theme…"/></div>
    <div class="form-group"><label class="form-label">Content</label>
      <textarea class="form-textarea" id="note-content" placeholder="Write freely…" rows="8"></textarea></div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="openNotesModal()">← Back</button>
      <button class="btn-primary"   onclick="submitNewNote()">Save</button>
    </div>`;
}

async function submitNewNote() {
  const title = document.getElementById('note-title').value.trim();
  if (!title) { toast('Title required', 'error'); return; }
  try {
    await POST('/api/notes', { title, content: document.getElementById('note-content').value.trim() });
    toast('Note saved', 'success'); openNotesModal();
  } catch (e) { toast('Could not save note', 'error'); }
}

async function openNoteView(filename) {
  document.getElementById('modal-content').innerHTML =
    `<div class="modal-title">Note</div><div style="color:var(--muted);">Loading…</div>`;
  try {
    const note = await GET(`/api/notes/${filename}`);
    document.getElementById('modal-content').innerHTML = `
      <div class="modal-title">Edit Note</div>
      <div class="form-group">
        <textarea class="form-textarea" id="note-edit-content" rows="14">${esc(note.content)}</textarea>
      </div>
      <div class="modal-actions">
        <button class="btn-danger"    onclick="deleteNote('${filename}')">Delete</button>
        <button class="btn-secondary" onclick="openNotesModal()">← Back</button>
        <button class="btn-primary"   onclick="saveNote('${filename}')">Save</button>
      </div>`;
  } catch (e) { toast('Could not load note', 'error'); }
}

async function saveNote(filename) {
  try {
    await PUT(`/api/notes/${filename}`, { content: document.getElementById('note-edit-content').value });
    toast('Saved', 'success'); openNotesModal();
  } catch (e) { toast('Could not save', 'error'); }
}

async function deleteNote(filename) {
  if (!confirm('Delete this note?')) return;
  try { await DEL(`/api/notes/${filename}`); toast('Deleted', 'success'); openNotesModal(); }
  catch (e) { toast('Could not delete', 'error'); }
}

// ── Settings View ────────────────────────────────────────────────────────────

function renderSettingsView() {
  const container = document.getElementById('settings-view-content');
  if (!container) return;
  
  const s = state.settings || {}, t = s.lead_measure_targets || {}, pe = s.plugins_enabled || {};
  const phaseTemplates = s.phase_templates || {};
  _wbsTemplates = JSON.parse(JSON.stringify(phaseTemplates));
  const prompts = s.asset_prompts || [];
  const promptSummaryList = prompts.length
    ? `<div class="prompt-summary-list">${prompts.map(p => `
        <div class="prompt-summary-row">
          <div class="prompt-summary-name">${esc(p.name)}</div>
          <div class="prompt-summary-desc">${esc(p.description.slice(0,90))}…</div>
        </div>`).join('')}</div>`
    : `<div style="font-size:13px;color:var(--muted);margin-bottom:10px;">No prompts saved yet.</div>`;
  const pluginToggles = state.plugins.map(p => `
    <label class="check-row" style="margin-bottom:8px;">
      <input type="checkbox" id="set-plugin-${p.name}" ${pe[p.name]!==false?'checked':''}/>
      ${esc(p.label)} — <span style="color:var(--muted);font-size:12px;">${esc(p.description)}</span>
    </label>`).join('') || '<div style="color:var(--muted);font-size:13px;">No plugins installed.</div>';

  container.innerHTML = `
    <div class="settings-view-panel" style="max-width:600px; margin:0 auto;">
      <div class="modal-title">Settings</div>
      <div class="form-group"><label class="form-label">Briefing Time</label>
        <input class="form-input" id="set-briefing" type="time" value="${s.briefing_time||'08:30'}"/></div>
      <div class="form-group"><label class="form-label">Productive Window Ends</label>
        <input class="form-input" id="set-wend" type="time" value="${s.window_end||'11:30'}"/></div>
      <div class="sidebar-title" style="margin:20px 0 14px;">Lead Measure Monthly Targets</div>
      ${[['pitches_sent','Pitches sent'],['pitch_meetings','Pitch meetings'],
         ['in_active_review','In active review'],['patreon_leads','Patreon leads'],
         ['follow_ups','Follow-ups done']].map(([k,label]) => `
        <div class="form-group"><label class="form-label">${label}</label>
          <input class="form-input" id="set-t-${k}" type="number" min="0"
            placeholder="Leave blank — no target" value="${t[k]!=null?t[k]:''}"/></div>`).join('')}
      <div class="sidebar-title" style="margin:20px 0 14px;">Default Project Phases</div>
      <div style="font-size:13px;color:var(--muted);margin-bottom:14px;">Manage named phase templates used in the project capture flow.</div>
      <div id="wbs-editor">${renderWbsEditor(_wbsTemplates)}</div>
      <button class="wbs-add-template-btn" onclick="addWbsTemplate()">＋ Add new template</button>
      <div class="sidebar-title" style="margin:20px 0 14px;">Asset Generation Prompts</div>
      <div style="font-size:13px;color:var(--muted);margin-bottom:14px;">Prompts used to generate chapter synopses, blurbs, taglines and image prompts. Edit or add new ones to evolve your workflow over time.</div>
      ${promptSummaryList}
      <button class="btn-secondary" style="margin-bottom:20px;width:100%;" onclick="openPromptsModal()">Manage Prompts →</button>
      <div class="sidebar-title" style="margin:20px 0 14px;">Plugins</div>
      ${pluginToggles}
      <div class="settings-actions" style="margin-top:24px; padding-top:20px; border-top:1px solid var(--border);">
        <button class="btn-primary" onclick="saveSettings()">Save Settings</button>
      </div>
    </div>`;
}

// ── Settings Modal ────────────────────────────────────────────────────────────

function openSettingsModal() {
  const s = state.settings, t = s.lead_measure_targets || {}, pe = s.plugins_enabled || {};
  const phaseTemplates = s.phase_templates || {};
  _wbsTemplates = JSON.parse(JSON.stringify(phaseTemplates));
  const prompts = s.asset_prompts || [];
  const promptSummaryList = prompts.length
    ? `<div class="prompt-summary-list">${prompts.map(p => `
        <div class="prompt-summary-row">
          <div class="prompt-summary-name">${esc(p.name)}</div>
          <div class="prompt-summary-desc">${esc(p.description.slice(0,90))}…</div>
        </div>`).join('')}</div>`
    : `<div style="font-size:13px;color:var(--muted);margin-bottom:10px;">No prompts saved yet.</div>`;
  const pluginToggles = state.plugins.map(p => `
    <label class="check-row" style="margin-bottom:8px;">
      <input type="checkbox" id="set-plugin-${p.name}" ${pe[p.name]!==false?'checked':''}/>
      ${esc(p.label)} — <span style="color:var(--muted);font-size:12px;">${esc(p.description)}</span>
    </label>`).join('') || '<div style="color:var(--muted);font-size:13px;">No plugins installed.</div>';

  // WBS editor is rendered separately
  const phaseTemplateInputs = '';

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Settings</div>
    <div class="form-group"><label class="form-label">Briefing Time</label>
      <input class="form-input" id="set-briefing" type="time" value="${s.briefing_time||'08:30'}"/></div>
    <div class="form-group"><label class="form-label">Productive Window Ends</label>
      <input class="form-input" id="set-wend" type="time" value="${s.window_end||'11:30'}"/></div>
    <div class="sidebar-title" style="margin:20px 0 14px;">Lead Measure Monthly Targets</div>
    ${[['pitches_sent','Pitches sent'],['pitch_meetings','Pitch meetings'],
       ['in_active_review','In active review'],['patreon_leads','Patreon leads'],
       ['follow_ups','Follow-ups done']].map(([k,label]) => `
      <div class="form-group"><label class="form-label">${label}</label>
        <input class="form-input" id="set-t-${k}" type="number" min="0"
          placeholder="Leave blank — no target" value="${t[k]!=null?t[k]:''}"/></div>`).join('')}
    <div class="sidebar-title" style="margin:20px 0 14px;">Default Project Phases</div>
    <div style="font-size:13px;color:var(--muted);margin-bottom:14px;">Manage named phase templates used in the project capture flow.</div>
    <div id="wbs-editor">${renderWbsEditor(_wbsTemplates)}</div>
    <button class="wbs-add-template-btn" onclick="addWbsTemplate()">＋ Add new template</button>
    <div class="sidebar-title" style="margin:20px 0 14px;">Asset Generation Prompts</div>
    <div style="font-size:13px;color:var(--muted);margin-bottom:14px;">Prompts used to generate chapter synopses, blurbs, taglines and image prompts. Edit or add new ones to evolve your workflow over time.</div>
    ${promptSummaryList}
    <button class="btn-secondary" style="margin-bottom:20px;width:100%;" onclick="openPromptsModal()">Manage Prompts →</button>
    <div class="sidebar-title" style="margin:20px 0 14px;">Plugins</div>
    ${pluginToggles}
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary"   onclick="saveSettings()">Save</button>
    </div>`;
  showModal();
}

// ── WBS Phase Template Editor ──────────────────────────────────────────────
let _wbsTemplates = {};
let _wbsExpanded  = {}; // Track which templates are expanded

function renderWbsEditor(templates) {
  const entries = Object.entries(templates);
  if (entries.length === 0) {
    return '<div style="color:var(--muted);font-size:13px;margin-bottom:14px;">No phase templates defined. Add one below.</div>';
  }
  return entries.map(([key, phases]) => {
    const isExpanded = _wbsExpanded[key] !== false; // Default to true if not set
    return `
      <div class="wbs-template-section" data-template="${esc(key)}">
        <div class="wbs-template-header" onclick="toggleWbsTemplate('${esc(key)}')">
          <div style="display:flex;align-items:center;gap:8px;">
            <span class="wbs-chevron">${isExpanded ? '▾' : '▸'}</span>
            <span>${esc(key)}</span>
          </div>
          <button class="wbs-btn" onclick="event.stopPropagation(); deleteWbsTemplate('${esc(key)}')" title="Remove template">✕</button>
        </div>
        <div class="wbs-template-body" style="display: ${isExpanded ? 'block' : 'none'}">
          <div class="wbs-phase-list">
            ${phases.map((phase, idx) => `
              <div class="wbs-phase-row">
                <input class="wbs-phase-input" type="text" value="${esc(phase)}" placeholder="Phase name"
                       onchange="updateWbsPhase('${esc(key)}', ${idx}, this.value)" />
                <button class="wbs-btn" onclick="moveWbsPhase('${esc(key)}', ${idx}, -1)" ${idx === 0 ? 'disabled' : ''} title="Move up">↑</button>
                <button class="wbs-btn" onclick="moveWbsPhase('${esc(key)}', ${idx}, 1)" ${idx === phases.length - 1 ? 'disabled' : ''} title="Move down">↓</button>
                <button class="wbs-btn" onclick="deleteWbsPhase('${esc(key)}', ${idx})" title="Delete phase">×</button>
              </div>
            `).join('')}
          </div>
          <button class="wbs-add-phase-btn" onclick="addWbsPhase('${esc(key)}')">＋ Add phase</button>
        </div>
      </div>
    `;
  }).join('');
}

function toggleWbsTemplate(key) {
  _wbsExpanded[key] = _wbsExpanded[key] === false;
  refreshWbsEditor();
}

function updateWbsPhase(templateKey, index, newValue) {
  if (!_wbsTemplates[templateKey]) return;
  _wbsTemplates[templateKey][index] = newValue.trim();
  // No need to re-render, just update the internal state
}

function addWbsPhase(templateKey) {
  if (!_wbsTemplates[templateKey]) _wbsTemplates[templateKey] = [];
  _wbsTemplates[templateKey].push('');
  refreshWbsEditor();
}

function deleteWbsPhase(templateKey, index) {
  if (!_wbsTemplates[templateKey]) return;
  _wbsTemplates[templateKey].splice(index, 1);
  refreshWbsEditor();
}

function moveWbsPhase(templateKey, index, direction) {
  if (!_wbsTemplates[templateKey]) return;
  const newIndex = index + direction;
  if (newIndex < 0 || newIndex >= _wbsTemplates[templateKey].length) return;
  const arr = _wbsTemplates[templateKey];
  [arr[index], arr[newIndex]] = [arr[newIndex], arr[index]];
  refreshWbsEditor();
}

function addWbsTemplate() {
  const name = prompt('Enter a name for the new template:', '');
  if (!name || name.trim() === '') return;
  const key = name.trim();
  if (_wbsTemplates[key]) {
    alert('A template with that name already exists.');
    return;
  }
  _wbsTemplates[key] = [];
  refreshWbsEditor();
}

function deleteWbsTemplate(templateKey) {
  if (!confirm(`Delete the template "${templateKey}" and all its phases?`)) return;
  delete _wbsTemplates[templateKey];
  refreshWbsEditor();
}

function refreshWbsEditor() {
  const container = document.getElementById('wbs-editor');
  if (!container) return;
  container.innerHTML = renderWbsEditor(_wbsTemplates);
}

async function saveSettings() {
  const pe = {};
  state.plugins.forEach(p => { pe[p.name] = document.getElementById(`set-plugin-${p.name}`)?.checked !== false; });
  const targets = {};
  ['pitches_sent','pitch_meetings','in_active_review','patreon_leads','follow_ups'].forEach(k => {
    const v = document.getElementById(`set-t-${k}`)?.value;
    targets[k] = (v !== '' && v != null) ? parseInt(v) : null;
  });
  const phaseTemplates = {};
  for (const [key, phases] of Object.entries(_wbsTemplates)) {
    const filtered = phases.filter(p => p.trim() !== '');
    if (filtered.length > 0) phaseTemplates[key] = filtered;
  }
  try {
    state.settings = await PUT('/api/settings', {
      briefing_time: document.getElementById('set-briefing').value,
      window_end:    document.getElementById('set-wend').value,
      lead_measure_targets: targets, plugins_enabled: pe,
      phase_templates: phaseTemplates,
      asset_prompts: state.settings.asset_prompts || [],
    });
    closeModal(); renderAll(); toast('Settings saved', 'success');
  } catch (e) { toast('Could not save settings', 'error'); }
}

// ── Prompt Templates Manager ──────────────────────────────────────────────────

function openPromptsModal() {
  const prompts = state.settings.asset_prompts || [];
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Prompt Templates</div>
    <div style="font-size:13px;color:var(--muted);margin-bottom:18px;">
      Your library of AI generation prompts. Each prompt records what it does, what it needs, and what it produces — so the intent is never lost over time.
    </div>
    <div id="prompt-list">
      ${prompts.length ? prompts.map((p, i) => renderPromptCard(p, i)).join('') : '<div style="color:var(--muted);font-size:13px;">No prompts yet.</div>'}
    </div>
    <button class="btn-secondary" style="width:100%;margin-top:16px;" onclick="openEditPromptModal(null)">+ Add New Prompt</button>
    <div class="modal-actions" style="margin-top:8px;">
      <button class="btn-secondary" onclick="openSettingsModal()">← Back to Settings</button>
      <button class="btn-secondary" onclick="closeModal()">Close</button>
    </div>`;
  showModal();
}

function renderPromptCard(p, i) {
  return `
    <div class="prompt-card" id="prompt-card-${esc(p.id)}">
      <div class="prompt-card-header" onclick="togglePromptCard('${esc(p.id)}')">
        <div>
          <div class="prompt-card-name">${esc(p.name)}</div>
          <div class="prompt-card-desc-short">${esc(p.description.slice(0,100))}${p.description.length > 100 ? '…' : ''}</div>
        </div>
        <div class="prompt-card-actions">
          <button class="btn-icon" title="Edit" onclick="event.stopPropagation();openEditPromptModal('${esc(p.id)}')">✎</button>
          <button class="btn-icon btn-icon-danger" title="Delete" onclick="event.stopPropagation();deletePrompt('${esc(p.id)}')">✕</button>
          <span class="prompt-chevron" id="chevron-${esc(p.id)}">▾</span>
        </div>
      </div>
      <div class="prompt-card-body" id="prompt-body-${esc(p.id)}" style="display:none;">
        <div class="prompt-meta-row"><span class="prompt-meta-label">What it does</span><span>${esc(p.description)}</span></div>
        <div class="prompt-meta-row"><span class="prompt-meta-label">Inputs</span><span>${esc(p.inputs)}</span></div>
        <div class="prompt-meta-row"><span class="prompt-meta-label">Outputs</span><span>${esc(p.outputs)}</span></div>
        <div class="prompt-meta-label" style="margin-top:12px;margin-bottom:6px;">Prompt text</div>
        <pre class="prompt-text-preview">${esc(p.prompt)}</pre>
      </div>
    </div>`;
}

function togglePromptCard(id) {
  const body = document.getElementById(`prompt-body-${id}`);
  const chev = document.getElementById(`chevron-${id}`);
  if (!body) return;
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : 'block';
  if (chev) chev.textContent = open ? '▾' : '▴';
}

function openEditPromptModal(id) {
  const prompts = state.settings.asset_prompts || [];
  const p = id ? prompts.find(x => x.id === id) : null;
  const isNew = !p;
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">${isNew ? 'New Prompt' : 'Edit Prompt'}</div>
    <div class="form-group">
      <label class="form-label">ID <span style="color:var(--muted);font-size:11px;">(unique key, no spaces — e.g. synopsis, blurb, my_custom_prompt)</span></label>
      <input class="form-input" id="ep-id" placeholder="e.g. synopsis" value="${esc(p?.id||'')}" ${isNew?'':'readonly style="opacity:0.6;"'}/>
    </div>
    <div class="form-group">
      <label class="form-label">Name <span style="color:var(--muted);font-size:11px;">(displayed in the UI)</span></label>
      <input class="form-input" id="ep-name" placeholder="e.g. Chapter Synopsis" value="${esc(p?.name||'')}"/>
    </div>
    <div class="form-group">
      <label class="form-label">What it does</label>
      <textarea class="form-input" id="ep-description" rows="3" placeholder="Describe the purpose of this prompt in plain English…">${esc(p?.description||'')}</textarea>
    </div>
    <div class="form-group">
      <label class="form-label">Inputs <span style="color:var(--muted);font-size:11px;">(what does this prompt need fed into it?)</span></label>
      <input class="form-input" id="ep-inputs" placeholder="e.g. Full raw text of a single chapter" value="${esc(p?.inputs||'')}"/>
    </div>
    <div class="form-group">
      <label class="form-label">Outputs <span style="color:var(--muted);font-size:11px;">(what does it produce?)</span></label>
      <textarea class="form-input" id="ep-outputs" rows="2" placeholder="e.g. 500–600 word present-tense synopsis…">${esc(p?.outputs||'')}</textarea>
    </div>
    <div class="form-group">
      <label class="form-label">Prompt text <span style="color:var(--muted);font-size:11px;">(use [CHAPTER TEXT] as placeholder for the content to be processed)</span></label>
      <textarea class="form-input prompt-edit-textarea" id="ep-prompt" rows="12" placeholder="Enter your full prompt here…">${esc(p?.prompt||'')}</textarea>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="openPromptsModal()">← Cancel</button>
      <button class="btn-primary"   onclick="savePrompt('${esc(id||'')}')">Save Prompt</button>
    </div>`;
  showModal();
}

async function savePrompt(existingId) {
  const id          = document.getElementById('ep-id').value.trim().replace(/\s+/g,'_');
  const name        = document.getElementById('ep-name').value.trim();
  const description = document.getElementById('ep-description').value.trim();
  const inputs      = document.getElementById('ep-inputs').value.trim();
  const outputs     = document.getElementById('ep-outputs').value.trim();
  const prompt      = document.getElementById('ep-prompt').value.trim();
  if (!id || !name || !prompt) { toast('ID, Name and Prompt text are required', 'error'); return; }
  const prompts = [...(state.settings.asset_prompts || [])];
  const idx = existingId ? prompts.findIndex(p => p.id === existingId) : -1;
  const entry = { id, name, description, inputs, outputs, prompt };
  if (idx >= 0) prompts[idx] = entry;
  else {
    if (prompts.find(p => p.id === id)) { toast(`A prompt with ID "${id}" already exists`, 'error'); return; }
    prompts.push(entry);
  }
  try {
    state.settings = await PUT('/api/settings', { ...state.settings, asset_prompts: prompts });
    toast('Prompt saved', 'success');
    openPromptsModal();
  } catch (e) { toast('Could not save prompt', 'error'); }
}

async function deletePrompt(id) {
  if (!confirm('Delete this prompt? This cannot be undone.')) return;
  const prompts = (state.settings.asset_prompts || []).filter(p => p.id !== id);
  try {
    state.settings = await PUT('/api/settings', { ...state.settings, asset_prompts: prompts });
    toast('Prompt deleted', 'success');
    openPromptsModal();
  } catch (e) { toast('Could not delete prompt', 'error'); }
}

// ── Plugins Modal ─────────────────────────────────────────────────────────────

function openPluginsModal() {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Plugins ⬡</div>
    <div class="modal-subtitle">Modular add-ons. Enable/disable in Settings.</div>
    ${!state.plugins.length
      ? '<div style="color:var(--muted);font-size:14px;margin-top:12px;">No plugins installed.</div>'
      : state.plugins.map(p => `
          <div class="plugin-item">
            <div class="plugin-label">${esc(p.label)}</div>
            <div class="plugin-desc">${esc(p.description)}</div>
            <div class="plugin-actions">
              ${(p.actions||[]).map(a => `
                <button class="btn-plugin" onclick="runPlugin('${p.name}','${a.id}')">${esc(a.label)}</button>`
              ).join('')}
            </div>
          </div>`).join('')}
    <div class="modal-actions"><button class="btn-secondary" onclick="closeModal()">Close</button></div>`;
  showModal();
}

async function runPlugin(name, action) {
  toast('Running…');
  try {
    const res = await POST(`/api/plugins/${name}/execute`, { action });
    if (res.ok && res.result) {
      downloadJSON(res.result, `indaba-${name}-${action}-${state.today}.json`);
      toast('Export ready — file downloaded', 'success'); closeModal();
    }
  } catch (e) { toast('Plugin error: ' + e.message, 'error'); }
}

function downloadJSON(data, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
  Object.assign(document.createElement('a'), { href: url, download: filename }).click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

// ── Help / Reference Modal ─────────────────────────────────────────────────────

function openHelpModal() {
  const c = state.caps;
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Indaba — Field Manual</div>
    <div class="help-section">
      <div class="help-heading">Energy Zones</div>
      <p>Every project lives in one of three zones matching your energy pattern through the day.</p>
      <ul class="help-list">
        <li><strong>☀ Morning Block (08:30–10:30)</strong> — Peak intellect and willpower. For creative writing, deep thinking, complex problem-solving. Hard cap: ${c.zone_caps?.morning || 3} projects.</li>
        <li><strong>◈ Paid Work (11:00–13:00)</strong> — Client and commissioned work. Ghost-writing, TV scripts, revenue-generating tasks. Hard cap: ${c.zone_caps?.paid_work || 3} projects.</li>
        <li><strong>◑ Evening Block (End of day)</strong> — Outreach, sales, admin, publishing. Lower cognitive demand. Hard cap: ${c.zone_caps?.evening || 2} projects.</li>
      </ul>
    </div>
    <div class="help-section">
      <div class="help-heading">Zone Focus (⊙)</div>
      <p>Each zone can have exactly <strong>one</strong> focus project — the thing you work on first, no debate. Click ⊙ on any project card to claim the focus slot. Click "⊙ Release" to step away consciously. No other project can hold focus in that zone until you release it.</p>
    </div>
    <div class="help-section">
      <div class="help-heading">Project Caps</div>
      <ul class="help-list">
        <li><strong>Total active projects:</strong> max ${c.total_cap || 8}. Finish or remove one before adding more.</li>
        <li><strong>Zone caps:</strong> Morning ${c.zone_caps?.morning || 3}, Paid Work ${c.zone_caps?.paid_work || 3}, Evening ${c.zone_caps?.evening || 2}.</li>
        <li>Change these under <em>Settings → Constants</em>.</li>
      </ul>
    </div>
    <div class="help-section">
      <div class="help-heading">Inbox</div>
      <ul class="help-list">
        <li>Capture raw ideas without friction. Max ${c.inbox_max || 15} items.</li>
        <li><strong>7-day expiry:</strong> items that are not triaged disappear permanently — no recovery, no archive. This is intentional. It keeps the inbox honest.</li>
        <li>Triage options: Promote to a project, archive to Dormant, or delete forever.</li>
      </ul>
    </div>
    <div class="help-section">
      <div class="help-heading">Dormant Archive</div>
      <p>Good ideas that aren't ready yet. Max ${c.dormant_max || 25} slots. Revive any dormant item back to the inbox (7-day clock restarts). Not a graveyard — a holding pen.</p>
    </div>
    <div class="help-section">
      <div class="help-heading">Today's Posts</div>
      <p>Daily accountability checklist for your four publishing platforms, in priority order: Patreon → Website → VIP Group → WA Channel. Resets at midnight. Each platform tracks a consecutive-day streak.</p>
    </div>
    <div class="help-section">
      <div class="help-heading">Phase Templates</div>
      <p>Named sequences of project phases (e.g. "World & Bible → First Draft → Edit → Publish"). Apply to a new project during capture, or to an existing project via Edit → Apply Phase Template. Replacing phases always shows a scratch-pad confirmation first.</p>
    </div>
    <div class="help-section">
      <div class="help-heading">Sequence (P1–P4)</div>
      <p>Within a zone, P1–P4 sets the order projects appear (P1 first). This is a <em>sequence</em> signal, not an absolute priority — that role belongs to the ⊙ Focus slot.</p>
    </div>
    <div class="help-section">
      <div class="help-heading">Promotion Machine: Cowork Handoff</div>
      <p>Indaba uses a file-based handoff for sending WhatsApp messages via Cowork:</p>
      <ul class="help-list">
        <li><strong>Dispatch:</strong> Click "Dispatch to Cowork" to write job files to the data folder.</li>
        <li><strong>Trigger Cowork:</strong> Open Cowork and run the command: <code>Send WhatsApps from Indaba</code>.</li>
        <li><strong>Reconcile:</strong> Once Cowork is done, click "Reconcile Results" in Indaba to update message statuses and lead communication logs.</li>
      </ul>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="openConstantsModal()">Edit Constants →</button>
      <button class="btn-primary"   onclick="closeModal()">Got it</button>
    </div>`;
  showModal();
}

// ── Constants Settings Modal ───────────────────────────────────────────────────

async function openConstantsModal() {
  let consts = {};
  try { consts = await GET('/api/settings/constants'); }
  catch (e) { toast('Could not load constants', 'error'); return; }
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">System Constants</div>
    <div style="font-size:13px;color:var(--muted);margin-bottom:18px;">
      These are the hard limits that govern how Indaba works. Change them carefully — they affect every cap and expiry check.
    </div>
    ${[
      ['inbox_max',          'Inbox max items',             consts.inbox_max],
      ['dormant_max',        'Dormant max items',           consts.dormant_max],
      ['inbox_expiry_days',  'Inbox expiry (days)',         consts.inbox_expiry_days],
      ['total_project_cap',  'Total active project cap',    consts.total_project_cap],
      ['zone_cap_morning',   'Zone cap — Morning',          consts.zone_cap_morning],
      ['zone_cap_paid_work', 'Zone cap — Paid Work',        consts.zone_cap_paid_work],
      ['zone_cap_evening',   'Zone cap — Evening',          consts.zone_cap_evening],
    ].map(([k, label, val]) => `
      <div class="form-group">
        <label class="form-label">${label}</label>
        <input class="form-input" id="const-${k}" type="number" min="1" value="${val}"/>
      </div>`).join('')}
    <div class="modal-actions">
      <button class="btn-secondary" onclick="openHelpModal()">← Back</button>
      <button class="btn-primary"   onclick="saveConstants()">Save Constants</button>
    </div>`;
  showModal();
}

async function saveConstants() {
  const keys = ['inbox_max','dormant_max','inbox_expiry_days','total_project_cap',
                 'zone_cap_morning','zone_cap_paid_work','zone_cap_evening'];
  const payload = {};
  for (const k of keys) {
    const v = document.getElementById(`const-${k}`)?.value;
    if (v === '' || v == null) { toast(`${k} cannot be empty`, 'error'); return; }
    payload[k] = parseInt(v);
    if (isNaN(payload[k]) || payload[k] < 1) { toast(`${k} must be a positive integer`, 'error'); return; }
  }
  try {
    await PUT('/api/settings/constants', payload);
    await loadDashboard();
    toast('Constants saved', 'success');
    closeModal();
  } catch (e) { toast('Could not save constants', 'error'); }
}

// ── Modal helpers ─────────────────────────────────────────────────────────────

function showModal()  { document.getElementById('modal-overlay').classList.remove('hidden'); }
function closeModal() { document.getElementById('modal-overlay').classList.add('hidden'); }

// ── Theme ─────────────────────────────────────────────────────────────────────

function applyStoredTheme() {
  if (localStorage.getItem('indaba-theme') === 'light') document.body.classList.add('light-mode');
  updateThemeBtn();
}
function toggleTheme() {
  const isLight = document.body.classList.toggle('light-mode');
  localStorage.setItem('indaba-theme', isLight ? 'light' : 'dark');
  updateThemeBtn();
}
function updateThemeBtn() {
  const btn = document.getElementById('btn-theme');
  if (!btn) return;
  const isLight = document.body.classList.contains('light-mode');
  btn.textContent = isLight ? 'Dark'  : 'Light';
  btn.title       = isLight ? 'Switch to dark mode' : 'Switch to light mode';
  btn.classList.toggle('active', false); // never sticky-highlight the theme btn
}

// ── Toast ─────────────────────────────────────────────────────────────────────

let _tc = null;
function toast(msg, type = '') {
  if (!_tc) { _tc = document.createElement('div'); _tc.id = 'toast-container'; document.body.appendChild(_tc); }
  const el = Object.assign(document.createElement('div'), { className: `toast ${type}`, textContent: msg });
  _tc.appendChild(el);
  setTimeout(() => el.classList.add('fade'), 2200);
  setTimeout(() => el.remove(), 2700);
}

// ── Constants ─────────────────────────────────────────────────────────────────

const TYPE_LABELS = {
  tv_script:'TV Script', ghostwriting:'Ghostwriting', original_fiction:'Original Fiction',
  original_screenplay:'Original Screenplay', tv_series:'TV Series',
  podcast:'Podcast', other:'Other',
};
const PIPELINE_LABELS = {
  creative_development:'Creative Dev', sales_funding:'Sales & Funding', publishing_engine:'Publishing',
};

// ── Utility ───────────────────────────────────────────────────────────────────

function esc(s) {
  if (s==null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
// Parse ISO datetime strings from Python as LOCAL time.
// Python datetime.now().isoformat() has no 'Z' suffix, but browsers
// treat those strings as UTC — appending a space forces local parse.
function parseLocalISO(iso) {
  if (!iso) return null;
  // If already has timezone offset (+HH:MM or Z) — parse as-is
  if (/[Z+]/.test(iso.slice(10))) return new Date(iso);
  // No timezone: force local interpretation by replacing 'T' with ' '
  return new Date(iso.replace('T', ' '));
}
function formatDateShort(iso) {
  if (!iso) return '';
  try {
    const d = parseLocalISO(iso);
    return d.toLocaleDateString('en-ZA',{day:'numeric',month:'short'}) + ' ' +
           d.toLocaleTimeString('en-ZA',{hour:'2-digit',minute:'2-digit'});
  } catch { return ''; }
}
function formatTimeShort(iso) {
  if (!iso) return '';
  try { return parseLocalISO(iso).toLocaleTimeString('en-ZA',{hour:'2-digit',minute:'2-digit'}); }
  catch { return ''; }
}

// ── PROMOTION MACHINE: Loaders ────────────────────────────────────────────────

async function loadPromoContacts() {
  try {
    const data = await GET('/api/promo/contacts');
    state.promoContacts = data.contacts || [];
    renderPromoContacts();
  } catch (e) { toast("Could not load contacts", "error"); }
}

async function loadPromoLeads() {
  try {
    const data = await GET('/api/promo/leads');
    state.promoLeads = data.leads || [];
    renderPromoLeads();
  } catch (e) { toast("Could not load leads", "error"); }
}

async function loadPromoMessages() {
  try {
    const data = await GET('/api/promo/messages');
    state.promoMessages = data.messages || [];
    state.promoOverdueCount = state.promoMessages.filter(m => m.status === 'overdue').length;
    state.promoDispatchedCount = state.promoMessages.filter(m => m.status === 'dispatched').length;
    renderPromoSender();
  } catch (e) { toast("Could not load messages", "error"); }
}

async function loadPromoProverbs() {
  try {
    const data = await GET('/api/promo/proverbs');
    state.promoProverbs = data.proverbs || [];
    renderPromoWaPostMaker();
  } catch (e) { toast("Could not load proverbs", "error"); }
}

async function loadPromoBooks() {
  try {
    const data = await GET('/api/promo/books');
    state.promoBooks = data.books || [];
    renderPromoBookSerializer();
  } catch (e) { toast("Could not load books", "error"); }
}

async function loadPromoSettings() {
  try {
    const data = await GET('/api/promo/settings');
    state.promoSettings = data || {};
    renderPromoSettings();
  } catch (e) { toast("Could not load settings", "error"); }
}

// ── PROMOTION MACHINE: Contacts Sub-tab ───────────────────────────────────────

function renderPromoContacts() {
  const container = document.getElementById('promo-view-contacts');
  if (!container) return;

  const rows = state.promoContacts.length === 0
    ? `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:40px;">No contacts yet. Add your first contact to get started.</td></tr>`
    : state.promoContacts.map(c => {
        const openLeadsCount = state.promoLeads.filter(l => l.contact_id === c.id && !['won', 'lost'].includes(l.stage)).length;
        return `
          <tr>
            <td><strong>${esc(c.name)}</strong></td>
            <td><code>${esc(c.phone)}</code></td>
            <td>${(c.tags || []).map(t => `<span class="badge" style="background:var(--surface2);border:1px solid var(--border2);margin-right:4px;">${esc(t)}</span>`).join('')}</td>
            <td>${openLeadsCount}</td>
            <td>
              <button class="btn-secondary" style="padding:4px 8px;font-size:11px;" onclick="openContactDetail('${c.id}')">View</button>
              <button class="btn-secondary" style="padding:4px 8px;font-size:11px;color:var(--p1);" onclick="confirmDeleteContact('${c.id}')">Delete</button>
            </td>
          </tr>`;
      }).join('');

  container.innerHTML = `
    <div class="promo-action-bar">
      <button class="btn-primary" onclick="addContactModal()">+ Add Contact</button>
      <button class="btn-secondary" onclick="document.getElementById('csv-import-input').click()">Import CSV</button>
      <input type="file" id="csv-import-input" accept=".csv" style="display:none;" onchange="importContactsCSV(this)">
    </div>
    <table class="promo-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Phone</th>
          <th>Tags</th>
          <th>Open Leads</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

async function importContactsCSV(input) {
  if (!input.files || !input.files[0]) return;
  const formData = new FormData();
  formData.append('file', input.files[0]);

  try {
    const res = await fetch('/api/promo/contacts/import_csv', { method: 'POST', body: formData });
    const data = await res.json();
    if (res.ok) {
      toast(`Imported ${data.imported} contacts. Skipped ${data.skipped_invalid} invalid, ${data.skipped_duplicate} duplicate.`, 'success');
      loadPromoContacts();
    } else {
      toast(data.error || 'Import failed', 'error');
    }
  } catch (e) { toast('Import failed', 'error'); }
  input.value = '';
}

function addContactModal() {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Add New Contact</div>
    <div class="form-group">
      <label class="form-label">Name *</label>
      <input class="form-input" id="con-name" type="text" placeholder="Full Name"/>
      <div id="con-err-name" class="inline-error" style="color:var(--p1);font-size:11px;display:none;">Name is required</div>
    </div>
    <div class="form-group">
      <label class="form-label">Phone *</label>
      <input class="form-input" id="con-phone" type="text" placeholder="+27821112222"/>
      <div id="con-err-phone" class="inline-error" style="color:var(--p1);font-size:11px;display:none;">Valid phone is required</div>
    </div>
    <div class="form-group">
      <label class="form-label">Email</label>
      <input class="form-input" id="con-email" type="email" placeholder="email@example.com"/>
    </div>
    <div class="form-group">
      <label class="form-label">Tags (comma separated)</label>
      <input class="form-input" id="con-tags" type="text" placeholder="tag1, tag2"/>
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <textarea class="form-textarea" id="con-notes" placeholder="Any additional context..."></textarea>
    </div>
    <div id="con-err-api" class="inline-error" style="color:var(--p1);font-size:11px;margin-bottom:10px;display:none;"></div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="saveNewContact()">Save Contact</button>
    </div>`;
  showModal();
}

async function saveNewContact() {
  const name  = document.getElementById('con-name').value.trim();
  const phone = document.getElementById('con-phone').value.trim();
  const email = document.getElementById('con-email').value.trim();
  const tagsText = document.getElementById('con-tags').value.trim();
  const notes = document.getElementById('con-notes').value.trim();

  let valid = true;
  document.getElementById('con-err-name').style.display = 'none';
  document.getElementById('con-err-phone').style.display = 'none';
  document.getElementById('con-err-api').style.display = 'none';

  if (!name) { document.getElementById('con-err-name').style.display = 'block'; valid = false; }
  if (!phone) { document.getElementById('con-err-phone').style.display = 'block'; valid = false; }

  if (!valid) return;

  const tags = tagsText ? tagsText.split(',').map(t => t.trim()).filter(t => t) : [];

  try {
    const res = await fetch('/api/promo/contacts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, phone, email, tags, notes })
    });
    const data = await res.json();
    if (res.status === 201) {
      toast('Contact added', 'success');
      closeModal();
      loadPromoContacts();
    } else if (res.status === 409) {
      document.getElementById('con-err-api').textContent = 'This phone number already exists';
      document.getElementById('con-err-api').style.display = 'block';
    } else {
      document.getElementById('con-err-api').textContent = data.error || 'Save failed';
      document.getElementById('con-err-api').style.display = 'block';
    }
  } catch (e) { toast('Save failed', 'error'); }
}

async function openContactDetail(contactId) {
  try {
    const contact = await GET(`/api/promo/contacts/${contactId}`);
    renderContactDetailModal(contact);
  } catch (e) { toast('Could not load contact details', 'error'); }
}

function renderContactDetailModal(data) {
  const contact = data.contact || {};
  const leads = data.leads || [];
  const allComms = [];
  leads.forEach(l => {
    (l.communication_log || []).forEach(entry => {
      allComms.push({ ...entry, product: l.product });
    });
  });
  allComms.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Contact Detail</div>
    
    <div class="promo-settings-section">
      <h3>Contact Info</h3>
      <div id="contact-info-display">
        <p><strong>Name:</strong> ${esc(contact.name)}</p>
        <p><strong>Phone:</strong> ${esc(contact.phone)}</p>
        <p><strong>Email:</strong> ${esc(contact.email || '—')}</p>
        <p><strong>Notes:</strong> ${esc(contact.notes || '—')}</p>
        <button class="btn-secondary" style="margin-top:10px;" onclick="editContactInfo('${contact.id}')">Edit Info</button>
      </div>
      <div id="contact-info-edit" style="display:none;">
        <div class="form-group"><input class="form-input" id="edit-con-name" value="${esc(contact.name)}"/></div>
        <div class="form-group"><input class="form-input" id="edit-con-phone" value="${esc(contact.phone)}"/></div>
        <div class="form-group"><input class="form-input" id="edit-con-email" value="${esc(contact.email)}"/></div>
        <div class="form-group"><textarea class="form-textarea" id="edit-con-notes">${esc(contact.notes)}</textarea></div>
        <button class="btn-primary" onclick="saveContactInfo('${contact.id}')">Save</button>
        <button class="btn-secondary" onclick="toggleContactEdit(false)">Cancel</button>
      </div>
    </div>

    <div class="promo-settings-section">
      <h3>Tags</h3>
      <div id="tag-chips" style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px;">
        ${(contact.tags || []).map(t => `
          <span class="badge" style="background:var(--surface2);border:1px solid var(--border2);display:flex;align-items:center;gap:6px;">
            ${esc(t)} <span style="cursor:pointer;opacity:0.5;" onclick="removeContactTag('${contact.id}', '${esc(t)}')">×</span>
          </span>
        `).join('')}
      </div>
      <div style="display:flex;gap:8px;">
        <input class="form-input" id="new-tag-input" placeholder="Add tag..."/>
        <button class="btn-secondary" onclick="addContactTag('${contact.id}')">Add</button>
      </div>
    </div>

    <div class="promo-settings-section">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
        <h3 style="margin-bottom:0;">All Leads</h3>
        <button class="btn-secondary" style="font-size:11px;" onclick="openNewLeadModal('${contact.id}')">+ New Lead</button>
      </div>
      ${leads.length === 0 ? '<p style="color:var(--muted);font-size:13px;">No leads for this contact.</p>' : `
        <table class="promo-table">
          <thead><tr><th>Product</th><th>Stage</th><th>Last Comm</th></tr></thead>
          <tbody>
            ${leads.map(l => `
              <tr style="cursor:pointer;" onclick="closeModal(); openLeadDetail('${l.id}')">
                <td>${esc(l.product)} <span class="promo-badge promo-badge-${l.product_type || 'other'}">${esc(l.product_type)}</span></td>
                <td><span class="promo-stage-badge promo-stage-${l.stage}">${esc(l.stage)}</span></td>
                <td><span style="font-size:11px;">${l.communication_log?.length ? formatDateShort(l.communication_log[l.communication_log.length-1].timestamp) : 'Never'}</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `}
    </div>

    <div class="promo-settings-section" style="border-bottom:none;">
      <h3>Communication History</h3>
      ${allComms.length === 0 ? '<p style="color:var(--muted);font-size:13px;">No history recorded.</p>' : `
        <div style="max-height:300px;overflow-y:auto;">
          ${allComms.map(e => `
            <div class="promo-comm-log-entry">
              <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-bottom:4px;">
                <span>${esc(e.product)}</span>
                <span>${formatDateShort(e.timestamp)}</span>
              </div>
              <div class="promo-comm-direction promo-comm-direction-${e.direction === 'inbound' ? 'in' : 'out'}">
                ${e.direction === 'inbound' ? '← Received' : '→ Sent'}
              </div>
              <div style="font-size:13px;">${esc(e.message)}</div>
            </div>
          `).join('')}
        </div>
      `}
    </div>

    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Close</button>
    </div>`;
  showModal();
}

function toggleContactEdit(editing) {
  document.getElementById('contact-info-display').style.display = editing ? 'none' : 'block';
  document.getElementById('contact-info-edit').style.display = editing ? 'block' : 'none';
}

function editContactInfo() { toggleContactEdit(true); }

async function saveContactInfo(contactId) {
  const name = document.getElementById('edit-con-name').value.trim();
  const phone = document.getElementById('edit-con-phone').value.trim();
  const email = document.getElementById('edit-con-email').value.trim();
  const notes = document.getElementById('edit-con-notes').value.trim();
  
  try {
    await PUT(`/api/promo/contacts/${contactId}`, { name, phone, email, notes });
    toast('Contact updated', 'success');
    openContactDetail(contactId);
    loadPromoContacts();
  } catch (e) { toast('Could not update contact', 'error'); }
}

async function addContactTag(contactId) {
  const input = document.getElementById('new-tag-input');
  const tag = input.value.trim();
  if (!tag) return;
  
  const contact = state.promoContacts.find(c => c.id === contactId);
  if (!contact) return;
  
  const tags = [...(contact.tags || []), tag];
  try {
    await POST(`/api/promo/contacts/${contactId}/tags`, { tags });
    input.value = '';
    openContactDetail(contactId);
    loadPromoContacts();
  } catch (e) { toast('Could not add tag', 'error'); }
}

async function removeContactTag(contactId, tag) {
  const contact = state.promoContacts.find(c => c.id === contactId);
  if (!contact) return;
  
  const tags = (contact.tags || []).filter(t => t !== tag);
  try {
    await POST(`/api/promo/contacts/${contactId}/tags`, { tags });
    openContactDetail(contactId);
    loadPromoContacts();
  } catch (e) { toast('Could not remove tag', 'error'); }
}

async function confirmDeleteContact(contactId) {
  const c = state.promoContacts.find(x => x.id === contactId);
  if (!c) return;
  if (!confirm(`Delete contact "${c.name}"? All their leads will also be deleted. This cannot be undone.`)) return;
  
  try {
    await DEL(`/api/promo/contacts/${contactId}`);
    toast('Contact deleted', 'success');
    loadPromoContacts();
  } catch (e) { toast('Could not delete contact', 'error'); }
}

// ── PROMOTION MACHINE: Leads Sub-tab ──────────────────────────────────────────

const LEAD_STAGES = ['lead', 'qualified', 'proposal', 'negotiation', 'won', 'lost'];

function renderPromoLeads() {
  const container = document.getElementById('promo-view-leads');
  if (!container) return;

  const stageLabels = {
    lead: 'Lead', qualified: 'Qualified', proposal: 'Proposal', 
    negotiation: 'Negotiation', won: 'Won', lost: 'Lost'
  };

  const kanban = LEAD_STAGES.map(stage => {
    const leads = state.promoLeads.filter(l => l.stage === stage);
    const cards = leads.length === 0 
      ? '<div style="color:var(--muted);font-size:12px;text-align:center;padding:12px;">No leads at this stage</div>'
      : leads.map(l => {
          const contact = state.promoContacts.find(c => c.id === l.contact_id);
          const lastComm = l.communication_log?.length 
            ? formatDateShort(l.communication_log[l.communication_log.length-1].timestamp)
            : formatDateShort(l.created_at);
          return `
            <div class="promo-lead-card" onclick="openLeadDetail('${l.id}')">
              <div class="promo-lead-card-contact">${esc(contact ? contact.name : 'Unknown')}</div>
              <div class="promo-lead-card-product">${esc(l.product)}</div>
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="promo-badge promo-badge-${l.product_type || 'other'}" style="font-size:9px;">${esc(l.product_type)}</span>
                <span style="font-size:10px;color:var(--muted);">${lastComm}</span>
              </div>
            </div>`;
        }).join('');
    
    return `
      <div class="promo-kanban-column">
        <div class="promo-kanban-column-header">${stageLabels[stage]}</div>
        <div class="promo-kanban-cards">${cards}</div>
      </div>`;
  }).join('');

  container.innerHTML = `<div class="promo-kanban-board">${kanban}</div>`;
}

function openNewLeadModal(contactId) {
  const c = state.promoContacts.find(x => x.id === contactId);
  if (!c) return;

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">New Lead for ${esc(c.name)}</div>
    <div class="form-group">
      <label class="form-label">Product Name *</label>
      <input class="form-input" id="lead-product" type="text" placeholder="e.g. Golf Day 2026"/>
    </div>
    <div class="form-group">
      <label class="form-label">Product Type</label>
      <select class="form-select" id="lead-type">
        <option value="event">Event</option>
        <option value="campaign">Campaign</option>
        <option value="membership">Membership</option>
        <option value="other">Other</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Initial Notes</label>
      <textarea class="form-textarea" id="lead-notes" placeholder="How did this lead start?"></textarea>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="saveNewLead('${contactId}')">Create Lead</button>
    </div>`;
  showModal();
}

async function saveNewLead(contactId) {
  const product = document.getElementById('lead-product').value.trim();
  const product_type = document.getElementById('lead-type').value;
  const notes = document.getElementById('lead-notes').value.trim();

  if (!product) { toast('Product name is required', 'error'); return; }

  try {
    const res = await POST('/api/promo/leads', { contact_id: contactId, product, product_type, notes });
    toast('Lead created', 'success');
    closeModal();
    loadPromoLeads();
    loadPromoContacts();
  } catch (e) { toast('Could not create lead', 'error'); }
}

async function openLeadDetail(leadId) {
  try {
    const lead = await GET(`/api/promo/leads/${leadId}`);
    const contact = state.promoContacts.find(c => c.id === lead.contact_id);
    renderLeadDetailModal(lead, contact);
  } catch (e) { toast('Could not load lead detail', 'error'); }
}

function renderLeadDetailModal(lead, contact) {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Lead: ${esc(lead.product)}</div>
    <div class="modal-subtitle">Contact: ${esc(contact ? contact.name : 'Unknown')}</div>

    <div class="promo-settings-section">
      <h3>Lead Configuration</h3>
      <div class="form-group">
        <label class="form-label">Product</label>
        <input class="form-input" id="ld-prod" value="${esc(lead.product)}" onchange="updateLeadField('${lead.id}', 'product', this.value)"/>
      </div>
      <div class="form-group">
        <label class="form-label">Product Type</label>
        <select class="form-select" id="ld-type" onchange="updateLeadField('${lead.id}', 'product_type', this.value)">
          <option value="event" ${lead.product_type==='event'?'selected':''}>Event</option>
          <option value="campaign" ${lead.product_type==='campaign'?'selected':''}>Campaign</option>
          <option value="membership" ${lead.product_type==='membership'?'selected':''}>Membership</option>
          <option value="other" ${lead.product_type==='other'?'selected':''}>Other</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Stage</label>
        <select class="form-select" id="ld-stage" onchange="updateLeadField('${lead.id}', 'stage', this.value)">
          ${LEAD_STAGES.map(s => `<option value="${s}" ${lead.stage===s?'selected':''}>${s.toUpperCase()}</option>`).join('')}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Notes</label>
        <textarea class="form-textarea" id="ld-notes" onchange="updateLeadField('${lead.id}', 'notes', this.value)">${esc(lead.notes)}</textarea>
      </div>
    </div>

    <div class="promo-settings-section">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <h3 style="margin-bottom:0;">Communication Log</h3>
        <button class="btn-secondary" style="font-size:11px;" onclick="logInboundMessage('${lead.id}')">Log Inbound ←</button>
      </div>
      <div style="max-height:200px;overflow-y:auto;background:var(--bg);padding:10px;border-radius:4px;">
        ${(lead.communication_log || []).map(e => `
          <div class="promo-comm-log-entry">
            <div class="promo-comm-direction promo-comm-direction-${e.direction === 'inbound' ? 'in' : 'out'}">
              ${e.direction === 'inbound' ? '← Received' : '→ Sent'} • ${formatDateShort(e.timestamp)}
            </div>
            <div style="font-size:13px;">${esc(e.message)}</div>
          </div>
        `).reverse().join('')}
      </div>
    </div>

    <div class="promo-settings-section" style="border-bottom:none;">
      <h3>Compose Message</h3>
      <textarea class="form-textarea" id="ld-compose" placeholder="Type your next message here..." style="min-height:100px;"></textarea>
      <div style="display:flex;gap:8px;margin-top:10px;">
        <button class="btn-secondary" id="btn-ai-suggest" onclick="suggestNextMessage('${lead.id}')">AI: Suggest Next</button>
        <button class="btn-primary" onclick="sendDirectMessage('${lead.id}', '${contact?.phone}', '${contact?.name}', 'manual_outbound')">Send Now →</button>
        <button class="btn-secondary" onclick="scheduleDirectMessage('${lead.id}', '${contact?.phone}', '${contact?.name}')">Schedule...</button>
      </div>
    </div>

    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Close</button>
    </div>`;
  showModal();
}

async function updateLeadField(leadId, field, value) {
  try {
    await PUT(`/api/promo/leads/${leadId}`, { [field]: value });
    toast('Lead updated', 'success');
  } catch (e) { toast('Update failed', 'error'); }
}

async function logInboundMessage(leadId) {
  const msg = prompt('Enter the message received:');
  if (!msg) return;
  
  try {
    await POST(`/api/promo/leads/${leadId}/log_communication`, { direction: 'inbound', message: msg });
    toast('Message logged', 'success');
    openLeadDetail(leadId);
    loadPromoLeads();
  } catch (e) { toast('Could not log message', 'error'); }
}

async function suggestNextMessage(leadId) {
  const btn = document.getElementById('btn-ai-suggest');
  btn.textContent = 'Generating...';
  btn.disabled = true;
  
  try {
    const res = await POST(`/api/promo/leads/${leadId}/ai_suggest`);
    if (res.suggestion) {
      document.getElementById('ld-compose').value = res.suggestion;
    } else {
      toast('AI returned no suggestion', 'error');
    }
  } catch (e) { 
    toast('AI unavailable. Check API keys in Settings.', 'error'); 
  } finally {
    btn.textContent = 'AI: Suggest Next';
    btn.disabled = false;
  }
}

async function sendDirectMessage(leadId, phone, name, source) {
  const content = document.getElementById('ld-compose').value.trim();
  if (!content) { toast('Message is empty', 'error'); return; }
  if (!phone) { toast('Contact phone missing', 'error'); return; }

  try {
    const res = await POST('/api/promo/messages/single', {
      recipient_phone: phone,
      recipient_name: name,
      content: content,
      lead_id: leadId,
      scheduled_at: null
    });
    if (res.status === 'sent') {
      toast('Message sent', 'success');
      document.getElementById('ld-compose').value = '';
      openLeadDetail(leadId);
      loadPromoLeads();
    } else {
      toast(`Message failed: ${res.error}`, 'error');
    }
  } catch (e) { toast('Send failed', 'error'); }
}

function scheduleDirectMessage(leadId, phone, name) {
  const content = document.getElementById('ld-compose').value.trim();
  if (!content) { toast('Message is empty', 'error'); return; }

  const timeStr = prompt('Enter schedule time (ISO or YYYY-MM-DD HH:MM):', new Date(Date.now() + 3600000).toISOString().slice(0,16));
  if (!timeStr) return;

  // Attempt to parse as ISO
  let iso = timeStr;
  if (timeStr.length === 16) iso = timeStr.replace(' ', 'T') + ':00';

  try {
    POST('/api/promo/messages/single', {
      recipient_phone: phone,
      recipient_name: name,
      content: content,
      lead_id: leadId,
      scheduled_at: iso
    }).then(res => {
      toast('Message scheduled', 'success');
      document.getElementById('ld-compose').value = '';
      openLeadDetail(leadId);
    });
  } catch (e) { toast('Schedule failed', 'error'); }
}

// ── PROMOTION MACHINE: Message Maker Sub-tab ──────────────────────────────────

function renderPromoMessageMaker() {
  const container = document.getElementById('promo-view-message-maker');
  if (!container) return;

  container.innerHTML = `
    <div class="hub-panel">
      <h2>Message Maker</h2>
      <div class="form-group">
        <label class="form-label">Purpose *</label>
        <textarea class="form-textarea" id="mm-purpose" placeholder="What is this message promoting?"></textarea>
      </div>
      <div class="promo-action-bar">
        <div class="form-group" style="flex:1;"><label class="form-label">Event Name</label><input class="form-input" id="mm-event-name" placeholder="e.g. Golf Day"/></div>
        <div class="form-group" style="flex:1;"><label class="form-label">Event Date</label><input class="form-input" id="mm-event-date" placeholder="e.g. 15 Oct"/></div>
      </div>
      <div class="promo-action-bar">
        <div class="form-group" style="flex:1;"><label class="form-label">Target Audience</label><input class="form-input" id="mm-audience" placeholder="e.g. Writers"/></div>
        <div class="form-group" style="flex:1;"><label class="form-label">Tone Notes</label><input class="form-input" id="mm-tone" placeholder="e.g. urgent, formal"/></div>
      </div>
      <div class="form-group">
        <label class="form-label">Recipient Name (for personalisation)</label>
        <input class="form-input" id="mm-recipient" placeholder="Optional"/>
      </div>
      <button class="btn-primary" id="btn-mm-generate" onclick="generatePromoMessage()">Generate Message</button>
      
      <div id="mm-result-container" style="display:none;margin-top:32px;border-top:1px solid var(--border);padding-top:24px;">
        <h3>Generated Message</h3>
        <textarea class="form-textarea" id="mm-result" style="min-height:200px;"></textarea>
        <div style="font-size:11px;color:var(--muted);margin-bottom:20px;" id="mm-word-count"></div>
        <div style="display:flex;gap:12px;">
          <div style="flex:1;background:var(--surface2);padding:16px;border-radius:8px;">
            <h4>Send to a Contact</h4>
            <div class="form-group">
              <input class="form-input" id="mm-send-phone" placeholder="+27821112222"/>
            </div>
            <button class="btn-primary" style="width:100%;" onclick="sendMmMessage('single')">Send Now →</button>
          </div>
          <div style="flex:1;background:var(--surface2);padding:16px;border-radius:8px;">
            <h4>Send to a Tag Group</h4>
            <div class="form-group">
              <input class="form-input" id="mm-send-tag" placeholder="Existing tag..."/>
            </div>
            <button class="btn-secondary" style="width:100%;" onclick="sendMmMessage('bulk')">Queue for Tag</button>
          </div>
        </div>
      </div>
    </div>`;
}

async function generatePromoMessage() {
  const purpose = document.getElementById('mm-purpose').value.trim();
  if (!purpose) { toast('Purpose is required', 'error'); return; }

  const btn = document.getElementById('btn-mm-generate');
  btn.textContent = 'Generating...';
  btn.disabled = true;

  const body = {
    purpose,
    event_name: document.getElementById('mm-event-name').value.trim(),
    event_date: document.getElementById('mm-event-date').value.trim(),
    target_audience: document.getElementById('mm-audience').value.trim(),
    tone_notes: document.getElementById('mm-tone').value.trim(),
    recipient_name: document.getElementById('mm-recipient').value.trim(),
  };

  try {
    const res = await POST('/api/promo/message_maker/generate', body);
    if (res.message) {
      const ta = document.getElementById('mm-result');
      ta.value = res.message;
      document.getElementById('mm-result-container').style.display = 'block';
      updateMmWordCount(res.message);
      ta.oninput = () => updateMmWordCount(ta.value);
    } else { toast('AI failed to generate message', 'error'); }
  } catch (e) { toast('AI unavailable. Check API keys in Settings.', 'error'); }
  finally { btn.textContent = 'Generate Message'; btn.disabled = false; }
}

function updateMmWordCount(text) {
  const count = text.split(/\s+/).filter(w => w).length;
  document.getElementById('mm-word-count').textContent = `${count} words`;
}

async function sendMmMessage(type) {
  const content = document.getElementById('mm-result').value.trim();
  if (!content) return;

  if (type === 'single') {
    const phone = document.getElementById('mm-send-phone').value.trim();
    if (!phone) { toast('Phone number required', 'error'); return; }
    try {
      await POST('/api/promo/messages/single', { recipient_phone: phone, content: content });
      toast('Message sent', 'success');
    } catch (e) { toast('Send failed', 'error'); }
  } else {
    const tag = document.getElementById('mm-send-tag').value.trim();
    if (!tag) { toast('Tag required', 'error'); return; }
    try {
      const res = await POST('/api/promo/messages/bulk', { tag, content, scheduled_at: null });
      toast(`Queued ${res.queued_count} messages for tag: ${tag}`, 'success');
    } catch (e) { toast('Send failed', 'error'); }
  }
}

// ── PROMOTION MACHINE: Book Serializer Sub-tab ────────────────────────────────

function renderPromoBookSerializer() {
  const container = document.getElementById('promo-view-book-serializer');
  if (!container) return;

  const selectedBookId = state.selectedBookId;
  const bookList = state.promoBooks.length === 0
    ? '<p style="color:var(--muted);padding:20px;text-align:center;">No books yet.</p>'
    : state.promoBooks.map(b => `
        <div class="promo-lead-card ${selectedBookId === b.id ? 'active' : ''}" style="${selectedBookId === b.id ? 'border-color:var(--accent);background:var(--p4-bg);' : ''}" onclick="selectBook('${b.id}')">
          <div class="promo-lead-card-contact">${esc(b.title)}</div>
          <div class="promo-lead-card-product">${esc(b.author)} • ${b.chunks?.length || 0} chunks</div>
        </div>
      `).join('');

  container.innerHTML = `
    <div class="promo-two-panel">
      <div class="promo-left-panel">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
          <h3 style="font-family:var(--font-mono);font-size:12px;text-transform:uppercase;color:var(--muted);">Books Library</h3>
          <button class="btn-secondary" style="font-size:10px;" onclick="openNewBookModal()">+ New Book</button>
        </div>
        ${bookList}
      </div>
      <div class="promo-right-panel" id="book-detail-panel">
        ${selectedBookId ? '<p style="color:var(--muted);padding:40px;text-align:center;">Loading book detail...</p>' : '<p style="color:var(--muted);padding:40px;text-align:center;">Select a book to manage its serialization.</p>'}
      </div>
    </div>`;

  if (selectedBookId) renderBookDetail(selectedBookId);
}

async function renderBookDetail(bookId) {
  const book = state.promoBooks.find(b => b.id === bookId);
  const panel = document.getElementById('book-detail-panel');
  if (!book || !panel) return;

  // Defaults from settings
  const targetWordCount = state.promoSettings.serializer_defaults?.target_chunk_word_count || 400;
  const maxWordCount    = state.promoSettings.serializer_defaults?.max_chunk_word_count || 550;

  panel.innerHTML = `
    <div class="promo-settings-section">
      <h3>Book Settings</h3>
      <div class="promo-action-bar">
        <div class="form-group" style="flex:1;"><label class="form-label">Title</label><input class="form-input" id="bk-title" value="${esc(book.title)}"/></div>
        <div class="form-group" style="flex:1;"><label class="form-label">Author</label><input class="form-input" id="bk-author" value="${esc(book.author)}"/></div>
      </div>
      <div class="promo-action-bar">
        <div class="form-group" style="flex:1;"><label class="form-label">Patreon URL</label><input class="form-input" id="bk-patreon" value="${esc(book.patreon_url)}"/></div>
        <div class="form-group" style="flex:1;"><label class="form-label">Website URL</label><input class="form-input" id="bk-website" value="${esc(book.website_url)}"/></div>
      </div>
      <button class="btn-primary" onclick="updateBookSettings('${book.id}')">Save Settings</button>
    </div>

    <div class="promo-settings-section">
      <h3>Ingest Content</h3>
      <div style="display:flex;gap:12px;margin-bottom:12px;">
        <button class="btn-secondary active" id="btn-ing-paste" onclick="toggleIngestMode('paste')">Paste Text</button>
        <button class="btn-secondary" id="btn-ing-file" onclick="toggleIngestMode('file')">Upload File</button>
      </div>
      <div id="ing-paste-box">
        <textarea class="form-textarea" id="bk-ingest-text" style="min-height:150px;" placeholder="Paste the book content here..."></textarea>
      </div>
      <div id="ing-file-box" style="display:none;">
        <input type="file" id="bk-ingest-file" accept=".txt,.docx"/>
      </div>
      <div class="promo-action-bar" style="margin-top:12px;">
        <div class="form-group" style="width:140px;"><label class="form-label">Target Words</label><input class="form-input" id="bk-target" type="number" value="${targetWordCount}"/></div>
        <div class="form-group" style="width:140px;"><label class="form-label">Max Words</label><input class="form-input" id="bk-max" type="number" value="${maxWordCount}"/></div>
      </div>
      <button class="btn-primary" id="btn-bk-serialize" onclick="serializeBookContent('${book.id}')">Serialize Content</button>
    </div>

    <div class="promo-settings-section" style="border-bottom:none;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
        <h3 style="margin-bottom:0;">Generated Chunks</h3>
        ${book.chunks?.some(c => c.status === 'pending') ? `
          <button class="btn-secondary" style="font-size:11px;" onclick="queueAllPendingChunksModal('${book.id}')">Queue All Pending...</button>
        ` : ''}
      </div>
      ${!book.chunks || book.chunks.length === 0 ? '<p style="color:var(--muted);font-size:13px;">No chunks generated yet. Ingest content to begin.</p>' : `
        <div class="promo-chunk-list">
          ${book.chunks.map((c, i) => `
            <div class="promo-chunk-item">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <span style="font-weight:bold;font-size:14px;">Chunk ${i+1}</span>
                <span class="promo-badge" style="background:var(--surface2);border:1px solid var(--border2); color:var(--text); opacity:0.7;">${c.word_count} words</span>
                <span class="promo-chunk-status-${c.status}" style="font-family:var(--font-mono);font-size:9px;text-transform:uppercase;">● ${c.status}</span>
              </div>
              <div style="font-size:13px;color:var(--muted);margin-bottom:10px;line-height:1.4;">
                ${esc(c.content.slice(0, 150))}...
                <a href="javascript:void(0)" onclick="toggleChunkContent(this)" style="color:var(--accent);font-size:11px;margin-left:4px;">Show Full</a>
              </div>
              <div class="full-chunk-content" style="display:none;font-size:13px;white-space:pre-wrap;background:var(--bg);padding:12px;border-radius:4px;margin-bottom:10px;">${esc(c.content)}</div>
              <div style="font-size:11px;font-style:italic;color:var(--muted2);margin-bottom:12px;">CLIFFHANGER: ${esc(c.cliffhanger_note || 'None')}</div>
              ${c.status === 'pending' ? `
                <div style="display:flex;gap:8px;">
                  <button class="btn-secondary" style="font-size:11px;" onclick="queueChunk('${book.id}', '${c.id}', true)">Send Now</button>
                  <button class="btn-secondary" style="font-size:11px;" onclick="queueChunk('${book.id}', '${c.id}', false)">Schedule...</button>
                </div>
              ` : ''}
            </div>
          `).join('')}
        </div>
      `}
    </div>`;
}

function selectBook(id) {
  state.selectedBookId = id;
  renderPromoBookSerializer();
}

function toggleChunkContent(link) {
  const full = link.parentElement.nextElementSibling;
  const isHidden = full.style.display === 'none';
  full.style.display = isHidden ? 'block' : 'none';
  link.textContent = isHidden ? 'Hide Full' : 'Show Full';
}

function openNewBookModal() {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Add New Book</div>
    <div class="form-group"><label class="form-label">Title *</label><input class="form-input" id="new-bk-title"/></div>
    <div class="form-group"><label class="form-label">Author</label><input class="form-input" id="new-bk-author"/></div>
    <div class="form-group"><label class="form-label">Patreon URL</label><input class="form-input" id="new-bk-patreon"/></div>
    <div class="form-group"><label class="form-label">Website URL</label><input class="form-input" id="new-bk-website"/></div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="saveNewBook()">Save Book</button>
    </div>`;
  showModal();
}

async function saveNewBook() {
  const title = document.getElementById('new-bk-title').value.trim();
  if (!title) { toast('Title required', 'error'); return; }
  
  try {
    const res = await POST('/api/promo/books', {
      title,
      author: document.getElementById('new-bk-author').value.trim(),
      patreon_url: document.getElementById('new-bk-patreon').value.trim(),
      website_url: document.getElementById('new-bk-website').value.trim()
    });
    toast('Book added', 'success');
    closeModal();
    state.selectedBookId = res.id;
    loadPromoBooks();
  } catch (e) { toast('Save failed', 'error'); }
}

async function updateBookSettings(id) {
  try {
    await PUT(`/api/promo/books/${id}`, {
      title: document.getElementById('bk-title').value.trim(),
      author: document.getElementById('bk-author').value.trim(),
      patreon_url: document.getElementById('bk-patreon').value.trim(),
      website_url: document.getElementById('bk-website').value.trim()
    });
    toast('Book updated', 'success');
    loadPromoBooks();
  } catch (e) { toast('Update failed', 'error'); }
}

function toggleIngestMode(mode) {
  document.getElementById('btn-ing-paste').classList.toggle('active', mode === 'paste');
  document.getElementById('btn-ing-file').classList.toggle('active', mode === 'file');
  document.getElementById('ing-paste-box').style.display = mode === 'paste' ? 'block' : 'none';
  document.getElementById('ing-file-box').style.display = mode === 'file' ? 'block' : 'none';
}

async function serializeBookContent(id) {
  const btn = document.getElementById('btn-bk-serialize');
  btn.textContent = 'Serializing... this may take a moment';
  btn.disabled = true;

  const target_words = document.getElementById('bk-target').value;
  const max_words = document.getElementById('bk-max').value;
  const isPaste = document.getElementById('btn-ing-paste').classList.contains('active');

  try {
    let res;
    if (isPaste) {
      const text = document.getElementById('bk-ingest-text').value.trim();
      if (!text) { toast('No text to serialize', 'error'); return; }
      res = await fetch(`/api/promo/books/${id}/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input_type: 'paste', text, target_words, max_words })
      });
    } else {
      const file = document.getElementById('bk-ingest-file').files[0];
      if (!file) { toast('No file selected', 'error'); return; }
      const formData = new FormData();
      formData.append('input_type', 'file');
      formData.append('file', file);
      formData.append('target_words', target_words);
      formData.append('max_words', max_words);
      res = await fetch(`/api/promo/books/${id}/ingest`, { method: 'POST', body: formData });
    }

    if (res.ok) {
      toast('Serialization complete', 'success');
      loadPromoBooks();
    } else {
      const data = await res.json();
      toast(data.error || 'Serialization failed', 'error');
    }
  } catch (e) { toast('Serialization failed', 'error'); }
  finally { btn.textContent = 'Serialize Content'; btn.disabled = false; }
}

async function queueChunk(bookId, chunkId, immediate) {
  let scheduled_at = null;
  if (!immediate) {
    const timeStr = prompt('Enter schedule time (YYYY-MM-DD HH:MM):', new Date(Date.now() + 3600000).toISOString().slice(0,16).replace('T', ' '));
    if (!timeStr) return;
    scheduled_at = timeStr.replace(' ', 'T') + ':00';
  }

  try {
    const res = await POST(`/api/promo/books/${bookId}/chunks/${chunkId}/queue`, { scheduled_at });
    toast('Chunk queued', 'success');
    loadPromoBooks();
  } catch (e) { toast('Queue failed', 'error'); }
}

function queueAllPendingChunksModal(bookId) {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Batch Queue Chunks</div>
    <div class="form-group">
      <label class="form-label">Start Date/Time</label>
      <input class="form-input" id="batch-start" type="datetime-local" value="${new Date(Date.now() + 3600000).toISOString().slice(0,16)}"/>
    </div>
    <div class="form-group">
      <label class="form-label">Interval (Days)</label>
      <input class="form-input" id="batch-interval" type="number" value="1"/>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="processBatchQueue('${bookId}')">Queue All</button>
    </div>`;
  showModal();
}

async function processBatchQueue(bookId) {
  const startStr = document.getElementById('batch-start').value;
  const interval = parseInt(document.getElementById('batch-interval').value) || 1;
  const book = state.promoBooks.find(b => b.id === bookId);
  if (!book) return;

  const pending = book.chunks.filter(c => c.status === 'pending');
  let startTime = new Date(startStr);
  let queued = 0;

  for (let i = 0; i < pending.length; i++) {
    const chunk = pending[i];
    const scheduled_at = new Date(startTime.getTime() + (i * interval * 24 * 60 * 60 * 1000)).toISOString();
    try {
      await POST(`/api/promo/books/${bookId}/chunks/${chunk.id}/queue`, { scheduled_at });
      queued++;
    } catch (e) {}
  }

  toast(`Queued ${queued} chunks`, 'success');
  closeModal();
  loadPromoBooks();
}

// ── PROMOTION MACHINE: WA Post Maker Sub-tab ──────────────────────────────────

function renderPromoWaPostMaker() {
  const container = document.getElementById('promo-view-wa-post-maker');
  if (!container) return;

  const total = state.promoProverbs.length;
  const used = state.promoProverbs.filter(p => p.used).length;
  const unused = total - used;

  container.innerHTML = `
    <div class="hub-panel">
      <h2>WA Post Maker</h2>
      
      <div class="promo-settings-section">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <h3 style="margin-bottom:0;">Generate Next Post</h3>
          <span style="font-size:12px;color:var(--muted);">${unused} proverbs remaining</span>
        </div>
        
        <div id="wa-poster-config-warning" style="display:none;background:#2a1414;border-left:4px solid var(--p1);padding:16px;margin-bottom:20px;border-radius:0 4px 4px 0;">
          <h4 style="color:var(--p1);font-size:14px;margin-bottom:4px;">Image generation not configured</h4>
          <p style="font-size:12px;color:var(--muted);">Set your image generation provider in Promotion Machine Settings before generating posts.</p>
        </div>
        
        <button class="btn-primary" id="btn-wa-generate" onclick="generateWaPost()">Generate Next Post</button>
        
        <div id="wa-post-result" style="display:none;margin-top:32px;border-top:1px solid var(--border);padding-top:24px;">
          <h3>Post Preview</h3>
          <div class="promo-post-preview">
            <img id="wa-post-img" src="" alt="Post visual" style="display:none;"/>
            <div id="wa-post-img-placeholder" style="width:100%;height:200px;background:var(--surface2);border:1px dashed var(--border2);display:flex;align-items:center;justify-content:center;color:var(--muted);margin-bottom:16px;">
              Image Placeholder
            </div>
            <div id="wa-post-proverb" style="font-weight:bold;font-size:18px;margin-bottom:12px;color:var(--accent);"></div>
            <div id="wa-post-meaning" style="font-size:15px;line-height:1.5;margin-bottom:20px;"></div>
            <textarea class="form-textarea" id="wa-post-content" readonly style="min-height:150px;font-family:var(--font-mono);font-size:12px;opacity:0.8;"></textarea>
          </div>
          
          <div style="background:var(--surface2);padding:20px;border-radius:8px;">
            <h4>Queue Post</h4>
            <div class="form-group">
              <label class="form-label">Recipient / Channel Phone *</label>
              <input class="form-input" id="wa-post-phone" placeholder="+27821112222"/>
            </div>
            <div class="form-group">
              <label class="form-label">Schedule Time (Optional)</label>
              <input class="form-input" id="wa-post-schedule" type="datetime-local"/>
            </div>
            <button class="btn-primary" id="btn-wa-queue" onclick="queueWaPost()">Queue Post</button>
          </div>
        </div>
      </div>

      <div class="promo-settings-section" style="border-bottom:none;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
          <h3 style="margin-bottom:0;">Proverbs Library</h3>
          <div style="display:flex;gap:8px;">
            <button class="btn-secondary" style="font-size:11px;" onclick="openImportProverbsModal()">Import JSON</button>
            <button class="btn-secondary" style="font-size:11px;" onclick="openAddProverbModal()">+ Add Proverb</button>
          </div>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:16px;align-items:center;">
          <span style="font-size:12px;color:var(--muted);">${total} total, ${used} used</span>
          <div class="btn-group" style="display:flex;gap:4px;">
            <button class="btn-secondary active" style="font-size:10px;padding:4px 8px;" onclick="filterProverbs('all', this)">All</button>
            <button class="btn-secondary" style="font-size:10px;padding:4px 8px;" onclick="filterProverbs('unused', this)">Unused</button>
            <button class="btn-secondary" style="font-size:10px;padding:4px 8px;" onclick="filterProverbs('used', this)">Used</button>
          </div>
        </div>
        <table class="promo-table">
          <thead><tr><th>Text</th><th>Origin</th><th>Used</th></tr></thead>
          <tbody id="proverbs-tbody">
            ${renderProverbsTableRows(state.promoProverbs)}
          </tbody>
        </table>
      </div>
    </div>`;
}

function renderProverbsTableRows(items) {
  if (items.length === 0) return '<tr><td colspan="3" style="text-align:center;color:var(--muted);padding:20px;">No proverbs found.</td></tr>';
  return items.map(p => `
    <tr>
      <td title="${esc(p.text)}">${esc(p.text.length > 60 ? p.text.slice(0, 60) + '...' : p.text)}</td>
      <td>${esc(p.origin)}</td>
      <td>${p.used ? '<span style="color:var(--p3);">YES</span>' : '<span style="color:var(--muted);">no</span>'}</td>
    </tr>
  `).join('');
}

function filterProverbs(filter, btn) {
  document.querySelectorAll('.btn-group button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  let items = state.promoProverbs;
  if (filter === 'unused') items = items.filter(p => !p.used);
  else if (filter === 'used') items = items.filter(p => p.used);
  document.getElementById('proverbs-tbody').innerHTML = renderProverbsTableRows(items);
}

async function generateWaPost() {
  const btn = document.getElementById('btn-wa-generate');
  btn.textContent = 'Generating...';
  btn.disabled = true;
  document.getElementById('wa-poster-config-warning').style.display = 'none';

  try {
    const res = await POST('/api/promo/wa_post/generate');
    if (res.error && res.error.includes('configured')) {
      document.getElementById('wa-poster-config-warning').style.display = 'block';
      toast('Configuration incomplete', 'error');
    } else if (res.post_content) {
      document.getElementById('wa-post-result').style.display = 'block';
      document.getElementById('wa-post-proverb').textContent = res.proverb_text;
      document.getElementById('wa-post-meaning').textContent = res.meaning;
      document.getElementById('wa-post-content').value = res.post_content;
      btn.dataset.proverbId = res.proverb_id;
      
      const img = document.getElementById('wa-post-img');
      const placeholder = document.getElementById('wa-post-img-placeholder');
      if (res.image_url) {
        img.src = res.image_url;
        img.style.display = 'block';
        placeholder.style.display = 'none';
      } else {
        img.style.display = 'none';
        placeholder.style.display = 'flex';
      }
    } else {
      toast(res.error || 'Generation failed', 'error');
    }
  } catch (e) { toast('Generation error', 'error'); }
  finally { btn.textContent = 'Generate Next Post'; btn.disabled = false; }
}

async function queueWaPost() {
  const btn = document.getElementById('btn-wa-generate');
  const proverbId = btn.dataset.proverbId;
  const phone = document.getElementById('wa-post-phone').value.trim();
  const schedule = document.getElementById('wa-post-schedule').value;
  
  if (!phone) { toast('Phone number required', 'error'); return; }

  try {
    await POST(`/api/promo/wa_post/${proverbId}/queue`, {
      recipient_phone: phone,
      scheduled_at: schedule || null
    });
    toast('Post queued', 'success');
    document.getElementById('wa-post-result').style.display = 'none';
    loadPromoProverbs();
  } catch (e) { toast('Queue failed', 'error'); }
}

function openAddProverbModal() {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Add Proverb</div>
    <div class="form-group"><label class="form-label">Text *</label><textarea class="form-textarea" id="new-pr-text"></textarea></div>
    <div class="form-group"><label class="form-label">Origin</label><input class="form-input" id="new-pr-origin" placeholder="e.g. Zulu"/></div>
    <div class="modal-actions"><button class="btn-secondary" onclick="closeModal()">Cancel</button><button class="btn-primary" onclick="saveNewProverb()">Save</button></div>`;
  showModal();
}

async function saveNewProverb() {
  const text = document.getElementById('new-pr-text').value.trim();
  if (!text) return;
  try {
    await POST('/api/promo/proverbs', { text, origin: document.getElementById('new-pr-origin').value.trim() });
    toast('Proverb added', 'success');
    closeModal();
    loadPromoProverbs();
  } catch (e) { toast('Save failed', 'error'); }
}

function openImportProverbsModal() {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Import JSON Proverbs</div>
    <p style="font-size:12px;margin-bottom:12px;">Paste a JSON array: <code>[{"text": "...", "origin": "..."}, ...]</code></p>
    <textarea class="form-textarea" id="pr-json-input" style="min-height:200px;" placeholder="[{&quot;text&quot;: &quot;Proverb text&quot;, &quot;origin&quot;: &quot;Zulu&quot;}, ...]"></textarea>
    <div class="modal-actions"><button class="btn-secondary" onclick="closeModal()">Cancel</button><button class="btn-primary" onclick="importProverbsBulk()">Import</button></div>`;
  showModal();
}

async function importProverbsBulk() {
  const input = document.getElementById('pr-json-input').value.trim();
  try {
    const proverbs = JSON.parse(input);
    if (!Array.isArray(proverbs)) throw new Error();
    const res = await POST('/api/promo/proverbs/import_bulk', { proverbs });
    toast(`Imported ${res.imported} proverbs`, 'success');
    closeModal();
    loadPromoProverbs();
  } catch (e) { toast('Invalid JSON format', 'error'); }
}

// ── PROMOTION MACHINE: Sender Sub-tab ─────────────────────────────────────────

function renderPromoSender() {
  const container = document.getElementById('promo-view-sender');
  if (!container) return;

  const msgs = state.promoMessages;
  const filter = state.currentMessageFilter || 'all';
  const filtered = filter === 'all' ? msgs : msgs.filter(m => m.status === filter);

  container.innerHTML = `
    <div class="hub-panel" style="max-width:1100px;">
      <h2>Message Queue & Sender</h2>
      
      ${state.promoInstruction ? `
        <div class="promo-instruction-banner">
          <button class="promo-banner-close" onclick="state.promoInstruction = null; renderPromoSender()">&times;</button>
          <h4>Action Required</h4>
          <p>${state.promoInstruction}</p>
          <div style="margin-top:12px; display:flex; gap:8px;">
            <code>Send WhatsApps from Indaba</code>
            <button class="btn-secondary" style="font-size:11px;" onclick="reconcileResults()">Reconcile Now</button>
          </div>
        </div>
      ` : ''}

      ${state.promoDispatchedCount > 0 && !state.promoInstruction ? `
        <div class="promo-dispatch-banner">
          <div style="color:#03a9f4; font-weight:bold;">${state.promoDispatchedCount} message(s) are with Cowork.</div>
          <button class="btn-secondary" style="font-size:11px;" onclick="reconcileResults()">Reconcile Results</button>
        </div>
      ` : ''}

      ${state.promoOverdueCount > 0 ? `
        <div class="promo-overdue-banner">
          <div class="promo-overdue-text">${state.promoOverdueCount} message(s) are overdue.</div>
          <button class="btn-primary" style="background:#e09a30;border-color:#e09a30;" onclick="dispatchPromoQueue()">Dispatch Overdue Now</button>
        </div>
      ` : ''}

      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
        <div class="btn-group" style="display:flex;gap:4px;">
          ${['all','queued','dispatched','sent','failed','overdue'].map(f => `
            <button class="btn-secondary ${filter === f ? 'active' : ''}" style="font-size:10px;padding:4px 10px;" onclick="state.currentMessageFilter='${f}'; renderPromoSender()">${f.toUpperCase()}</button>
          `).join('')}
        </div>
        <div style="display:flex; gap:8px;">
          <button class="btn-secondary" onclick="reconcileResults()">Reconcile Results</button>
          <button class="btn-primary" onclick="dispatchPromoQueue()">Dispatch to Cowork</button>
        </div>
      </div>

      <table class="promo-table">
        <thead>
          <tr>
            <th>Recipient</th>
            <th>Preview</th>
            <th>Status</th>
            <th>Scheduled</th>
            <th>Source</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${filtered.length === 0 ? '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:40px;">No messages.</td></tr>' : filtered.map(m => `
            <tr>
              <td><strong>${esc(m.recipient_name)}</strong><br/><span style="font-size:11px;color:var(--muted);">${esc(m.recipient_phone)}</span></td>
              <td title="${esc(m.content)}">${esc(m.content.slice(0, 60))}${m.content.length > 60 ? '...' : ''}</td>
              <td><span class="badge promo-message-status-${m.status}">● ${m.status.toUpperCase()}</span></td>
              <td><span style="font-size:11px;">${m.scheduled_at ? formatDateShort(m.scheduled_at) : 'Immediately'}</span></td>
              <td>${esc(m.source)}</td>
              <td>
                ${m.status === 'dispatched' ? '<span style="color:var(--muted);font-size:11px;">Awaiting Cowork</span>' : ''}
                ${(m.status === 'queued' || m.status === 'overdue') ? `
                  <button class="btn-secondary" style="padding:4px 8px;font-size:11px;" onclick="dispatchMessageNow('${m.id}')">Dispatch Now</button>
                  <button class="btn-secondary" style="padding:4px 8px;font-size:11px;" onclick="rescheduleMessagePrompt('${m.id}')">Schedule</button>
                ` : ''}
                ${m.status === 'failed' ? `
                   <button class="btn-secondary" style="padding:4px 8px;font-size:11px;" onclick="rescheduleMessage('${m.id}', null)">Retry</button>
                ` : ''}
                ${m.status !== 'sent' && m.status !== 'dispatched' ? `
                  <button class="btn-secondary" style="padding:4px 8px;font-size:11px;color:var(--p1);" onclick="deleteMessage('${m.id}')">Delete</button>
                ` : ''}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>`;
}

async function dispatchPromoQueue() {
  try {
    const res = await POST('/api/promo/sender/process_queue');
    if (res.failed > 0) {
      toast(`Warning: ${res.failed} job file(s) failed to write.`, 'error');
    }
    if (res.dispatched > 0) {
      state.promoInstruction = `✓ ${res.dispatched} message(s) dispatched. <br/>Now trigger Cowork with the command:`;
      loadPromoMessages();
    } else {
      toast('No messages qualified for dispatch.', 'info');
    }
  } catch (e) { toast('Dispatch failed', 'error'); }
}

async function dispatchMessageNow(id) {
  try {
    const res = await POST(`/api/promo/sender/send_now`, { message_id: id });
    if (res.ok) {
      toast("Job dispatched. Trigger Cowork: 'Send WhatsApps from Indaba'", "success");
      loadPromoMessages();
    } else {
      toast(`Dispatch failed: ${res.error}`, "error");
    }
  } catch (e) { toast('Dispatch failed', 'error'); }
}

async function reconcileResults() {
  try {
    const res = await POST('/api/promo/sender/reconcile');
    if (res.reconciled > 0) {
      toast(`Reconciled ${res.reconciled} results. Sent: ${res.sent}. Failed: ${res.failed}.`, 'success');
      state.promoInstruction = null; // Clear instruction if results found
      loadPromoMessages();
    } else {
      toast("No result files found. Has Cowork finished sending?", "info");
    }
  } catch (e) { toast('Reconcile failed', 'error'); }
}

function rescheduleMessagePrompt(id) {
  const timeStr = prompt('Enter new schedule time (YYYY-MM-DD HH:MM):');
  if (!timeStr) return;
  let iso = timeStr;
  if (timeStr.length === 16) iso = timeStr.replace(' ', 'T') + ':00';
  rescheduleMessage(id, iso);
}

async function rescheduleMessage(id, time) {
  try {
    await POST(`/api/promo/messages/${id}/reschedule`, { scheduled_at: time });
    toast('Updated', 'success');
    loadPromoMessages();
  } catch (e) { toast('Failed to update', 'error'); }
}

async function deleteMessage(id) {
  if (!confirm('Delete this message?')) return;
  try {
    await DEL(`/api/promo/messages/${id}`);
    toast('Deleted', 'success');
    loadPromoMessages();
  } catch (e) { toast('Delete failed', 'error'); }
}

// ── PROMOTION MACHINE: Settings Sub-tab ───────────────────────────────────────

function renderPromoSettings() {
  const container = document.getElementById('promo-view-promo-settings');
  if (!container) return;

  const s = state.promoSettings;
  const p = s.ai_providers || {};

  container.innerHTML = `
    <div class="hub-panel">
      <h2>Promotion Machine Settings</h2>
      
      <div class="promo-settings-section">
        <h3>AI Provider Config</h3>
        ${renderAiProviderFields('message_maker', 'Message Maker', p.message_maker)}
        ${renderAiProviderFields('book_serializer', 'Book Serializer', p.book_serializer)}
        ${renderAiProviderFields('wa_post_maker', 'WA Post Maker', p.wa_post_maker)}
        ${renderAiProviderFields('crm_assist', 'CRM AI Assist', p.crm_assist)}
        
        <div style="margin-top:24px;border-top:1px dashed var(--border);padding-top:20px;">
          <h4>Image Generation</h4>
          <div class="form-group"><label class="form-label">Provider (sdxl-lightning, dall-e-3, etc.)</label><input class="form-input" id="set-img-provider" value="${esc(p.image_gen?.provider)}"/></div>
          <div class="form-group"><label class="form-label">Model Name</label><input class="form-input" id="set-img-model" value="${esc(p.image_gen?.model)}"/></div>
          <div class="form-group"><label class="form-label">Endpoint URL (DALL-E uses standard OpenAI path)</label><input class="form-input" id="set-img-endpoint" value="${esc(p.image_gen?.endpoint)}"/></div>
          <div class="form-group"><label class="form-label">API Key Env Var (e.g. DEEPSEEK_API_KEY)</label><input class="form-input" id="set-img-env" value="${esc(p.image_gen?.api_key_env)}"/></div>
        </div>
      </div>

      <div class="promo-settings-section">
        <h3>Call-to-Action Links</h3>
        <div class="form-group"><label class="form-label">Patreon URL</label><input class="form-input" id="set-cta-patreon" value="${esc(s.cta_links?.patreon)}"/></div>
        <div class="form-group"><label class="form-label">Website URL</label><input class="form-input" id="set-cta-website" value="${esc(s.cta_links?.website)}"/></div>
      </div>

      <div class="promo-settings-section">
        <h3>Serializer Defaults</h3>
        <div class="form-group"><label class="form-label">Target Chunk Word Count</label><input class="form-input" id="set-ser-target" type="number" value="${s.serializer_defaults?.target_chunk_word_count}"/></div>
        <div class="form-group"><label class="form-label">Max Chunk Word Count (Avoid truncation)</label><input class="form-input" id="set-ser-max" type="number" value="${s.serializer_defaults?.max_chunk_word_count}"/></div>
      </div>

      <div class="promo-settings-section">
        <h3>WhatsApp Channel Branding</h3>
        <div class="form-group"><label class="form-label">Channel Name</label><input class="form-input" id="set-wa-name" value="${esc(s.wa_channel_branding?.channel_name)}"/></div>
        <div class="form-group"><label class="form-label">Channel Description</label><textarea class="form-textarea" id="set-wa-desc">${esc(s.wa_channel_branding?.channel_description)}</textarea></div>
        <div class="form-group"><label class="form-label">CTA Emoji (max 2)</label><input class="form-input" id="set-wa-emoji" value="${esc(s.wa_channel_branding?.cta_emoji)}" maxlength="2" style="width:60px;"/></div>
        <div class="form-group"><label class="form-label">CTA Text</label><input class="form-input" id="set-wa-cta" value="${esc(s.wa_channel_branding?.cta_text)}"/></div>
      </div>

      <button class="btn-primary" onclick="savePromoSettings()">Save Settings</button>
    </div>`;
}

function renderAiProviderFields(key, label, data = {}) {
  return `
    <div style="margin-bottom:16px;">
      <h4>${label}</h4>
      <div style="display:flex;gap:12px;">
        <div class="form-group" style="flex:1;"><label class="form-label">Provider</label><input class="form-input ai-p" data-key="${key}" data-field="provider" value="${esc(data.provider)}"/></div>
        <div class="form-group" style="flex:1;"><label class="form-label">Model</label><input class="form-input ai-p" data-key="${key}" data-field="model" value="${esc(data.model)}"/></div>
        <div class="form-group" style="flex:1;"><label class="form-label">API Key Env Var</label><input class="form-input ai-p" data-key="${key}" data-field="api_key_env" value="${esc(data.api_key_env)}"/></div>
      </div>
    </div>`;
}

async function savePromoSettings() {
  const s = {
    ai_providers: {
      image_gen: {
        provider: document.getElementById('set-img-provider').value.trim(),
        model: document.getElementById('set-img-model').value.trim(),
        endpoint: document.getElementById('set-img-endpoint').value.trim(),
        api_key_env: document.getElementById('set-img-env').value.trim()
      }
    },
    cta_links: {
      patreon: document.getElementById('set-cta-patreon').value.trim(),
      website: document.getElementById('set-cta-website').value.trim()
    },
    serializer_defaults: {
      target_chunk_word_count: parseInt(document.getElementById('set-ser-target').value) || 400,
      max_chunk_word_count: parseInt(document.getElementById('set-ser-max').value) || 550
    },
    wa_channel_branding: {
      channel_name: document.getElementById('set-wa-name').value.trim(),
      channel_description: document.getElementById('set-wa-desc').value.trim(),
      cta_emoji: document.getElementById('set-wa-emoji').value.trim(),
      cta_text: document.getElementById('set-wa-cta').value.trim()
    }
  };

  // Map AI providers dynamically
  document.querySelectorAll('.ai-p').forEach(input => {
    const key = input.dataset.key;
    const field = input.dataset.field;
    if (!s.ai_providers[key]) s.ai_providers[key] = {};
    s.ai_providers[key][field] = input.value.trim();
  });

  try {
    await PUT('/api/promo/settings', s);
    toast('Settings saved', 'success');
    loadPromoSettings();
  } catch (e) { toast('Failed to save settings', 'error'); }
}
