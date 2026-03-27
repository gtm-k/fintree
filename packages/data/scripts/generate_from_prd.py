#!/usr/bin/env python3
"""
Parse fintree_prd.md Section 6.2 and generate YAML node files.

Strategy:
1. Parse the markdown tree structure (heading levels = tree depth)
2. Extract node metadata from inline annotations ([L1], [LEAF], [DECISION], etc.)
3. Extract definitions and examples from italic text blocks
4. Generate YAML files with all required fields
5. Fields not extractable from PRD (variance_drivers, comparability, coa_mapping)
   get sensible defaults that can be enriched later
"""
import re
import yaml
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(label: str) -> str:
    """Convert 'Net Revenue' to 'NetRevenue' for IDs."""
    words = re.sub(r'[^a-zA-Z0-9\s]', '', label).split()
    return ''.join(w.capitalize() for w in words)


def slug_to_filename(slug: str) -> str:
    """Convert 'NetRevenue' to 'net-revenue' for file names."""
    return re.sub(r'(?<!^)(?=[A-Z])', '-', slug).lower()


# Revenue-related labels where the normal accounting balance is CREDIT
_CREDIT_KEYWORDS = {
    'revenue', 'income', 'gain', 'profit', 'sales', 'royalty',
    'franchise', 'subscription', 'licensing', 'dividend',
}
# Expense / cost keywords where normal balance is DEBIT
_DEBIT_KEYWORDS = {
    'expense', 'cost', 'loss', 'depreciation', 'amortization',
    'tax', 'write', 'impairment', 'restructuring', 'charge',
    'deduction', 'discount', 'return', 'allowance', 'rebate',
    'wage', 'salary', 'compensation', 'rent', 'freight',
    'supply', 'maintenance', 'insurance', 'fee',
}


def guess_normal_balance(label: str, hint: str | None, parent_label: str | None) -> str:
    """Heuristic: revenue items = CREDIT, expense/cost items = DEBIT."""
    lower = label.lower()
    parent_lower = (parent_label or '').lower()

    # Contra-revenue items are DEBIT
    if any(kw in lower for kw in ('deduction', 'discount', 'return', 'allowance', 'rebate')):
        return 'DEBIT'

    # Revenue items
    if any(kw in lower for kw in ('revenue', 'sales', 'royalty', 'franchise', 'licensing', 'subscription')):
        return 'CREDIT'

    # Gross Profit, Operating Income, Pre-Tax Income, Net Income -> CREDIT
    if any(kw in lower for kw in ('profit', 'income', 'gain', 'dividend income')):
        # But NOT "income tax expense"
        if 'tax expense' in lower or 'expense' in lower:
            return 'DEBIT'
        return 'CREDIT'

    # Parent context: if parent is a revenue node, child is CREDIT
    if any(kw in parent_lower for kw in ('revenue', 'gross revenue')):
        if not any(kw in lower for kw in ('deduction', 'contra', 'return', 'discount', 'rebate', 'allowance')):
            return 'CREDIT'

    return 'DEBIT'


def guess_sign_convention(label: str, hint: str | None) -> str:
    """Items that reduce their parent subtotal get -1."""
    lower = label.lower()
    # COGS reduces Net Revenue to get Gross Profit
    if 'cost of goods' in lower or 'cost of revenue' in lower or lower.startswith('cogs'):
        return '-1'
    # Operating Expenses reduce Gross Profit to get Operating Income
    if 'operating expenses' in lower and 'non-operating' not in lower:
        return '-1'
    # Income tax reduces Pre-Tax Income
    if 'income tax expense' in lower:
        return '-1'
    # Revenue deductions
    if any(kw in lower for kw in ('deduction', 'return', 'discount', 'rebate', 'allowance', 'contra')):
        return '-1'
    # Ending inventory is subtracted in COGS calculation
    if 'ending inventory' in lower:
        return '-1'
    return '+1'


# ---------------------------------------------------------------------------
# PRD Parsing
# ---------------------------------------------------------------------------

