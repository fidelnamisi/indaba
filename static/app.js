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
  currentMode:     null,
  currentView:     'dashboard',
  inbox:           [],
  inboxUrgent:     0,
  caps:            { total_active: 0, total_cap: 8, zone_counts: {}, zone_caps: {morning:3,paid_work:3,evening:2}, inbox_count: 0, inbox_max: 15, dormant_count: 0, dormant_max: 25 },
  triageQuestion:  'If you had one more year of productive work left, would you spend any of it on this?',
  postingToday:    { patreon: false, website: false, vip_group: false, wa_channel: false },
  postingStreaks:  { patreon: 0, website: 0, vip_group: 0, wa_channel: 0 },
  zonePriorities:  { morning: null, paid_work: null, evening: null },
  
  // Promotion Machine State
  currentPromoTab:   "command-center",
  promoContacts:     [],
  promoLeads:        [],
  promoMessages:     [],
  promoProverbs:     [],
  broadcastPostLastResult:  null,
  promoBooks:        [],
  promoSettings:     {},
  selectedBookId:    null,
  selectedContactId: null,
  selectedLeadId:    null,
  promoOverdueCount: 0,
  promoDispatchedCount: 0,
  promoInstruction: null,
  currentMessageFilter: "queued",
  lwStories: [],
  lwCurrentStoryId: null,
  lwCurrentStory: null,
  lwCurrentStage: 1,
  broadcastPostQueue:       [],   // all pending/approved posts
  broadcastPostFilter: 'pending',  // current filter
  scrivengsWorkId:   null,   // non-null → Scrivenings mode active in Inventory
  scrivengsData:     null,   // {work_title, modules}
  entities:          [],   // entity model
  entityTypeFilter:  'all',
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
  
// ── Chrome Extension: WhatsApp send result listener ──
document.addEventListener('WHATSAPP_CRM_SEND_RESULT', async function(e) {
  const { message_id, success, reason } = e.detail || {};
  if (!message_id) return;
  try {
    await POST(`/api/promo/messages/${message_id}/extension_result`, { success, reason });
    if (success) {
      toast('WhatsApp sent successfully.', 'success');
    } else {
      toast(`WhatsApp send failed: ${reason || 'Unknown error'}`, 'error');
    }
    if (state.currentPromoTab === 'sender') loadPromoMessages();
    if (state.currentMode === 'promote') await loadPromoLeads();
  } catch(err) {
    console.error('Failed to record extension result', err);
  }
});

// ── Mode & View Switching (The Orchestrator) ──────────────────────────

async function switchMode(mode, pushState = true) {
  if (state.currentMode === mode && !pushState) return;
  state.currentMode = mode;

  if (pushState) {
    const url = `/${mode}`;
    history.pushState({ mode }, '', url);
  }

  // Update top nav mode buttons
  document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });

  // Toggle visibility of mode view containers
  document.querySelectorAll('.mode-view').forEach(el => {
    el.style.display = el.id === `view-${mode}` ? 'block' : 'none';
  });

  // Load relevant data for the mode
  if (mode === 'pipeline') {
    await loadPipeline();
  } else if (mode === 'works') {
    await loadWorks();
  } else if (mode === 'promote') {
    // Default to broadcast-posts; avoid command-center (replaced by Pipeline/Works)
    if (!state.currentPromoTab ||
        state.currentPromoTab === 'command-center' ||
        state.currentPromoTab === 'promo-settings') {
      state.currentPromoTab = 'broadcast-posts';
    }
    await switchPromoTab(state.currentPromoTab);
  }

  closeModal();
}

/**
 * Handles sub-navigation within MANAGE mode (formerly Promotion Machine)
 */
// ── Outbox EC2 polling ────────────────────────────────────────────────────────

let _outboxPollTimer = null;

function startOutboxPolling() {
  stopOutboxPolling();
  _outboxPollTimer = setInterval(async () => {
    try {
      const r = await POST('/api/outbox/sync', {});
      if (r.updated > 0) loadPromoMessages();
    } catch (_) {}
  }, 30000);
}

function stopOutboxPolling() {
  if (_outboxPollTimer) { clearInterval(_outboxPollTimer); _outboxPollTimer = null; }
}

async function switchPromoTab(tabName) {
  state.currentPromoTab = tabName;
  if (tabName !== 'sender') stopOutboxPolling();
  
  // Hide all promo views
  document.querySelectorAll('.promo-view-container').forEach(el => {
    el.style.display = 'none';
  });
  
  // Show selected promo view
  const target = document.getElementById(`promo-view-${tabName}`);
  if (target) target.style.display = 'block';
  
  // Update sub-tab button active state in Manage Sidebar
  document.querySelectorAll('.promo-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.promoTab === tabName);
  });
  
  // Load data based on sub-tab
  try {
    if (tabName === 'command-center')   await loadCommandCenter();
    else if (tabName === 'contacts')   await loadPromoContacts();
    else if (tabName === 'leads')      await loadPromoLeads();
    else if (tabName === 'message-maker') await renderPromoMessageMaker();
    else if (tabName === 'book-serializer') await loadPromoWorks();
    else if (tabName === 'broadcast-posts') await loadBroadcastPostQueue();
    else if (tabName === 'sender')      { state.currentMessageFilter = 'queued'; await loadPromoMessages(); startOutboxPolling(); }
    else if (tabName === 'promo-settings') await loadPromoSettings();
  } catch (e) {
    console.error(`Failed to load ${tabName}:`, e);
    toast(`Failed to load ${tabName}`, 'error');
  }
}

// ── Routing Handler ───────────────────────────────────────────────────────────

function handleRoute() {
  const path = window.location.pathname;
  if (path === '/works')   switchMode('works',   false);
  else if (path === '/promote') switchMode('promote', false);
  else switchMode('pipeline', false); // Default
}

window.onpopstate = () => handleRoute();

// ── Initialization ─────────────────────────────────────────────────────────────

window.onload = async () => {
  // Sync state with current URL
  handleRoute();

  // Setup icon listeners
  document.getElementById('btn-settings').onclick = openSettingsPanel;
  document.getElementById('btn-theme').onclick    = toggleTheme;
  document.getElementById('btn-notes').onclick    = openNotesModal;
  document.getElementById('btn-help').onclick     = openHelpModal;
  document.getElementById('btn-log').onclick      = openLogModal;

  applyStoredTheme();

  // Global Interval for clock/date
  setInterval(updateClock, 1000);
  updateClock();
};

function updateClock() {
    const now = new Date();
    const dateStr = now.toLocaleDateString('en-ZA', { weekday: 'long', day: 'numeric', month: 'long' });
    const timeStr = now.toLocaleTimeString('en-ZA', { hour: '2-digit', minute: '2-digit' });
    const dateEl = document.getElementById('topbar-date');
    const timeEl = document.getElementById('clock');
    if (dateEl) dateEl.textContent = dateStr;
    if (timeEl) timeEl.textContent = timeStr;
}

// ── Pipeline Overview (Phase 3) ───────────────────────────────────────────────

// contentWorkflow state for Pipeline screen
const pipelineState = {
  filter:        'All',   // 'All' | 'Book' | 'Podcast' | 'Campaign' | 'Event'
  activeStage:   'producing',
  overviewData:  null,    // cached API response
};

// work_type → filter label mapping
const WT_FILTER_MAP = {
  'Book':                 'Book',
  'Podcast':              'Podcast',
  'Fundraising Campaign': 'Campaign',
  'Retreat (Event)':      'Event',
};
const FILTER_WT_MAP = {
  'Book':     'Book',
  'Podcast':  'Podcast',
  'Campaign': 'Fundraising Campaign',
  'Event':    'Retreat (Event)',
};

// Work-type colour helpers
function wtBadgeClass(workType) {
  const m = { 'Book': 'book', 'Podcast': 'podcast', 'Fundraising Campaign': 'campaign', 'Retreat (Event)': 'event' };
  return 'wt-badge wt-badge-' + (m[workType] || 'book');
}
function wtBarClass(workType) {
  const m = { 'Book': 'wt-book', 'Podcast': 'wt-podcast', 'Fundraising Campaign': 'wt-campaign', 'Retreat (Event)': 'wt-event' };
  return m[workType] || 'wt-book';
}
function wtLabel(workType) {
  return WT_FILTER_MAP[workType] || workType;
}

async function loadPipeline() {
  const container = document.getElementById('pipeline-container');
  if (!container) return;
  try {
    pipelineState.overviewData = await GET('/api/pipeline/overview');
    renderPipelineOverview(container);
  } catch (e) {
    container.innerHTML = `<div class="stub-placeholder">Failed to load pipeline: ${e.message}</div>`;
  }
}

function renderPipelineOverview(container) {
  const { counts, modules } = pipelineState.overviewData;
  const stages = [
    { key: 'producing',  label: 'Producing',  num: 1 },
    { key: 'publishing', label: 'Publishing', num: 2 },
    { key: 'promoting',  label: 'Promoting',  num: 3 },
  ];
  const filters = ['All', 'Book', 'Podcast', 'Campaign', 'Event'];

  // Filter bar
  const filterHtml = filters.map(f => `
    <button class="pipeline-filter-btn${f === pipelineState.filter ? ' active' : ''}"
            onclick="setPipelineFilter('${f}')">${f}</button>
  `).join('');

  // Stage cards
  const cardsHtml = stages.map(s => {
    const c = counts[s.key] || { total: 0, breakdown: {} };
    const total = c.total;
    const breakdown = c.breakdown;
    const WORK_TYPES = ['Book', 'Podcast', 'Fundraising Campaign', 'Retreat (Event)'];

    // Breakdown text
    const parts = WORK_TYPES
      .filter(wt => (breakdown[wt] || 0) > 0)
      .map(wt => `${breakdown[wt]} ${wtLabel(wt).toLowerCase()}`);
    const breakdownText = parts.length ? parts.join(' · ') : '—';

    // Proportional colour bar
    const barSegments = total > 0
      ? WORK_TYPES.filter(wt => (breakdown[wt] || 0) > 0).map(wt => {
          const pct = ((breakdown[wt] / total) * 100).toFixed(1);
          return `<div class="pipeline-stage-bar-segment ${wtBarClass(wt)}" style="width:${pct}%"></div>`;
        }).join('')
      : '';

    const isActive = s.key === pipelineState.activeStage;
    return `
      <div class="pipeline-stage-card${isActive ? ' active' : ''}"
           onclick="setPipelineStage('${s.key}')">
        <div class="pipeline-stage-card-title">Stage ${s.num}: ${s.label}</div>
        <div class="pipeline-stage-card-count">${total}</div>
        <div class="pipeline-stage-card-breakdown">${breakdownText}</div>
        <div class="pipeline-stage-card-bar">${barSegments}</div>
      </div>`;
  }).join('');

  // Drill-down list
  const drillHtml = renderPipelineDrilldown(modules);

  container.innerHTML = `
    <div style="max-width:1100px; margin:0 auto;">
      <div class="pipeline-filter-bar">${filterHtml}</div>
      <div class="pipeline-stage-cards">${cardsHtml}</div>
      <div id="pipeline-drilldown">${drillHtml}</div>
    </div>`;
}

function renderPipelineDrilldown(allModules) {
  const stage  = pipelineState.activeStage;
  const filter = pipelineState.filter;

  let modules = allModules.filter(m => m.workflow_stage === stage);
  if (filter !== 'All') {
    const targetWt = FILTER_WT_MAP[filter];
    if (targetWt) modules = modules.filter(m => m.work_type === targetWt);
  }

  const stageLabel = { producing: 'Producing', publishing: 'Publishing', promoting: 'Promoting' }[stage];

  if (!modules.length) {
    return `<div class="pipeline-drilldown-header">Modules — ${stageLabel}</div>
            <div class="pipeline-drilldown-empty">No modules in ${stageLabel}${filter !== 'All' ? ` (${filter})` : ''}.</div>`;
  }

  const rows = modules.map(m => `
    <div class="pipeline-module-row">
      <span class="${wtBadgeClass(m.work_type)}">${wtLabel(m.work_type)}</span>
      <span class="pipeline-module-title">${m.title}</span>
      <span class="pipeline-module-work">${m.work_name}</span>
      <button class="pipeline-open-btn" onclick="openModuleDetail('${m.id}')">Open</button>
    </div>`).join('');

  return `<div class="pipeline-drilldown-header">Modules — ${stageLabel} (${modules.length})</div>${rows}`;
}

function setPipelineFilter(filter) {
  pipelineState.filter = filter;
  if (!pipelineState.overviewData) return;
  // Re-render just filter bar + drilldown (cards don't change)
  const container = document.getElementById('pipeline-container');
  if (container) renderPipelineOverview(container);
}

function setPipelineStage(stage) {
  pipelineState.activeStage = stage;
  if (!pipelineState.overviewData) return;
  const container = document.getElementById('pipeline-container');
  if (container) renderPipelineOverview(container);
}

// ── Works Screen (Phase 3) ────────────────────────────────────────────────────

async function loadWorks() {
  const container = document.getElementById('works-container');
  if (!container) return;
  try {
    const data = await GET('/api/pipeline/overview');
    renderWorksScreen(container, data.modules);
  } catch (e) {
    container.innerHTML = `<div class="stub-placeholder">Failed to load works: ${e.message}</div>`;
  }
}

function renderWorksScreen(container, modules) {
  const WORK_TYPES = ['Book', 'Podcast', 'Fundraising Campaign', 'Retreat (Event)'];

  const sectionsHtml = WORK_TYPES.map(wt => {
    const wtModules = modules.filter(m => m.work_type === wt);
    if (!wtModules.length) return '';

    // Group by work_name
    const byWork = {};
    wtModules.forEach(m => {
      const key = m.work_name || 'Unknown';
      if (!byWork[key]) byWork[key] = [];
      byWork[key].push(m);
    });

    const cardsHtml = wtModules.map(m => {
      const stageClass = 'stage-' + (m.workflow_stage || 'producing');
      const stageLabel = { producing: 'Producing', publishing: 'Publishing', promoting: 'Promoting' }[m.workflow_stage] || m.workflow_stage;
      return `
        <div class="works-card" onclick="openModuleDetail('${m.id}')">
          <div class="works-card-header">
            <div>
              <div class="works-card-title">${m.title}</div>
              <div class="works-card-work">${m.work_name}</div>
            </div>
            <div class="works-card-stage ${stageClass}">${stageLabel}</div>
          </div>
        </div>`;
    }).join('');

    const sectionTitle = wt === 'Fundraising Campaign' ? 'Campaign' : wt === 'Retreat (Event)' ? 'Event' : wt;
    return `
      <div class="works-section">
        <div class="works-section-header">
          <span class="${wtBadgeClass(wt)}">${sectionTitle}</span>
          <span class="works-section-title">${wt}</span>
          <span class="works-section-count">${wtModules.length}</span>
        </div>
        <div class="works-grid">${cardsHtml}</div>
      </div>`;
  }).join('');

  container.innerHTML = `<div style="max-width:1100px; margin:0 auto;">${sectionsHtml}</div>`;
}

// ── Module Detail View (Phase 4) ──────────────────────────────────────────────

// contentWorkflow state for module detail
const moduleDetailState = {
  module:       null,
  activeStage:  'producing',
  originMode:   'pipeline',  // which mode opened this module
};

async function openModuleDetail(moduleId) {
  // Remember which mode we came from
  moduleDetailState.originMode = pipelineState.overviewData ? state.currentMode : 'pipeline';

  try {
    const data = await GET('/api/content-pipeline');
    const module = data.find(e => e.id === moduleId);
    if (!module) { toast('Module not found', 'error'); return; }
    moduleDetailState.module = module;
    moduleDetailState.activeStage = module.workflow_stage || 'producing';

    // Render in the active mode container
    const containerId = state.currentMode === 'works' ? 'works-container' : 'pipeline-container';
    const container = document.getElementById(containerId);
    if (!container) return;
    renderModuleDetail(container);
  } catch (e) {
    toast('Failed to load module: ' + e.message, 'error');
  }
}

function renderModuleDetail(container) {
  const m     = moduleDetailState.module;
  const stage = moduleDetailState.activeStage;

  const stageCards = [
    { key: 'producing',  num: 1, label: 'Producing'  },
    { key: 'publishing', num: 2, label: 'Publishing' },
    { key: 'promoting',  num: 3, label: 'Promoting'  },
  ];

  // Compute progress for each stage card
  function stageProgress(stageKey) {
    if (stageKey === 'producing') {
      const ps = m.producing_status || {};
      const ea = ps.essential_asset === 'done' ? 1 : 0;
      const sa = Object.values(ps.supporting_assets || {});
      const saDone = sa.filter(v => v === 'done').length;
      const total  = 1 + sa.length;
      const done   = ea + saDone;
      return { done, total, pct: total > 0 ? Math.round((done / total) * 100) : 0, label: `${done} of ${total} assets done` };
    }
    if (stageKey === 'publishing') {
      const pub = m.publishing_status || {};
      const platforms = Object.values(pub);
      const done = platforms.filter(v => v === 'published' || v === 'done').length;
      return { done, total: platforms.length, pct: platforms.length > 0 ? Math.round((done / platforms.length) * 100) : 0, label: `${done} of ${platforms.length} platforms` };
    }
    if (stageKey === 'promoting') {
      const pr = m.promoting_status || {};
      const actions = Object.values(pr);
      const done = actions.filter(v => v === 'sent').length;
      return { done, total: actions.length, pct: actions.length > 0 ? Math.round((done / actions.length) * 100) : 0, label: `${done} of ${actions.length} actions done` };
    }
    return { done: 0, total: 0, pct: 0, label: '' };
  }

  const stageBarHtml = stageCards.map(s => {
    const prog = stageProgress(s.key);
    return `
      <div class="module-stage-card${s.key === stage ? ' active' : ''}"
           onclick="switchModuleStage('${s.key}')">
        <div class="module-stage-card-num">Stage ${s.num}</div>
        <div class="module-stage-card-name">${s.label}</div>
        <div class="module-stage-card-progress">
          <div class="module-stage-card-progress-fill" style="width:${prog.pct}%"></div>
        </div>
        <div class="module-stage-card-stat">${prog.label}</div>
      </div>`;
  }).join('');

  // Detail panel content
  const panelHtml = renderModuleDetailPanel(m, stage);

  const workType   = m.work_type || 'Book';
  const workName   = m.book || '';
  const stageLabel = { producing: 'Producing', publishing: 'Publishing', promoting: 'Promoting' }[m.workflow_stage] || m.workflow_stage;
  const backLabel  = moduleDetailState.originMode === 'works' ? 'Works' : 'Pipeline';
  const backFn     = moduleDetailState.originMode === 'works' ? 'loadWorks' : 'loadPipeline';

  container.innerHTML = `
    <div class="module-detail-view">
      <button class="module-back-btn" onclick="${backFn}()">← ${backLabel}</button>
      <div class="module-detail-breadcrumb">
        <span onclick="${backFn}()">${workName}</span> › ${m.chapter}
      </div>
      <div class="module-detail-title">${m.chapter}</div>
      <div class="module-detail-meta">
        <span class="${wtBadgeClass(workType)}" style="margin-right:8px">${wtLabel(workType)}</span>
        ${workName} · ${stageLabel}
      </div>
      <div class="module-stage-bar">${stageBarHtml}</div>
      <div id="module-detail-panel" class="module-detail-panel">${panelHtml}</div>
    </div>`;
}

function renderModuleDetailPanel(m, stage) {
  if (stage === 'producing') return renderProducingPanel(m);
  if (stage === 'publishing') return renderPublishingPanel(m);
  if (stage === 'promoting')  return renderPromotingPanel(m);
  return '';
}

function renderProducingPanel(m) {
  const ps   = m.producing_status || {};
  const eaDone = ps.essential_asset === 'done';
  const sa   = ps.supporting_assets || {};

  // Essential asset label by work type
  const essentialLabel = {
    'Book':                 'Chapter Prose',
    'Podcast':              'Audio Recording',
    'Fundraising Campaign': 'Campaign Narrative',
    'Retreat (Event)':      'Event Offer Write-up',
  }[m.work_type] || 'Essential Asset';

  const eaRow = `
    <div class="module-asset-row">
      <div class="module-asset-dot ${eaDone ? 'dot-done' : 'dot-missing'}"></div>
      <span class="module-asset-name">${essentialLabel}</span>
      <button class="module-asset-action" onclick="viewModuleAsset('${m.id}', 'essential')">${eaDone ? 'View' : 'Add'}</button>
    </div>`;

  const saRows = Object.entries(sa).map(([key, val]) => {
    const done    = val === 'done';
    const label   = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    const dotClass = done ? 'dot-done' : 'dot-optional';
    return `
      <div class="module-asset-row">
        <div class="module-asset-dot ${dotClass}"></div>
        <span class="module-asset-name">${label}</span>
        <button class="module-asset-action" onclick="viewModuleAsset('${m.id}', '${key}')">${done ? 'View' : 'Generate'}</button>
      </div>`;
  }).join('');

  return `
    <div class="module-detail-panel-title">Stage 1: Producing</div>
    <div class="module-asset-section-title">Essential Asset</div>
    ${eaRow}
    <div class="module-asset-section-title">Supporting Assets</div>
    ${saRows || '<div style="color:var(--muted);font-size:13px;padding:8px 0;">No supporting assets defined.</div>'}
    <div style="margin-top:16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
      <button class="module-asset-action" onclick="moveModuleToStage('${m.id}', 'publishing')" style="border-color:var(--accent)">→ Move to Publishing</button>
    </div>`;
}

function renderPublishingPanel(m) {
  const pub = m.publishing_status || {};

  // Platform display labels
  const PLATFORM_LABELS = {
    vip_group: 'VIP Group', patreon: 'Patreon', website: 'Website',
    wa_channel: 'WA Channel', spotify: 'Spotify', apple_podcasts: 'Apple Podcasts',
    gofundme: 'GoFundMe', social: 'Social Pages',
    landing_page: 'Landing Page', eventbrite: 'Eventbrite',
  };

  const rows = Object.entries(pub).map(([platform, status]) => {
    const label      = PLATFORM_LABELS[platform] || platform;
    const isPublished = status === 'published' || status === 'done';
    const statusLabel = isPublished ? 'Published' : (status === 'in_progress' ? 'In Progress' : 'Not Started');
    return `
      <div class="module-platform-row">
        <span class="module-platform-name">${label}</span>
        <span class="module-platform-status${isPublished ? ' published' : ''}">${statusLabel}</span>
        ${!isPublished ? `<button class="module-platform-mark-btn" onclick="markPlatformPublished('${m.id}', '${platform}')">Mark Published</button>` : ''}
      </div>`;
  }).join('');

  return `
    <div class="module-detail-panel-title">Stage 2: Publishing</div>
    <div class="module-asset-section-title">Platforms</div>
    ${rows || '<div style="color:var(--muted);font-size:13px;padding:8px 0;">No platforms configured.</div>'}
    <div style="margin-top:16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
      <button class="module-asset-action" onclick="moveModuleToStage('${m.id}', 'producing')" style="color:var(--muted)">← Back to Producing</button>
      <button class="module-asset-action" onclick="moveModuleToStage('${m.id}', 'promoting')" style="border-color:var(--accent)">→ Move to Promoting</button>
    </div>`;
}

function renderPromotingPanel(m) {
  const pr = m.promoting_status || {};

  const ACTION_LABELS = {
    wa_broadcast:    'WhatsApp Broadcast',
    email_excerpt:   'Email Excerpt',
    serializer_post: 'Serializer Post',
  };

  const broadcastRows = Object.entries(pr).map(([key, val]) => {
    const label  = ACTION_LABELS[key] || key.replace(/_/g, ' ');
    const isSent = val === 'sent';
    return `
      <div class="module-broadcast-row">
        <span class="module-broadcast-name">${label}</span>
        <span class="module-broadcast-status${isSent ? ' sent' : ''}">${isSent ? 'Sent' : 'Not Sent'}</span>
        ${!isSent ? `<button class="module-broadcast-action" onclick="queueBroadcastAction('${m.id}', '${key}')">Queue</button>` : ''}
      </div>`;
  }).join('');

  return `
    <div class="module-detail-panel-title">Stage 3: Promoting</div>
    <div class="module-asset-section-title">Broadcast Actions</div>
    ${broadcastRows}
    <div class="module-asset-section-title">CRM</div>
    <div class="module-asset-row">
      <div class="module-asset-dot dot-optional"></div>
      <span class="module-asset-name">Contacts &amp; Leads for this module</span>
      <button class="module-asset-action" onclick="switchMode('promote').then(()=>switchPromoTab('contacts'))">View CRM</button>
    </div>
    <div style="margin-top:16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
      <button class="module-asset-action" onclick="moveModuleToStage('${m.id}', 'publishing')" style="color:var(--muted)">← Back to Publishing</button>
    </div>`;
}

