// FinTree — P&L Hierarchy Explorer (Frontend)

const API = '';  // same origin
let treeData = null;
let selectedNodeId = null;
let industryOverlay = null;  // current overlay name or null

// ─── Bootstrap ──────────────────────────────────────────────

async function init() {
  await Promise.all([
    loadTree(),
    loadStats(),
    loadIndustryOptions(),
  ]);
  setupSearch();
  setupControls();
}

// ─── Tree ───────────────────────────────────────────────────

async function loadTree(industry = null) {
  const url = industry
    ? `${API}/api/industry/${industry}/tree`
    : `${API}/api/tree/full`;
  const res = await fetch(url);
  const data = await res.json();
  treeData = industry ? data.tree : data;
  renderTree();
}

function renderTree() {
  const container = document.getElementById('treeContainer');
  container.innerHTML = '';
  if (!treeData) return;
  container.appendChild(buildTreeNode(treeData, true));
}

function buildTreeNode(node, isRoot = false) {
  const el = document.createElement('div');
  el.className = 'tree-node';

  const hasChildren = node.children && node.children.length > 0;
  const row = document.createElement('div');
  row.className = `tree-node-row level-${node.level} type-${node.node_type}`;
  if (node.emphasized) row.classList.add('emphasized');
  row.dataset.nodeId = node.id;

  // Toggle arrow
  const toggle = document.createElement('span');
  toggle.className = `toggle ${hasChildren ? '' : 'hidden'}`;
  toggle.textContent = '▶';

  // Icon
  const icon = document.createElement('span');
  icon.className = 'node-icon';
  icon.textContent = getNodeIcon(node);

  // Label
  const label = document.createElement('span');
  label.className = 'node-label';
  label.textContent = node.label;

  // Badge
  const badge = document.createElement('span');
  badge.className = 'node-badge';
  if (node.node_type === 'GAAP_SUBTOTAL') {
    badge.className += ' badge-subtotal';
    badge.textContent = 'SUBTOTAL';
  } else if (node.node_type === 'MAJOR_CATEGORY') {
    badge.className += ' badge-category';
    badge.textContent = 'CATEGORY';
  } else if (node.is_decision_node) {
    badge.className += ' badge-decision';
    badge.textContent = 'DECISION';
  } else if (node.is_leaf) {
    badge.className += ' badge-leaf';
    badge.textContent = 'LEAF';
  }

  row.appendChild(toggle);
  row.appendChild(icon);
  row.appendChild(label);
  if (badge.textContent) row.appendChild(badge);

  // Click handlers
  row.addEventListener('click', (e) => {
    e.stopPropagation();
    selectNode(node.id);
  });

  if (hasChildren) {
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleChildren(el);
    });
    row.addEventListener('dblclick', (e) => {
      e.stopPropagation();
      toggleChildren(el);
    });
  }

  el.appendChild(row);

  // Children container
  if (hasChildren) {
    const childrenEl = document.createElement('div');
    childrenEl.className = `tree-node-children ${isRoot ? 'expanded' : ''}`;
    if (isRoot) toggle.classList.add('expanded');
    for (const child of node.children) {
      childrenEl.appendChild(buildTreeNode(child));
    }
    el.appendChild(childrenEl);
  }

  return el;
}

function toggleChildren(nodeEl) {
  const childrenEl = nodeEl.querySelector(':scope > .tree-node-children');
  const toggle = nodeEl.querySelector(':scope > .tree-node-row .toggle');
  if (!childrenEl) return;
  childrenEl.classList.toggle('expanded');
  toggle.classList.toggle('expanded');
}

function expandAll() {
  document.querySelectorAll('.tree-node-children').forEach(el => el.classList.add('expanded'));
  document.querySelectorAll('.toggle:not(.hidden)').forEach(el => el.classList.add('expanded'));
}

function collapseAll() {
  document.querySelectorAll('.tree-node-children').forEach(el => el.classList.remove('expanded'));
  document.querySelectorAll('.toggle').forEach(el => el.classList.remove('expanded'));
  // Keep root expanded
  const root = document.querySelector('#treeContainer > .tree-node > .tree-node-children');
  const rootToggle = document.querySelector('#treeContainer > .tree-node > .tree-node-row .toggle');
  if (root) root.classList.add('expanded');
  if (rootToggle) rootToggle.classList.add('expanded');
}

function getNodeIcon(node) {
  if (node.is_decision_node) return '◆';
  if (node.node_type === 'GAAP_SUBTOTAL') return '◉';
  if (node.node_type === 'MAJOR_CATEGORY') return '●';
  if (node.node_type === 'SUB_CATEGORY') return '○';
  if (node.is_leaf) return '·';
  return '○';
}