def parse_prd_section_62(prd_path: str) -> list[dict]:
    """
    Parse PRD markdown Section 6.2 and extract all nodes.

    Format in the PRD:
      #### NET INCOME `[L1][DERIVED]`
      *Definition: ...*
      *Example: ...*

      ##### ├── PRE-TAX INCOME (EBT) `[L1][DERIVED]`
      ...

    Heading depth (number of '#') indicates tree depth:
      #### = depth 0  (root: Net Income)
      ##### = depth 1
      ###### = depth 2
      etc.

    The [L1]-[L5] annotation indicates the semantic GAAP level.
    """
    text = Path(prd_path).read_text(encoding='utf-8')
    lines = text.split('\n')

    # Find section 6.2 start and end
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if '### 6.2' in line:
            start_idx = i
        elif start_idx is not None and (line.startswith('### 6.3') or line.startswith('## 7')):
            end_idx = i
            break

    if start_idx is None:
        raise ValueError("Could not find Section 6.2 in PRD")
    if end_idx is None:
        end_idx = len(lines)

    section_lines = lines[start_idx:end_idx]

    nodes = []
    # Stack tracks (heading_depth, node_index) for parent resolution
    depth_stack: list[tuple[int, int]] = []

    for line in section_lines:
        # Match heading lines with backtick annotations
        heading_match = re.match(r'^(#{3,15})\s+(.*?)`\[([^\]]+)\](.*)$', line)
        if not heading_match:
            # Try to capture definition or example for the last node
            if nodes:
                def_match = re.match(r'^\*Definition:\s*(.*?)\*?\s*$', line)
                if def_match:
                    nodes[-1]['definition'] = def_match.group(1).rstrip('*').strip()
                    continue

                ex_match = re.match(r'^\*Example:\s*(.*?)\*?\s*$', line)
                if ex_match:
                    nodes[-1]['example'] = ex_match.group(1).rstrip('*').strip()
                    continue

                # Some definitions/examples span without ending *
                note_match = re.match(r'^\*(?:Decision|Note):\s*(.*?)\*?\s*$', line)
                if note_match:
                    nodes[-1]['classification_notes'] = note_match.group(1).rstrip('*').strip()
                    continue
            continue

        hashes = heading_match.group(1)
        heading_depth = len(hashes)
        raw_label = heading_match.group(2)
        first_tag = heading_match.group(3)
        rest_annotations = heading_match.group(4)

        # Clean the label: remove tree connectors ├── └── and leading/trailing spaces
        label = re.sub(r'[├└│─]+', '', raw_label).strip()
        # Remove parenthetical descriptions for the ID but keep in label
        label_for_display = label
        # For slugification, use a cleaner version without long parentheticals
        label_for_slug = re.sub(r'\s*\(.*?\)\s*', ' ', label).strip()
        # But keep short parentheticals that are part of the name
        if len(label_for_slug) < 3:
            label_for_slug = label

        # Parse all annotations: [L1][DERIVED], [L2][contra-revenue], etc.
        all_annotation_text = f'[{first_tag}]' + rest_annotations.split('`')[0] if '`' in rest_annotations else f'[{first_tag}]{rest_annotations}'
        tags = re.findall(r'\[([^\]]+)\]', all_annotation_text)

        level = None
        hint = None
        extra_tags = []
        for tag in tags:
            tag_upper = tag.upper().strip()
            if tag_upper.startswith('L') and tag_upper[1:].isdigit():
                level = int(tag_upper[1:])
            elif tag_upper in ('LEAF', 'DECISION', 'DERIVED', 'NON-GAAP'):
                hint = tag_upper
            else:
                extra_tags.append(tag.strip())

        if level is None:
            continue  # skip lines without level annotation

        # Determine parent using heading depth
        while depth_stack and depth_stack[-1][0] >= heading_depth:
            depth_stack.pop()

        parent_id = None
        parent_label = None
        if depth_stack:
            parent_idx = depth_stack[-1][1]
            parent_label = nodes[parent_idx].get('label_for_slug', nodes[parent_idx]['label'])
            parent_id = f"fintree:{slugify(parent_label)}"

        node = {
            'label': label_for_display,
            'label_for_slug': label_for_slug,
            'level': level,
            'hint': hint,
            'heading_depth': heading_depth,
            'parent_id': parent_id,
            'parent_label': parent_label,
            'extra_tags': extra_tags,
            'definition': '',
            'example': '',
            'classification_notes': '',
        }

        node_idx = len(nodes)
        nodes.append(node)
        depth_stack.append((heading_depth, node_idx))

    return nodes


# ---------------------------------------------------------------------------
# YAML Generation
# ---------------------------------------------------------------------------

def determine_node_type(level: int, hint: str | None, has_children: bool) -> str:
    if hint == 'DECISION':
        return 'DECISION'
    if hint == 'NON-GAAP':
        return 'NON_GAAP'
    if level == 1:
        return 'GAAP_SUBTOTAL'
    if level == 2:
        return 'MAJOR_CATEGORY'
    if level == 3:
        return 'SUB_CATEGORY'
    if level == 4 and not has_children:
        return 'LINE_ITEM'
    if level == 5:
        return 'ADJUSTMENT'
    if not has_children:
        return 'LINE_ITEM'
    return 'SUB_CATEGORY'