function switchModuleStage(stage) {
  moduleDetailState.activeStage = stage;
  const panel = document.getElementById('module-detail-panel');
  if (panel && moduleDetailState.module) {
    panel.innerHTML = renderModuleDetailPanel(moduleDetailState.module, stage);
    // Update active card border
    document.querySelectorAll('.module-stage-card').forEach(card => {
      card.classList.toggle('active', card.getAttribute('onclick').includes(`'${stage}'`));
    });
  }
}

async function moveModuleToStage(moduleId, newStage) {
  try {
    await PUT(`/api/content-pipeline/${moduleId}/workflow-stage`, { stage: newStage });
    // Refresh pipeline cache
    pipelineState.overviewData = null;
    toast(`Moved to ${newStage}`, 'success');
    // Re-open the module from fresh data
    await openModuleDetail(moduleId);
  } catch (e) {
    toast('Failed to move stage: ' + e.message, 'error');
  }
}

async function markPlatformPublished(moduleId, platform) {
  try {
    await PUT(`/api/content-pipeline/${moduleId}/publishing-status`, { [platform]: 'published' });
    toast('Marked as published', 'success');
    await openModuleDetail(moduleId);
  } catch (e) {
    toast('Failed: ' + e.message, 'error');
  }
}

async function queueBroadcastAction(moduleId, actionKey) {
  // Navigate to promote / broadcast-posts for now
  await switchMode('promote');
  await switchPromoTab('broadcast-posts');
  toast('Navigated to Broadcast Posts — queue your post there.', 'info');
}

function viewModuleAsset(moduleId, assetKey) {
  // Navigate to the publishing screen for this chapter
  toast('Asset view — open the chapter in the publishing screen.', 'info');
}

// ── Settings Modal (Phase 5) ──────────────────────────────────────────────────

function openSettingsPanel() {
  const modal = document.getElementById('settings-modal');
  if (modal) {
    modal.classList.remove('hidden');
    loadSettingsModal();
  }
}

function closeSettingsModal() {
  const modal = document.getElementById('settings-modal');
  if (modal) modal.classList.add('hidden');
}

let _settingsActiveTab = 'branding';

function switchSettingsTab(tab) {
  _settingsActiveTab = tab;
  document.querySelectorAll('.settings-tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.settingsTab === tab);
  });
  document.querySelectorAll('.settings-tab-pane').forEach(p => {
    p.classList.toggle('active', p.id === `settings-pane-${tab}`);
  });
}

async function loadSettingsModal() {
  const body = document.getElementById('settings-modal-body');
  if (!body) return;
  try {
    const [promoSettings, appSettings] = await Promise.all([
      GET('/api/promo/settings'),
      GET('/api/settings'),
    ]);
    renderSettingsModal(body, promoSettings, appSettings);
    switchSettingsTab(_settingsActiveTab);
  } catch (e) {
    body.innerHTML = `<div style="color:var(--muted);padding:16px;">Failed to load settings: ${e.message}</div>`;
  }
}

function renderSettingsModal(body, promo, app) {
  const ws = promo.whatsapp_sender || {};
  const ai = promo.ai_providers || {};

  body.innerHTML = `
    <div id="settings-pane-branding" class="settings-tab-pane">
      <div class="settings-section-title">WhatsApp Channel Branding</div>
      <table class="settings-kv-table">
        <tr><td>Channel Name</td><td><input class="form-input" id="s-wa-channel-name" value="${escHtml(ws.channel_name || '')}"/></td></tr>
        <tr><td>Author Name</td><td><input class="form-input" id="s-wa-author-name" value="${escHtml(ws.author_name || '')}"/></td></tr>
        <tr><td>CTA URL</td><td><input class="form-input" id="s-wa-cta-url" value="${escHtml(ws.cta_url || '')}"/></td></tr>
        <tr><td>CTA Label</td><td><input class="form-input" id="s-wa-cta-label" value="${escHtml(ws.cta_label || '')}"/></td></tr>
      </table>
    </div>
    <div id="settings-pane-ai" class="settings-tab-pane">
      <div class="settings-section-title">AI Providers</div>
      <table class="settings-kv-table">
        <tr><td>Proverb Generator</td><td><input class="form-input" id="s-ai-proverb" value="${escHtml((ai.proverb_generator || {}).model || '')}"/></td></tr>
        <tr><td>Message Maker</td><td><input class="form-input" id="s-ai-message" value="${escHtml((ai.message_maker || {}).model || '')}"/></td></tr>
        <tr><td>Work Serializer</td><td><input class="form-input" id="s-ai-serializer" value="${escHtml((ai.work_serializer || {}).model || '')}"/></td></tr>
        <tr><td>Broadcast Post</td><td><input class="form-input" id="s-ai-broadcast" value="${escHtml((ai.broadcast_post || {}).model || '')}"/></td></tr>
      </table>
    </div>
    <div id="settings-pane-schedule" class="settings-tab-pane">
      <div class="settings-section-title">Delivery Schedule</div>
      <table class="settings-kv-table">
        <tr><td>Delivery Hour (24h)</td><td><input class="form-input" type="number" id="s-delivery-hour" value="${escHtml(String(promo.delivery_hour ?? 8))}"/></td></tr>
        <tr><td>Posting Days</td><td><input class="form-input" id="s-posting-days" value="${escHtml((promo.posting_days || []).join(', '))}"/></td></tr>
      </table>
    </div>`;
}

async function saveSettingsModal() {
  try {
    // Read branding fields
    const patchPromo = {
      whatsapp_sender: {
        channel_name: document.getElementById('s-wa-channel-name')?.value || '',
        author_name:  document.getElementById('s-wa-author-name')?.value  || '',
        cta_url:      document.getElementById('s-wa-cta-url')?.value      || '',
        cta_label:    document.getElementById('s-wa-cta-label')?.value    || '',
      }
    };
    // Delivery schedule
    const delivHour  = parseInt(document.getElementById('s-delivery-hour')?.value || '8');
    const postDays   = (document.getElementById('s-posting-days')?.value || '')
                         .split(',').map(s => s.trim()).filter(Boolean);
    patchPromo.delivery_hour = delivHour;
    patchPromo.posting_days  = postDays;

    await PUT('/api/promo/settings', patchPromo);
    toast('Settings saved', 'success');
    closeSettingsModal();
  } catch (e) {
    toast('Save failed: ' + e.message, 'error');
  }
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
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

// ── Living Writer Dashboard ──────────────────────────────────────────────────

// ── Living Writer Dashboard ──────────────────────────────────────────────────

async function loadLwDashboard() {
  try {
    const data = await GET('/api/lw/stories');
    state.lwStories = data.stories || [];
    renderLwPipeline();
  } catch (e) {
    console.error('LW Dashboard load failed:', e);
    toast('Could not load stories', 'error');
  }
}

function renderLwPipeline() {
  state.lwCurrentStoryId = null;
  state.lwCurrentStory = null;
  state.currentTopTab = 'living-writer';

  const container = document.getElementById('view-living-writer');
  if (!container) return;

  const pipelineView = document.getElementById('lw-pipeline-view');
  const storyView = document.getElementById('lw-story-view');
  if (pipelineView) pipelineView.style.display = 'block';
  if (storyView) storyView.style.display = 'none';

  const list = document.getElementById('lw-pipeline-list');
  if (!list) return;

  if (state.lwStories.length === 0) {
    list.innerHTML = `
      <div class="lw-empty-state">
        <div class="lw-empty-icon">📖</div>
        <p>Your pipeline is empty. Start a new creative journey below.</p>
        <button class="btn-primary" onclick="newLwStoryModal()">+ Add New Story</button>
      </div>`;
  } else {
    list.innerHTML = '<div class="lw-pipeline-grid">' + state.lwStories.map(story => {
      const progress = ((story.current_stage - 1) / 6) * 100;
      const stageName = [
        "", "Concept Note", "World Bible", "Episode Grid", 
        "Beat Cruxes", "Treatment", "Memorize", "First Draft"
      ][story.current_stage];
      
      const lastUpdated = formatDateShort(story.updated_at);
      
      return `
        <div class="lw-pipeline-card" onclick="openLwStory('${story.id}')">
          <div class="lw-card-header">
            <h3 class="lw-card-title">${esc(story.title)}</h3>
            ${story.draft_complete ? `<span class="lw-draft-badge">Draft Complete</span>` : ''}
          </div>
          
          <div class="lw-card-stage-info">
            <div class="lw-stage-label">Stage ${story.current_stage}: ${stageName}</div>
            <div class="lw-progress-track">
              <div class="lw-progress-bar" style="width: ${progress}%"></div>
            </div>
          </div>
          
          <div class="lw-card-meta">
            <div class="lw-card-date">Updated ${lastUpdated}</div>
            <div class="lw-card-actions">
              <button class="btn-icon" title="Delete Story" onclick="event.stopPropagation(); confirmDeleteLwStory('${story.id}')">✕</button>
            </div>
          </div>
        </div>
      `;
    }).join('') + '</div>';
  }
}

function newLwStoryModal() {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">+ Add New Story</div>
    <div class="form-group">
      <label class="form-label">Story Title *</label>
      <input class="form-input" id="new-lw-title" placeholder="e.g. Echoes of the Deep" autofocus />
      <div id="new-lw-error" style="color:var(--p1);font-size:12px;margin-top:4px;display:none;">Please give your story a name.</div>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="saveNewLwStory()">Start Story</button>
    </div>`;
  showModal();
}

async function saveNewLwStory() {
  const titleInput = document.getElementById('new-lw-title');
  const errorEl = document.getElementById('new-lw-error');
  const title = titleInput.value.trim();
  
  if (!title) {
    if (errorEl) errorEl.style.display = 'block';
    return;
  }
  
  try {
    const res = await POST('/api/lw/stories', { title });
    closeModal();
    toast('Story added to pipeline', 'success');
    await loadLwDashboard();
    if (res.id) openLwStory(res.id);
  } catch (e) {
    if (e.message.includes('409')) {
      toast('Pipeline capacity reached (8 max)', 'error');
    } else {
      toast('Operation failed', 'error');
    }
  }
}

function confirmDeleteLwStory(storyId) {
  if (confirm("Permanently delete this story? All progress and metadata will be lost.")) {
    DEL(`/api/lw/stories/${storyId}`).then(() => {
      toast('Story removed from pipeline', 'success');
      loadLwDashboard();
    }).catch(() => {
      toast('Delete failed', 'error');
    });
  }
}

// ── Living Writer Story View ─────────────────────────────────────────────────

async function openLwStory(storyId) {
  try {
    const story = await GET(`/api/lw/stories/${storyId}`);
    state.lwCurrentStoryId = storyId;
    state.lwCurrentStory = story;
    state.lwCurrentStage = story.current_stage;
    
    document.getElementById('lw-pipeline-view').style.display = 'none';
    document.getElementById('lw-story-view').style.display = 'block';
    
    renderLwPage();
  } catch (e) {
    console.error('Open story failed:', e);
    toast('Could not open story', 'error');
    renderLwPipeline();
  }
}

function renderLwPage() {
  if (!state.lwCurrentStory) return;
  renderLwStageSidebar(state.lwCurrentStory);
  renderLwStageContent(state.lwCurrentStory);
}

function renderLwStageSidebar(story) {
  const sidebar = document.getElementById('lw-stage-sidebar');
  if (!sidebar) return;

  const stageNames = [
    "", "Concept Note", "World Bible", "Episode Grid", 
    "Beat Cruxes", "Treatment", "Memorize", "First Draft"
  ];

  let stagesHtml = '';
  for (let i = 1; i <= 7; i++) {
    const isCompleted = i < story.current_stage;
    const isActive = i === state.lwCurrentStage;
    const isLocked = i > story.current_stage;
    
    stagesHtml += `
      <div class="lw-stage-item ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''} ${isLocked ? 'locked' : ''}" 
           onclick="switchLwStage(${i})">
        <div class="lw-stage-status"></div>
        <div class="lw-stage-name">${i}. ${stageNames[i]}</div>
      </div>
    `;
  }

  sidebar.innerHTML = `
    <div class="lw-sidebar-header">
      <button class="lw-back-btn" onclick="renderLwPipeline()">← BACK TO PIPELINE</button>
      <h2 class="lw-sidebar-title">${esc(story.title)}</h2>
    </div>
    <div class="lw-stage-list">
      ${stagesHtml}
    </div>
  `;
}

async function switchLwStage(stageNumber) {
  state.lwCurrentStage = stageNumber;
  renderLwPage();
}

function renderLwStageContent(story) {
  const content = document.getElementById('lw-stage-content');
  if (!content) return;

  const currentStage = state.lwCurrentStage;
  const isLocked = currentStage > story.current_stage;
  
  content.innerHTML = '';
  
  if (isLocked) {
    content.innerHTML = `
      <div class="lw-empty-state">
        <div class="lw-empty-icon">🔒</div>
        <h2>Stage Locked</h2>
        <p>Complete "Stage ${story.current_stage}: ${[
          "", "Concept Note", "World Bible", "Episode Grid", 
          "Beat Cruxes", "Treatment", "Memorize", "First Draft"
        ][story.current_stage]}" to unlock this phase.</p>
      </div>`;
    return;
  }

  switch (currentStage) {
    case 1: renderLwStage1(story); break;
    case 2: renderLwStage2(story); break;
    case 3: renderLwStage3(story); break;
    case 4: renderLwStage4(story); break;
    case 5: renderLwStage5(story); break;
    case 6: renderLwStage6(story); break;
    case 7: renderLwStage7(story); break;
  }
}

async function advanceLwStage(storyId) {
  try {
    const res = await POST(`/api/lw/stories/${storyId}/advance`);
    if (res && res.error) {
      toast(res.error, 'error');
      return;
    }
    toast('Stage complete! Advancing...', 'success');
    openLwStory(storyId);
  } catch (e) {
    toast(e.message || 'Advance failed. Check requirements.', 'error');
  }
}

async function completeLwStory(storyId) {
  if (confirm("VICTORY APPROACHES: Finalize this draft? This will signal completion across the system.")) {
    try {
      await POST(`/api/lw/stories/${storyId}/complete`);
      toast('MAGNUM OPUS COMPLETE!', 'success');
      openLwStory(storyId);
    } catch (e) {
      toast('Completion failed', 'error');
    }
  }
}


function renderLwStage1(story) {
  const content = document.getElementById('lw-stage-content');
  const s1 = story.stage1 || {};
  
  content.innerHTML = `
    <div class="lw-stage-heading">
      <h2>Stage 1: Concept Note</h2>
      <p>The spark of the idea. Write it down. Locate your research.</p>
    </div>

    <div class="lw-info-box">
      <div class="lw-info-icon">💡</div>
      <div class="lw-info-text">
        Pro-tip: Check <strong>DEVONthink</strong> for any existing notes, research, or snippets related to this concept before you deep-dive.
      </div>
    </div>

    <div class="lw-field">
      <label class="lw-label">CONCEPT NOTE / CORE PREMISE</label>
      <textarea id="lw-s1-note" class="lw-concept-textarea" 
                placeholder="What is the heart of this story? Write it here..."
                oninput="updateLwWordCount('lw-s1-note', 'lw-s1-wc')"
                onblur="saveLwS1('${story.id}')">${esc(s1.concept_note || '')}</textarea>
      <div id="lw-s1-wc" class="lw-word-count">0 words</div>
    </div>

    <div class="lw-field">
      <label class="lw-label">DEVONthink LOCATION / RESEARCH PATH</label>
      <input type="text" id="lw-s1-dt" class="lw-input" 
             placeholder="e.g. x-devonthink-item://... or local path"
             value="${esc(s1.devonthink_path || '')}"
             onblur="saveLwS1('${story.id}')" />
    </div>

    <div class="lw-stage-actions">
      ${story.current_stage === 1 ? `
        <button class="btn-lw-complete" onclick="advanceLwStage('${story.id}')">COMPLETE STAGE 1</button>
      ` : `
        <button class="btn-lw-complete" disabled style="opacity:0.6; cursor:default;">✔ STAGE 1 COMPLETED</button>
      `}
    </div>
  `;
  updateLwWordCount('lw-s1-note', 'lw-s1-wc');
}

async function saveLwS1(storyId) {
  const payload = {
    stage1: {
      concept_note: document.getElementById('lw-s1-note').value,
      devonthink_path: document.getElementById('lw-s1-dt').value
    }
  };
  try {
    await PUT(`/api/lw/stories/${storyId}`, payload);
  } catch (e) { console.error('Auto-save failed'); }
}

function updateLwWordCount(textareaId, displayId) {
  const text = document.getElementById(textareaId)?.value || '';
  const count = text.trim() ? text.trim().split(/\s+/).length : 0;
  const el = document.getElementById(displayId);
  if (el) el.textContent = `${count} words`;
}

// ── Shared File Stage Renderer (Stages 2, 3, 4, 5) ───────────────────────────

function renderLwStage2(story) { renderLwFileStage(story, 2, "World Bible", "Define the rules, physics, and history of your world."); }
function renderLwStage3(story) { renderLwFileStage(story, 3, "Episode Grid", "Map out the emotional beats and structural milestones."); }

function renderLwFileStage(story, stageNum, title, desc) {
  const content = document.getElementById('lw-stage-content');
  const stageData = story['stage' + stageNum] || { cts_files: [], definitions_file: "" };
  
  const filesHtml = (stageData.cts_files || []).map(f => `
    <div class="lw-file-entry">
      <div class="lw-file-info">
        <div class="lw-file-label">${esc(f.name)}</div>
        <div class="lw-file-path">${esc(f.path)}</div>
      </div>
      <div class="lw-file-actions">
        <button class="btn-icon btn-icon-danger" onclick="removeLwFile('${story.id}', ${stageNum}, '${f.id}')">✕</button>
      </div>
    </div>
  `).join('');

  content.innerHTML = `
    <div class="lw-stage-heading">
      <h2>Stage ${stageNum}: ${title}</h2>
      <p>${desc}</p>
    </div>

    <div class="lw-file-section">
      <div class="lw-label">CREATIVE FILES (.cts)</div>
      <div class="lw-file-list">
        ${filesHtml || '<div class="lw-empty-files">No files linked. Click below to add your TreeSheets workspace.</div>'}
      </div>
      <button class="btn-secondary" onclick="addLwFileModal('${story.id}', ${stageNum})">+ Add .cts File</button>
    </div>

    ${stageNum <= 3 ? `
    <div class="lw-field">
      <label class="lw-label">DEFINITIONS FILE PATH (Optional)</label>
      <input type="text" id="lw-s${stageNum}-def" class="lw-input" 
             placeholder="Path to definitions TreeSheets..."
             value="${esc(stageData.definitions_file || '')}"
             onblur="saveLwDef('${story.id}', ${stageNum})" />
    </div>` : ''}

    <button class="lw-open-all-btn" onclick="openLwStageFiles('${story.id}', ${stageNum})">
      <span>🚀</span> OPEN ALL STAGE FILES
    </button>

    <div class="lw-stage-actions">
      ${story.current_stage === stageNum ? `
        <button class="btn-lw-complete" onclick="advanceLwStage('${story.id}')">COMPLETE STAGE ${stageNum}</button>
      ` : `
        <button class="btn-lw-complete" disabled style="opacity:0.6; cursor:default;">✔ STAGE ${stageNum} COMPLETED</button>
      `}
    </div>
  `;
}

// ── File Utility Handlers ────────────────────────────────────────────────────

function addLwFileModal(storyId, stageNum) {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">+ Add Creative File</div>
    <div class="form-group">
      <label class="form-label">Display Name</label>
      <input type="text" class="form-input" id="lw-new-file-name" placeholder="e.g. Main Character Bible" />
    </div>
    <div class="form-group">
      <label class="form-label">Absolute Local Path</label>
      <input type="text" class="form-input" id="lw-new-file-path" placeholder="/Users/name/writing/project/file.cts" />
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="saveLwFile('${storyId}', ${stageNum})">Link File</button>
    </div>
  `;
  showModal();
}

async function saveLwFile(storyId, stageNum) {
  const name = document.getElementById('lw-new-file-name').value.trim();
  const path = document.getElementById('lw-new-file-path').value.trim();
  if (!name || !path) return;

  try {
    const story = await GET(`/api/lw/stories/${storyId}`);
    const stage = story['stage' + stageNum] || {};
    const files = stage.cts_files || [];
    files.push({ id: crypto.randomUUID(), name, path });
    
    await PUT(`/api/lw/stories/${storyId}`, { ['stage' + stageNum]: { cts_files: files } });
    closeModal();
    openLwStory(storyId);
  } catch (e) { toast('Failed to link file', 'error'); }
}

async function removeLwFile(storyId, stageNum, fileId) {
  if (!confirm("Unlink this file?")) return;
  try {
    const story = await GET(`/api/lw/stories/${storyId}`);
    const stage = story['stage' + stageNum] || {};
    const files = (stage.cts_files || []).filter(f => f.id !== fileId);
    
    await PUT(`/api/lw/stories/${storyId}`, { ['stage' + stageNum]: { cts_files: files } });
    openLwStory(storyId);
  } catch (e) { toast('Failed to remove file', 'error'); }
}

async function saveLwDef(storyId, stageNum) {
  const val = document.getElementById(`lw-s${stageNum}-def`).value.trim();
  try {
    await PUT(`/api/lw/stories/${storyId}`, { ['stage' + stageNum]: { definitions_file: val } });
  } catch (e) {}
}

async function openLwStageFiles(storyId, stageNum) {
  try {
    await POST(`/api/lw/stories/${storyId}/stages/${stageNum}/open`);
    toast('Opening files in TreeSheets...', 'success');
  } catch (e) { toast('Local open failed. Check paths.', 'error'); }
}
function renderLwStage4(story) { renderLwFileStage(story, 4, "Chapter & Beat Cruxes", "Break down your episodes into chapters and specific emotional cruxes."); }
function renderLwStage5(story) { renderLwFileStage(story, 5, "Treatment + Descriptionary", "The full creative landscape. Every sensory detail linked."); }

function renderLwStage6(story) {
  const content = document.getElementById('lw-stage-content');
  const s6 = story.stage6 || {};
  
  content.innerHTML = `
    <div class="lw-stage-heading">
      <h2>Stage 6: Internalization</h2>
      <p>Memorize the story. Know it so well you don't need the notes.</p>
    </div>

    <div class="lw-field">
      <label class="lw-label">NARRATIVE SUMMARY (Full Core Storyboard)</label>
      <textarea id="lw-s6-summary" class="lw-concept-textarea" style="min-height:300px;"
                placeholder="Write the entire story from memory, beat by beat..."
                onblur="saveLwS6('${story.id}')">${esc(s6.narrative_summary || '')}</textarea>
      <div id="lw-s6-wc" class="lw-word-count">0 words</div>
    </div>

    <div class="lw-info-box">
      <div class="lw-info-icon">🧠</div>
      <div class="lw-info-text">
        Pro-tip: Read this summary aloud. If you stumble or get bored, the story isn't ready.
      </div>
    </div>

    <div class="lw-stage-actions">
      ${story.current_stage === 6 ? `
        <button class="btn-lw-complete" onclick="advanceLwStage('${story.id}')">COMPLETE STAGE 6</button>
      ` : `
        <button class="btn-lw-complete" disabled style="opacity:0.6; cursor:default;">✔ STAGE 6 COMPLETED</button>
      `}
    </div>
  `;
  updateLwWordCount('lw-s6-summary', 'lw-s6-wc');
}

