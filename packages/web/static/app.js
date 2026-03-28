// FinTree — P&L Hierarchy Explorer (River + Cards Frontend)

const API = '';
let currentIndustry = null;
let plData = null;

// ─── Init ───────────────────────────────────────────────────

async function init() {
  await Promise.all([loadIndustryOptions(), loadStats()]);
  await loadPLSections();
  setupSearch();
  setupKeyboard();
}

// ─── P&L Sections ───────────────────────────────────────────

async function loadPLSections(industry = null) {
  const url = industry
    ? `${API}/api/tree/pl-sections?industry=${encodeURIComponent(industry)}`
    : `${API}/api/tree/pl-sections`;
  const res = await fetch(url);
  plData = await res.json();
  renderRiver(plData.sections);
  renderCards(plData.sections);
  updateStats(plData.stats, industry);
}

// ─── River Overview ─────────────────────────────────────────

const RIVER_NODES = [
  { key: 'revenue', label: 'Revenue', type: 'revenue' },
  { key: 'cogs', label: 'COGS', type: 'expense' },
  { key: 'gross_profit', label: 'Gross Profit', type: 'subtotal' },
  { key: 'opex', label: 'OpEx', type: 'expense' },
  { key: 'ebit', label: 'EBIT', type: 'subtotal' },
  { key: 'tax', label: 'Tax', type: 'expense' },
  { key: 'net_income', label: 'Net Income', type: 'bottom' },
];

function renderRiver(sections) {
  const container = document.getElementById('riverFlow');
  container.innerHTML = '';

  const sectionMap = {};
  sections.forEach(s => sectionMap[s.key] = s);

  RIVER_NODES.forEach((rn, i) => {
    if (i > 0) {
      const arrow = document.createElement('div');
      arrow.className = 'river-arrow';
      arrow.textContent = '›';
      container.appendChild(arrow);
    }

    const node = document.createElement('div');
    node.className = `river-node rn-${rn.type}`;
    node.dataset.key = rn.key;

    const sec = sectionMap[rn.key];
    const nodeCount = sec ? (sec.total || sec.visible || '') : '';

    node.innerHTML = `
      <div class="rn-amount">${rn.label}</div>
      <div class="rn-name">${nodeCount ? nodeCount + ' nodes' : rn.type === 'subtotal' || rn.type === 'bottom' ? 'computed' : ''}</div>
      <div class="rn-margin" style="width:${getMarginWidth(rn.key)}%"></div>
    `;

    node.addEventListener('click', () => scrollToSection(rn.key));
    container.appendChild(node);
  });
}

function getMarginWidth(key) {
  const widths = { revenue: 100, cogs: 55, gross_profit: 45, opex: 30, ebit: 31, tax: 7, net_income: 24 };
  return widths[key] || 50;
}

function scrollToSection(key) {
  const el = document.querySelector(`[data-section-key="${key}"]`);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });

  // Highlight river node
  document.querySelectorAll('.river-node').forEach(n => n.classList.remove('active'));
  const rn = document.querySelector(`.river-node[data-key="${key}"]`);
  if (rn) rn.classList.add('active');
}

// ─── Statement Cards ────────────────────────────────────────

function renderCards(sections) {
  const container = document.getElementById('cardsSection');
  container.innerHTML = '';

  sections.forEach(sec => {
    if (sec.type === 'section') {
      container.appendChild(buildSectionCard(sec));
    } else if (sec.type === 'subtotal') {
      container.appendChild(buildSubtotalRow(sec, 'st-subtotal'));
    } else if (sec.type === 'bottom_line') {
      container.appendChild(buildSubtotalRow(sec, 'st-bottom'));
    }
  });
}