def determine_aggregation(hint: str | None, is_leaf: bool) -> str:
    if hint == 'DERIVED':
        return 'DERIVED'
    if hint == 'DECISION':
        return 'DECISION'
    if hint == 'LEAF' or is_leaf:
        return 'LEAF'
    return 'SUM'


def generate_node_yaml(node: dict, has_children: bool) -> dict:
    """Generate full YAML dict for a node."""
    slug = slugify(node['label_for_slug'])
    node_id = f"fintree:{slug}"
    is_leaf = node.get('hint') == 'LEAF' or (not has_children and node['level'] >= 3)

    # Build the output dict matching the seed node format
    result: dict = {
        'id': node_id,
        'xbrl_tag': '',
        'label': node['label'],
        'short_label': node['label'][:30] if len(node['label']) > 30 else node['label'],
        'level': node['level'],
        'node_type': determine_node_type(node['level'], node.get('hint'), has_children),
        'parent_id': node.get('parent_id') or 'null',
        'aggregation_type': determine_aggregation(node.get('hint'), is_leaf),
        'formula_human': '',
        'asc_reference': '',
        'definition': node.get('definition', ''),
        'example': node.get('example', ''),
        'normal_balance': guess_normal_balance(
            node['label'], node.get('hint'), node.get('parent_label')
        ),
        'sign_convention': guess_sign_convention(node['label'], node.get('hint')),
        'industry_variants': ['manufacturing', 'saas', 'retail', 'financial_services', 'professional_services'],
        'is_leaf': is_leaf,
        'is_decision_node': node.get('hint') == 'DECISION',
        'is_non_gaap': node.get('hint') == 'NON-GAAP',
        'below_the_line': False,
        'non_recurring': False,
        'ai_context_tags': [],
        'classification_notes': node.get('classification_notes', ''),
        'variance_drivers': {
            'tags': [],
            'playbook': {'if_increased': '', 'if_decreased': ''},
        },
        'comparability': {
            'variations': '',
            'examples': [],
        },
        'coa_mapping': {},
    }

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    prd_path = Path(__file__).resolve().parent.parent.parent.parent / 'fintree_prd.md'
    output_dir = Path(__file__).resolve().parent.parent / 'nodes'
    output_dir.mkdir(exist_ok=True)

    if not prd_path.exists():
        print(f"ERROR: PRD not found at {prd_path}")
        return

    print(f"Parsing PRD: {prd_path}")
    nodes = parse_prd_section_62(str(prd_path))
    print(f"Parsed {len(nodes)} nodes from PRD Section 6.2")

    # Compute which nodes have children (for is_leaf determination)
    node_ids = set()
    parent_ids = set()
    for node in nodes:
        slug = slugify(node['label_for_slug'])
        nid = f"fintree:{slug}"
        node_ids.add(nid)
        if node.get('parent_id'):
            parent_ids.add(node['parent_id'])

    # Detect below-the-line nodes
    below_the_line_depth = None
    for node in nodes:
        lower = node['label'].lower()
        if 'below-the-line' in lower or 'below the line' in lower:
            below_the_line_depth = node['heading_depth']
        if below_the_line_depth is not None and node['heading_depth'] >= below_the_line_depth:
            node['below_the_line'] = True
        else:
            node['below_the_line'] = False
            below_the_line_depth_reset = None

    # Non-recurring flags
    non_recurring_keywords = ['restructuring', 'impairment', 'extraordinary', 'discontinued', 'cumulative effect']
    for node in nodes:
        lower = node['label'].lower()
        if any(kw in lower for kw in non_recurring_keywords):
            node['non_recurring'] = True

    # Get existing files
    existing = {f.stem for f in output_dir.glob('*.yaml')}
    print(f"Found {len(existing)} existing YAML files")

    generated = 0
    skipped_existing = 0
    for node in nodes:
        slug = slugify(node['label_for_slug'])
        nid = f"fintree:{slug}"
        filename = slug_to_filename(slug)

        has_children = nid in parent_ids

        if filename in existing:
            skipped_existing += 1
            print(f"  SKIP (exists): {filename}.yaml")
            continue

        yaml_data = generate_node_yaml(node, has_children)
        yaml_data['below_the_line'] = node.get('below_the_line', False)
        yaml_data['non_recurring'] = node.get('non_recurring', False)

        filepath = output_dir / f"{filename}.yaml"
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        generated += 1
        print(f"  CREATED: {filename}.yaml")

    print(f"\n{'='*60}")
    print(f"Generated {generated} new node files.")
    print(f"Skipped {skipped_existing} existing files.")
    print(f"Total nodes parsed: {len(nodes)}")
    print(f"Total YAML files: {generated + skipped_existing}")


if __name__ == '__main__':
    main()