async function saveLwS6(storyId) {
  const val = document.getElementById('lw-s6-summary').value;
  try {
    await PUT(`/api/lw/stories/${storyId}`, { stage6: { narrative_summary: val } });
  } catch (e) {}
}

function renderLwStage7(story) {
  const content = document.getElementById('lw-stage-content');
  
  content.innerHTML = `
    <div class="lw-stage-heading">
      <h2>Stage 7: Drafting in Flow</h2>
      <p>The final march. Use the Support Pack to stay in the zone.</p>
    </div>

    <div class="lw-export-section">
      <div class="lw-label">DRAFT SUPPORT PACK</div>
      <p style="font-size:13px; color:var(--muted); margin-bottom:16px;">
        Generates a consolidated file of your Concept, World Bible, Episode Grid, and Descriptions.
      </p>
      
      <div class="lw-export-options">
        <label class="lw-radio">
          <input type="radio" name="export-target" value="word" checked> <span>Word / Scrivener</span>
        </label>
        <label class="lw-radio">
          <input type="radio" name="export-target" value="markdown"> <span>Ulysses / Markdown</span>
        </label>
      </div>

      <button class="btn-primary" onclick="exportLwSupport('${story.id}')">🚀 EXPORT SUPPORT PACK</button>
    </div>

    <div class="lw-info-box" style="margin-top:32px;">
      <div class="lw-info-icon">✍️</div>
      <div class="lw-info-text">
        <strong>RECONSTRUCTION MODE:</strong> If you change something major during the draft, log it in your <strong>Reconstruction Session</strong> notes immediately.
      </div>
    </div>

    <div class="lw-stage-actions">
      <button class="btn-lw-victory" onclick="completeLwStory('${story.id}')">🏆 MARK DRAFT COMPLETE</button>
    </div>
  `;
}

async function exportLwSupport(storyId) {
  const target = document.querySelector('input[name="export-target"]:checked').value;
  try {
    await POST(`/api/lw/stories/${storyId}/stage7/export`, { target });
    toast('Support Pack exported to /exports', 'success');
  } catch (e) { toast('Export failed', 'error'); }
}


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
    if (state.lwCurrentStoryId) {
      // Re-open current story if we were inside one
      openLwStory(state.lwCurrentStoryId); 
    } else {
      renderLwPipeline();
    }
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

let _selectedForWebPublish = new Set();

function renderPublishingDashboard() {
  const container = document.getElementById('publishing-container');
  const pipeline = state.contentPipeline || [];

  const rows = pipeline.map(entry => {
    const rev  = entry.revision || 1;
    const wrev = entry.website_revision || 0;
    const wst  = entry.website_status || 'not_started';

    // Website cell — dedicated publish flow
    let websiteCell;
    if (wst === 'live' && wrev >= rev) {
      websiteCell = `
      <div class="platform-cell">
        <div class="platform-label">Website</div>
        <div class="platform-status live" style="color:var(--success,#4caf50);">v${wrev} ✓ Live</div>
      </div>`;
    } else if (wst === 'live' && wrev < rev) {
      websiteCell = `
      <div class="platform-cell">
        <div class="platform-label">Website</div>
        <div class="platform-status in_progress" style="color:var(--warning,#ff9800);">v${wrev} — needs update</div>
        <button class="btn-card" style="margin-top:4px;" id="pub-btn-${entry.id}"
          onclick="publishChapterToWebsite('${entry.id}', this)">Re-publish</button>
      </div>`;
    } else {
      websiteCell = `
      <div class="platform-cell">
        <div class="platform-label">Website</div>
        <div class="platform-status ${wst}">${wst.replace(/_/g,' ')}</div>
        <button class="btn-card" style="margin-top:4px;" id="pub-btn-${entry.id}"
          onclick="publishChapterToWebsite('${entry.id}', this)">Publish to Website</button>
      </div>`;
    }

    // Other platform cells (unchanged behaviour)
    const otherPlatforms = [
      { key: 'vip_group',  label: 'VIP Group',  status: entry.vip_group_status,  rev: entry.vip_group_revision  || 0 },
      { key: 'patreon',    label: 'Patreon',    status: entry.patreon_status,    rev: entry.patreon_revision    || 0 },
      { key: 'wa_channel', label: 'WA Channel', status: entry.wa_channel_status, rev: entry.wa_channel_revision || 0 },
    ];
    const otherCells = otherPlatforms.map(p => `
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

    const platformCells = websiteCell + otherCells;

    const patreonUrl = state.promoSettings?.cta_links?.patreon || '';
    const defaultMsg = [
      entry.assets?.tagline  || '',
      '',
      entry.assets?.excerpt  || '',
      '',
      patreonUrl ? `Read the full chapter at: ${patreonUrl}` : ''
    ].join('\n').trim();

    const waSection = `
      <div class="publishing-wa-section">
        <div class="publishing-wa-header" onclick="toggleWaSection('${entry.id}')">
          ▾ Send to WhatsApp
        </div>
        <div class="publishing-wa-body" id="wa-body-${entry.id}" style="display:none;">
          <textarea
            class="form-input publishing-wa-composer"
            id="wa-msg-${entry.id}"
            rows="6"
          >${esc(defaultMsg)}</textarea>
          <div class="publishing-wa-controls">
            <label style="font-size:12px;color:var(--muted);">
              <input type="checkbox" id="wa-sched-toggle-${entry.id}"
                onchange="toggleWaSchedule('${entry.id}')"> Schedule
            </label>
            <input type="datetime-local" class="form-input"
              id="wa-sched-${entry.id}"
              style="display:none;width:200px;font-size:12px;">
          </div>
          <div class="publishing-wa-buttons">
            <button class="btn-secondary" style="font-size:12px;"
              onclick="queueAndSendWa('${entry.id}', 'vip_group')">
              📲 Send to VIP Group
            </button>
            <button class="btn-secondary" style="font-size:12px;"
              onclick="queueAndSendWa('${entry.id}', 'channel')">
              📢 Send to Channel
            </button>
          </div>
        </div>
      </div>
    `;

    const isSelected = _selectedForWebPublish.has(entry.id);
    return `
      <div class="pipeline-row">
        <div class="pipeline-module">
          <label style="display:flex;align-items:flex-start;gap:8px;cursor:pointer;">
            <input type="checkbox" value="${entry.id}"
              ${isSelected ? 'checked' : ''}
              onchange="toggleWebPublishSelection('${entry.id}', this.checked)"
              onclick="event.stopPropagation()"
              style="margin-top:3px;flex-shrink:0;">
            <span>
              <strong>${esc(entry.book)} · Module ${entry.chapter_number}: ${esc(entry.chapter)}</strong>
              <div class="module-title">${esc(entry.title || '')}</div>
            </span>
          </label>
        </div>
        <div class="pipeline-platforms">
          ${platformCells}
        </div>
        ${waSection}
      </div>
    `;
  }).join('');

  const selCount = _selectedForWebPublish.size;
  container.innerHTML = `
    <div class="publishing-header">
      <h2>Publishing Dashboard</h2>
      <p>Revision tracking and pipeline management.</p>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <button onclick="openAddChapterModal()" class="btn-capture">+ Add Module</button>
        ${selCount > 0 ? `<button class="btn-secondary" onclick="publishSelectedToWebsite()">
          Publish Selected to Website (${selCount})</button>` : ''}
        <button class="btn-secondary" onclick="deployWebsite()" style="margin-left:auto;">Deploy Website</button>
      </div>
    </div>
    <div style="font-size:12px;color:var(--muted);margin-bottom:8px;">
      Tip: After publishing multiple chapters, re-publish earlier chapters to update their "Next Chapter" links.
    </div>
    <div class="publishing-pipeline">
      ${rows}
    </div>
  `;
}

function toggleWebPublishSelection(id, checked) {
  if (checked) _selectedForWebPublish.add(id);
  else         _selectedForWebPublish.delete(id);
  renderPublishingDashboard();
}

async function publishChapterToWebsite(id, btn) {
  const entry = state.contentPipeline.find(x => x.id === id);
  if (!entry) return;
  if (!entry.assets?.prose?.trim()) {
    toast('Add chapter text first (Edit Assets → Chapter Text)', 'error');
    return;
  }
  const origText  = btn.textContent;
  btn.disabled    = true;
  btn.textContent = '…';
  try {
    const res = await POST('/api/website/publish', { entry_id: id });
    if (res.ok) {
      const i = state.contentPipeline.findIndex(x => x.id === id);
      if (i >= 0) {
        state.contentPipeline[i].website_status   = 'live';
        state.contentPipeline[i].website_revision = state.contentPipeline[i].revision || 1;
      }
      toast('Chapter published to website ✓', 'success');
      renderPublishingDashboard();
    } else {
      toast(res.error || 'Publish failed', 'error');
      btn.disabled    = false;
      btn.textContent = origText;
    }
  } catch (err) {
    toast('Publish failed', 'error');
    btn.disabled    = false;
    btn.textContent = origText;
  }
}

async function publishSelectedToWebsite() {
  const ids = [..._selectedForWebPublish];
  if (!ids.length) return;
  const missingProse = ids.filter(id => {
    const e = state.contentPipeline.find(x => x.id === id);
    return !e?.assets?.prose?.trim();
  });
  if (missingProse.length) {
    const names = missingProse.map(id => {
      const e = state.contentPipeline.find(x => x.id === id);
      return e ? e.chapter : id;
    });
    toast(`Missing prose for: ${names.join(', ')}. Add chapter text first.`, 'error');
    return;
  }
  try {
    const res     = await POST('/api/website/publish-batch', { entry_ids: ids });
    const results = res.results || [];
    const okCount = results.filter(r => r.ok).length;
    const failCount = results.filter(r => !r.ok).length;
    results.forEach(r => {
      if (r.ok) {
        const i = state.contentPipeline.findIndex(x => x.id === r.entry_id);
        if (i >= 0) {
          state.contentPipeline[i].website_status   = 'live';
          state.contentPipeline[i].website_revision = state.contentPipeline[i].revision || 1;
        }
      }
    });
    _selectedForWebPublish.clear();
    if (failCount === 0) {
      toast(`Published ${okCount} chapter${okCount > 1 ? 's' : ''} to website ✓`, 'success');
    } else {
      toast(`Published ${okCount}/${ids.length} chapters. ${failCount} failed — check each row for details.`, 'error');
    }
    renderPublishingDashboard();
  } catch (err) {
    toast('Batch publish failed', 'error');
  }
}

async function deployWebsite() {
  try {
    const res = await POST('/api/website/deploy', {});
    if (res.ok) toast('Website deploy triggered ✓', 'success');
    else        toast(res.error || 'Deploy failed', 'error');
  } catch (err) {
    toast('Deploy failed', 'error');
  }
}

async function incrementRevision(entryId, field) {
  await POST(`/api/content-pipeline/${entryId}/increment-revision`, { field, delta: 1 });
  await loadDashboard();
}

async function decrementRevision(entryId, field) {
  await POST(`/api/content-pipeline/${entryId}/increment-revision`, { field, delta: -1 });
  await loadDashboard();
}

function toggleWaSection(id) {
  const el = document.getElementById(`wa-body-${id}`);
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

function toggleWaSchedule(id) {
  const toggle = document.getElementById(`wa-sched-toggle-${id}`);
  const input  = document.getElementById(`wa-sched-${id}`);
  input.style.display = toggle.checked ? 'block' : 'none';
}

async function queueAndSendWa(moduleId, recipient) {
  const content = document.getElementById(`wa-msg-${moduleId}`).value.trim();
  const schedToggle = document.getElementById(`wa-sched-toggle-${moduleId}`);
  const schedInput  = document.getElementById(`wa-sched-${moduleId}`);
  
  let scheduled_at = null;
  if (schedToggle.checked) {
    if (!schedInput.value) return toast('Please select a schedule time', 'error');
    scheduled_at = new Date(schedInput.value).toISOString();
  }

  try {
    const res = await POST(`/api/publishing/modules/${moduleId}/queue_wa`, {
      recipient, content, scheduled_at
    });
    
    if (scheduled_at) {
      toast(`Message scheduled for ${new Date(scheduled_at).toLocaleString()}`, 'success');
      toggleWaSection(moduleId); // Collapse
    } else {
      // Immediate send
      const phone = getWaRecipientPhone(recipient);
      if (!phone) {
        toast(`Error: No phone number configured for ${recipient}. Check Promo Settings.`, 'error');
        return;
      }
      sendViaExtension(phone, content, res.message_id);
    }
  } catch (e) {
    toast(`Failed to queue message: ${e.message}`, 'error');
  }
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

  const BOOK_LABELS = {};
  (state.promoBooks || []).forEach(b => { if (b.id) BOOK_LABELS[b.id] = b.title; });

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
          <td colspan="5">${esc(BOOK_LABELS[book] || book)}<span class="pipeline-book-count">${groupMap[book].length} modules</span></td>
        </tr>
        ${groupMap[book].map(renderRow).join('')}`).join('')
    : state.contentPipeline.map(renderRow).join('');

  panel.innerHTML = `
    <div class="sidebar-section">
      <div class="sidebar-title">Content Pipeline</div>
      <table class="pipeline-table">
        <thead><tr><th>Module</th><th>VIP Group</th><th>Patreon</th><th>Website</th><th>WA Channel</th></tr></thead>
        <tbody>${tableBody}</tbody>
      </table>
      <button class="btn-pipeline-add" onclick="openAddChapterModal()">+ Add module</button>
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
    <hr style="border:none;border-top:1px solid var(--border);margin:18px 0 14px;">
    <div class="sidebar-title" style="margin-bottom:14px;">Website Publishing</div>
    <div class="form-group"><label class="form-label">Chapter Text</label>
      <textarea class="form-textarea" id="edit-ch-prose" rows="16"
        style="font-family:monospace;min-height:300px;font-size:13px;"
        placeholder="Paste the chapter text here. Separate paragraphs with a blank line.">${esc(assets.prose||'')}</textarea></div>
    <div class="form-group"><label class="form-label">Author's Note <span style="color:var(--muted);font-size:11px;">(optional)</span></label>
      <textarea class="form-textarea" id="edit-ch-author-note" rows="3"
        style="min-height:80px;"
        placeholder="A brief note shown to readers before the chapter text. Leave blank to omit.">${esc(assets.author_note||'')}</textarea></div>
    <div class="form-group"><label class="form-label">Header Image</label>
      <div style="font-size:12px;color:var(--muted);margin-bottom:6px;" id="edit-ch-image-current">
        ${assets.header_image_path ? 'Current: ' + esc(assets.header_image_path.split('/').pop()) : 'No image'}
      </div>
      <input type="file" id="edit-ch-header-image" accept="image/jpeg,image/png"
        style="font-size:13px;"
        onchange="uploadChapterHeaderImage('${e.id}', this)">
      <div id="edit-ch-image-status" style="font-size:12px;color:var(--muted);margin-top:4px;"></div>
    </div>
    <div class="modal-actions">
      <button class="btn-danger"    onclick="deleteChapter('${e.id}')">Delete chapter</button>
      <button class="btn-secondary" onclick="renderPipeline();closeModal();">Cancel</button>
      <button class="btn-primary"   onclick="saveChapterAssets('${e.id}')">Save</button>
    </div>`;
  showModal();
}

async function saveChapterAssets(id) {
  const entry = state.contentPipeline.find(x => x.id === id);
  if (!entry) return;
  const existingAssets = entry.assets || {};
  try {
    const updated = await PUT(`/api/content-pipeline/${id}`, {
      assets: {
        ...existingAssets,
        tagline:      document.getElementById('edit-ch-tagline').value.trim()      || null,
        blurb:        document.getElementById('edit-ch-blurb').value.trim()        || null,
        synopsis:     document.getElementById('edit-ch-synopsis').value.trim()     || null,
        excerpt:      document.getElementById('edit-ch-excerpt').value.trim()      || null,
        image_prompt: document.getElementById('edit-ch-image-prompt').value.trim() || null,
        prose:        document.getElementById('edit-ch-prose').value.trim()        || '',
        author_note:  document.getElementById('edit-ch-author-note').value.trim()  || '',
      }
    });
    const i = state.contentPipeline.findIndex(x => x.id === id);
    if (i >= 0) state.contentPipeline[i] = updated;
    closeModal(); renderPipeline();
    toast('Assets updated', 'success');
  } catch (e) { toast('Could not save', 'error'); }
}

async function uploadChapterHeaderImage(id, input) {
  const file = input.files[0];
  if (!file) return;
  const statusEl  = document.getElementById('edit-ch-image-status');
  const currentEl = document.getElementById('edit-ch-image-current');
  statusEl.textContent = 'Uploading…';
  const formData = new FormData();
  formData.append('image', file);
  try {
    const res  = await fetch(`/api/pipeline/${id}/upload-image`, { method: 'POST', body: formData });
    const data = await res.json();
    if (data.ok) {
      statusEl.textContent  = 'Uploaded ✓';
      currentEl.textContent = 'Current: ' + data.filename;
      const i = state.contentPipeline.findIndex(x => x.id === id);
      if (i >= 0) {
        state.contentPipeline[i].assets = state.contentPipeline[i].assets || {};
        state.contentPipeline[i].assets.header_image_path = data.path;
      }
    } else {
      statusEl.textContent = 'Upload failed: ' + (data.error || 'Unknown error');
    }
  } catch (err) {
    statusEl.textContent = 'Upload failed';
  }
}

async function deleteChapter(id) {
  const e = state.contentPipeline.find(x => x.id === id);
  if (!e || !confirm(`Delete "${e.chapter}"?`)) return;
  try {
    await DEL(`/api/content-pipeline/${id}`);
    state.contentPipeline = state.contentPipeline.filter(x => x.id !== id);
    closeModal(); renderPipeline();
    toast('Module deleted', 'success');
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
  const workOptions = (state.promoBooks || [])
    .map(b => `<option value="${esc(b.id)}">${esc(b.title)}</option>`)
    .join('');

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Add Module</div>
    <div class="form-group"><label class="form-label">Work</label>
      <select class="form-select" id="ch-work">
        <option value="">— None / Standalone —</option>
        ${workOptions}
      </select></div>
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
      book: document.getElementById('ch-work').value || null,
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
  } catch (e) { toast('Could not add module', 'error'); }
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
      <div class="sidebar-title" style="margin:20px 0 14px;">Website Publishing</div>
      <div class="form-group"><label class="form-label">Website Directory</label>
        <input class="form-input" id="set-website-dir" type="text"
          value="${esc((s.website||{}).website_dir||'')}"
          placeholder="/Users/fidelnamisi/28 Titles/1. WIP/realmsandroads.com"/>
      </div>
      <div class="form-group">
        <label class="check-row">
          <input type="checkbox" id="set-website-auto-deploy" ${(s.website||{}).auto_deploy ? 'checked' : ''}/>
          Auto-deploy after publishing
        </label>
      </div>
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:14px;">
        <button class="btn-secondary" onclick="testWebsiteConnection()">Test Connection</button>
        <span id="website-status-indicator" style="font-size:12px;"></span>
      </div>
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
  const ws = state.settings.website || {};
  try {
    state.settings = await PUT('/api/settings', {
      briefing_time: document.getElementById('set-briefing').value,
      window_end:    document.getElementById('set-wend').value,
      lead_measure_targets: targets, plugins_enabled: pe,
      phase_templates: phaseTemplates,
      asset_prompts: state.settings.asset_prompts || [],
      website: {
        ...ws,
        website_dir:  (document.getElementById('set-website-dir')?.value || '').trim(),
        auto_deploy:  document.getElementById('set-website-auto-deploy')?.checked || false,
      },
    });
    closeModal(); renderAll(); toast('Settings saved', 'success');
  } catch (e) { toast('Could not save settings', 'error'); }
}

async function testWebsiteConnection() {
  const indicator = document.getElementById('website-status-indicator');
  if (indicator) indicator.textContent = 'Checking…';
  try {
    const res = await GET('/api/website/status');
    if (indicator) {
      indicator.textContent = res.ok ? '✓ Connected' : '✗ ' + (res.error || 'Not connected');
      indicator.style.color = res.ok ? 'var(--success,#4caf50)' : 'var(--danger,#f44336)';
    }
  } catch (err) {
    if (indicator) { indicator.textContent = '✗ Request failed'; indicator.style.color = 'var(--danger,#f44336)'; }
  }
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
      <div class="help-heading">The Three Modes</div>
      <p>Indaba is designed to isolate the three phases of production to reduce cognitive load:</p>
      <ul class="help-list">
        <li><strong>EXECUTE</strong> — The Operational Brain. Focuses on "What should I do now?" Next actions, blockers, pipeline health, and Sales Pipeline follow-ups.</li>
        <li><strong>CREATE</strong> — The Creative Engine. Focuses on "What am I writing?" Living Writer workflow, 7-stage story development, and drafting.</li>
        <li><strong>MANAGE</strong> — The Inspection Layer. Focuses on "What exists?" All tabs for inventory, entities, contacts, deals, outbox, WA posts, serializer, messages, and settings.</li>
      </ul>
    </div>

    <div class="help-section">
      <div class="help-heading">Entity Model</div>
      <p>Entities are the generalized unit for anything monetizable or distributable:</p>
      <ul class="help-list">
        <li><strong>chapter</strong> — A piece of long-form content from your pipeline</li>
        <li><strong>membership</strong> — A Patreon tier or subscription offering</li>
        <li><strong>event</strong> — A live event, workshop, or appearance</li>
        <li><strong>fundraiser</strong> — A campaign or drive with a goal</li>
      </ul>
      <p>Entities are managed in <strong>Manage → Entities</strong>. Assets and Deals can be linked to entities.</p>
    </div>

    <div class="help-section">
      <div class="help-heading">Full Flow: Entity → Revenue</div>
      <ol class="help-list">
        <li><strong>Entity</strong> — Create or auto-migrate from content pipeline</li>
        <li><strong>Assets</strong> — Attach production assets (audio, taglines, images) to the entity</li>
        <li><strong>Distribution</strong> — Serialize and distribute via Book Serializer or Broadcast Posts</li>
        <li><strong>Contact</strong> — Identify who needs to hear about it (Contacts tab)</li>
        <li><strong>Deal</strong> — Create a deal from a contact interaction (Deals tab or + Deal button in Outbox)</li>
        <li><strong>Pipeline</strong> — Move deal through: Lead → Qualified → Proposal → Negotiation</li>
        <li><strong>Close</strong> — Mark Won or Lost. Won deals count towards monthly totals in Execute mode.</li>
      </ol>
    </div>

    <div class="help-section">
      <div class="help-heading">Manage Mode Tabs</div>
      <ul class="help-list">
        <li><strong>Inventory</strong> — Full book/chapter/asset registry with role-based taxonomy</li>
        <li><strong>Entities</strong> — Create and manage all entities (chapter, membership, event, fundraiser)</li>
        <li><strong>Contacts</strong> — CRM contact list with tags and communication history</li>
        <li><strong>Deals</strong> — Kanban pipeline for all deals (was "Leads")</li>
        <li><strong>Outbox</strong> — Message queue with send controls and "+ Deal" conversion</li>
        <li><strong>Broadcast Posts</strong> — Proverb-based WhatsApp channel post queue</li>
        <li><strong>Serializer</strong> — AI book serializer for WhatsApp channel distribution</li>
        <li><strong>Messages</strong> — AI message maker for bulk or targeted outreach</li>
        <li><strong>Settings</strong> — AI provider config, WA branding, recipient numbers</li>
      </ul>
    </div>

    <div class="help-section">
      <div class="help-heading">Keyboard Shortcuts</div>
      <ul class="help-list">
        <li><strong>E</strong> — Not implemented (use top nav)</li>
        <li><strong>?</strong> — This help panel (click the ? button)</li>
        <li><strong>Esc</strong> — Close any open modal</li>
      </ul>
    </div>

    <div class="modal-actions">
      <button class="btn-secondary" onclick="openConstantsModal()">Edit Constants</button>
      <button class="btn-primary" onclick="closeModal()">Enter System</button>
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
const _log = [];   // in-memory event log — persists for the session

function toast(msg, type = '') {
  if (!_tc) { _tc = document.createElement('div'); _tc.id = 'toast-container'; document.body.appendChild(_tc); }
  const el = Object.assign(document.createElement('div'), { className: `toast ${type}`, textContent: msg });
  _tc.appendChild(el);
  setTimeout(() => el.classList.add('fade'), 2200);
  setTimeout(() => el.remove(), 2700);

  // Record to log
  const entry = { ts: new Date().toISOString(), type: type || 'info', msg };
  _log.unshift(entry);           // newest first
  if (_log.length > 200) _log.pop();   // cap history
  try { localStorage.setItem('indaba_log', JSON.stringify(_log.slice(0, 200))); } catch(e) {}
}

function _copyLog() {
  const text = _log.map(e =>
    `[${new Date(e.ts).toLocaleTimeString()}] [${e.type.toUpperCase()}] ${e.msg}`
  ).join('\n');
  navigator.clipboard.writeText(text).then(() => toast('Log copied to clipboard', 'success'));
}

function _clearLog() {
  _log.length = 0;
  try { localStorage.removeItem('indaba_log'); } catch(e) {}
  openLogModal();
}

function openLogModal() {
  const rows = _log.length === 0
    ? '<p style="color:var(--muted);padding:20px;text-align:center;">No events yet this session.</p>'
    : _log.map(e => {
        const colour = e.type === 'error'   ? 'var(--p1)'
                     : e.type === 'success' ? 'var(--p3)'
                     : 'var(--muted)';
        const ts = new Date(e.ts).toLocaleTimeString();
        return `<div class="log-entry" style="display:flex;gap:8px;align-items:baseline;padding:5px 0;border-bottom:1px solid var(--border);">
          <span style="font-size:10px;color:var(--muted);white-space:nowrap;">${esc(ts)}</span>
          <span style="font-size:11px;font-weight:600;text-transform:uppercase;color:${colour};min-width:46px;">${esc(e.type)}</span>
          <span style="font-size:12px;color:var(--text);word-break:break-word;">${esc(e.msg)}</span>
        </div>`;
      }).join('');

  document.getElementById('modal-content').innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="margin:0;">Event Log</h2>
      <div style="display:flex;gap:8px;">
        <button class="btn-secondary" onclick="_copyLog()">Copy All</button>
        <button class="btn-secondary" onclick="_clearLog()">Clear</button>
      </div>
    </div>
    <p style="font-size:11px;color:var(--muted);margin-bottom:12px;">${_log.length} event(s) — newest first. Cleared on page reload.</p>
    <div style="max-height:420px;overflow-y:auto;font-family:monospace;">${rows}</div>`;
  document.getElementById('modal-overlay').classList.remove('hidden');
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
    renderBroadcastPosts();
  } catch (e) { toast("Could not load proverbs", "error"); }
}

async function loadBroadcastPostQueue() {
  try {
    const data = await GET('/api/promo/proverbs');
    state.promoProverbs = data.proverbs || [];
    // Queue = all posts that have been generated
    state.broadcastPostQueue = state.promoProverbs.filter(
      p => p.queue_status && p.queue_status !== null
    );
    renderBroadcastPosts();
  } catch(e) {
    toast('Could not load queue', 'error');
  }
}

async function loadPromoBooks() {
  try {
    // Ensure promo settings are loaded so word-count defaults in the UI are accurate
    if (!state.promoSettings || !state.promoSettings.ai_providers) {
      try {
        const s = await GET('/api/promo/settings');
        state.promoSettings = s || {};
      } catch (_) {}
    }
    const data = await GET('/api/works');
    state.promoBooks = data.works || [];
    renderPromoBookSerializer();
  } catch (e) { toast("Could not load works", "error"); }
}

async function loadPromoWorks() {
  return loadPromoBooks();
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

// ── COMMAND CENTER ────────────────────────────────────────────────────────────

async function loadCommandCenter() {
  try {
    const data = await GET('/api/command-center');
    state.commandCenterData = data;
    renderCommandCenter();
  } catch(e) {
    console.error(e);
    toast('Failed to load inventory data', 'error');
  }
}

function renderCommandCenter() {
  const container = document.getElementById('promo-view-command-center');
  if (!container) return;

  // Scrivenings mode takes over the panel
  if (state.scrivengsWorkId) {
    renderScrivenings(container);
    return;
  }

  const data = state.commandCenterData || [];
  
  if (data.length === 0) {
    container.innerHTML = `<div class="empty-state">No works or modules found to track. <button class="btn-primary" style="margin-top:12px;" onclick="openNewBookModal()">+ Add Work</button></div>`;
    return;
  }

  const html = `
    <div class="cc-main">
      <div class="cc-header-row">
        <div>
          <h1 class="cc-title">Inventory & Registry</h1>
          <p class="cc-subtitle">Management Mode · Role-Based Taxonomy</p>
        </div>
        <div class="cc-global-actions">
           <button class="btn-primary" onclick="openNewBookModal()">+ Add Work</button>
           <button class="btn-secondary" onclick="toggleAllCC(true)">Expand All</button>
           <button class="btn-secondary" onclick="toggleAllCC(false)">Collapse All</button>
        </div>
      </div>
        <div class="cc-list">
          ${data.map(work => `
            <div class="cc-book-card" id="cc-work-${work.work_id}">
              <div class="cc-book-header">
                <div class="cc-book-info" onclick="toggleCCElement('cc-work-body-${work.work_id}')" style="display:flex; align-items:center; gap:10px; flex:1; cursor:pointer;">
                  <span class="cc-toggle-icon">▶</span>
                  <span class="cc-book-title">${esc(work.work_title)}</span>
                  <span class="cc-book-meta">${work.modules.length} Modules</span>
                </div>
                <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                  <button class="btn-secondary" onclick="openScrivenings('${work.work_id}')" style="font-size:11px; padding:4px 10px;" title="Read &amp; edit all chapters as one continuous document">Scrivenings</button>
                  <button class="btn-secondary" onclick="openImportChaptersModal('${work.work_id}', 'modules')" style="font-size:11px; padding:4px 10px;">↑ Import Chapters</button>
                  <button class="btn-secondary" onclick="openBulkGenerateModal('${work.work_id}', 'modules')" style="font-size:11px; padding:4px 10px;">⚡ Assets</button>
                  <button class="btn-secondary" onclick="openAddModuleModal('${work.work_id}')" style="font-size:11px; padding:4px 10px;">+ Add Module</button>
                  <button class="btn-icon-danger" onclick="deleteWorkFromManage('${work.work_id}')" title="Delete Work and all Assets" style="background:none; border:none; cursor:pointer; font-size:16px;">🗑️</button>
                </div>
              </div>
              <div class="cc-book-body" id="cc-work-body-${work.work_id}" style="display:none;">
                ${work.modules.map(mod => `
                  <div class="cc-module-row">
                    <div class="cc-module-header">
                      <div class="cc-module-info" onclick="toggleCCElement('cc-module-assets-${mod.module_id}')" style="display:flex; align-items:center; gap:10px; flex:1; cursor:pointer;">
                        <span class="cc-toggle-icon">▶</span>
                        <span class="cc-module-title">${esc(mod.module_title)}</span>
                        <span class="cc-module-status ${mod.status}">${mod.status}</span>
                      </div>
                      <button class="btn-text" onclick="openSerializerModuleEdit('${mod.module_id}')" style="color:var(--accent); font-size:12px; cursor:pointer; background:none; border:none; padding:4px 8px;">Edit Module</button>
                    </div>
                    <div class="cc-module-assets" id="cc-module-assets-${mod.module_id}" style="display:none;">

                      <div class="cc-section-label" style="display:flex; justify-content:space-between; align-items:center;">
                        <span>Essential Pipeline</span>
                        <button class="btn-add-mini" onclick="addAssetManually('${mod.module_id}', '${work.work_id}', 'essential')">+ Add</button>
                      </div>
                      <div class="cc-asset-grid">
                        ${mod.essential.map(asset => renderAssetPill(asset, mod.module_id)).join('')}
                      </div>

                      <div class="cc-section-label" style="margin-top:16px; display:flex; justify-content:space-between; align-items:center;">
                        <span>Promotional Enhancements</span>
                        <button class="btn-add-mini" onclick="addAssetManually('${mod.module_id}', '${work.work_id}', 'promotional')">+ Add</button>
                      </div>
                      <div class="cc-asset-grid">
                        ${mod.promotional.map(asset => renderAssetPill(asset, mod.module_id)).join('')}
                      </div>

                    </div>
                  </div>
                `).join('')}
              </div>
            </div>
          `).join('')}
        </div>
    </div>
  `;

  container.innerHTML = html;
}

async function openSerializerModuleEdit(moduleId) {
  try {
    const res = await fetch(`/api/modules/${moduleId}`);
    if (!res.ok) { toast('Module not found', 'error'); return; }
    const mod = await res.json();

    // Chapter Prose = Content asset content (single source of truth), fall back to module.prose
    const contentAsset = (mod.assets || []).find(a => a.type === 'content')
      || (mod.assets || []).find(a => a.id === `asset_mod_${moduleId}`);
    const prose          = contentAsset?.content || mod.prose || '';
    const contentAssetId = contentAsset?.id || `asset_mod_${moduleId}`;

    document.getElementById('modal-content').innerHTML = `
      <div class="modal-title">Edit Module</div>
      <div class="modal-subtitle">ID: ${mod.id || moduleId}</div>

      <div class="form-group" style="margin-top:20px;">
        <label class="form-label">Title</label>
        <input type="text" id="edit-module-title" class="form-input" value="${esc(mod.title || mod.module_title || '')}">
      </div>

      <div class="form-group">
        <label class="form-label">Status</label>
        <select id="edit-module-status" class="form-input">
          <option value="draft"   ${mod.status === 'draft'   ? 'selected' : ''}>Draft</option>
          <option value="review"  ${mod.status === 'review'  ? 'selected' : ''}>Review</option>
          <option value="final"   ${mod.status === 'final'   ? 'selected' : ''}>Final</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label">Chapter Prose</label>
        <textarea id="edit-module-prose" class="form-textarea" style="min-height:250px;">${esc(prose)}</textarea>
      </div>

      <div class="modal-actions" style="display:flex; justify-content:space-between; margin-top:24px;">
        <button class="btn-secondary" onclick="deleteModuleFromManage('${moduleId}')" style="color:#ef4444; border-color:rgba(239, 68, 68, 0.3);">Delete Module</button>
        <div style="display:flex; gap:12px;">
          <button class="btn-secondary" onclick="closeModal()">Cancel</button>
          <button class="btn-primary" onclick="saveModule('${moduleId}', '${contentAssetId}')">Save Changes</button>
        </div>
      </div>
    `;
    showModal();
  } catch (e) { console.error(e); toast('Error loading module', 'error'); }
}

// Backwards-compat alias (serializer module edit)
async function openChapterDetail(chapterId) { return openSerializerModuleEdit(chapterId); }

async function saveModule(moduleId, contentAssetId) {
  const title  = document.getElementById('edit-module-title').value;
  const status = document.getElementById('edit-module-status').value;
  const prose  = document.getElementById('edit-module-prose').value;
  const assetId = contentAssetId || `asset_mod_${moduleId}`;

  try {
    // Save title + status to the module record
    const modRes = await fetch(`/api/modules/${moduleId}`, {
      method:  'PUT',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ title, status }),
    });
    if (!modRes.ok) { toast('Error saving module', 'error'); return; }

    // Find work_id from state (already loaded in command center)
    let workId = '';
    (state.commandCenterData || []).forEach(w => {
      (w.modules || []).forEach(m => { if (m.module_id === moduleId) workId = w.work_id; });
    });

    // Save prose to the Content asset (upsert — single source of truth)
    await fetch('/api/assets', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        id:         assetId,
        type:       'content',
        title:      'Chapter Prose',
        work_id:    workId,
        module_id:  moduleId,
        content:    prose,
        production: prose.trim() ? 'done' : 'not_started',
      }),
    });

    toast('Module saved');
    closeModal();
    loadCommandCenter();
  } catch (e) { toast('Network error', 'error'); }
}

// Backwards-compat alias
async function saveChapter(chapterId) { return saveModule(chapterId); }

async function deleteModuleFromManage(moduleId) {
  if (!confirm('Are you sure? Removing this module will also delete its assets.')) return;
  try {
    const res = await fetch(`/api/modules/${moduleId}`, { method: 'DELETE' });
    if (res.ok) {
      toast('Module deleted');
      closeModal();
      loadCommandCenter();
    } else { toast('Error deleting module', 'error'); }
  } catch (e) { toast('Network error', 'error'); }
}

// Backwards-compat alias
async function deleteChapterFromManage(id) { return deleteModuleFromManage(id); }

function openAddModuleModal(workId) {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Add Module</div>
    <div class="form-group" style="margin-top:16px;">
      <label class="form-label">Module Title *</label>
      <input type="text" id="new-mod-title" class="form-input" placeholder="e.g. Chapter 4: The Return"/>
    </div>
    <div class="form-group">
      <label class="form-label">Status</label>
      <select id="new-mod-status" class="form-input">
        <option value="draft">Draft</option>
        <option value="review">Review</option>
        <option value="final">Final</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Prose (optional)</label>
      <textarea id="new-mod-prose" class="form-textarea" style="min-height:150px;" placeholder="Paste source content here…"></textarea>
    </div>
    <div class="modal-actions" style="margin-top:24px;">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="submitAddModule('${workId}')">Add Module</button>
    </div>
  `;
  showModal();
}

async function submitAddModule(workId) {
  const title = document.getElementById('new-mod-title').value.trim();
  if (!title) { toast('Title required', 'error'); return; }
  try {
    const res = await fetch('/api/modules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        work_id: workId,
        status:  document.getElementById('new-mod-status').value,
        prose:   document.getElementById('new-mod-prose').value.trim()
      })
    });
    if (!res.ok) { toast('Could not add module', 'error'); return; }
    toast('Module added', 'success');
    closeModal();
    loadCommandCenter();
  } catch (e) { toast('Could not add module', 'error'); }
}

