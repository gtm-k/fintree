#!/usr/bin/env python3
"""
Compile all YAML node files into a single tree.json.

Reads node .yaml files from packages/data/nodes/, industry overlays from
packages/data/industry/, and non-GAAP measures from packages/data/non-gaap/.
Resolves parent/child relationships, computes P&L ordering, and outputs
packages/data/tree.json.
"""
import json
import re
import yaml
from pathlib import Path
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# P&L Section Order — controls the display order of the tree
# ---------------------------------------------------------------------------
PL_SECTION_ORDER = [
    'fintree:NetRevenue',
    'fintree:GrossRevenue',
    'fintree:RevenueDeductions',
    'fintree:CostOfGoodsSoldCostOfRevenue',
    'fintree:GrossProfit',
    'fintree:OperatingExpenses',
    'fintree:SellingExpenses',
    'fintree:GeneralAdministrativeExpenses',
    'fintree:ResearchDevelopment',
    'fintree:DepreciationAmortization',
    'fintree:OperatingIncome',
    'fintree:NonoperatingIncomeExpenses',
    'fintree:NonoperatingIncome',
    'fintree:NonoperatingExpenses',
    'fintree:PretaxIncome',
    'fintree:IncomeTaxExpense',
    'fintree:CurrentTaxExpense',
    'fintree:DeferredTaxExpense',
    'fintree:NetIncome',
    'fintree:BelowthelineItems',
    'fintree:DiscontinuedOperations',
    'fintree:ExtraordinaryItems',
    'fintree:CumulativeEffectOfAccountingChanges',
]


def load_yaml_files(directories: list[Path]) -> dict[str, dict]:
    """Load all YAML node files from the given directories."""
    nodes = {}
    for directory in directories:
        if not directory.exists():
            continue
        for yaml_file in sorted(directory.glob('*.yaml')):
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if data and 'id' in data:
                    node_id = data['id']
                    if node_id in nodes:
                        print(f"  WARNING: Duplicate node ID '{node_id}' in {yaml_file.name} (already loaded)")
                    nodes[node_id] = data
                    nodes[node_id]['_source_file'] = yaml_file.name
                else:
                    print(f"  WARNING: Skipping {yaml_file.name} — no 'id' field")
            except Exception as e:
                print(f"  ERROR loading {yaml_file.name}: {e}")
    return nodes


def load_yaml_list(directory: Path) -> list[dict]:
    """Load all YAML files from a directory as a list (for overlays/measures)."""
    items = []
    if not directory.exists():
        return items
    for yaml_file in sorted(directory.glob('*.yaml')):
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if data:
                data['_source_file'] = yaml_file.name
                items.append(data)
        except Exception as e:
            print(f"  ERROR loading {yaml_file.name}: {e}")
    return items


def compute_children(nodes: dict[str, dict]) -> dict[str, list[str]]:
    """Build a mapping of node_id -> list of children_ids."""
    children_map: dict[str, list[str]] = {nid: [] for nid in nodes}
    for nid, node in nodes.items():
        parent = node.get('parent_id')
        if parent and parent != 'null' and parent in nodes:
            children_map[parent].append(nid)
    return children_map


def compute_pl_order(nodes: dict[str, dict], children_map: dict[str, list[str]]) -> dict[str, int]:
    """
    Assign a P&L display order to each node using DFS traversal from root.
    Major sections follow the PL_SECTION_ORDER; within each section, children
    are ordered by their level and then alphabetically.
    """
    # Build order lookup for known section nodes
    section_rank = {nid: idx for idx, nid in enumerate(PL_SECTION_ORDER)}

    order_map: dict[str, int] = {}
    counter = [0]

    def sort_key(nid: str) -> tuple:
        """Sort children: section-order first, then level, then label."""
        rank = section_rank.get(nid, 9999)
        node = nodes.get(nid, {})
        level = node.get('level', 99)
        label = node.get('label', '')
        return (rank, level, label)

    def dfs(nid: str):
        if nid in order_map:
            return
        order_map[nid] = counter[0]
        counter[0] += 1
        kids = sorted(children_map.get(nid, []), key=sort_key)
        for kid in kids:
            dfs(kid)

    # Start from root
    root_id = 'fintree:NetIncome'
    if root_id in nodes:
        dfs(root_id)

    # Handle any orphan nodes not reachable from root
    for nid in sorted(nodes.keys()):
        if nid not in order_map:
            dfs(nid)

    return order_map