// Expand to and highlight a node
function revealNode(nodeId) {
  const row = document.querySelector(`.tree-node-row[data-node-id="${CSS.escape(nodeId)}"]`);
  if (!row) return;

  // Walk up and expand all ancestor tree-node-children
  let parent = row.parentElement;
  while (parent) {
    if (parent.classList.contains('tree-node-children')) {
      parent.classList.add('expanded');
      const sibToggle = parent.previousElementSibling?.querySelector('.toggle');
      if (sibToggle) sibToggle.classList.add('expanded');
    }
    parent = parent.parentElement;
  }

  row.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ─── Node Detail ────────────────────────────────────────────

async function selectNode(nodeId) {
  // Highlight in tree
  document.querySelectorAll('.tree-node-row.selected').forEach(el => el.classList.remove('selected'));
  const row = document.querySelector(`.tree-node-row[data-node-id="${CSS.escape(nodeId)}"]`);
  if (row) row.classList.add('selected');

  selectedNodeId = nodeId;

  const res = await fetch(`${API}/api/nodes/detail?id=${encodeURIComponent(nodeId)}`);
  if (!res.ok) return;
  const node = await res.json();

  // Get ancestors for breadcrumb
  const ancRes = await fetch(`${API}/api/nodes/ancestors?id=${encodeURIComponent(nodeId)}`);
  const ancData = await ancRes.json();

  renderDetail(node, ancData.ancestors || []);
}

function renderDetail(node, ancestors) {
  document.getElementById('detailTitle').textContent = node.label;
  const content = document.getElementById('detailContent');

  let html = '';

  // Breadcrumb
  if (ancestors.length > 0) {
    html += '<div class="breadcrumb">';
    const path = [...ancestors].reverse();
    for (let i = 0; i < path.length; i++) {
      html += `<a onclick="navigateNode('${path[i].id}')">${path[i].label}</a>`;
      html += '<span class="sep">›</span>';
    }
    html += `<span>${node.label}</span></div>`;
  }

  // Definition
  if (node.definition) {
    html += `<div class="detail-section">
      <h3>Definition</h3>
      <div class="definition-text">${escHtml(node.definition)}</div>
    </div>`;
  }

  // Properties
  html += '<div class="detail-section"><h3>Properties</h3>';
  html += field('ID', node.id, true);
  html += field('Type', node.node_type);
  html += field('Level', node.level);
  html += field('Aggregation', node.aggregation_type);
  if (node.normal_balance) html += field('Balance', node.normal_balance);
  if (node.sign_convention) html += field('Sign', node.sign_convention);
  if (node.xbrl_tag) html += field('XBRL', node.xbrl_tag, true);
  if (node.asc_reference) html += field('ASC Ref', node.asc_reference);
  html += '</div>';

  // Formula
  if (node.formula_human) {
    html += `<div class="detail-section">
      <h3>Formula</h3>
      <div class="formula-box">${escHtml(node.formula_human)}</div>
    </div>`;
  }
  if (node.formula_machine) {
    html += `<div class="detail-section">
      <h3>Machine Formula</h3>
      <div class="formula-box">${escHtml(node.formula_machine)}</div>
    </div>`;
  }

  // Example
  if (node.example) {
    html += `<div class="detail-section">
      <h3>Example</h3>
      <div class="variance-box">${escHtml(node.example)}</div>
    </div>`;
  }

  // Variance drivers
  if (node.variance_drivers && node.variance_drivers.playbook) {
    const vd = node.variance_drivers;
    html += '<div class="detail-section"><h3>Variance Drivers</h3>';
    if (vd.tags && vd.tags.length) {
      html += '<div class="tag-list" style="margin-bottom:8px">';
      vd.tags.forEach(t => html += `<span class="tag">${escHtml(t)}</span>`);
      html += '</div>';
    }
    html += '<div class="variance-box">';
    if (vd.playbook.if_increased) {
      html += `<div class="up"><strong>▲ If Increased:</strong> ${escHtml(vd.playbook.if_increased)}</div>`;
    }
    if (vd.playbook.if_decreased) {
      html += `<div class="down" style="margin-top:6px"><strong>▼ If Decreased:</strong> ${escHtml(vd.playbook.if_decreased)}</div>`;
    }
    html += '</div></div>';
  }

  // Comparability
  if (node.comparability) {
    const comp = node.comparability;
    html += '<div class="detail-section"><h3>Comparability</h3>';
    if (comp.variations) {
      html += `<div class="variance-box" style="margin-bottom:8px">${escHtml(comp.variations)}</div>`;
    }
    if (comp.examples && comp.examples.length) {
      html += '<div style="font-size:12px">';
      comp.examples.forEach(ex => {
        html += `<div class="detail-field"><span class="key">${escHtml(ex.company)}</span><span class="val">${escHtml(ex.treatment)}</span></div>`;
      });
      html += '</div>';
    }
    html += '</div>';
  }

  // COA Mapping
  if (node.coa_mapping) {
    const coa = node.coa_mapping;
    html += '<div class="detail-section"><h3>Chart of Accounts</h3>';
    if (coa.quickbooks) html += field('QuickBooks', coa.quickbooks);
    if (coa.netsuite) html += field('NetSuite', coa.netsuite);
    if (coa.sap) html += field('SAP', coa.sap);
    html += '</div>';
  }

  // AI Context Tags
  if (node.ai_context_tags && node.ai_context_tags.length) {
    html += '<div class="detail-section"><h3>AI Context Tags</h3>';
    html += '<div class="tag-list">';
    node.ai_context_tags.forEach(t => html += `<span class="tag">${escHtml(t)}</span>`);
    html += '</div></div>';
  }

  // Children
  if (node.children_ids && node.children_ids.length) {
    html += `<div class="detail-section"><h3>Children (${node.children_ids.length})</h3>`;
    html += '<ul class="children-list">';
    node.children_ids.forEach(cid => {
      const shortLabel = cid.replace('fintree:', '');
      html += `<li><a onclick="navigateNode('${cid}')">${shortLabel}</a></li>`;
    });
    html += '</ul></div>';
  }

  content.innerHTML = html;
}

function field(key, val, mono = false) {
  return `<div class="detail-field"><span class="key">${escHtml(key)}</span><span class="val${mono ? ' mono' : ''}">${escHtml(String(val))}</span></div>`;
}

function escHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function navigateNode(nodeId) {
  revealNode(nodeId);
  selectNode(nodeId);
}

// ─── Search ─────────────────────────────────────────────────

let searchTimeout = null;

function setupSearch() {
  const input = document.getElementById('searchInput');
  const dropdown = document.getElementById('searchResults');

  input.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    const q = input.value.trim();
    if (q.length < 2) {
      dropdown.classList.remove('visible');
      return;
    }
    searchTimeout = setTimeout(() => doSearch(q), 200);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      dropdown.classList.remove('visible');
      input.blur();
    }
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-box')) {
      dropdown.classList.remove('visible');
    }
  });
}