function buildSectionCard(sec) {
  const el = document.createElement('div');
  el.className = `pl-section sec-${sec.key}`;
  el.dataset.sectionKey = sec.key;

  const emphasizedCount = sec.emphasized_count || 0;
  const suppressed = sec.total - sec.visible;

  // Header
  const header = document.createElement('div');
  header.className = 'pl-header';
  header.innerHTML = `
    <div class="sec-title">
      <div class="sec-icon">${sec.icon}</div>
      ${esc(sec.label)}
    </div>
    <div class="sec-meta">
      ${emphasizedCount ? `<span class="sec-emphasized">${emphasizedCount} emphasized</span>` : ''}
      <span class="sec-count">${sec.visible} nodes${suppressed ? ` (${suppressed} hidden)` : ''}</span>
      <span class="sec-arrow">▶</span>
    </div>
  `;

  // Body with chips
  const body = document.createElement('div');
  body.className = 'sec-body';

  const chips = document.createElement('div');
  chips.className = 'chips';

  // Sort: emphasized first, then suppressed last
  const sorted = [...(sec.nodes || [])].sort((a, b) => {
    if (a.emphasized && !b.emphasized) return -1;
    if (!a.emphasized && b.emphasized) return 1;
    if (a.suppressed && !b.suppressed) return 1;
    if (!a.suppressed && b.suppressed) return -1;
    return 0;
  });

  const MAX_SHOW = 20;
  const visible = sorted.slice(0, MAX_SHOW);
  const remaining = sorted.length - MAX_SHOW;

  visible.forEach(node => {
    const chip = document.createElement('div');
    chip.className = 'chip';
    if (node.emphasized) chip.classList.add('emphasized');
    if (node.suppressed) chip.classList.add('suppressed');
    chip.textContent = (node.emphasized ? '✦ ' : '') + node.label;
    chip.addEventListener('click', (e) => {
      e.stopPropagation();
      selectNode(node.id);
    });
    chips.appendChild(chip);
  });

  if (remaining > 0) {
    const more = document.createElement('span');
    more.className = 'chip-more';
    more.textContent = `+${remaining} more`;
    more.addEventListener('click', (e) => {
      e.stopPropagation();
      // Show all
      chips.innerHTML = '';
      sorted.forEach(node => {
        const chip = document.createElement('div');
        chip.className = 'chip';
        if (node.emphasized) chip.classList.add('emphasized');
        if (node.suppressed) chip.classList.add('suppressed');
        chip.textContent = (node.emphasized ? '✦ ' : '') + node.label;
        chip.addEventListener('click', (ev) => {
          ev.stopPropagation();
          selectNode(node.id);
        });
        chips.appendChild(chip);
      });
    });
    chips.appendChild(more);
  }

  body.appendChild(chips);
  el.appendChild(header);
  el.appendChild(body);

  // Toggle expand
  let expanded = false;
  header.addEventListener('click', () => {
    expanded = !expanded;
    body.classList.toggle('visible', expanded);
    header.querySelector('.sec-arrow').classList.toggle('open', expanded);
  });

  return el;
}

function buildSubtotalRow(sec, cssClass) {
  const el = document.createElement('div');
  el.className = `subtotal-row ${cssClass}`;
  el.dataset.sectionKey = sec.key;
  if (sec.node_id) el.dataset.nodeId = sec.node_id;

  el.innerHTML = `
    <div class="st-label"><span class="st-eq">═</span> ${esc(sec.label)}</div>
    <div class="st-formula">${esc(sec.formula || '')}</div>
  `;

  if (sec.node_id) {
    el.addEventListener('click', () => selectNode(sec.node_id));
  }

  return el;
}

// ─── Node Detail ────────────────────────────────────────────

async function selectNode(nodeId) {
  // Highlight subtotal if clicked
  document.querySelectorAll('.subtotal-row.selected').forEach(el => el.classList.remove('selected'));
  const stRow = document.querySelector(`.subtotal-row[data-node-id="${CSS.escape(nodeId)}"]`);
  if (stRow) stRow.classList.add('selected');

  const [nodeRes, ancRes] = await Promise.all([
    fetch(`${API}/api/nodes/detail?id=${encodeURIComponent(nodeId)}`),
    fetch(`${API}/api/nodes/ancestors?id=${encodeURIComponent(nodeId)}`),
  ]);

  if (!nodeRes.ok) return;
  const node = await nodeRes.json();
  const ancData = await ancRes.json();
  renderDetail(node, ancData.ancestors || []);
}