async function deleteWorkFromManage(workId) {
  if (!confirm('EXTREME WARNING: This will delete the work, all its modules, and all associated assets. Continue?')) return;
  try {
    const res = await fetch(`/api/works/${workId}`, { method: 'DELETE' });
    if (res.ok) {
      toast('Work and all cascading data removed');
      loadCommandCenter();
    } else { toast('Error deleting work', 'error'); }
  } catch (e) { toast('Network error', 'error'); }
}

// Backwards-compat alias
async function deleteBookFromManage(id) { return deleteWorkFromManage(id); }

function _assetTypeLabel(type) {
  if (type === 'content') return 'Chapter Prose';
  return type.replace(/_/g, ' ');
}

function renderAssetPill(asset, chapterId) {
  const isMulti = asset.quantity === 'multiple';
  const label = isMulti ? `${_assetTypeLabel(asset.type)} (${asset.count})` : _assetTypeLabel(asset.type);
  const cssClass = asset.exists ? 'exists' : 'missing';
  
  // Serialize asset for click handler using encodeURIComponent to safely handle apostrophes and special chars
  const assetData = encodeURIComponent(JSON.stringify(asset));

  return `
    <div class="cc-asset-pill ${cssClass} ${isMulti ? 'multi' : ''}"
         onclick="handleAssetAction(decodeURIComponent('${assetData}'), '${chapterId}')">
      <div class="cc-asset-type">
        ${label}
      </div>
      <div class="cc-asset-status-icon">${asset.exists ? (isMulti ? '📂' : '✅') : '❌'}</div>
    </div>
  `;
}

function handleAssetAction(assetJson, moduleId) {
  const asset = JSON.parse(assetJson);
  if (asset.quantity === 'multiple' && asset.exists) {
    openMultiAssetModal(asset, moduleId);
  } else if (asset.exists) {
    inspectAsset(asset.items[0]);
  } else {
    // Find work_id from command center state
    let workId = null;
    (state.commandCenterData || []).forEach(w => {
      (w.modules || []).forEach(mod => {
        if (mod.module_id === moduleId) workId = w.work_id;
      });
    });
    addAssetManually(moduleId, workId || '', asset.role || 'promotional', asset.type);
  }
}

function openMultiAssetModal(asset, moduleId) {
  const label = _assetTypeLabel(asset.type).toUpperCase();
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">In-Registry: ${label}</div>
    <div class="modal-subtitle">Quantity: Multiple · Count: ${asset.count}</div>
    
    <div class="cc-multi-list" style="margin-top:20px; max-height:400px; overflow-y:auto; padding-right:8px;">
      ${asset.items.map((item, idx) => `
        <div class="cc-multi-item" onclick="inspectAsset(${JSON.stringify(item).replace(/"/g, '&quot;')})">
          <div class="cc-multi-item-head">
            <strong>Instance #${idx+1}</strong>
            <span class="cc-ind-dot ${item.production}"></span>
          </div>
          <div class="cc-multi-item-meta">
            ID: ...${item.asset_id.slice(-8)} · Updated: ${new Date(item.updated_at).toLocaleDateString()}
          </div>
        </div>
      `).join('')}
    </div>
    
    <div class="modal-actions" style="display:flex; justify-content:space-between; align-items:center; margin-top:24px;">
      <button class="btn-secondary" onclick="addAssetManually('${moduleId}', '${asset.items[0].work_id || asset.items[0].book_id}', '${asset.role}', '${asset.type}')" style="background:rgba(139, 92, 246, 0.1); color:#a78bfa; border-color:rgba(139, 92, 246, 0.3);">+ Add New ${_assetTypeLabel(asset.type).toUpperCase()}</button>
      <button class="btn-primary" onclick="closeModal()">Close</button>
    </div>
  `;
  showModal();
}

async function inspectAsset(item) {
  const label   = _assetTypeLabel(item.type || 'item').toUpperCase();
  const content = item.content || '';
  const moduleId = item.module_id || item.chapter_id || '';
  const assetType = item.type || '';
  const isGeneratable = GENERATABLE_ASSET_TYPES.includes(assetType);

  // Pre-load modal state for the generate function (re-uses _assetModal)
  if (isGeneratable && moduleId) {
    let prose = '', moduleTitle = '';
    try {
      const res = await fetch(`/api/modules/${moduleId}`);
      if (res.ok) { const m = await res.json(); prose = m.prose || ''; moduleTitle = m.title || ''; }
    } catch(e) {}
    const prompts = (state.settings && state.settings.asset_prompts) || [];
    _assetModal = { moduleId, workId: item.work_id || '', role: item.role || 'promotional', prose, title: moduleTitle, prompts };
  }

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">${label} — Manage Asset</div>
    <div class="modal-subtitle">ID: ...${(item.asset_id || item.id || '').slice(-8)} · Role: ${(item.role || 'PROMOTIONAL').toUpperCase()}</div>

    ${isGeneratable ? `<div id="asset-generate-section" style="margin-top:16px;"></div>` : ''}

    <div class="inspect-view" style="margin-top:${isGeneratable ? '0' : '16px'}">
      <div class="inspect-group">
        <div class="inspect-label">Asset Content</div>
        <textarea id="edit-asset-content" class="form-textarea" style="min-height:150px;">${esc(content)}</textarea>
        <div style="font-size:10px; color:var(--muted); margin-top:4px;">Editing will update the registry directly.</div>
      </div>

      <div class="inspect-row" style="display:flex;gap:16px;margin-top:12px;">
        <div class="inspect-group" style="flex:1;">
          <div class="inspect-label">Production</div>
          <div class="cc-status-pill ${item.production || 'not_started'}">${item.production || 'not_started'}</div>
        </div>
        <div class="inspect-group" style="flex:1;">
          <div class="inspect-label">Promotion</div>
          <div class="cc-status-pill ${item.promotion || 'not_promoted'}">${item.promotion || 'not_promoted'}</div>
        </div>
      </div>

      <div class="inspect-group" style="margin-top:12px;">
        <div class="inspect-label">Lifecycle</div>
        <div class="inspect-log">
          Created: ${new Date(item.created_at || Date.now()).toLocaleString()}<br>
          Updated: ${new Date(item.updated_at || Date.now()).toLocaleString()}
        </div>
      </div>
    </div>

    <div class="modal-actions" style="display:flex; justify-content:space-between; gap:10px; margin-top:20px;">
      <button class="btn-secondary" onclick="deleteAssetFromManage('${item.asset_id}')" style="background:rgba(239, 68, 68, 0.1); color:#ef4444; border:1px solid rgba(239, 68, 68, 0.3);">Delete</button>
      <div style="display:flex; gap:10px;">
        <button class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn-primary" onclick="saveAsset('${item.asset_id}')">Save Changes</button>
      </div>
    </div>
  `;
  showModal();

  // Render generate section after modal is in DOM
  if (isGeneratable) {
    _assetModal._inspectType = assetType;
    onAssetTypeChange(assetType);
  }
}