def build_edges(nodes: dict[str, dict]) -> list[dict]:
    """Build an edge list for graph representation."""
    edges = []
    for nid, node in nodes.items():
        parent = node.get('parent_id')
        if parent and parent != 'null' and parent in nodes:
            edges.append({
                'source': parent,
                'target': nid,
                'relationship': 'parent_of',
            })
    return edges


def build_tree_json(
    nodes: dict[str, dict],
    children_map: dict[str, list[str]],
    pl_order: dict[str, int],
    edges: list[dict],
    industry_overlays: list[dict],
    non_gaap_measures: list[dict],
) -> dict:
    """Assemble the final tree.json structure."""
    # Build enriched node list
    node_list = []
    for nid, node in nodes.items():
        enriched = dict(node)
        # Remove internal tracking fields
        enriched.pop('_source_file', None)
        # Add computed fields
        enriched['children_ids'] = sorted(
            children_map.get(nid, []),
            key=lambda cid: pl_order.get(cid, 9999)
        )
        enriched['pl_order'] = pl_order.get(nid, 9999)
        # Ensure parent_id is null (not string 'null') for root
        if enriched.get('parent_id') == 'null' or not enriched.get('parent_id'):
            enriched['parent_id'] = None
        node_list.append(enriched)

    # Sort nodes by P&L order
    node_list.sort(key=lambda n: n.get('pl_order', 9999))

    # Clean overlays and measures (remove _source_file)
    clean_overlays = [{k: v for k, v in o.items() if k != '_source_file'} for o in industry_overlays]
    clean_measures = [{k: v for k, v in m.items() if k != '_source_file'} for m in non_gaap_measures]

    # Compute stats
    total = len(node_list)
    leaf_count = sum(1 for n in node_list if n.get('is_leaf', False))
    decision_count = sum(1 for n in node_list if n.get('is_decision_node', False))
    non_gaap_count = sum(1 for n in node_list if n.get('is_non_gaap', False))
    levels = {}
    for n in node_list:
        lvl = n.get('level', 0)
        levels[f'L{lvl}'] = levels.get(f'L{lvl}', 0) + 1

    return {
        'version': '2.0.0',
        'gaap_standard': 'US GAAP',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'root_node_id': 'fintree:NetIncome',
        'stats': {
            'total_nodes': total,
            'leaf_nodes': leaf_count,
            'decision_nodes': decision_count,
            'non_gaap_nodes': non_gaap_count,
            'industry_overlays': len(clean_overlays),
            'non_gaap_measures': len(clean_measures),
            'by_level': dict(sorted(levels.items())),
        },
        'nodes': node_list,
        'edges': edges,
        'industry_overlays': clean_overlays,
        'non_gaap_measures': clean_measures,
    }


def main():
    base_dir = Path(__file__).resolve().parent.parent
    nodes_dir = base_dir / 'nodes'
    industry_dir = base_dir / 'industry'
    non_gaap_dir = base_dir / 'non-gaap'
    output_path = base_dir / 'tree.json'

    print(f"Loading YAML files from:")
    print(f"  Nodes:     {nodes_dir}")
    print(f"  Industry:  {industry_dir}")
    print(f"  Non-GAAP:  {non_gaap_dir}")

    nodes = load_yaml_files([nodes_dir])
    print(f"\nLoaded {len(nodes)} nodes")

    industry_overlays = load_yaml_list(industry_dir)
    print(f"Loaded {len(industry_overlays)} industry overlays")

    non_gaap_measures = load_yaml_list(non_gaap_dir)
    print(f"Loaded {len(non_gaap_measures)} non-GAAP measures")

    # Compute relationships
    children_map = compute_children(nodes)
    pl_order = compute_pl_order(nodes, children_map)
    edges = build_edges(nodes)

    # Build tree
    tree = build_tree_json(nodes, children_map, pl_order, edges, industry_overlays, non_gaap_measures)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)

    print(f"\nWrote tree.json to {output_path}")
    print(f"  Total nodes: {tree['stats']['total_nodes']}")
    print(f"  Leaf nodes: {tree['stats']['leaf_nodes']}")
    print(f"  Decision nodes: {tree['stats']['decision_nodes']}")
    print(f"  Non-GAAP nodes: {tree['stats']['non_gaap_nodes']}")
    print(f"  Industry overlays: {tree['stats']['industry_overlays']}")
    print(f"  Non-GAAP measures: {tree['stats']['non_gaap_measures']}")
    print(f"  Edges: {len(edges)}")
    print(f"  By level: {tree['stats']['by_level']}")


if __name__ == '__main__':
    main()