function renderDetail(node, ancestors) {
  document.getElementById('detailTitle').textContent = node.label;

  // Breadcrumb
  const bc = document.getElementById('detailBreadcrumb');
  if (ancestors.length) {
    const path = [...ancestors].reverse();
    bc.innerHTML = path.map(a => `<a onclick="selectNode('${a.id}')">${esc(a.label)}</a>`).join(' › ') + ` › <span>${esc(node.label)}</span>`;
  } else {
    bc.innerHTML = '';
  }

  const content = document.getElementById('detailContent');
  let html = '';

  // Definition
  if (node.definition) {
    html += `<div class="detail-block"><h4>Definition</h4><div class="def-box">${esc(node.definition)}</div></div>`;
  }

  // Formula
  if (node.formula_human) {
    html += `<div class="detail-block"><h4>Formula</h4><div class="formula-box">${esc(node.formula_human)}${node.formula_machine ? '<br><span style="opacity:0.4;font-size:10px">' + esc(node.formula_machine) + '</span>' : ''}</div></div>`;
  }

  // Properties
  html += '<div class="detail-block"><h4>Properties</h4>';
  html += field('ID', node.id);
  html += field('Type', node.node_type);
  html += field('Level', node.level);
  html += field('Aggregation', node.aggregation_type);
  if (node.normal_balance) html += field('Balance', node.normal_balance);
  if (node.xbrl_tag) html += field('XBRL', node.xbrl_tag);
  if (node.asc_reference) html += field('ASC Ref', node.asc_reference);
  html += '</div>';

  // Example
  if (node.example) {
    html += `<div class="detail-block"><h4>Example</h4><div class="def-box" style="border-color:var(--amber)">${esc(node.example)}</div></div>`;
  }

  // Variance Drivers
  if (node.variance_drivers?.playbook) {
    const vd = node.variance_drivers;
    html += '<div class="detail-block"><h4>Variance Drivers</h4>';
    if (vd.tags?.length) {
      html += '<div class="tag-row" style="margin-bottom:8px">';
      vd.tags.forEach(t => html += `<span class="tag">${esc(t)}</span>`);
      html += '</div>';
    }
    html += '<div class="variance-box">';
    if (vd.playbook.if_increased) html += `<div class="var-up"><strong>▲ Increased:</strong> ${esc(vd.playbook.if_increased)}</div>`;
    if (vd.playbook.if_decreased) html += `<div class="var-down"><strong>▼ Decreased:</strong> ${esc(vd.playbook.if_decreased)}</div>`;
    html += '</div></div>';
  }

  // Comparability
  if (node.comparability) {
    html += '<div class="detail-block"><h4>Comparability</h4>';
    if (node.comparability.variations) {
      html += `<div class="def-box" style="border-color:var(--purple);margin-bottom:8px;font-size:12px">${esc(node.comparability.variations)}</div>`;
    }
    if (node.comparability.examples?.length) {
      node.comparability.examples.forEach(ex => {
        html += field(ex.company, ex.treatment);
      });
    }
    html += '</div>';
  }

  // COA Mapping
  if (node.coa_mapping) {
    html += '<div class="detail-block"><h4>Chart of Accounts</h4>';
    if (node.coa_mapping.quickbooks) html += field('QuickBooks', node.coa_mapping.quickbooks);
    if (node.coa_mapping.netsuite) html += field('NetSuite', node.coa_mapping.netsuite);
    if (node.coa_mapping.sap) html += field('SAP', node.coa_mapping.sap);
    html += '</div>';
  }

  // AI Tags
  if (node.ai_context_tags?.length) {
    html += '<div class="detail-block"><h4>AI Context Tags</h4><div class="tag-row">';
    node.ai_context_tags.forEach(t => html += `<span class="tag">${esc(t)}</span>`);
    html += '</div></div>';
  }

  // Children
  if (node.children_ids?.length) {
    html += `<div class="detail-block"><h4>Children (${node.children_ids.length})</h4><ul class="children-list">`;
    node.children_ids.forEach(cid => {
      html += `<li><a onclick="selectNode('${cid}')">${cid.replace('fintree:', '')}</a></li>`;
    });
    html += '</ul></div>';
  }

  content.innerHTML = html;
}