async function saveAsset(asset_id) {
  const content = document.getElementById('edit-asset-content').value;
  try {
    const res = await fetch(`/api/assets/${asset_id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content })
    });
    if (res.ok) {
      toast('Asset updated successfully');
      closeModal();
      refreshCommandCenter();
    } else {
      toast('Error updating asset', 'error');
    }
  } catch (err) {
    console.error(err);
    toast('Network error', 'error');
  }
}

async function deleteAssetFromManage(asset_id) {
  if (!confirm('Are you sure you want to delete this asset? This cannot be undone.')) return;
  try {
    const res = await fetch(`/api/assets/${asset_id}`, { method: 'DELETE' });
    if (res.ok) {
      toast('Asset deleted');
      closeModal();
      refreshCommandCenter();
    } else {
       toast('Error deleting asset', 'error');
    }
  } catch (err) {
    console.error(err);
    toast('Network error', 'error');
  }
}

function refreshCommandCenter() {
  if (state.currentMode === 'manage') {
    loadCommandCenter();
  }
}

// Asset types that can be AI-generated from prose
const GENERATABLE_ASSET_TYPES = ['synopsis', 'tagline', 'blurb', 'header_image_prompt', 'excerpt'];

// Module-level state for the asset modal (avoids re-fetching on type change)
let _assetModal = { moduleId: null, workId: null, role: null, prose: '', title: '', prompts: [] };

async function addAssetManually(moduleId, workId, role, initialType = null) {
  const types = ['synopsis', 'tagline', 'blurb', 'content', 'excerpt', 'header_image', 'audio', 'podcast_episode'];

  // Fetch module data for prose pre-fill and AI generation
  let prose = '', moduleTitle = '';
  try {
    const res = await fetch(`/api/modules/${moduleId}`);
    if (res.ok) { const m = await res.json(); prose = m.prose || ''; moduleTitle = m.title || ''; }
  } catch(e) {}

  const prompts = (state.settings && state.settings.asset_prompts) || [];
  _assetModal = { moduleId, workId, role, prose, title: moduleTitle, prompts };

  const selectedType = initialType || types[0];

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Add Asset</div>
    <div class="modal-subtitle">${esc(moduleTitle)} · Role: ${role.toUpperCase()}</div>

    <div class="form-group" style="margin-top:20px;">
      <label class="form-label">Asset Type</label>
      <select id="new-asset-type" class="form-input" onchange="onAssetTypeChange(this.value)">
        ${types.map(t => `<option value="${t}" ${selectedType === t ? 'selected' : ''}>${t.replace(/_/g, ' ').toUpperCase()}</option>`).join('')}
      </select>
    </div>

    <div id="asset-generate-section"></div>

    <div class="form-group">
      <label class="form-label">Content</label>
      <textarea id="new-asset-content" class="form-textarea" style="min-height:160px;" placeholder="Enter asset text, or use Generate above..."></textarea>
    </div>

    <div class="modal-actions" style="margin-top:24px;">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="submitManualAsset('${moduleId}', '${workId}', '${role}')">Create Asset</button>
    </div>
  `;
  showModal();
  onAssetTypeChange(selectedType);
}

function onAssetTypeChange(type) {
  const { prose, prompts } = _assetModal;
  const section = document.getElementById('asset-generate-section');
  if (!section) return;

  // Pre-fill content with prose if type is 'content'
  const contentEl = document.getElementById('new-asset-content');
  if (type === 'content' && contentEl) {
    if (prose) {
      contentEl.value = prose;
      contentEl.style.minHeight = '200px';
    }
    section.innerHTML = prose
      ? `<div class="asset-generate-note" style="font-size:11px;color:var(--muted);margin-bottom:8px;">Pre-filled with module prose. Edit before saving if needed.</div>`
      : `<div class="asset-generate-note" style="font-size:11px;color:var(--muted);margin-bottom:8px;">No prose saved on this module. Edit the module to add prose first.</div>`;
    return;
  }

  // Clear content pre-fill if switching away from 'content'
  if (contentEl && contentEl.value && type !== 'content') {
    // Only clear if it looks like it was prose-pre-filled (don't clear user edits)
  }

  if (!GENERATABLE_ASSET_TYPES.includes(type)) {
    section.innerHTML = '';
    return;
  }

  // Find matching prompt config
  const cfg = prompts.find(p => p.asset_type === type);
  const activeVer = cfg ? cfg.active_version || 'A' : 'A';
  const promptText = cfg ? (cfg.versions?.[activeVer]?.prompt || '') : '';
  const versionsHtml = cfg ? ['A','B','C'].map(v => {
    const ver = cfg.versions?.[v] || {};
    const label = ver.label || (v === activeVer ? '(active)' : '(empty)');
    const disabled = !ver.active && v !== activeVer ? 'disabled' : '';
    return `<option value="${v}" ${v === activeVer ? 'selected' : ''} ${disabled}>${v}: ${label}</option>`;
  }).join('') : '<option value="A">A (default)</option>';

  const supportsRefImage = cfg && cfg.supports_reference_image;

  section.innerHTML = `
    <div class="asset-generate-panel" style="background:var(--card-bg,rgba(0,0,0,0.08));border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:14px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <span style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);">Generate with AI</span>
        <span style="font-size:11px;color:var(--muted);">Input: ${cfg ? esc(cfg.input_description) : 'module prose'}</span>
      </div>

      ${!prose ? `<div style="font-size:12px;color:#f59e0b;margin-bottom:10px;">⚠ No prose on this module — add prose via Edit Module before generating.</div>` : ''}

      <div style="display:flex;gap:8px;align-items:center;margin-bottom:10px;">
        <select id="prompt-version-select" class="form-input" style="flex:1;font-size:12px;" onchange="onPromptVersionChange(this.value, '${type}')">
          ${versionsHtml}
        </select>
        <button class="btn-secondary" style="font-size:11px;padding:4px 10px;white-space:nowrap;" onclick="togglePromptPreview()">Edit Prompt</button>
      </div>

      <div id="prompt-preview-panel" style="display:none;margin-bottom:10px;">
        <textarea id="prompt-preview-text" class="form-textarea" style="min-height:120px;font-size:11px;font-family:var(--font-mono,monospace);">${esc(promptText)}</textarea>
        <div style="font-size:10px;color:var(--muted);margin-top:4px;">Use <code>{{prose}}</code> where the chapter text should be inserted. Changes here apply to this generation only — save permanent edits in Settings.</div>
      </div>

      ${supportsRefImage ? `
      <div class="form-group" style="margin-bottom:10px;">
        <label class="form-label" style="font-size:11px;">Reference Image (optional) — URL or upload</label>
        <div style="display:flex;gap:8px;">
          <input type="url" id="ref-image-url" class="form-input" style="flex:1;font-size:12px;" placeholder="https://example.com/style-reference.jpg"/>
          <label class="btn-secondary" style="font-size:11px;padding:4px 10px;cursor:pointer;white-space:nowrap;">
            Upload<input type="file" id="ref-image-upload" accept="image/*" style="display:none;" onchange="handleRefImageUpload(this)"/>
          </label>
        </div>
        <div id="ref-image-preview" style="margin-top:6px;"></div>
      </div>` : ''}

      <div style="display:flex;gap:8px;align-items:center;">
        <button class="btn-primary" id="btn-generate-asset" onclick="generateAssetContent()" ${!prose ? 'disabled' : ''} style="flex:1;">
          Generate
        </button>
        <div id="generate-asset-status" style="font-size:11px;color:var(--muted);"></div>
      </div>
    </div>
  `;
}

function togglePromptPreview() {
  const panel = document.getElementById('prompt-preview-panel');
  if (panel) panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

function onPromptVersionChange(version, assetType) {
  const prompts = _assetModal.prompts;
  const cfg = prompts.find(p => p.asset_type === assetType);
  if (!cfg) return;
  const promptText = cfg.versions?.[version]?.prompt || '';
  const el = document.getElementById('prompt-preview-text');
  if (el) el.value = promptText;
}

function handleRefImageUpload(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const urlInput = document.getElementById('ref-image-url');
    const preview  = document.getElementById('ref-image-preview');
    if (urlInput) urlInput.value = e.target.result; // base64 data URL
    if (preview)  preview.innerHTML = `<img src="${e.target.result}" style="max-height:80px;border-radius:4px;margin-top:4px;"/>`;
  };
  reader.readAsDataURL(file);
}

async function generateAssetContent() {
  const { moduleId, prompts } = _assetModal;
  // Works in both add-asset modal (new-asset-type select) and inspect modal (type stored in _assetModal)
  const assetType = document.getElementById('new-asset-type')?.value || _assetModal._inspectType;
  const version   = document.getElementById('prompt-version-select')?.value || 'A';
  const refImage  = document.getElementById('ref-image-url')?.value?.trim() || '';

  // Use edited prompt text if preview is open
  const previewEl = document.getElementById('prompt-preview-text');
  const customPrompt = (previewEl && previewEl.style.display !== 'none' && document.getElementById('prompt-preview-panel')?.style.display !== 'none')
    ? previewEl.value.trim() : '';

  const btn    = document.getElementById('btn-generate-asset');
  const status = document.getElementById('generate-asset-status');
  if (btn)    { btn.disabled = true; btn.textContent = 'Generating…'; }
  if (status) status.textContent = '';

  try {
    const res = await fetch(`/api/modules/${moduleId}/generate-asset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ asset_type: assetType, prompt_version: version, reference_image_url: refImage, custom_prompt: customPrompt })
    });
    const data = await res.json();
    if (!res.ok) {
      toast(data.error || 'Generation failed', 'error');
      if (status) status.textContent = data.error || 'Failed';
    } else {
      const contentEl = document.getElementById('new-asset-content') || document.getElementById('edit-asset-content');
      if (contentEl) contentEl.value = data.content;
      if (status) status.textContent = '✓ Generated';
      toast('Generated — review and save when ready', 'success');
    }
  } catch(e) {
    toast('Network error during generation', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Generate'; }
  }
}

async function submitManualAsset(moduleId, workId, role) {
  const type    = document.getElementById('new-asset-type').value;
  const content = document.getElementById('new-asset-content').value;

  const payload = {
    type,
    content,
    module_id: moduleId,
    work_id:   workId,
    role,
    source_type: 'manual',
    production:  'done'
  };
  
  try {
    const res = await fetch('/api/assets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      toast('Asset created manually');
      closeModal();
      loadCommandCenter();
    } else {
      toast('Error creating asset', 'error');
    }
  } catch (e) { toast('Network error', 'error'); }
}

function toggleCCElement(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const isHidden = el.style.display === 'none';
  el.style.display = isHidden ? 'block' : 'none';
  
  // Rotate icon
  const header = el.previousElementSibling;
  const icon = header.querySelector('.cc-toggle-icon');
  if (icon) icon.style.transform = isHidden ? 'rotate(90deg)' : 'rotate(0deg)';
}

function toggleAllCC(expand) {
  const display = expand ? 'block' : 'none';
  const rotation = expand ? 'rotate(90deg)' : 'rotate(0deg)';
  
  document.querySelectorAll('.cc-book-body, .cc-module-assets').forEach(el => {
    el.style.display = display;
  });
  document.querySelectorAll('.cc-toggle-icon').forEach(icon => {
    icon.style.transform = rotation;
  });
}

// ── PROMOTION MACHINE: Book Serializer Sub-tab ────────────────────────────────

function renderPromoBookSerializer() {
  const container = document.getElementById('promo-view-book-serializer');
  if (!container) return;

  const selectedBookId = state.selectedBookId;
  const workList = state.promoBooks.length === 0
    ? '<p style="color:var(--muted);padding:20px;text-align:center;">No works yet.</p>'
    : state.promoBooks.map(b => `
        <div class="promo-lead-card ${selectedBookId === b.id ? 'active' : ''}" style="${selectedBookId === b.id ? 'border-color:var(--accent);background:var(--p4-bg);' : ''}" onclick="selectBook('${b.id}')">
          <div class="promo-lead-card-contact">${esc(b.title)}</div>
          <div class="promo-lead-card-product">${esc(b.author)} • ${b.chunks?.length || 0} modules</div>
        </div>
      `).join('');

  container.innerHTML = `
    <div class="promo-two-panel">
      <div class="promo-left-panel">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
          <h3 style="font-family:var(--font-mono);font-size:12px;text-transform:uppercase;color:var(--muted);">Works Library</h3>
          <button class="btn-secondary" style="font-size:10px;" onclick="openNewBookModal()">+ New Work</button>
        </div>
        ${workList}
      </div>
      <div class="promo-right-panel" id="book-detail-panel">
        ${selectedBookId ? '<p style="color:var(--muted);padding:40px;text-align:center;">Loading work detail...</p>' : '<p style="color:var(--muted);padding:40px;text-align:center;">Select a work to manage its WA serialization.<br><span style="font-size:11px;opacity:0.6;">This is separate from the Inventory module registry.</span></p>'}
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
      <h3>Work Settings</h3>
      <div class="promo-action-bar">
        <div class="form-group" style="flex:1;"><label class="form-label">Title</label><input class="form-input" id="bk-title" value="${esc(book.title)}"/></div>
        <div class="form-group" style="flex:1;"><label class="form-label">Author</label><input class="form-input" id="bk-author" value="${esc(book.author)}"/></div>
      </div>
      <div class="promo-action-bar">
        <div class="form-group" style="flex:1;"><label class="form-label">Patreon URL</label><input class="form-input" id="bk-patreon" value="${esc(book.patreon_url)}"/></div>
        <div class="form-group" style="flex:1;"><label class="form-label">Website URL</label><input class="form-input" id="bk-website" value="${esc(book.website_url)}"/></div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <button class="btn-primary" onclick="updateBookSettings('${book.id}')">Save Settings</button>
        <button class="btn-secondary" style="color:var(--danger);border-color:rgba(255,100,100,0.3);" onclick="deleteBook('${book.id}')">Delete Work</button>
      </div>
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
        <input type="file" id="bk-ingest-file" accept=".txt,.rtf,.docx"/>
        <div style="font-size:11px;color:var(--muted);margin-top:6px;">Supported: .txt \u00b7 .rtf \u00b7 .docx (Word)</div>
      </div>
      <div class="promo-action-bar" style="margin-top:12px;">
        <div class="form-group" style="width:140px;"><label class="form-label">Target Words</label><input class="form-input" id="bk-target" type="number" value="${targetWordCount}"/></div>
        <div class="form-group" style="width:140px;"><label class="form-label">Max Words</label><input class="form-input" id="bk-max" type="number" value="${maxWordCount}"/></div>
      </div>
      <button class="btn-primary" id="btn-bk-serialize" onclick="serializeBookContent('${book.id}')">Serialize Content</button>
    </div>

    <div class="promo-settings-section" style="border-bottom:none;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;flex-wrap:wrap;gap:8px;">
        <h3 style="margin-bottom:0;">Chapters / Modules (${book.chunks?.length || 0})</h3>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn-secondary" style="font-size:11px;" onclick="openImportChaptersModal('${book.id}')">↑ Import Chapters</button>
          <button class="btn-secondary" style="font-size:11px;" onclick="openManualModuleModal('${book.id}')">+ Add Manual</button>
          ${book.chunks?.length ? `
            <button class="btn-secondary" style="font-size:11px;" onclick="openBulkGenerateModal('${book.id}')">⚡ Generate Assets</button>
            <button class="btn-secondary" style="font-size:11px;" onclick="openHeaderPromptsModal('${book.id}')">🖼 Header Prompts</button>
          ` : ''}
          ${book.chunks?.some(c => c.status === 'pending') ? `
            <button class="btn-secondary" style="font-size:11px;" onclick="queueAllPendingChunksModal('${book.id}')">Queue All Pending...</button>
          ` : ''}
        </div>
      </div>
      ${!book.chunks || book.chunks.length === 0 ? '<p style="color:var(--muted);font-size:13px;">No modules yet. Use "Import Chapters" to bulk-import your manuscript, or "Ingest Content" to serialize it into WA posts.</p>' : `
        <div class="promo-chunk-list">
          ${book.chunks.map((c, i) => `
            <div class="promo-chunk-item">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                  ${c.title ? `<span style="font-weight:bold;font-size:13px;">${esc(c.title)}</span>` : `<span style="font-weight:bold;font-size:14px;">Module ${i+1}</span>`}
                  <span class="promo-badge" style="background:var(--surface2);border:1px solid var(--border2); color:var(--text); opacity:0.7;">${c.word_count} w</span>
                  <span class="promo-chunk-status-${c.status}" style="font-family:var(--font-mono);font-size:9px;text-transform:uppercase;">● ${c.status}</span>
                </div>
                <div style="display:flex;gap:6px;">
                  <button class="icon-btn" title="Edit Module" onclick="editChunkModal('${book.id}', '${c.id}')">✎</button>
                  <button class="icon-btn" style="color:var(--danger);" title="Delete Module" onclick="deleteChunk('${book.id}', '${c.id}')">×</button>
                </div>
              </div>
              <div style="font-size:13px;color:var(--muted);margin-bottom:10px;line-height:1.4;white-space:pre-wrap;">
                ${esc(c.content.slice(0, 150))}...
                <a href="javascript:void(0)" onclick="toggleChunkContent(this)" style="color:var(--accent);font-size:11px;margin-left:4px;">Show Full</a>
              </div>
              <div class="full-chunk-content" style="display:none;font-size:13px;white-space:pre-wrap;background:var(--bg);padding:12px;border-radius:4px;margin-bottom:10px;">${esc(c.content)}</div>
              ${c.cliffhanger_note ? `<div style="font-size:11px;font-style:italic;color:var(--muted2);margin-bottom:12px;">CLIFFHANGER: ${esc(c.cliffhanger_note)}</div>` : ''}
              ${c.status === 'pending' ? `
                <div style="display:flex;gap:8px;">
                  <button class="btn-secondary" style="font-size:11px;" onclick="queueWorkModuleModal('${book.id}', '${c.id}')">Queue...</button>
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
    <div class="modal-title">Add New Work</div>
    <div class="form-group"><label class="form-label">Title *</label><input class="form-input" id="new-bk-title"/></div>
    <div class="form-group"><label class="form-label">Author</label><input class="form-input" id="new-bk-author"/></div>
    <div class="form-group"><label class="form-label">Patreon URL</label><input class="form-input" id="new-bk-patreon"/></div>
    <div class="form-group"><label class="form-label">Website URL</label><input class="form-input" id="new-bk-website"/></div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="saveNewBook()">Save Work</button>
    </div>`;
  showModal();
}

async function saveNewBook() {
  const title = document.getElementById('new-bk-title').value.trim();
  if (!title) { toast('Title required', 'error'); return; }
  
  try {
    const res = await POST('/api/works', {
      title,
      author: document.getElementById('new-bk-author').value.trim(),
      patreon_url: document.getElementById('new-bk-patreon').value.trim(),
      website_url: document.getElementById('new-bk-website').value.trim()
    });
    toast('Work added', 'success');
    closeModal();
    if (state.currentPromoTab === 'command-center') {
      loadCommandCenter();
    } else {
      state.selectedBookId = res.id;
      loadPromoWorks();
    }
  } catch (e) { toast('Save failed', 'error'); }
}

async function updateBookSettings(id) {
  try {
    await PUT(`/api/works/${id}`, {
      title: document.getElementById('bk-title').value.trim(),
      author: document.getElementById('bk-author').value.trim(),
      patreon_url: document.getElementById('bk-patreon').value.trim(),
      website_url: document.getElementById('bk-website').value.trim()
    });
    toast('Work updated', 'success');
    loadPromoWorks();
  } catch (e) { toast('Update failed', 'error'); }
}

async function deleteBook(id) {
  if (!confirm('Are you sure you want to delete this entire work and all its modules?')) return;
  try {
    await DEL(`/api/works/${id}`);
    toast('Work deleted', 'success');
    state.selectedBookId = null;
    loadPromoWorks();
  } catch (e) { toast('Delete failed', 'error'); }
}

function openManualModuleModal(bookId) {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Add Manual Module</div>
    <div class="form-group">
      <label class="form-label">Content (Full formatted post)</label>
      <textarea class="form-textarea" id="man-chunk-content" style="min-height:250px;" placeholder="**Part X**\n\nStory text..."></textarea>
    </div>
    <div class="form-group">
      <label class="form-label">Cliffhanger Note (Internal only)</label>
      <input class="form-input" id="man-chunk-cliff" placeholder="Why this break point?"/>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="saveManualModuleContent('${bookId}')">Add Chunk</button>
    </div>`;
  showModal();
}

async function saveManualModuleContent(bookId) {
  const content = document.getElementById('man-chunk-content').value.trim();
  if (!content) { toast('Content required', 'error'); return; }
  try {
    await POST(`/api/works/${bookId}/modules`, {
      content,
      cliffhanger_note: document.getElementById('man-chunk-cliff').value.trim()
    });
    toast('Module added', 'success');
    closeModal();
    loadPromoWorks();
  } catch (e) { toast('Failed to add chunk', 'error'); }
}

function editChunkModal(bookId, chunkId) {
  const book = state.promoBooks.find(b => b.id === bookId);
  const chunk = book.chunks.find(c => c.id === chunkId);
  if (!chunk) return;

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Edit Module</div>
    <div class="form-group">
      <label class="form-label">Content</label>
      <textarea class="form-textarea" id="edit-chunk-content" style="min-height:250px;">${esc(chunk.content)}</textarea>
    </div>
    <div class="form-group">
      <label class="form-label">Cliffhanger Note</label>
      <input class="form-input" id="edit-chunk-cliff" value="${esc(chunk.cliffhanger_note || '')}"/>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="saveChunkEdit('${bookId}', '${chunkId}')">Save Changes</button>
    </div>`;
  showModal();
}

async function saveChunkEdit(bookId, chunkId) {
  const content = document.getElementById('edit-chunk-content').value.trim();
  if (!content) return;
  try {
    await PUT(`/api/works/${bookId}/modules/${chunkId}`, {
      content,
      cliffhanger_note: document.getElementById('edit-chunk-cliff').value.trim()
    });
    toast('Module updated', 'success');
    closeModal();
    loadPromoWorks();
  } catch (e) { toast('Update failed', 'error'); }
}

async function deleteChunk(bookId, chunkId) {
  if (!confirm('Remove this module?')) return;
  try {
    await DELETE(`/api/works/${bookId}/modules/${chunkId}`);
    toast('Module removed', 'success');
    loadPromoWorks();
  } catch (e) { toast('Delete failed', 'error'); }
}

function toggleIngestMode(mode) {
  document.getElementById('btn-ing-paste').classList.toggle('active', mode === 'paste');
  document.getElementById('btn-ing-file').classList.toggle('active', mode === 'file');
  document.getElementById('ing-paste-box').style.display = mode === 'paste' ? 'block' : 'none';
  document.getElementById('ing-file-box').style.display = mode === 'file' ? 'block' : 'none';
}

async function serializeBookContent(id) {
  const btn = document.getElementById('btn-bk-serialize');
  btn.textContent = 'Serializing… this may take a moment';
  btn.disabled = true;

  const target_words = document.getElementById('bk-target').value;
  const max_words    = document.getElementById('bk-max').value;
  const isPaste      = document.getElementById('btn-ing-paste').classList.contains('active');

  try {
    let res;
    if (isPaste) {
      const text = document.getElementById('bk-ingest-text').value.trim();
      if (!text) { toast('Please paste some text first.', 'error'); return; }
      res = await fetch(`/api/works/${id}/ingest`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ text, target_words, max_words })
      });
    } else {
      const file = document.getElementById('bk-ingest-file').files[0];
      if (!file) { toast('Please select a file (.txt, .rtf, or .docx).', 'error'); return; }
      const allowed = ['.txt', '.rtf', '.docx'];
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      if (!allowed.includes(ext)) {
        toast(`Unsupported format: ${ext}. Use .txt, .rtf, or .docx.`, 'error');
        return;
      }
      const formData = new FormData();
      formData.append('file', file);
      formData.append('target_words', target_words);
      formData.append('max_words', max_words);
      res = await fetch(`/api/works/${id}/ingest`, { method: 'POST', body: formData });
    }

    const contentType = res.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    const data = isJson ? await res.json() : { error: `Server error (${res.status}). Check logs.` };

    if (res.ok) {
      const chunkCount  = data.chunks  ? data.chunks.length  : '?';
      const windowCount = data.windows ? data.windows        : 1;
      const partialErr  = data.errors  && data.errors.length > 0
        ? ` (${data.errors.length} window error(s) — check Log)` : '';
      toast(`✓ ${chunkCount} module(s) generated from ${windowCount} pass(es).${partialErr}`, 'success');
      if (data.errors && data.errors.length > 0) {
        data.errors.forEach(e => console.warn('[Serializer partial error]', e));
      }
      await loadPromoWorks();
    } else {
      toast(data.error || 'Serialization failed.', 'error');
    }
  } catch (e) {
    toast('Request failed: ' + e.message, 'error');
    console.error('[Serialize Error]', e);
  } finally {
    btn.textContent = 'Serialize Content';
    btn.disabled = false;
  }
}

function queueWorkModuleModal(workId, chunkId) {
  const book = state.promoBooks.find(b => b.id === workId);
  const urls = [];
  if (book?.patreon_url) urls.push({ label: 'Patreon', url: book.patreon_url });
  if (book?.website_url) urls.push({ label: 'Website', url: book.website_url });

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Queue Chunk</div>
    <p style="margin:12px 0;font-size:13px;color:var(--muted);">
      This chunk will be auto-scheduled into the next available story slot.
    </p>
    <div class="form-group">
      <label class="form-label">CTA Link (appended to bottom of message)</label>
      <select class="form-input" id="queue-cta-url">
        <option value="">No CTA link</option>
        ${urls.map(u => `<option value="${esc(u.url)}">${u.label}: ${esc(u.url)}</option>`).join('')}
      </select>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="submitQueueWorkModule('${workId}', '${chunkId}')">Queue</button>
    </div>`;
  showModal();
}

async function submitQueueWorkModule(workId, chunkId) {
  const ctaUrl = document.getElementById('queue-cta-url')?.value || '';
  closeModal();
  try {
    const res  = await POST(`/api/works/${workId}/modules/${chunkId}/queue`, { cta_url: ctaUrl });
    const when = res.scheduled_at ? new Date(res.scheduled_at).toLocaleString() : 'next available slot';
    if (res.ec2_synced === false) {
      toast(`Queued locally for ${when} — EC2 sync failed. May not send automatically.`, 'error');
    } else {
      toast(`Queued — scheduled for ${when}`, 'success');
    }
    loadPromoWorks();
  } catch (e) { toast('Queue failed', 'error'); }
}

function queueAllPendingChunksModal(bookId) {
  const book    = state.promoBooks.find(b => b.id === bookId);
  const pending = book ? book.chunks.filter(c => c.status === 'pending') : [];
  const urls    = [];
  if (book?.patreon_url) urls.push({ label: 'Patreon', url: book.patreon_url });
  if (book?.website_url) urls.push({ label: 'Website', url: book.website_url });

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Queue All Pending Chunks</div>
    <p style="margin:16px 0;color:var(--muted);font-size:13px;">
      <strong>${pending.length} pending chunk${pending.length !== 1 ? 's' : ''}</strong> will be auto-scheduled
      into the next available story slots based on your Delivery Schedule in Settings.
    </p>
    <p style="font-size:12px;color:var(--muted);margin-bottom:16px;">
      Each chunk is assigned one slot — lunchtime (12:30) or evening (18:30) — filling sequentially,
      skipping Sundays (lighter day) and respecting max posts/day and spacing rules.
    </p>
    <div class="form-group" style="margin-bottom:20px;">
      <label class="form-label">CTA Link (appended to every chunk)</label>
      <select class="form-input" id="batch-queue-cta-url">
        <option value="">No CTA link</option>
        ${urls.map(u => `<option value="${esc(u.url)}">${u.label}: ${esc(u.url)}</option>`).join('')}
      </select>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="processBatchQueue('${bookId}')">Queue All (Auto-schedule)</button>
    </div>`;
  showModal();
}

async function processBatchQueue(bookId) {
  const book   = state.promoBooks.find(b => b.id === bookId);
  if (!book) return;
  const ctaUrl = document.getElementById('batch-queue-cta-url')?.value || '';

  const pending = book.chunks.filter(c => c.status === 'pending');
  let queued = 0, failed = 0;

  for (const chunk of pending) {
    try {
      await POST(`/api/works/${bookId}/modules/${chunk.id}/queue`, { cta_url: ctaUrl });
      queued++;
    } catch (e) { failed++; }
  }

  if (failed > 0) toast(`Queued ${queued}, ${failed} failed`, 'error');
  else toast(`Queued ${queued} chunks — scheduled automatically`, 'success');
  closeModal();
  loadPromoBooks();
}

// ── BULK CHAPTER IMPORT ───────────────────────────────────────────────────────

let _importState  = { workId: null, chapters: [], target: 'chunks' };
let _bulkJobId    = null;
let _bulkPollTimer = null;

function openImportChaptersModal(workId, target = 'chunks') {
  _importState = { workId, chapters: [], target };
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Import Chapters</div>
    <div style="font-size:12px;color:var(--muted);margin:8px 0 16px;">
      ⓘ Paste or upload your manuscript. Chapter headings (e.g. "Chapter 1", "Chapter 2: Title") are detected automatically. You can rename or merge chapters in the next step.
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px;">
      <button class="btn-secondary active" id="imp-tab-paste" onclick="toggleImportTab('paste')">Paste Text</button>
      <button class="btn-secondary" id="imp-tab-file" onclick="toggleImportTab('file')">Upload File</button>
    </div>
    <div id="imp-paste-box">
      <textarea class="form-textarea" id="imp-text" style="min-height:200px;" placeholder="Paste full manuscript here..."></textarea>
    </div>
    <div id="imp-file-box" style="display:none;">
      <input type="file" id="imp-file" accept=".txt,.rtf,.docx"/>
      <div style="font-size:11px;color:var(--muted);margin-top:6px;">Supported: .txt \u00b7 .rtf \u00b7 .docx</div>
    </div>
    <div class="modal-actions" style="margin-top:16px;">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" id="btn-imp-preview" onclick="previewChapterSplit('${workId}')">Preview Split</button>
    </div>`;
  showModal();
}

function toggleImportTab(tab) {
  document.getElementById('imp-tab-paste').classList.toggle('active', tab === 'paste');
  document.getElementById('imp-tab-file').classList.toggle('active', tab === 'file');
  document.getElementById('imp-paste-box').style.display = tab === 'paste' ? 'block' : 'none';
  document.getElementById('imp-file-box').style.display  = tab === 'file'  ? 'block' : 'none';
}

async function previewChapterSplit(workId) {
  const btn = document.getElementById('btn-imp-preview');
  btn.disabled = true;
  btn.textContent = 'Detecting chapters...';

  try {
    const isPaste = document.getElementById('imp-tab-paste').classList.contains('active');
    let res;
    if (isPaste) {
      const text = document.getElementById('imp-text').value.trim();
      if (!text) { toast('Paste some text first.', 'error'); return; }
      res = await fetch(`/api/works/${workId}/preview_split`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ text }),
      });
    } else {
      const file = document.getElementById('imp-file').files[0];
      if (!file) { toast('Select a file first.', 'error'); return; }
      const fd = new FormData();
      fd.append('file', file);
      res = await fetch(`/api/works/${workId}/preview_split`, { method: 'POST', body: fd });
    }
    const data = await res.json();
    if (!res.ok) { toast(data.error || 'Split failed', 'error'); return; }

    _importState.workId   = workId;
    _importState.chapters = data.chapters.map(c => ({ ...c, merge_next: false }));
    _renderSplitPreview();
  } catch (e) {
    toast('Split failed: ' + e.message, 'error');
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Preview Split';
  }
}

function _buildImportGroups(chapters) {
  const groups = [];
  let i = 0;
  while (i < chapters.length) {
    const group = {
      title:      chapters[i].title,
      word_count: chapters[i].word_count,
      preview:    chapters[i].preview,
      indices:    [chapters[i].index],
    };
    while (chapters[i].merge_next && i + 1 < chapters.length) {
      i++;
      group.word_count += chapters[i].word_count;
      group.indices.push(chapters[i].index);
    }
    groups.push(group);
    i++;
  }
  return groups;
}

function _renderSplitPreview() {
  const groups  = _buildImportGroups(_importState.chapters);
  const workId  = _importState.workId;

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Review Split — ${groups.length} chapter${groups.length !== 1 ? 's' : ''}</div>
    <div style="font-size:12px;color:var(--muted);margin-bottom:12px;">
      Edit titles, or use "↓ Merge" to combine a chapter with the one below.
    </div>
    <div style="max-height:360px;overflow-y:auto;border:1px solid var(--border2);border-radius:6px;margin-bottom:14px;">
      ${groups.map((g, gi) => `
        <div style="padding:10px 14px;border-bottom:${gi < groups.length-1 ? '1px solid var(--border2)' : 'none'};">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            <span style="font-family:var(--font-mono);font-size:10px;color:var(--muted);min-width:22px;">${gi+1}.</span>
            <input class="form-input" style="flex:1;font-size:12px;padding:4px 8px;"
                   id="imp-title-${gi}" value="${esc(g.title)}" placeholder="Chapter title"/>
            <span style="font-family:var(--font-mono);font-size:10px;color:var(--muted);white-space:nowrap;">${g.word_count} w</span>
            ${gi < groups.length - 1 ? `<button class="btn-secondary" style="font-size:10px;padding:3px 8px;" onclick="toggleImportMerge(${gi})">&#x2193; Merge</button>` : ''}
          </div>
          <div style="font-size:11px;color:var(--muted2);padding-left:30px;font-style:italic;line-height:1.4;">${esc(g.preview)}${g.preview.length >= 200 ? '…' : ''}</div>
        </div>
      `).join('')}
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="openImportChaptersModal('${workId}', '${_importState.target}')">&#x2190; Back</button>
      <button class="btn-secondary" onclick="confirmChapterImport('${workId}', false)">Add to Work</button>
      <button class="btn-primary" onclick="confirmChapterImport('${workId}', true)">Replace All Chapters</button>
    </div>`;
  showModal();
}

function toggleImportMerge(groupIdx) {
  const groups = _buildImportGroups(_importState.chapters);
  const group  = groups[groupIdx];
  // The last chapter in this group is at index group.indices[group.indices.length - 1]
  const lastChapterIdx = _importState.chapters.findIndex(
    c => c.index === group.indices[group.indices.length - 1]
  );
  if (lastChapterIdx >= 0) {
    _importState.chapters[lastChapterIdx].merge_next = !_importState.chapters[lastChapterIdx].merge_next;
  }
  _renderSplitPreview();
}

async function confirmChapterImport(workId, replace) {
  const groups   = _buildImportGroups(_importState.chapters);
  const chapters = groups.map((g, gi) => ({
    title:   (document.getElementById(`imp-title-${gi}`)?.value || g.title).trim(),
    indices: g.indices,
  }));
  const isModules = _importState.target === 'modules';
  const deleteUrl = `/api/works/${workId}/${isModules ? 'bulk_delete_chapters' : 'bulk_delete_modules'}`;
  const importUrl = `/api/works/${workId}/${isModules ? 'bulk_import_chapters' : 'bulk_import_modules'}`;

  try {
    if (replace) {
      const delRes  = await fetch(deleteUrl, { method: 'POST' });
      const delData = await delRes.json();
      if (!delRes.ok) {
        toast(delData.error || 'Could not clear existing chapters', 'error');
        return;
      }
    }
    const data = await POST(importUrl, { chapters });
    closeModal();
    toast(`Imported ${data.imported} chapter${data.imported !== 1 ? 's' : ''}`, 'success');
    if (isModules) {
      // If Scrivenings is open for this work, refresh it too
      if (state.scrivengsWorkId === workId) {
        const fresh = await GET(`/api/works/${workId}/scrivenings`);
        state.scrivengsData = fresh;
      }
      await loadCommandCenter();
    } else {
      await loadPromoWorks();
    }
  } catch (e) {
    toast('Import failed: ' + e.message, 'error');
  }
}


// ── BULK ASSET GENERATION ─────────────────────────────────────────────────────

function openBulkGenerateModal(workId, source = 'chunks') {
  const book  = state.promoBooks.find(b => b.id === workId);
  const count = source === 'modules'
    ? (state.commandCenterData?.find(w => w.work_id === workId)?.modules?.length || 0)
    : (book?.chunks?.length || 0);
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Generate Assets</div>
    <p style="font-size:13px;color:var(--muted);margin:8px 0 16px;">
      Generate assets for all ${count} modules in this work. Modules that already have an asset will be skipped.
    </p>
    <div style="display:flex;flex-direction:column;gap:12px;margin-bottom:20px;">
      <label style="display:flex;align-items:flex-start;gap:10px;font-size:13px;cursor:pointer;">
        <input type="checkbox" id="gen-synopsis" checked style="margin-top:2px;"/>
        <div>
          <div style="font-weight:600;">Synopsis</div>
          <div style="font-size:11px;color:var(--muted);">80\u2013150 word plot summary per chapter</div>
        </div>
      </label>
      <label style="display:flex;align-items:flex-start;gap:10px;font-size:13px;cursor:pointer;">
        <input type="checkbox" id="gen-tagline" checked style="margin-top:2px;"/>
        <div>
          <div style="font-weight:600;">Tagline</div>
          <div style="font-size:11px;color:var(--muted);">12-word punchy hook per chapter</div>
        </div>
      </label>
      <label style="display:flex;align-items:flex-start;gap:10px;font-size:13px;cursor:pointer;">
        <input type="checkbox" id="gen-blurb" checked style="margin-top:2px;"/>
        <div>
          <div style="font-weight:600;">Blurb</div>
          <div style="font-size:11px;color:var(--muted);">50\u201380 word promotional teaser per chapter</div>
        </div>
      </label>
    </div>
    <div id="bulk-gen-progress" style="display:none;padding:12px;background:var(--surface2);border-radius:6px;margin-bottom:16px;">
      <div style="height:4px;background:var(--border2);border-radius:2px;margin-bottom:8px;overflow:hidden;">
        <div id="bulk-gen-bar" style="height:100%;background:var(--accent);border-radius:2px;width:0%;transition:width 0.4s;"></div>
      </div>
      <div id="bulk-gen-current" style="font-size:12px;color:var(--muted);margin-bottom:4px;">Starting...</div>
      <div id="bulk-gen-count" style="font-family:var(--font-mono);font-size:11px;color:var(--muted);"></div>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" id="btn-bulk-gen" onclick="startBulkGenerate('${workId}', '${source}')">Generate</button>
    </div>`;
  showModal();
}

async function startBulkGenerate(workId, source = 'chunks') {
  const types = [];
  if (document.getElementById('gen-synopsis')?.checked) types.push('synopsis');
  if (document.getElementById('gen-tagline')?.checked)  types.push('tagline');
  if (document.getElementById('gen-blurb')?.checked)    types.push('blurb');
  if (!types.length) { toast('Select at least one asset type', 'error'); return; }

  const btn = document.getElementById('btn-bulk-gen');
  btn.disabled = true;
  btn.textContent = 'Starting...';

  try {
    const res = await POST(`/api/works/${workId}/modules/bulk_generate_assets`, { asset_types: types, source });
    _bulkJobId = res.job_id;
    document.getElementById('bulk-gen-progress').style.display = 'block';
    _pollBulkJob(res.total);
  } catch (e) {
    toast('Could not start generation: ' + e.message, 'error');
    btn.disabled    = false;
    btn.textContent = 'Generate';
  }
}

function _pollBulkJob(total) {
  if (_bulkPollTimer) clearTimeout(_bulkPollTimer);
  _bulkPollTimer = setTimeout(async () => {
    if (!_bulkJobId) return;
    try {
      const job = await GET(`/api/works/jobs/${_bulkJobId}`);
      const pct = total > 0 ? Math.round(((job.done || 0) / total) * 100) : 0;
      const bar = document.getElementById('bulk-gen-bar');
      if (bar) bar.style.width = pct + '%';
      const curr = document.getElementById('bulk-gen-current');
      if (curr) curr.textContent = job.current || '';
      const cnt = document.getElementById('bulk-gen-count');
      if (cnt) cnt.textContent = `${job.done || 0} / ${job.total || total} complete`;

      if (job.status === 'done') {
        _bulkJobId = null;
        const errMsg = job.errors?.length ? ` — ${job.errors.length} error(s)` : '';
        toast(`Asset generation complete${errMsg}`, job.errors?.length ? 'error' : 'success');
        closeModal();
      } else if (job.status === 'failed') {
        _bulkJobId = null;
        toast('Generation failed: ' + (job.error || 'Unknown error'), 'error');
        closeModal();
      } else {
        _pollBulkJob(total);
      }
    } catch (_) {
      _pollBulkJob(total);
    }
  }, 2000);
}


// ── HEADER IMAGE PROMPTS ──────────────────────────────────────────────────────

function openHeaderPromptsModal(workId) {
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Generate Header Image Prompts</div>
    <p style="font-size:13px;color:var(--muted);margin:8px 0 16px;">
      Creates Imagen 3 prompts for each chapter that has a synopsis. Chapters without synopses are skipped.
      Run "Generate Assets" (synopsis) first if needed.
    </p>
    <div class="form-group" style="margin-bottom:16px;">
      <label class="form-label">Reference Image — optional</label>
      <input type="file" id="header-ref-img" accept="image/jpeg,image/png,image/webp"/>
      <div style="font-size:11px;color:var(--muted);margin-top:6px;">
        Upload a photo to guide the visual style. Gemini Flash will describe it and use the style as a guide.
        Requires GOOGLE_SA_KEY to be configured.
      </div>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" id="btn-header-gen" onclick="submitHeaderPrompts('${workId}')">Generate Prompts</button>
    </div>`;
  showModal();
}

async function submitHeaderPrompts(workId) {
  const btn = document.getElementById('btn-header-gen');
  btn.disabled    = true;
  btn.textContent = 'Generating...';

  try {
    const fileInput = document.getElementById('header-ref-img');
    const body = {};
    if (fileInput?.files[0]) {
      const file = fileInput.files[0];
      const b64  = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload  = () => resolve(reader.result.split(',')[1]);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      body.reference_image_b64  = b64;
      body.reference_image_mime = file.type || 'image/jpeg';
    }
    const res = await POST(`/api/works/${workId}/modules/bulk_generate_header_prompts`, body);
    closeModal();
    const errNote = res.errors?.length ? ` (${res.errors.length} error${res.errors.length !== 1 ? 's' : ''})` : '';
    toast(`Generated ${res.generated} header prompt${res.generated !== 1 ? 's' : ''}${res.skipped ? `, ${res.skipped} skipped` : ''}${errNote}`,
          res.errors?.length ? 'error' : 'success');
  } catch (e) {
    toast('Failed: ' + e.message, 'error');
    btn.disabled    = false;
    btn.textContent = 'Generate Prompts';
  }
}


// ── SCRIVENINGS VIEW ─────────────────────────────────────────────────────────

async function openScrivenings(workId) {
  try {
    const data = await GET(`/api/works/${workId}/scrivenings`);
    state.scrivengsWorkId = workId;
    state.scrivengsData   = data;
    renderCommandCenter();
  } catch (e) {
    toast('Could not load Scrivenings view: ' + e.message, 'error');
  }
}

function closeScrivenings() {
  state.scrivengsWorkId = null;
  state.scrivengsData   = null;
  renderCommandCenter();
}

function renderScrivenings(container) {
  const data    = state.scrivengsData || {};
  const modules = data.modules || [];
  const title   = data.work_title || 'Untitled Work';

  const totalWords = modules.reduce((sum, m) => sum + (m.prose || '').split(/\s+/).filter(Boolean).length, 0);

  container.innerHTML = `
    <div style="max-width:860px;margin:0 auto;padding:0 0 80px;">
      <div style="display:flex;justify-content:space-between;align-items:center;
                  padding:20px 0 16px;border-bottom:1px solid var(--border2);
                  margin-bottom:32px;position:sticky;top:0;background:var(--bg);z-index:10;">
        <div>
          <button class="btn-secondary" style="font-size:11px;" onclick="closeScrivenings()">&#x2190; Back to Inventory</button>
        </div>
        <div style="text-align:center;">
          <div style="font-size:14px;font-weight:600;">${esc(title)}</div>
          <div style="font-size:11px;color:var(--muted);">${modules.length} chapters \u00b7 ${totalWords.toLocaleString()} words</div>
        </div>
        <div style="display:flex;gap:8px;">
          <button class="btn-secondary" style="font-size:11px;" onclick="openImportChaptersModal('${state.scrivengsWorkId}', 'modules')">&#x2191; Import</button>
          <button class="btn-secondary" style="font-size:11px;" onclick="openBulkGenerateModal('${state.scrivengsWorkId}', 'modules')">&#x26A1; Assets</button>
        </div>
      </div>
      ${modules.length === 0
        ? `<div style="text-align:center;color:var(--muted);padding:60px 0;">
             No chapters yet.<br>
             <button class="btn-primary" style="margin-top:16px;" onclick="openImportChaptersModal('${state.scrivengsWorkId}', 'modules')">&#x2191; Import Chapters</button>
           </div>`
        : modules.map((mod, i) => `
          <div class="scriv-chapter" id="scriv-${mod.id}" style="margin-bottom:48px;">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
              <span style="font-family:var(--font-mono);font-size:10px;color:var(--muted);
                           min-width:24px;text-align:right;">${i + 1}</span>
              <input class="form-input" id="scriv-title-${mod.id}"
                     style="font-size:16px;font-weight:600;font-family:var(--font-serif,serif);
                            border:none;background:transparent;padding:4px 0;
                            border-bottom:1px solid transparent;flex:1;"
                     value="${esc(mod.title || '')}"
                     onblur="saveScriveningsTitle('${mod.id}', this.value)"
                     onfocus="this.style.borderBottomColor='var(--accent)'"
                     placeholder="Chapter title..."/>
              <span style="font-family:var(--font-mono);font-size:10px;color:var(--muted);white-space:nowrap;"
                    id="scriv-wc-${mod.id}">${(mod.prose || '').split(/\s+/).filter(Boolean).length} w</span>
            </div>
            <textarea id="scriv-prose-${mod.id}"
                      style="width:100%;min-height:320px;font-size:14px;line-height:1.8;
                             font-family:var(--font-serif,Georgia,serif);resize:vertical;
                             background:transparent;border:1px solid transparent;
                             border-radius:4px;padding:12px;color:var(--text);"
                      onfocus="this.style.borderColor='var(--border2)'"
                      onblur="saveScriveningsProse('${mod.id}','${mod.content_asset_id}','${state.scrivengsWorkId}',this.value);this.style.borderColor='transparent'"
                      oninput="updateScrivWordCount('${mod.id}', this.value)"
                      placeholder="Chapter prose...">${esc(mod.prose || '')}</textarea>
          </div>
        `).join('<hr style="border:none;border-top:1px dashed var(--border2);margin:0 0 48px;">')}
    </div>`;
}

async function saveScriveningsTitle(moduleId, newTitle) {
  try {
    await fetch(`/api/modules/${moduleId}`, {
      method:  'PUT',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ title: newTitle.trim() }),
    });
  } catch (e) { console.error('[Scrivenings] Title save failed', e); }
}

async function saveScriveningsProse(moduleId, contentAssetId, workId, prose) {
  try {
    // Upsert the Content asset — this is the single source of truth for chapter prose
    await fetch('/api/assets', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        id:         contentAssetId,
        type:       'content',
        title:      'Chapter Prose',
        work_id:    workId,
        module_id:  moduleId,
        content:    prose,
        production: prose.trim() ? 'done' : 'not_started',
      }),
    });
  } catch (e) { console.error('[Scrivenings] Prose save failed', e); }
}

