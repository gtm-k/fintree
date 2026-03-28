// FinTree — P&L Hierarchy Explorer (River + Cards Frontend)
// Works in two modes: API mode (with FastAPI backend) or Static mode (embedded data)

const API = '';
let currentIndustry = null;
let plData = null;

// ─── Static Data Layer ─────────────────────────────────────
// When window.FINTREE_DATA is present, all data comes from it
// instead of API calls. This enables GitHub Pages hosting.

const _static = (() => {
  if (!window.FINTREE_DATA) return null;

  const tree = window.FINTREE_DATA;
  const nodeMap = {};
  tree.nodes.forEach(n => nodeMap[n.id] = n);

  const PL_SECTIONS = [
    { key: 'revenue', label: 'Revenue', icon: '📈', color: '#10b981', type: 'section',
      root_ids: ['fintree:NetRevenue', 'fintree:GrossRevenue', 'fintree:RevenueDeductions'] },
    { key: 'cogs', label: 'Cost of Revenue', icon: '⚙️', color: '#ef4444', type: 'section',
      root_ids: ['fintree:CostOfGoodsSoldCostOfRevenue', 'fintree:Cogs'] },
    { key: 'gross_profit', label: 'Gross Profit', type: 'subtotal',
      formula: 'Revenue − Cost of Revenue', node_id: 'fintree:GrossProfit' },
    { key: 'opex', label: 'Operating Expenses', icon: '💼', color: '#f59e0b', type: 'section',
      root_ids: ['fintree:OperatingExpenses', 'fintree:SellingExpenses', 'fintree:GeneralAdministrativeExpenses',
                 'fintree:ResearchDevelopment', 'fintree:DepreciationAmortization'] },
    { key: 'ebit', label: 'Operating Income (EBIT)', type: 'subtotal',
      formula: 'Gross Profit − Operating Expenses', node_id: 'fintree:OperatingIncome' },
    { key: 'nonop', label: 'Non-Operating Income & Expenses', icon: '📊', color: '#64748b', type: 'section',
      root_ids: ['fintree:NonoperatingIncomeExpenses', 'fintree:NonoperatingIncome', 'fintree:NonoperatingExpenses'] },
    { key: 'ebt', label: 'Pre-Tax Income (EBT)', type: 'subtotal',
      formula: 'EBIT ± Non-Operating Items', node_id: 'fintree:PretaxIncome' },
    { key: 'tax', label: 'Income Tax Expense', icon: '🏛️', color: '#f87171', type: 'section',
      root_ids: ['fintree:IncomeTaxExpense', 'fintree:CurrentTaxExpense', 'fintree:DeferredTaxExpense'] },
    { key: 'net_income', label: 'Net Income', type: 'bottom_line',
      formula: 'EBT − Income Tax Expense', node_id: 'fintree:NetIncome' },
    { key: 'btl', label: 'Below-the-Line Items', icon: '📋', color: '#475569', type: 'section',
      root_ids: ['fintree:BelowthelineItems', 'fintree:DiscontinuedOperations', 'fintree:ExtraordinaryItems', 'fintree:CumulativeEffectOfAccountingChanges'] },
  ];

  function subtree(rootId) {
    const results = [];
    const stack = [rootId];
    const seen = new Set();
    while (stack.length) {
      const id = stack.pop();
      if (seen.has(id)) continue;
      seen.add(id);
      const n = nodeMap[id];
      if (!n) continue;
      results.push(n);
      (n.children_ids || []).forEach(c => stack.push(c));
    }
    return results;
  }

  function getOverlay(industry) {
    if (!industry) return null;
    return tree.industry_overlays.find(o => o.industry === industry) || null;
  }

  function plSections(industry) {
    const overlay = getOverlay(industry);
    const suppressed = new Set(overlay ? overlay.modifications.suppress : []);
    const emphasized = new Set(overlay ? overlay.modifications.emphasize : []);
    const renames = overlay ? (overlay.modifications.rename || {}) : {};

    const sections = PL_SECTIONS.map(sec => {
      const entry = { key: sec.key, label: sec.label, type: sec.type };
      if (sec.type === 'section') {
        entry.icon = sec.icon;
        entry.color = sec.color;
        const nodes = [];
        const seen = new Set();
        sec.root_ids.forEach(rid => {
          subtree(rid).forEach(n => {
            if (seen.has(n.id) || sec.root_ids.includes(n.id)) { seen.add(n.id); return; }
            seen.add(n.id);
            nodes.push({
              id: n.id, label: renames[n.id] || n.label, level: n.level,
              node_type: n.node_type, is_leaf: n.is_leaf, parent_id: n.parent_id,
              suppressed: suppressed.has(n.id), emphasized: emphasized.has(n.id),
            });
          });
        });
        entry.nodes = nodes;
        entry.total = nodes.length;
        entry.visible = nodes.filter(n => !n.suppressed).length;
        entry.emphasized_count = nodes.filter(n => n.emphasized).length;
        for (const rid of sec.root_ids) { if (nodeMap[rid]) { entry.node_id = rid; break; } }
      } else {
        entry.formula = sec.formula;
        const n = nodeMap[sec.node_id];
        if (n) { entry.node_id = sec.node_id; entry.label = renames[n.id] || n.label; }
      }
      return entry;
    });

    const allSectionNodes = sections.filter(s => s.nodes).flatMap(s => s.nodes);
    return {
      industry, sections,
      stats: {
        total_nodes: tree.stats.total_nodes,
        suppressed: allSectionNodes.filter(n => n.suppressed).length,
        visible: tree.stats.total_nodes - allSectionNodes.filter(n => n.suppressed).length,
        emphasized: allSectionNodes.filter(n => n.emphasized).length,
      },
    };
  }

  function ancestors(nodeId) {
    const result = [];
    let n = nodeMap[nodeId];
    if (!n) return [];
    while (n.parent_id && nodeMap[n.parent_id]) {
      n = nodeMap[n.parent_id];
      result.push({ id: n.id, label: n.label });
    }
    return result;
  }

  function search(query, limit = 12) {
    const q = query.toLowerCase();
    const scored = tree.nodes
      .map(n => {
        let score = 0;
        if (n.label.toLowerCase() === q) score = 100;
        else if (n.label.toLowerCase().startsWith(q)) score = 80;
        else if (n.label.toLowerCase().includes(q)) score = 60;
        else if (n.id.toLowerCase().includes(q)) score = 40;
        else if (n.definition && n.definition.toLowerCase().includes(q)) score = 20;
        return { node: n, score };
      })
      .filter(s => s.score > 0)
      .sort((a, b) => b.score - a.score || a.node.level - b.node.level)
      .slice(0, limit);
    return {
      query, total: scored.length,
      results: scored.map(s => ({
        id: s.node.id, label: s.node.label, level: s.node.level,
        node_type: s.node.node_type, definition: s.node.definition,
        parent_id: s.node.parent_id, is_leaf: s.node.is_leaf,
      })),
    };
  }

  return {
    getNode: id => nodeMap[id] || null,
    plSections,
    ancestors,
    search,
    stats: () => tree.stats,
    overlays: () => tree.industry_overlays.map(o => ({
      industry: o.industry, label: o.label || o.industry,
      suppress_count: (o.modifications.suppress || []).length,
      emphasize_count: (o.modifications.emphasize || []).length,
    })),
  };
})();