function field(k, v) {
  return `<div class="detail-field"><span class="k">${esc(k)}</span><span class="v">${esc(String(v))}</span></div>`;
}

// ─── Search ─────────────────────────────────────────────────

let searchTimeout = null;

function setupSearch() {
  const input = document.getElementById('searchInput');
  const dropdown = document.getElementById('searchDropdown');

  input.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    const q = input.value.trim();
    if (q.length < 2) { dropdown.classList.remove('visible'); return; }
    searchTimeout = setTimeout(() => doSearch(q), 200);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { dropdown.classList.remove('visible'); input.blur(); }
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-box')) dropdown.classList.remove('visible');
  });
}

async function doSearch(query) {
  const res = await fetch(`${API}/api/search?q=${encodeURIComponent(query)}&limit=12`);
  const data = await res.json();
  const dropdown = document.getElementById('searchDropdown');

  if (!data.results.length) {
    dropdown.innerHTML = '<div class="search-result"><span class="sr-label">No results</span></div>';
    dropdown.classList.add('visible');
    return;
  }

  dropdown.innerHTML = data.results.map(r => `
    <div class="search-result" onclick="handleSearchClick('${r.id}')">
      <div class="sr-label">${esc(r.label)}</div>
      <div class="sr-meta">${esc(r.node_type)} · L${r.level}${r.definition ? ' · ' + esc(r.definition.substring(0, 80)) + '...' : ''}</div>
    </div>
  `).join('');
  dropdown.classList.add('visible');
}

function handleSearchClick(nodeId) {
  document.getElementById('searchDropdown').classList.remove('visible');
  document.getElementById('searchInput').value = '';
  selectNode(nodeId);
}

// ─── Industry Overlay ───────────────────────────────────────

async function loadIndustryOptions() {
  const res = await fetch(`${API}/api/industry`);
  const data = await res.json();
  const select = document.getElementById('industrySelect');

  data.overlays.forEach(o => {
    const opt = document.createElement('option');
    opt.value = o.industry;
    opt.textContent = `${o.label}`;
    select.appendChild(opt);
  });

  select.addEventListener('change', () => {
    currentIndustry = select.value || null;
    select.classList.toggle('active', !!currentIndustry);
    loadPLSections(currentIndustry);
  });
}

// ─── Stats ──────────────────────────────────────────────────

async function loadStats() {
  const res = await fetch(`${API}/api/tree/stats`);
  const stats = await res.json();
  document.getElementById('searchInput').placeholder = `Search ${stats.total_nodes} nodes...  /`;
}

function updateStats(stats, industry) {
  const bar = document.getElementById('statsBar');
  bar.innerHTML = `
    <span>Nodes: <strong>${stats.total_nodes}</strong></span>
    <span>Visible: <strong>${stats.visible}</strong></span>
    ${stats.suppressed ? `<span>Suppressed: <strong>${stats.suppressed}</strong></span>` : ''}
    ${stats.emphasized ? `<span>Emphasized: <strong>${stats.emphasized}</strong></span>` : ''}
    ${industry ? `<span>Overlay: <strong class="overlay-active">${industry}</strong></span>` : ''}
    <span>Standard: <strong>US GAAP</strong></span>
  `;
}

// ─── Keyboard ───────────────────────────────────────────────

function setupKeyboard() {
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && !e.target.closest('input')) {
      e.preventDefault();
      document.getElementById('searchInput').focus();
    }
  });
}

// ─── Helpers ────────────────────────────────────────────────

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// ─── Boot ───────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