function updateScrivWordCount(moduleId, prose) {
  const el = document.getElementById(`scriv-wc-${moduleId}`);
  if (el) el.textContent = prose.split(/\s+/).filter(Boolean).length + ' w';
}


// ── PROMOTION MACHINE: Broadcast Posts Sub-tab ────────────────────────────────

function renderBroadcastPosts() {
  const container = document.getElementById(
    'promo-view-broadcast-posts');
  if (!container) return;

  const total    = state.promoProverbs.length;
  const unused   = state.promoProverbs.filter(p => !p.used).length;
  const used     = total - unused;
  const pending  = state.promoProverbs.filter(
    p => p.queue_status === 'pending').length;
  const approved = state.promoProverbs.filter(
    p => p.queue_status === 'approved').length;
  const sent     = state.promoProverbs.filter(
    p => p.queue_status === 'sent').length;

  const filter   = state.broadcastPostFilter || 'pending';
  const filtered = state.promoProverbs.filter(
    p => p.queue_status === filter);

  container.innerHTML = `
    <div class="hub-panel">
      <div style="display:flex;justify-content:space-between;
                  align-items:flex-start;margin-bottom:24px;
                  flex-wrap:wrap;gap:16px;">
        <div>
          <h2 style="margin-bottom:4px;">Broadcast Posts</h2>
          <div style="font-size:12px;color:var(--muted);">
            ${unused} unused proverbs ·
            <span style="color:var(--p2); cursor:pointer;" onclick="state.broadcastPostFilter='pending';renderBroadcastPosts();">
              ${pending} pending
            </span> ·
            <span style="color:var(--p3); cursor:pointer;" onclick="state.broadcastPostFilter='approved';renderBroadcastPosts();">
              ${approved} approved
            </span> ·
            ${sent} sent
          </div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;
                    align-items:center;">
          <button class="btn-secondary" onclick="loadBroadcastPostQueue()" style="font-size:12px;">↻ Refresh</button>
          <select class="form-input"
            id="bulk-gen-count"
            style="width:70px;font-size:12px;">
            <option value="1">1</option>
            <option value="3">3</option>
            <option value="5" selected>5</option>
            <option value="10">10</option>
            <option value="20">20</option>
          </select>
          <button class="btn-secondary"
            id="btn-bulk-generate"
            onclick="bulkGenerateWaPosts()"
            style="font-size:12px;">
            ⚡ Bulk Generate
          </button>
          <button class="btn-secondary"
            id="btn-single-generate"
            onclick="singleGenerateWaPost()"
            style="font-size:12px;">
            + Generate One
          </button>
          ${approved > 0 ? `
          <button class="btn-primary"
            onclick="sendNextApprovedPost()"
            style="font-size:12px;background:var(--p3);
                   border-color:var(--p3);">
            📤 Send Next (${approved})
          </button>` : ''}
          ${pending > 0 ? `
          <button class="btn-secondary"
            onclick="bulkApproveAll()"
            style="font-size:12px;">
            ✓ Approve All (${pending})
          </button>` : ''}
        </div>
      </div>

      <div id="wa-queue-warning"
           style="display:none;background:#2a1414;
                  border-left:4px solid var(--p1);
                  padding:12px 16px;margin-bottom:16px;
                  border-radius:0 4px 4px 0;
                  font-size:13px;">
      </div>

      <div id="wa-bulk-progress"
           style="display:none;padding:12px 16px;
                  background:var(--surface2);
                  border:1px solid var(--border2);
                  border-radius:4px;margin-bottom:16px;
                  font-size:13px;color:var(--muted);">
      </div>

      <div style="display:flex;gap:6px;margin-bottom:20px;">
        ${['pending','approved','sent','rejected'].map(f => `
          <button class="btn-secondary
            ${filter === f ? ' active' : ''}"
            style="font-size:11px;padding:4px 10px;"
            onclick="state.broadcastPostFilter='${f}';
                     renderBroadcastPosts();">
            ${f.charAt(0).toUpperCase()+f.slice(1)}
            ${f === 'pending' ? `(${pending})`
              : f === 'approved' ? `(${approved})`
              : f === 'sent' ? `(${sent})` : ''}
          </button>
        `).join('')}
      </div>

      ${filtered.length === 0 ? `
        <div style="text-align:center;padding:60px 20px;
                    color:var(--muted);font-size:14px;">
          No ${filter} posts.
          ${filter === 'pending'
            ? ' Click Bulk Generate to create some.'
            : ''}
        </div>
      ` : `
        <div class="broadcast-post-grid">
          ${filtered.map(p => renderWaPostCard(p))
                    .join('')}
        </div>
      `}

      <div style="margin-top:40px;
                  border-top:1px solid var(--border);
                  padding-top:24px;">
        <div style="display:flex;justify-content:
                    space-between;align-items:center;
                    margin-bottom:12px;">
          <h3 style="margin:0;">Proverbs Library</h3>
          <div style="display:flex;gap:8px;">
            <button class="btn-secondary"
              style="font-size:11px;"
              onclick="openImportProverbsModal()">
              Import JSON
            </button>
            <button class="btn-secondary"
              style="font-size:11px;"
              onclick="openAddProverbModal()">
              + Add
            </button>
          </div>
        </div>
        <span style="font-size:12px;color:var(--muted);">
          ${total} total · ${unused} unused · ${used} used
        </span>
        <table class="promo-table" style="margin-top:10px;">
          <thead>
            <tr>
              <th>Proverb</th>
              <th>Origin</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody id="proverbs-tbody">
            ${renderProverbsTableRows(
              state.promoProverbs)}
          </tbody>
        </table>
      </div>
    </div>`;
}