// ─── Init ───────────────────────────────────────────────────

async function init() {
  await Promise.all([loadIndustryOptions(), loadStats()]);
  await loadPLSections();
  setupSearch();
  setupKeyboard();
  setupMobilePanel();
}

// ─── P&L Sections ───────────────────────────────────────────

async function loadPLSections(industry = null) {
  if (_static) {
    plData = _static.plSections(industry);
  } else {
    const url = industry
      ? `${API}/api/tree/pl-sections?industry=${encodeURIComponent(industry)}`
      : `${API}/api/tree/pl-sections`;
    const res = await fetch(url);
    plData = await res.json();
  }
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

    node.addEventListener('click', () => {
      scrollToSection(rn.key);
      const secData = sectionMap[rn.key];
      if (secData && secData.node_id) selectNode(secData.node_id);
    });
    container.appendChild(node);
  });
}

function getMarginWidth(key) {
  const widths = { revenue: 100, cogs: 55, gross_profit: 45, opex: 30, ebit: 31, tax: 7, net_income: 24 };
  return widths[key] || 50;
}

function scrollToSection(key) {
  const el = document.querySelector(`[data-section-key="${key}"]`);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const body = el.querySelector('.sec-body');
    const arrow = el.querySelector('.sec-arrow');
    if (body && !body.classList.contains('visible')) {
      body.classList.add('visible');
      if (arrow) arrow.classList.add('open');
    }
  }

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
  if (sec.node_id) el.dataset.nodeId = sec.node_id;

  const emphasizedCount = sec.emphasized_count || 0;
  const suppressed = sec.total - sec.visible;

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

  const body = document.createElement('div');
  body.className = 'sec-body';

  const chips = document.createElement('div');
  chips.className = 'chips';

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
    chip.addEventListener('click', (e) => { e.stopPropagation(); selectNode(node.id); });
    chips.appendChild(chip);
  });

  if (remaining > 0) {
    const more = document.createElement('span');
    more.className = 'chip-more';
    more.textContent = `+${remaining} more`;
    more.addEventListener('click', (e) => {
      e.stopPropagation();
      chips.innerHTML = '';
      sorted.forEach(node => {
        const chip = document.createElement('div');
        chip.className = 'chip';
        if (node.emphasized) chip.classList.add('emphasized');
        if (node.suppressed) chip.classList.add('suppressed');
        chip.textContent = (node.emphasized ? '✦ ' : '') + node.label;
        chip.addEventListener('click', (ev) => { ev.stopPropagation(); selectNode(node.id); });
        chips.appendChild(chip);
      });
    });
    chips.appendChild(more);
  }

  body.appendChild(chips);
  el.appendChild(header);
  el.appendChild(body);

  let expanded = false;
  header.addEventListener('click', () => {
    expanded = !expanded;
    body.classList.toggle('visible', expanded);
    header.querySelector('.sec-arrow').classList.toggle('open', expanded);
    if (sec.node_id) selectNode(sec.node_id);
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
  document.querySelectorAll('.subtotal-row.selected').forEach(el => el.classList.remove('selected'));
  const stRow = document.querySelector(`.subtotal-row[data-node-id="${CSS.escape(nodeId)}"]`);
  if (stRow) stRow.classList.add('selected');

  let node, ancestors;

  if (_static) {
    node = _static.getNode(nodeId);
    ancestors = _static.ancestors(nodeId);
    if (!node) return;
  } else {
    const [nodeRes, ancRes] = await Promise.all([
      fetch(`${API}/api/nodes/detail?id=${encodeURIComponent(nodeId)}`),
      fetch(`${API}/api/nodes/ancestors?id=${encodeURIComponent(nodeId)}`),
    ]);
    if (!nodeRes.ok) return;
    node = await nodeRes.json();
    const ancData = await ancRes.json();
    ancestors = ancData.ancestors || [];
  }

  renderDetail(node, ancestors);

  const panel = document.getElementById('detailPanel');
  if (window.innerWidth <= 768) panel.classList.add('visible');
}

function renderDetail(node, ancestors) {
  document.getElementById('detailTitle').textContent = node.label;

  const bc = document.getElementById('detailBreadcrumb');
  if (ancestors.length) {
    bc.innerHTML = ancestors.map(a => `<a onclick="selectNode('${a.id}')">${esc(a.label)}</a>`).join(' › ');
  } else {
    bc.innerHTML = '';
  }

  const content = document.getElementById('detailContent');
  let html = '';

  if (node.definition) {
    html += `<div class="detail-block"><h4>Definition</h4><div class="def-box">${esc(node.definition)}</div></div>`;
  }

  if (node.formula_human) {
    html += `<div class="detail-block"><h4>Formula</h4><div class="formula-box">${esc(node.formula_human)}${node.formula_machine ? '<br><span style="opacity:0.4;font-size:10px">' + esc(node.formula_machine) + '</span>' : ''}</div></div>`;
  }

  html += '<div class="detail-block"><h4>Properties</h4>';
  html += field('ID', node.id);
  html += field('Type', node.node_type);
  html += field('Level', node.level);
  html += field('Aggregation', node.aggregation_type);
  if (node.normal_balance) html += field('Balance', node.normal_balance);
  if (node.xbrl_tag) html += field('XBRL', node.xbrl_tag);
  if (node.asc_reference) html += field('ASC Ref', node.asc_reference);
  html += '</div>';

  if (node.example) {
    html += `<div class="detail-block"><h4>Example</h4><div class="def-box" style="border-color:var(--amber)">${esc(node.example)}</div></div>`;
  }

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

  if (node.comparability) {
    html += '<div class="detail-block"><h4>Comparability</h4>';
    if (node.comparability.variations) {
      html += `<div class="def-box" style="border-color:var(--purple);margin-bottom:8px;font-size:12px">${esc(node.comparability.variations)}</div>`;
    }
    if (node.comparability.examples?.length) {
      node.comparability.examples.forEach(ex => { html += field(ex.company, ex.treatment); });
    }
    html += '</div>';
  }

  if (node.coa_mapping) {
    html += '<div class="detail-block"><h4>Chart of Accounts</h4>';
    if (node.coa_mapping.quickbooks) html += field('QuickBooks', node.coa_mapping.quickbooks);
    if (node.coa_mapping.netsuite) html += field('NetSuite', node.coa_mapping.netsuite);
    if (node.coa_mapping.sap) html += field('SAP', node.coa_mapping.sap);
    html += '</div>';
  }

  if (node.ai_context_tags?.length) {
    html += '<div class="detail-block"><h4>AI Context Tags</h4><div class="tag-row">';
    node.ai_context_tags.forEach(t => html += `<span class="tag">${esc(t)}</span>`);
    html += '</div></div>';
  }

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
  let data;
  if (_static) {
    data = _static.search(query, 12);
  } else {
    const res = await fetch(`${API}/api/search?q=${encodeURIComponent(query)}&limit=12`);
    data = await res.json();
  }
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
  let overlays;
  if (_static) {
    overlays = _static.overlays();
  } else {
    const res = await fetch(`${API}/api/industry`);
    const data = await res.json();
    overlays = data.overlays;
  }

  const select = document.getElementById('industrySelect');
  overlays.forEach(o => {
    const opt = document.createElement('option');
    opt.value = o.industry;
    opt.textContent = o.label;
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
  let stats;
  if (_static) {
    stats = _static.stats();
  } else {
    const res = await fetch(`${API}/api/tree/stats`);
    stats = await res.json();
  }
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

// ─── Mobile Detail Panel ───────────────────────────────────

function setupMobilePanel() {
  const panel = document.getElementById('detailPanel');
  const toggle = document.getElementById('detailToggle');
  if (!toggle) return;

  toggle.addEventListener('click', () => { panel.classList.add('visible'); });

  const close = document.getElementById('detailClose');
  if (close) { close.addEventListener('click', () => { panel.classList.remove('visible'); }); }

  panel.addEventListener('touchstart', (e) => { panel._touchY = e.touches[0].clientY; }, { passive: true });
  panel.addEventListener('touchmove', (e) => {
    if (e.touches[0].clientY - (panel._touchY || 0) > 60) panel.classList.remove('visible');
  }, { passive: true });
}

// ─── Helpers ────────────────────────────────────────────────

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// ─── Boot ───────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