async function doSearch(query) {
  const res = await fetch(`${API}/api/search?q=${encodeURIComponent(query)}&limit=15`);
  const data = await res.json();
  const dropdown = document.getElementById('searchResults');

  if (!data.results.length) {
    dropdown.innerHTML = '<div class="search-result"><span class="label">No results</span></div>';
    dropdown.classList.add('visible');
    return;
  }

  dropdown.innerHTML = data.results.map(r => `
    <div class="search-result" onclick="handleSearchClick('${r.id}')">
      <div class="label">${escHtml(r.label)}</div>
      <div class="meta">${escHtml(r.node_type)} · Level ${r.level}${r.definition ? ' · ' + escHtml(r.definition.substring(0, 80)) + '…' : ''}</div>
    </div>
  `).join('');
  dropdown.classList.add('visible');
}

function handleSearchClick(nodeId) {
  document.getElementById('searchResults').classList.remove('visible');
  document.getElementById('searchInput').value = '';
  revealNode(nodeId);
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
    opt.textContent = `${o.label} (${o.emphasize_count} emphasized, ${o.suppress_count} suppressed)`;
    select.appendChild(opt);
  });

  select.addEventListener('change', () => {
    industryOverlay = select.value || null;
    loadTree(industryOverlay);
  });
}

// ─── Stats ──────────────────────────────────────────────────

async function loadStats() {
  const res = await fetch(`${API}/api/tree/stats`);
  const stats = await res.json();
  const bar = document.getElementById('statsBar');
  bar.innerHTML = `
    <span>Nodes: <strong>${stats.total_nodes}</strong></span>
    <span>Leaf: <strong>${stats.leaf_nodes}</strong></span>
    <span>Decision: <strong>${stats.decision_nodes}</strong></span>
    <span>Overlays: <strong>${stats.industry_overlays}</strong></span>
    <span>Non-GAAP: <strong>${stats.non_gaap_measures}</strong></span>
    <span>Levels: ${Object.entries(stats.by_level).map(([k, v]) => `${k}=${v}`).join(', ')}</span>
  `;
}

// ─── Controls ───────────────────────────────────────────────

function setupControls() {
  document.getElementById('expandAll').addEventListener('click', expandAll);
  document.getElementById('collapseAll').addEventListener('click', collapseAll);

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && !e.target.closest('input')) {
      e.preventDefault();
      document.getElementById('searchInput').focus();
    }
  });
}

// ─── Init ───────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