function renderWaPostCard(p) {
  const filename = p.composite_path
    ? p.composite_path.split('/').pop()
    : null;
  const imgUrl = filename
    ? `/data/images/${filename}?t=${Date.now()}`
    : null;

  const statusColour = {
    pending:  'var(--muted)',
    approved: 'var(--p3)',
    sent:     'var(--p4)',
    rejected: 'var(--p1)'
  }[p.queue_status] || 'var(--muted)';

  return `
    <div class="broadcast-post-card"
         id="wa-card-${p.id}">
      <div class="broadcast-post-card-img">
        ${imgUrl
          ? `<img src="${imgUrl}"
                  style="width:100%;height:100%;
                         object-fit:cover;
                         border-radius:4px 4px 0 0;"/>`
          : `<div style="width:100%;height:100%;
                         display:flex;align-items:center;
                         justify-content:center;
                         color:var(--muted);font-size:12px;">
               No image
             </div>`
        }
      </div>
      <div class="broadcast-post-card-body">
        <div style="font-size:11px;font-weight:600;
                    color:${statusColour};
                    text-transform:uppercase;
                    margin-bottom:6px;">
          ● ${p.queue_status}
        </div>
        <div style="font-size:12px;font-weight:600;
                    margin-bottom:4px;
                    color:var(--text);"
             title="${esc(p.text)}">
          ${esc(p.text.length > 80
            ? p.text.slice(0,80)+'...'
            : p.text)}
        </div>
        <div style="font-size:11px;color:var(--muted);
                    line-height:1.4;margin-bottom:10px;"
             title="${esc(p.meaning||'')}">
          ${esc((p.meaning||'').slice(0,100))}${
            (p.meaning||'').length > 100 ? '...' : ''}
        </div>
        <div class="broadcast-post-card-actions">
          ${p.queue_status === 'pending' ? `
            <button class="btn-secondary"
              style="font-size:11px;padding:3px 8px;
                     color:var(--p3);"
              onclick="approveWaPost('${p.id}')">
              ✓ Approve
            </button>
            <button class="btn-secondary"
              style="font-size:11px;padding:3px 8px;"
              onclick="regenWaPostImage('${p.id}')">
              ↻ New Image
            </button>
            <button class="btn-secondary"
              style="font-size:11px;padding:3px 8px;
                     color:var(--p1);"
              onclick="rejectWaPost('${p.id}')">
              ✕
            </button>
          ` : ''}
          ${p.queue_status === 'approved' ? (() => {
            const isQueued = (state.promoMessages || []).some(m => m.proverb_id === p.id && m.status === 'queued');
            return `
            ${isQueued ? `
              <span style="font-size:11px;font-weight:700;color:var(--p2);padding:6px 8px;">
                ✓ Queued
              </span>
            ` : `
              <button class="btn-primary"
                style="font-size:11px;padding:3px 8px;
                       background:var(--p2);
                       border-color:var(--p2);"
                onclick="queueProverbToOutbox('${p.id}')">
                📤 Send to Outbox
              </button>
            `}
            <button class="btn-primary"
              style="font-size:11px;padding:3px 12px;
                     background:var(--p3);
                     border-color:var(--p3);"
              onclick="sendThisPost('${p.id}')">
              🚀 Send Now
            </button>
            <button class="btn-secondary"
              style="font-size:11px;padding:3px 8px;
                     color:var(--muted);"
              onclick="setPendingWaPost('${p.id}')">
              ← Undo
            </button>
          `})() : ''}
          ${p.queue_status === 'sent' ? `
            <span style="font-size:11px;
                         color:var(--muted);">
              Sent ${p.sent_at
                ? new Date(p.sent_at)
                    .toLocaleDateString()
                : ''}
            </span>
          ` : ''}
        </div>
      </div>
    </div>`;
}

async function bulkGenerateWaPosts() {
  const btn = document.getElementById(
    'btn-bulk-generate');
  const countEl = document.getElementById(
    'bulk-gen-count');
  const progress = document.getElementById(
    'wa-bulk-progress');
  const count = countEl ? parseInt(countEl.value) : 5;

  btn.disabled = true;
  btn.textContent = 'Generating...';
  progress.style.display = 'block';
  progress.textContent =
    `Generating ${count} posts — this will take `+
    `${count * 20}–${count * 40} seconds. Please wait...`;

  try {
    const res = await POST(
      '/api/promo/broadcast_post/bulk_generate',
      { count });
    if (res.generated > 0) {
      toast(
        `Generated ${res.generated} posts.` +
        (res.errors > 0
          ? ` ${res.errors} failed.` : ''),
        res.errors > 0 ? 'info' : 'success');
    } else {
      toast(
        res.error || 'Generation failed.', 'error');
    }
    state.broadcastPostFilter = 'pending';
    await loadBroadcastPostQueue();
  } catch(e) {
    toast('Bulk generate failed: ' + e.message,
          'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '⚡ Bulk Generate';
    progress.style.display = 'none';
  }
}

async function singleGenerateWaPost() {
  const btn = document.getElementById(
    'btn-single-generate');
  btn.disabled = true;
  btn.textContent = 'Generating...';
  try {
    const res = await POST(
      '/api/promo/broadcast_post/generate');
    if (res.error) {
      toast(res.error, 'error'); return;
    }
    toast('Post generated.', 'success');
    state.broadcastPostFilter = 'pending';
    await loadBroadcastPostQueue();
  } catch(e) {
    toast('Generate failed: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '+ Generate One';
  }
}

async function approveWaPost(id) {
  try {
    await POST(`/api/promo/broadcast_post/${id}/status`,
      { status: 'approved' });
    toast('Approved.', 'success');
    // Ensure we keep the pending view if that's where we were, 
    // but the approved post will naturally move out of 'filtered'.
    await loadBroadcastPostQueue();
  } catch(e) {
    toast('Failed: ' + e.message, 'error');
  }
}

async function rejectWaPost(id) {
  try {
    await POST(`/api/promo/broadcast_post/${id}/status`,
      { status: 'rejected' });
    await loadBroadcastPostQueue();
  } catch(e) {
    toast('Failed: ' + e.message, 'error');
  }
}

async function setPendingWaPost(id) {
  try {
    await POST(`/api/promo/broadcast_post/${id}/status`,
      { status: 'pending' });
    await loadBroadcastPostQueue();
  } catch(e) {
    toast('Failed: ' + e.message, 'error');
  }
}

async function bulkApproveAll() {
  try {
    const res = await POST('/api/promo/broadcast_post/bulk_approve');
    if (res.ec2_synced === false) {
      toast(`${res.approved} posts approved — ${res.ec2_failures} EC2 sync failure(s). Those may not auto-fire.`, 'error');
    } else {
      toast(`${res.approved} posts approved and synced to EC2.`, 'success');
    }
    state.broadcastPostFilter = 'approved';
    await loadBroadcastPostQueue();
  } catch(e) {
    toast('Failed: ' + e.message, 'error');
  }
}

async function regenWaPostImage(id) {
  const card = document.getElementById(
    `wa-card-${id}`);
  if (card) {
    card.style.opacity = '0.5';
    card.style.pointerEvents = 'none';
  }
  try {
    const res = await POST(
      `/api/promo/broadcast_post/${id}/regen_image`);
    if (res.ok) {
      toast('New image generated.', 'success');
      await loadBroadcastPostQueue();
    } else {
      toast(res.error || 'Regen failed.', 'error');
    }
  } catch(e) {
    toast('Regen failed: ' + e.message, 'error');
    if (card) {
      card.style.opacity = '1';
      card.style.pointerEvents = 'auto';
    }
  }
}

async function queueProverbToOutbox(id, forceText = false, forceRetry = false) {
  try {
    const res = await POST(`/api/promo/broadcast_post/${id}/queue`, { 
        force_text: forceText,
        force_retry: forceRetry 
    });
    if (res.ok) {
      if (res.ec2_synced === false) {
        const msg = `Added locally, but EC2 sync failed: ${res.error || 'S3 upload error'}.\n\nBroadcast posts require an image to look correct. Do you want to override and send as TEXT ONLY instead?`;
        if (confirm(msg)) {
           return queueProverbToOutbox(id, true);
        }
      } else if (res.already_exists) {
        const msg = "This proverb is already in your Outbox.\n\nIf it hasn't appeared on your EC2 queue, do you want to remove it and RE-QUEUE it now?";
        if (confirm(msg)) {
           return queueProverbToOutbox(id, false, true);
        }
      } else {
        toast(forceText ? 'Queued as text (override successful).' : 'Added to Outbox', 'success');
      }
      await Promise.all([
          loadPromoMessages(),
          loadBroadcastPostQueue()
      ]);
    } else {
      toast(res.error || 'Failed to queue.', 'error');
    }
  } catch(e) {
    toast('Queue failed: ' + e.message, 'error');
  }
}

async function sendThisPost(id) {
  try {
    const res = await POST(
      `/api/promo/broadcast_post/${id}/send`);
    if (res.ok) {
      toast('Posted to channel!', 'success');
      state.broadcastPostFilter = 'approved';
      await loadBroadcastPostQueue();
    } else {
      toast(res.error || 'Send failed.', 'error');
    }
  } catch(e) {
    toast('Send failed: ' + e.message, 'error');
  }
}

async function sendNextApprovedPost() {
  try {
    const res = await POST(
      '/api/promo/broadcast_post/send_next');
    if (res.ok) {
      toast(
        `Sent: "${res.proverb.slice(0,50)}..."`,
        'success');
      await loadBroadcastPostQueue();
    } else {
      toast(
        res.message || res.error || 'Nothing to send.',
        'info');
    }
  } catch(e) {
    toast('Failed: ' + e.message, 'error');
  }
}

// Stub for cleanup
async function generateWaPost() {}
async function sendWaPost() {}

// Stub to remove old helper functions that are no longer needed
function toggleWaPostSchedule() {}
function updateWaPostPhoneLabel() {}
async function queueWaPost() {}

function renderProverbsTableRows(items) {
  if (!items || items.length === 0)
    return '<tr><td colspan="4" style="text-align:center;' +
           'color:var(--muted);padding:20px;">' +
           'No proverbs found.</td></tr>';
  return items.map(p => `
    <tr>
      <td title="${esc(p.text)}" style="max-width:300px;">
        ${esc(p.text.length > 70
          ? p.text.slice(0, 70) + '...'
          : p.text)}
      </td>
      <td>${esc(p.origin || '')}</td>
      <td>${p.used
        ? '<span style="color:var(--p3);">● Used</span>'
        : '<span style="color:var(--muted);">○ Unused</span>'}
      </td>
      <td>
        <div style="display:flex;gap:4px;">
          <button class="btn-secondary"
            style="padding:2px 8px;font-size:11px;"
            onclick="openEditProverbModal('${p.id}')">
            Edit
          </button>
          ${p.used ? `
          <button class="btn-secondary"
            style="padding:2px 8px;font-size:11px;"
            onclick="markProverbUnused('${p.id}')">
            Reset
          </button>` : ''}
          <button class="btn-secondary"
            style="padding:2px 8px;font-size:11px;
                   color:var(--p1);"
            onclick="deleteProverb('${p.id}')">
            Delete
          </button>
        </div>
      </td>
    </tr>
  `).join('');
}

function filterProverbs(filter, btn) {
  if (!btn) return;
  document.querySelectorAll('.btn-group button, #promo-view-broadcast-posts .btn-secondary')
    .forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  let items = state.promoProverbs;
  if (filter === 'unused') items = items.filter(p => !p.used);
  else if (filter === 'used')   items = items.filter(p =>  p.used);
  const el = document.getElementById('proverbs-tbody');
  if (el) el.innerHTML = renderProverbsTableRows(items);
}

async function deleteProverb(id) {
  if (!confirm(
    'Delete this proverb? This cannot be undone.'))
    return;
  try {
    await DEL(`/api/promo/proverbs/${id}`);
    toast('Proverb deleted.', 'success');
    loadPromoProverbs();
  } catch(e) {
    toast('Delete failed: ' + e.message, 'error');
  }
}

async function markProverbUnused(id) {
  try {
    await PUT(`/api/promo/proverbs/${id}`,
      { used: false });
    toast('Proverb marked as unused.', 'success');
    loadPromoProverbs();
  } catch(e) {
    toast('Reset failed: ' + e.message, 'error');
  }
}

function openEditProverbModal(id) {
  const p = state.promoProverbs.find(x => x.id === id);
  if (!p) return;
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Edit Proverb</div>
    <div class="form-group">
      <label class="form-label">Text *</label>
      <textarea class="form-textarea"
        id="edit-pr-text"
        rows="3">${esc(p.text)}</textarea>
    </div>
    <div class="form-group">
      <label class="form-label">Origin</label>
      <input class="form-input" id="edit-pr-origin"
        value="${esc(p.origin || '')}"/>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary"
        onclick="closeModal()">Cancel</button>
      <button class="btn-primary"
        onclick="saveEditedProverb('${id}')">
        Save Changes
      </button>
    </div>`;
  showModal();
}

async function saveEditedProverb(id) {
  const text = document.getElementById(
    'edit-pr-text').value.trim();
  const origin = document.getElementById(
    'edit-pr-origin').value.trim();
  if (!text) {
    toast('Proverb text cannot be empty.', 'error');
    return;
  }
  try {
    await PUT(`/api/promo/proverbs/${id}`,
      { text, origin });
    toast('Proverb updated.', 'success');
    closeModal();
    loadPromoProverbs();
  } catch(e) {
    toast('Update failed: ' + e.message, 'error');
  }
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

function _renderOutboxRow(m) {
  const isTimed     = !!m.scheduled_at;
  const statusColor = m.status === 'sent' ? 'var(--p3)' : (m.status === 'failed' ? 'var(--p1)' : 'var(--p2)');
  const sourceLabel = m.source === 'wa_post_maker' ? 'broadcast'
                    : m.source === 'work_serializer' ? 'serializer'
                    : m.source === 'message_maker' ? 'message'
                    : m.source;
  return `
  <tr>
    <td>
      <input type="checkbox" class="outbox-check"
             ${(state.selectedOutboxMessages || []).includes(m.id) ? 'checked' : ''}
             ${m.status === 'sent' ? 'disabled' : ''}
             onchange="toggleOutboxSelection('${m.id}', this.checked)">
    </td>
    <td>
      <div style="font-weight:600;font-size:13px;">${esc(m.recipient_name)}</div>
      <div style="font-size:11px;color:var(--muted);">${esc(m.recipient_phone)}</div>
    </td>
    <td title="${esc(m.content)}">
      <div style="font-size:12px;max-width:400px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
        ${m.media_url ? '🖼️ ' : ''}${esc(m.content)}
      </div>
    </td>
    <td>
      <span style="font-size:10px;font-weight:700;color:${statusColor};text-transform:uppercase;">
        ● ${m.status}
      </span>
    </td>
    <td>
      ${isTimed ? `
        <div style="font-size:11px;color:var(--p2);">🕒 ${formatDateShort(m.scheduled_at)}</div>
        <div style="font-size:10px;color:var(--muted);">EC2 auto-fires</div>
      ` : `
        <div style="font-size:11px;color:var(--muted);">No schedule set</div>
      `}
    </td>
    <td>
      <span class="badge" style="background:var(--surface);border:1px solid var(--border);font-size:10px;">
        ${sourceLabel}
      </span>
    </td>
    <td>
      <div style="display:flex;gap:4px;flex-wrap:wrap;">
        ${m.status === 'queued' || m.status === 'failed' ? `
          <button class="btn-secondary" style="padding:2px 8px;font-size:10px;"
                  title="Fires immediately via EC2, bypassing the schedule."
                  onclick="dispatchOutboxItemNow('${m.id}')">Fire Now</button>
          <button class="btn-secondary" style="padding:2px 8px;font-size:10px;"
                  title="Send preview to +27822909093 via EC2."
                  onclick="previewOutboxMessage('${m.id}')">Preview</button>
          <button class="btn-secondary" style="padding:2px 8px;font-size:10px;"
                  onclick="openEditMessageModal('${m.id}')">Edit</button>
          <button class="btn-secondary" style="padding:2px 8px;font-size:10px;color:var(--p1);"
                  onclick="deleteQueueMessage('${m.id}')">Delete</button>
        ` : ''}
        ${(m.status === 'sent' || m.status === 'queued') && !m.lead_id && !m.source_ref?.lead_id
          && ['manual_single','manual_outbound','message_maker','crm_assist'].includes(m.source) ? `
          <button class="btn-secondary" style="padding:2px 8px;font-size:10px;color:var(--p2);"
                  onclick="openCreateDealFromMessageModal('${m.id}')">+ Deal</button>
        ` : ''}
      </div>
    </td>
  </tr>`;
}

function renderPromoSender() {
  const container = document.getElementById('promo-view-sender');
  if (!container) return;

  const msgs         = state.promoMessages;
  const active       = msgs.filter(m => m.status === 'queued' || m.status === 'failed');
  const history      = msgs.filter(m => m.status === 'sent');
  const selectedCount = (state.selectedOutboxMessages || []).length;
  const failedCount  = active.filter(m => m.status === 'failed').length;

  const TABLE_HEADER = `
    <table class="promo-table">
      <thead>
        <tr>
          <th style="width:40px;"></th>
          <th style="width:160px;">Recipient</th>
          <th>Content Preview</th>
          <th style="width:100px;">Status</th>
          <th style="width:140px;">Delivery</th>
          <th style="width:120px;">Source</th>
          <th style="width:200px;">Actions</th>
        </tr>
      </thead>`;

  container.innerHTML = `
    <div class="hub-panel" style="max-width:1300px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px;">
        <div>
          <h2>Outbox (The Bucket)</h2>
          <div style="font-size:12px;color:var(--muted);">
            ${active.length} pending · ${failedCount > 0 ? `<span style="color:var(--p1)">${failedCount} failed</span> · ` : ''}${history.length} sent
          </div>
        </div>
        <div style="display:flex;gap:8px;">
          <button class="btn-secondary" onclick="loadPromoMessages()" style="font-size:12px;">↻ Refresh</button>
          <button class="btn-primary" onclick="popNextFromBucket()"
                  style="font-size:12px;background:var(--p3);border-color:var(--p3);"
                  title="Fires the next due message via EC2, bypassing the schedule.">
            🚀 Fire Next Due (EC2)
          </button>
        </div>
      </div>

      <div style="display:flex;justify-content:flex-end;align-items:center;margin-bottom:16px;gap:12px;">
        ${selectedCount > 0 ? `
          <span style="font-size:12px;font-weight:600;color:var(--p3);">${selectedCount} selected</span>
          <button class="btn-primary" onclick="sendSelectedOutboxNow()"
                  style="font-size:11px;padding:6px 16px;background:var(--p3);border-color:var(--p3);">
            🚀 Send Selected Now
          </button>
          <button class="btn-secondary" onclick="state.selectedOutboxMessages=[]; renderPromoSender()"
                  style="font-size:11px;padding:6px 12px;">Clear Selection</button>
        ` : `
          <span style="font-size:12px;color:var(--muted);">Select messages to bulk send</span>
        `}
      </div>

      ${TABLE_HEADER}
        <tbody>
          ${active.length === 0
            ? '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:60px;">Queue is empty — nothing pending.</td></tr>'
            : active.map(m => _renderOutboxRow(m)).join('')}
        </tbody>
      </table>

      ${history.length > 0 ? `
        <details style="margin-top:32px;">
          <summary style="cursor:pointer;font-size:13px;font-weight:600;color:var(--muted);
                          padding:10px 0;border-top:1px solid var(--border);list-style:none;
                          display:flex;justify-content:space-between;align-items:center;">
            <span>▶ History (${history.length} sent)</span>
            <button class="btn-secondary" style="font-size:11px;padding:4px 12px;color:var(--p1);"
                    onclick="event.stopPropagation();clearOutboxHistory()">Clear History</button>
          </summary>
          <div style="margin-top:12px;">
            ${TABLE_HEADER}
              <tbody>
                ${history.map(m => _renderOutboxRow(m)).join('')}
              </tbody>
            </table>
          </div>
        </details>
      ` : ''}
    </div>`;
}

function toggleOutboxSelection(id, checked) {
  if (!state.selectedOutboxMessages) state.selectedOutboxMessages = [];
  if (checked) {
    if (!state.selectedOutboxMessages.includes(id)) state.selectedOutboxMessages.push(id);
  } else {
    state.selectedOutboxMessages = state.selectedOutboxMessages.filter(x => x !== id);
  }
  renderPromoSender();
}

function toggleAllOutboxSelection(checked) {
  const targetIds = state.promoMessages.filter(m => m.status === 'queued' || m.status === 'failed').map(m => m.id);
  
  if (checked) {
    state.selectedOutboxMessages = targetIds;
  } else {
    state.selectedOutboxMessages = [];
  }
  renderPromoSender();
}

async function sendSelectedOutboxNow() {
  const ids = state.selectedOutboxMessages || [];
  if (!ids.length) return;
  if (!confirm(`Send ${ids.length} selected message(s) immediately? This bypasses the schedule.`)) return;
  
  try {
    const res = await POST('/api/promo/messages/bulk_send_now', { ids });
    if (res.ok) {
      toast(`Successfully sent ${res.sent} message(s).`, 'success');
      state.selectedOutboxMessages = [];
      loadPromoMessages();
    } else {
      toast(res.error || 'Bulk send failed', 'error');
    }
  } catch(e) { toast('Error: ' + e.message, 'error'); }
}

async function dispatchOutboxItemNow(id) {
    try {
        const res = await POST('/api/promo/messages/bulk_send_now', { ids: [id] });
        if (res.ok && res.sent > 0) {
            toast('Message sent via EC2', 'success');
            loadPromoMessages();
        } else {
            const errDetail = res.errors && res.errors.length ? `: ${res.errors[0]}` : '';
            toast(`Send failed${errDetail}`, 'error');
        }
    } catch(e) { toast('Send failed', 'error'); }
}

async function previewOutboxMessage(id) {
  try {
    const res = await POST(`/api/promo/messages/${id}/preview`);
    if (res.ok) {
      toast('Preview sent to +27822909093', 'success');
    } else {
      toast(`Preview failed: ${res.error || 'Unknown error'}`, 'error');
    }
  } catch(e) { toast('Preview failed: ' + e.message, 'error'); }
}

async function clearOutboxHistory() {
  if (!confirm('Clear all sent messages from history? This cannot be undone.')) return;
  try {
    const res = await DEL('/api/promo/messages/history');
    if (res.ok) {
      toast(`History cleared — ${res.cleared} message(s) removed.`, 'success');
      loadPromoMessages();
    } else {
      toast('Clear failed', 'error');
    }
  } catch(e) { toast('Clear failed: ' + e.message, 'error'); }
}

async function popNextFromBucket() {
  try {
    const res = await POST('/api/promo/sender/pop_next');
    if (res.ok) {
      toast('Message dispatched via EC2', 'success');
      loadPromoMessages();
    } else {
      toast(res.message || res.error || 'Bucket empty or no messages due', 'info');
    }
  } catch (e) { toast('Execution failed', 'error'); }
}

async function deleteQueueMessage(id) {
  if (!confirm('Remove this message from the Outbox?')) return;
  try {
    const r = await DEL(`/api/promo/messages/${id}`);
    if (r.ec2_synced === false) {
      toast('Removed locally — EC2 sync failed. Message may still send at its scheduled time.', 'error');
    } else {
      toast('Removed from Outbox and EC2 queue', 'success');
    }
    loadPromoMessages();
  } catch (e) { toast('Delete failed', 'error'); }
}

function openEditMessageModal(id) {
  const m = state.promoMessages.find(x => x.id === id);
  if (!m) return;
  
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">Edit Queued Message</div>
    <div class="form-group">
      <label class="form-label">Recipient Name</label>
      <input class="form-input" id="edit-msg-name" value="${esc(m.recipient_name)}"/>
    </div>
    <div class="form-group">
      <label class="form-label">Phone Number</label>
      <input class="form-input" id="edit-msg-phone" value="${esc(m.recipient_phone)}"/>
    </div>
    <div class="form-group">
      <label class="form-label">Scheduled Time (Optional ISO or YYYY-MM-DD HH:MM)</label>
      <input class="form-input" id="edit-msg-time" value="${m.scheduled_at || ''}" placeholder="Leave empty for FIFO"/>
    </div>
    <div class="form-group">
      <label class="form-label">Content</label>
      <textarea class="form-textarea" id="edit-msg-content" rows="5">${esc(m.content)}</textarea>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="saveEditedMessage('${id}')">Update Message</button>
    </div>`;
  showModal();
}

async function saveEditedMessage(id) {
  const payload = {
    recipient_name:  document.getElementById('edit-msg-name').value.trim(),
    recipient_phone: document.getElementById('edit-msg-phone').value.trim(),
    content:         document.getElementById('edit-msg-content').value,
    scheduled_at:    document.getElementById('edit-msg-time').value.trim() || null
  };
  
  try {
    await PUT(`/api/promo/messages/${id}`, payload);
    toast('Message updated', 'success');
    closeModal();
    loadPromoMessages();
  } catch (e) { toast('Update failed: ' + e.message, 'error'); }
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

function openCreateDealFromMessageModal(messageId) {
  const msg = state.promoMessages.find(m => m.id === messageId);
  if (!msg) return;

  const contacts = state.promoContacts || [];
  const contactOptions = contacts.map(c => `<option value="${c.id}">${esc(c.name)} (${esc(c.phone)})</option>`).join('');

  document.getElementById('modal-content').innerHTML = `
    <div class="modal-title">+ Create Deal from Message</div>
    <div class="promo-settings-section" style="font-size:12px;color:var(--muted);margin-bottom:16px;">
      Message: "${esc((msg.content || '').slice(0, 80))}${msg.content && msg.content.length > 80 ? '...' : ''}"
    </div>
    <div class="form-group">
      <label class="form-label">Link to Contact *</label>
      <select class="form-select" id="cdm-contact">
        <option value="">-- Select Contact --</option>
        ${contactOptions}
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Product / Deal Name *</label>
      <input class="form-input" id="cdm-product" placeholder="e.g. Golf Day Sponsorship" />
    </div>
    <div class="form-group">
      <label class="form-label">Product Type</label>
      <select class="form-select" id="cdm-type">
        <option value="event">Event</option>
        <option value="campaign">Campaign</option>
        <option value="membership">Membership</option>
        <option value="other">Other</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <textarea class="form-textarea" id="cdm-notes" placeholder="Context for this deal..."></textarea>
    </div>
    <div class="modal-actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="saveDealFromMessage('${messageId}')">Create Deal</button>
    </div>`;
  showModal();
}

async function saveDealFromMessage(messageId) {
  const contactId = document.getElementById('cdm-contact').value;
  const product = document.getElementById('cdm-product').value.trim();
  const productType = document.getElementById('cdm-type').value;
  const notes = document.getElementById('cdm-notes').value.trim();

  if (!contactId) { toast('Please select a contact', 'error'); return; }
  if (!product) { toast('Product name is required', 'error'); return; }

  try {
    const res = await POST(`/api/promo/messages/${messageId}/create_deal`, {
      contact_id: contactId,
      product,
      product_type: productType,
      notes
    });
    toast('Deal created successfully', 'success');
    closeModal();
    loadPromoMessages();
  } catch(e) { toast('Failed to create deal: ' + e.message, 'error'); }
}

function sendViaExtension(phone, message, message_id) {
  if (!document.body.dataset.whatsappExtension) {
    toast('WhatsApp Chrome Extension not detected. Is it installed and enabled?', 'error');
    return false;
  }
  document.dispatchEvent(new CustomEvent('WHATSAPP_CRM_SEND', {
    detail: { phone, message, message_id }
  }));
  toast('Sending via WhatsApp extension...', 'info');
  return true;
}

async function sendQueuedMessageViaExtension(id) {
  const m = state.promoMessages.find(x => x.id === id);
  if (!m) return;
  if (!m.recipient_phone) {
    toast('No recipient phone found for this message.', 'error');
    return;
  }
  sendViaExtension(m.recipient_phone, m.content, m.id);
}

function getWaRecipientPhone(recipient) {
  const r = state.promoSettings?.publishing_wa_recipients || {};
  return recipient === 'vip_group'
    ? (r.vip_group_id || '')
    : (r.channel_id || '');
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
    const r = await POST(`/api/promo/messages/${id}/reschedule`, { scheduled_at: time });
    if (r.ec2_synced === false) {
      toast('Rescheduled locally — EC2 sync failed. Old time may still fire.', 'error');
    } else {
      toast('Updated', 'success');
    }
    loadPromoMessages();
  } catch (e) { toast('Failed to update', 'error'); }
}

async function deleteMessage(id) {
  if (!confirm('Delete this message?')) return;
  try {
    const r = await DEL(`/api/promo/messages/${id}`);
    if (r.ec2_synced === false) {
      toast('Deleted locally — EC2 sync failed. Message may still send.', 'error');
    } else {
      toast('Deleted', 'success');
    }
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
        ${renderAiProviderFields('message_maker',   'Message Maker',    p.message_maker)}
        ${renderAiProviderFields('work_serializer', 'Work Serializer',  p.work_serializer)}
        ${renderAiProviderFields('wa_post_maker',   'Broadcast Posts',  p.wa_post_maker)}
        ${renderAiProviderFields('crm_assist',      'CRM AI Assist',    p.crm_assist)}
        ${renderAiProviderFields('asset_generator', 'Asset Generator',  p.asset_generator)}
        
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

      <div class="promo-settings-section">
        <h3>Delivery Schedule</h3>
        <p style="font-size:11px;color:var(--muted);margin-bottom:16px;">
          When you queue a story chunk, the system picks the next available slot automatically.
          Sunday is the lighter day (max 1 post). All times are local (SAST, UTC+2).
        </p>
        ${(() => {
          const ds = s.delivery_schedule || {};
          const slots = ds.slots || [];
          return `
          <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px;">
            <div class="form-group" style="flex:1;min-width:120px;">
              <label class="form-label">Max Posts / Day</label>
              <input class="form-input" id="ds-max-per-day" type="number" min="1" max="6" value="${ds.max_posts_per_day ?? 3}"/>
            </div>
            <div class="form-group" style="flex:1;min-width:120px;">
              <label class="form-label">Min Spacing (hrs)</label>
              <input class="form-input" id="ds-min-spacing" type="number" min="1" max="12" value="${ds.min_spacing_hours ?? 3}"/>
            </div>
            <div class="form-group" style="flex:1;min-width:120px;">
              <label class="form-label">Lighter Day Max Posts</label>
              <input class="form-input" id="ds-lighter-max" type="number" min="0" max="3" value="${ds.lighter_day_max_posts ?? 1}"/>
            </div>
          </div>

          <div class="form-label" style="margin-bottom:8px;">Time Slots</div>
          <div id="ds-slots-list">
            ${slots.map((slot, i) => `
            <div class="ds-slot-row" data-idx="${i}" style="display:flex;gap:8px;align-items:flex-end;margin-bottom:10px;padding:10px;background:var(--surface);border:1px solid var(--border);border-radius:6px;">
              <div class="form-group" style="flex:2;margin:0;">
                <label class="form-label" style="font-size:10px;">Label</label>
                <input class="form-input ds-slot-label" style="font-size:12px;" value="${esc(slot.label || slot.name)}" placeholder="e.g. Morning Proverbs"/>
              </div>
              <div class="form-group" style="flex:1;margin:0;">
                <label class="form-label" style="font-size:10px;">Start</label>
                <input class="form-input ds-slot-start" type="time" style="font-size:12px;" value="${slot.window_start}"/>
              </div>
              <div class="form-group" style="flex:1;margin:0;">
                <label class="form-label" style="font-size:10px;">End</label>
                <input class="form-input ds-slot-end" type="time" style="font-size:12px;" value="${slot.window_end}"/>
              </div>
              <div class="form-group" style="flex:2;margin:0;">
                <label class="form-label" style="font-size:10px;">Content Types (comma-separated)</label>
                <input class="form-input ds-slot-types" style="font-size:12px;" value="${esc((slot.content_types || []).join(', '))}" placeholder="story, proverb, engagement"/>
              </div>
              <button class="btn-secondary" style="font-size:11px;padding:4px 8px;color:var(--p1);flex-shrink:0;" onclick="removeDsSlot(${i})">✕</button>
            </div>`).join('')}
          </div>
          <button class="btn-secondary" style="font-size:12px;margin-top:4px;" onclick="addDsSlot()">+ Add Slot</button>
          `;
        })()}
      </div>

      <div class="promo-settings-section">
        <h3>WhatsApp Recipients</h3>
        <p style="font-size:11px;color:var(--muted);margin-bottom:12px;">WhatsApp Channels and Groups use IDs (not phone numbers). Paste the full ID for each recipient here.</p>
        <div style="display:flex;gap:12px;margin-bottom:12px;">
          <div class="form-group" style="flex:1;"><label class="form-label">VIP Group ID</label><input class="form-input" id="set-wa-vip-id" value="${esc(s.publishing_wa_recipients?.vip_group_id)}"/></div>
          <div class="form-group" style="flex:1;"><label class="form-label">VIP Group Label</label><input class="form-input" id="set-wa-vip-label" value="${esc(s.publishing_wa_recipients?.vip_group_label || 'VIP WhatsApp Group')}"/></div>
        </div>
        <div style="display:flex;gap:12px;">
          <div class="form-group" style="flex:1;"><label class="form-label">WA Channel ID</label><input class="form-input" id="set-wa-chan-id" value="${esc(s.publishing_wa_recipients?.channel_id)}"/></div>
          <div class="form-group" style="flex:1;"><label class="form-label">WA Channel Label</label><input class="form-input" id="set-wa-chan-label" value="${esc(s.publishing_wa_recipients?.channel_label || 'WA Channel')}"/></div>
        </div>
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

function addDsSlot() {
  const list = document.getElementById('ds-slots-list');
  if (!list) return;
  const idx = list.querySelectorAll('.ds-slot-row').length;
  const row = document.createElement('div');
  row.className = 'ds-slot-row';
  row.dataset.idx = idx;
  row.style.cssText = 'display:flex;gap:8px;align-items:flex-end;margin-bottom:10px;padding:10px;background:var(--surface);border:1px solid var(--border);border-radius:6px;';
  row.innerHTML = `
    <div class="form-group" style="flex:2;margin:0;"><label class="form-label" style="font-size:10px;">Label</label><input class="form-input ds-slot-label" style="font-size:12px;" placeholder="e.g. Afternoon"/></div>
    <div class="form-group" style="flex:1;margin:0;"><label class="form-label" style="font-size:10px;">Start</label><input class="form-input ds-slot-start" type="time" style="font-size:12px;" value="12:00"/></div>
    <div class="form-group" style="flex:1;margin:0;"><label class="form-label" style="font-size:10px;">End</label><input class="form-input ds-slot-end" type="time" style="font-size:12px;" value="13:00"/></div>
    <div class="form-group" style="flex:2;margin:0;"><label class="form-label" style="font-size:10px;">Content Types</label><input class="form-input ds-slot-types" style="font-size:12px;" placeholder="story, engagement"/></div>
    <button class="btn-secondary" style="font-size:11px;padding:4px 8px;color:var(--p1);flex-shrink:0;" onclick="this.closest('.ds-slot-row').remove()">✕</button>`;
  list.appendChild(row);
}

function removeDsSlot(idx) {
  const rows = document.querySelectorAll('.ds-slot-row');
  if (rows[idx]) rows[idx].remove();
}

function _collectDeliverySchedule() {
  const slots = [];
  document.querySelectorAll('.ds-slot-row').forEach(row => {
    const label  = row.querySelector('.ds-slot-label')?.value.trim() || '';
    const start  = row.querySelector('.ds-slot-start')?.value || '';
    const end    = row.querySelector('.ds-slot-end')?.value || '';
    const types  = (row.querySelector('.ds-slot-types')?.value || '').split(',').map(t => t.trim()).filter(Boolean);
    if (start && end) slots.push({ name: label.toLowerCase().replace(/\s+/g, '_'), label, content_types: types, window_start: start, window_end: end });
  });
  const existing = (state.promoSettings && state.promoSettings.delivery_schedule) || {};
  return {
    ...existing,
    max_posts_per_day:     parseInt(document.getElementById('ds-max-per-day')?.value) || 3,
    min_spacing_hours:     parseFloat(document.getElementById('ds-min-spacing')?.value) || 3,
    lighter_day_max_posts: parseInt(document.getElementById('ds-lighter-max')?.value) || 1,
    slots,
  };
}

async function savePromoSettings() {
  const s = {
    publishing_wa_recipients: {
      vip_group_id:    document.getElementById('set-wa-vip-id').value.trim(),
      vip_group_label: document.getElementById('set-wa-vip-label').value.trim(),
      channel_id:      document.getElementById('set-wa-chan-id').value.trim(),
      channel_label:   document.getElementById('set-wa-chan-label').value.trim(),
    },
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
    },
    delivery_schedule: _collectDeliverySchedule(),
    asset_prompts: state.promoSettings?.asset_prompts || []
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

// ── EXECUTION DASHBOARD (Operational Brain) ───────────────────────────────────

async function loadDashboard() {
  try {
    const [data, logs, leadsData, contactsData, worksData] = await Promise.all([
      GET('/api/dashboard'),
      GET('/api/execution-log'),
      GET('/api/promo/leads'),
      GET('/api/promo/contacts'),
      GET('/api/works')
    ]);
    state.dashboardData = data;
    state.executionLogs = logs;
    state.runnerRunning = data.runner_running;
    state.promoLeads = leadsData.leads || [];
    state.promoContacts = contactsData.contacts || [];
    state.promoBooks = worksData.works || [];
    renderDashboard();
  } catch(e) {
    console.error(e);
    toast('Failed to load Operational Brain', 'error');
  }
}

function renderDashboard() {
  const container = document.getElementById('dashboard-container');
  if (!container) return;

  const data = state.dashboardData;
  if (!data) {
    container.innerHTML = '<div class="loading">Informing the spirits...</div>';
    return;
  }

  const { next_actions, blockers, stats, deals_summary } = data;
  const logs = (state.executionLogs || []).slice(0, 10);
  const ds = deals_summary || { open_deals: 0, won_this_month: 0, lost_this_month: 0, follow_up_needed: 0, follow_up_leads: [] };

  const html = `
    <div class="dash-grid">
      <div class="dash-main">
        <header class="dash-header">
          <div class="dash-title-group">
            <h1 class="dash-title">Operational Brain</h1>
            <p class="dash-subtitle">High-Priority Execution Dashboard</p>
          </div>
          <div class="dash-global-actions">
            <button class="btn-primary" onclick="runOnceManual()">Run Next Action</button>
            <button class="btn-secondary ${state.runnerRunning ? 'active' : ''}" onclick="toggleAutoMode()">
              ${state.runnerRunning ? 'Stop Auto Mode' : 'Start Auto Mode'}
            </button>
          </div>
        </header>

        <!-- SECTION 1: NEXT ACTIONS -->
        <section class="dash-section">
          <div class="dash-section-header">
            <h2 class="dash-section-title">⚡ NEXT ACTIONS</h2>
            <span class="dash-section-meta">Top 10 High-Impact Tasks</span>
          </div>
          <div class="dash-actions-list">
            ${next_actions.length === 0 ? '<div class="empty-state">No unblocked actions. System Idle.</div>' : next_actions.map(action => `
              <div class="dash-action-card ${action.blocked ? 'blocked' : 'ready'}">
                <div class="dash-action-left">
                  <div class="dash-action-indicator"></div>
                  <div class="dash-action-content">
                    <div class="dash-action-label">${esc(action.label)}</div>
                    <div class="dash-action-book">${esc(action.work_title)}</div>
                  </div>
                </div>
                <div class="dash-action-right">
                  <span class="dash-action-score">${action.score}</span>
                  <button class="btn-action-run" onclick="runOnceManual()" ${action.blocked ? 'disabled' : ''}>Run</button>
                </div>
              </div>
            `).join('')}
          </div>
        </section>

        <!-- SECTION 2: EXECUTION LOG -->
        <section class="dash-section">
          <div class="dash-section-header">
            <h2 class="dash-section-title">✔ EXECUTION LOG</h2>
          </div>
          <div class="dash-log-panel">
            ${logs.length === 0 ? '<p class="muted center">No missions recorded yet.</p>' : logs.map(l => `
              <div class="dash-log-entry ${l.result.success ? 'success' : 'error'}">
                <span class="dash-log-bullet">${l.result.success ? '✔' : '✘'}</span>
                <span class="dash-log-text"><strong>${l.result.success ? 'Produced' : 'Failed'}</strong> ${esc(l.action.label)}</span>
                <span class="dash-log-time">${new Date(l.timestamp).toLocaleTimeString()}</span>
              </div>
            `).join('')}
          </div>
        </section>
      </div>

      <div class="dash-sidebar">
        <!-- SECTION 3: PIPELINE HEALTH -->
        <div class="dash-panel glass">
          <h3>📊 PIPELINE HEALTH</h3>
          <div class="dash-metrics-grid">
            <div class="dash-metric">
              <div class="dash-metric-val">${stats.production_pending}</div>
              <div class="dash-metric-label">In Production</div>
            </div>
            <div class="dash-metric">
              <div class="dash-metric-val">${stats.ready_to_publish}</div>
              <div class="dash-metric-label">Ready to Publish</div>
            </div>
            <div class="dash-metric">
              <div class="dash-metric-val">${stats.ready_to_promote}</div>
              <div class="dash-metric-label">Ready to Promote</div>
            </div>
          </div>
        </div>

        <!-- SECTION 4: BLOCKERS -->
        <div class="dash-panel">
          <h3>BLOCKERS</h3>
          <div class="dash-blockers-list">
            ${blockers.length === 0 ? '<p class="muted small">No active blockages.</p>' : blockers.map(b => `
              <div class="dash-blocker-item">
                <div class="dash-blocker-head">
                  <strong>${b.asset_type.replace('_', ' ')}</strong>
                  <span class="dash-blocker-book">${esc(b.work_title)}</span>
                </div>
                <div class="dash-blocker-reason">${b.blocker === 'module_is_draft' ? 'Module still in draft — assets locked until status is review or final' : 'Missing ' + b.blocker.replace('missing_', '').replace(/_/g, ' ')}</div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- SECTION 5: SALES PIPELINE -->
        <div class="dash-panel glass">
          <h3>SALES PIPELINE</h3>
          <div class="dash-metrics-grid">
            <div class="dash-metric">
              <div class="dash-metric-val">${ds.open_deals}</div>
              <div class="dash-metric-label">Open Deals</div>
            </div>
            <div class="dash-metric">
              <div class="dash-metric-val" style="color:var(--p3)">${ds.won_this_month}</div>
              <div class="dash-metric-label">Won This Month</div>
            </div>
            <div class="dash-metric">
              <div class="dash-metric-val" style="color:var(--p1)">${ds.lost_this_month}</div>
              <div class="dash-metric-label">Lost This Month</div>
            </div>
            <div class="dash-metric">
              <div class="dash-metric-val" style="color:var(--p2)">${ds.follow_up_needed}</div>
              <div class="dash-metric-label">Need Follow-up</div>
            </div>
          </div>
          ${ds.follow_up_leads && ds.follow_up_leads.length > 0 ? `
            <div style="margin-top:12px;border-top:1px solid var(--border);padding-top:12px;">
              <div style="font-size:11px;font-weight:700;text-transform:uppercase;color:var(--muted);margin-bottom:8px;">Follow-up Needed</div>
              ${ds.follow_up_leads.map(l => {
                const STAGES = ['lead','qualified','proposal','negotiation','won','lost'];
                const idx = STAGES.indexOf(l.stage);
                const nextStage = idx >= 0 && idx < STAGES.length - 3 ? STAGES[idx + 1] : null;
                return `
                <div class="dash-deal-followup" style="padding:6px;background:var(--surface);border-radius:4px;margin-bottom:4px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;cursor:pointer;" onclick="switchMode('promote').then(()=>switchPromoTab('leads').then(()=>openLeadDetail('${l.id}')))">
                    <div>
                      <div style="font-size:12px;font-weight:600;">${esc(l.contact_name)}</div>
                      <div style="font-size:11px;color:var(--muted);">${esc(l.product)}</div>
                    </div>
                    <span class="promo-stage-badge promo-stage-${l.stage}" style="font-size:9px;">${l.stage}</span>
                  </div>
                  <div style="display:flex;gap:4px;margin-top:4px;">
                    ${nextStage ? `<button class="btn-secondary" style="font-size:9px;padding:2px 6px;" onclick="advanceDealStage('${l.id}','${nextStage}')">→ ${nextStage}</button>` : ''}
                    <button class="btn-secondary" style="font-size:9px;padding:2px 6px;color:var(--p3);" onclick="closeDeal('${l.id}','won')">Won ✓</button>
                    <button class="btn-secondary" style="font-size:9px;padding:2px 6px;color:var(--p1);" onclick="closeDeal('${l.id}','lost')">Lost ✗</button>
                  </div>
                </div>`
              }).join('')}
            </div>
          ` : ''}
          <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;">
            <button class="btn-secondary" style="font-size:11px;" onclick="switchMode('promote'); switchPromoTab('leads');">View Pipeline</button>
            <button class="btn-secondary" style="font-size:11px;" onclick="switchMode('promote'); switchPromoTab('contacts');">Add Contact</button>
          </div>
        </div>
      </div>
    </div>
  `;

  container.innerHTML = html;
}

async function advanceDealStage(leadId, nextStage) {
  try {
    await PUT(`/api/promo/leads/${leadId}`, { stage: nextStage });
    toast(`Lead moved to ${nextStage}`, 'success');
    await loadPromoLeads();
  } catch(e) { toast('Could not advance lead', 'error'); }
}

async function closeDeal(leadId, outcome) {
  if (!confirm(`Mark this lead as ${outcome.toUpperCase()}?`)) return;
  try {
    await PUT(`/api/promo/leads/${leadId}`, { stage: outcome });
    toast(`Lead closed: ${outcome}`, outcome === 'won' ? 'success' : 'error');
    await loadPromoLeads();
  } catch(e) { toast('Could not close lead', 'error'); }
}
