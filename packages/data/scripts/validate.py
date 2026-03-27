#!/usr/bin/env python3
"""
Validate the FinTree data layer:
1. Every parent_id references a valid node
2. Every children_ids entry references a valid node
3. Leaf nodes have no children
4. Required fields are present on every node
5. Root node exists
6. No orphan nodes (every non-root node has a valid parent)
7. No circular references
"""
import json
import yaml
from pathlib import Path


REQUIRED_FIELDS = ['id', 'label', 'level', 'node_type', 'aggregation_type']
VALID_NODE_TYPES = {'GAAP_SUBTOTAL', 'MAJOR_CATEGORY', 'SUB_CATEGORY', 'LINE_ITEM', 'ADJUSTMENT', 'DECISION', 'NON_GAAP'}
VALID_AGGREGATION_TYPES = {'SUM', 'DIFFERENCE', 'DERIVED', 'CONTRA', 'SUBTOTAL', 'LEAF', 'DECISION'}
VALID_BALANCES = {'DEBIT', 'CREDIT'}
ROOT_NODE_ID = 'fintree:NetIncome'


class ValidationResult:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def error(self, msg: str):
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def log(self, msg: str):
        self.info.append(msg)

    def print_report(self):
        print("\n" + "=" * 60)
        print("VALIDATION REPORT")
        print("=" * 60)

        if self.info:
            print(f"\nINFO ({len(self.info)}):")
            for msg in self.info:
                print(f"  [INFO] {msg}")

        if self.warnings:
            print(f"\nWARNINGS ({len(self.warnings)}):")
            for msg in self.warnings:
                print(f"  [WARN] {msg}")

        if self.errors:
            print(f"\nERRORS ({len(self.errors)}):")
            for msg in self.errors:
                print(f"  [ERROR] {msg}")

        print(f"\n{'=' * 60}")
        if self.errors:
            print(f"RESULT: FAIL ({len(self.errors)} errors, {len(self.warnings)} warnings)")
        else:
            print(f"RESULT: PASS ({len(self.warnings)} warnings)")
        print("=" * 60)

        return len(self.errors) == 0


def load_nodes_from_yaml(directories: list[Path]) -> dict[str, dict]:
    """Load all YAML node files."""
    nodes = {}
    for directory in directories:
        if not directory.exists():
            continue
        for yaml_file in sorted(directory.glob('*.yaml')):
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if data and 'id' in data:
                    nodes[data['id']] = data
            except Exception as e:
                print(f"  ERROR loading {yaml_file.name}: {e}")
    return nodes


def validate_yaml_nodes(nodes: dict[str, dict], result: ValidationResult):
    """Validate YAML node files directly."""
    result.log(f"Validating {len(nodes)} YAML nodes")

    all_ids = set(nodes.keys())

    # Check root exists
    if ROOT_NODE_ID not in nodes:
        result.error(f"Root node '{ROOT_NODE_ID}' not found")
    else:
        root = nodes[ROOT_NODE_ID]
        parent = root.get('parent_id')
        if parent and parent != 'null' and parent is not None:
            result.error(f"Root node has non-null parent_id: '{parent}'")

    # Per-node validation
    for nid, node in nodes.items():
        # Required fields
        for field in REQUIRED_FIELDS:
            if field not in node or node[field] is None or node[field] == '':
                result.error(f"{nid}: Missing required field '{field}'")

        # Valid node_type
        nt = node.get('node_type', '')
        if nt and nt not in VALID_NODE_TYPES:
            result.error(f"{nid}: Invalid node_type '{nt}'")

        # Valid aggregation_type
        at = node.get('aggregation_type', '')
        if at and at not in VALID_AGGREGATION_TYPES:
            result.error(f"{nid}: Invalid aggregation_type '{at}'")

        # Valid normal_balance
        nb = node.get('normal_balance', '')
        if nb and nb not in VALID_BALANCES:
            result.error(f"{nid}: Invalid normal_balance '{nb}'")

        # parent_id validation
        parent = node.get('parent_id')
        if parent and parent != 'null' and parent is not None:
            if parent not in all_ids:
                result.error(f"{nid}: parent_id '{parent}' references non-existent node")

        # Level range
        level = node.get('level')
        if level is not None and (level < 1 or level > 5):
            result.error(f"{nid}: level {level} is out of range [1,5]")

        # Leaf consistency
        if node.get('is_leaf', False):
            # Will check children after computing children map
            pass

        # ID format
        if not nid.startswith('fintree:'):
            result.error(f"{nid}: ID does not start with 'fintree:'")

    # Compute children
    children_map: dict[str, list[str]] = {nid: [] for nid in all_ids}
    for nid, node in nodes.items():
        parent = node.get('parent_id')
        if parent and parent != 'null' and parent is not None and parent in all_ids:
            children_map[parent].append(nid)

    # Leaf nodes should have no children
    for nid, node in nodes.items():
        if node.get('is_leaf', False) and children_map[nid]:
            result.warn(f"{nid}: Marked as leaf but has {len(children_map[nid])} children: {children_map[nid]}")

    # Non-leaf parent nodes should have children
    for nid, node in nodes.items():
        if not node.get('is_leaf', False) and not children_map[nid]:
            if nid != ROOT_NODE_ID:
                result.warn(f"{nid}: Not marked as leaf but has no children")

    # Check for orphans (non-root nodes without valid parent)
    for nid, node in nodes.items():
        if nid == ROOT_NODE_ID:
            continue
        parent = node.get('parent_id')
        if not parent or parent == 'null' or parent is None:
            result.warn(f"{nid}: Non-root node with null parent_id (orphan)")

    # Check for circular references
    def has_cycle(start: str) -> bool:
        visited = set()
        current = start
        while current:
            if current in visited:
                return True
            visited.add(current)
            parent = nodes.get(current, {}).get('parent_id')
            if parent == 'null' or parent is None:
                break
            current = parent
        return False

    for nid in nodes:
        if has_cycle(nid):
            result.error(f"{nid}: Circular reference detected in parent chain")


def validate_tree_json(tree_path: Path, result: ValidationResult):
    """Validate the compiled tree.json."""
    if not tree_path.exists():
        result.error(f"tree.json not found at {tree_path}")
        return

    with open(tree_path, 'r', encoding='utf-8') as f:
        tree = json.load(f)

    result.log(f"Validating tree.json ({tree.get('version', 'unknown')} version)")

    # Check top-level fields
    for field in ['version', 'gaap_standard', 'root_node_id', 'nodes', 'edges']:
        if field not in tree:
            result.error(f"tree.json: Missing top-level field '{field}'")

    if tree.get('root_node_id') != ROOT_NODE_ID:
        result.error(f"tree.json: root_node_id is '{tree.get('root_node_id')}', expected '{ROOT_NODE_ID}'")

    nodes_list = tree.get('nodes', [])
    all_ids = {n['id'] for n in nodes_list if 'id' in n}

    result.log(f"tree.json contains {len(nodes_list)} nodes and {len(tree.get('edges', []))} edges")

    # Validate children_ids references
    for node in nodes_list:
        nid = node.get('id', 'UNKNOWN')
        for child_id in node.get('children_ids', []):
            if child_id not in all_ids:
                result.error(f"tree.json {nid}: children_ids references non-existent node '{child_id}'")

    # Validate edges
    for edge in tree.get('edges', []):
        if edge.get('source') not in all_ids:
            result.error(f"tree.json edge: source '{edge.get('source')}' not found")
        if edge.get('target') not in all_ids:
            result.error(f"tree.json edge: target '{edge.get('target')}' not found")

    # Check root exists in nodes
    if ROOT_NODE_ID not in all_ids:
        result.error(f"tree.json: Root node '{ROOT_NODE_ID}' not in nodes list")


def main():
    base_dir = Path(__file__).resolve().parent.parent
    nodes_dir = base_dir / 'nodes'
    non_gaap_dir = base_dir / 'non-gaap'
    tree_path = base_dir / 'tree.json'

    result = ValidationResult()

    print("FinTree Data Validation")
    print("-" * 40)

    # 1. Validate YAML nodes
    print("\n1. Validating YAML node files...")
    nodes = load_nodes_from_yaml([nodes_dir, non_gaap_dir])
    validate_yaml_nodes(nodes, result)

    # 2. Validate tree.json (if it exists)
    print("2. Validating tree.json...")
    validate_tree_json(tree_path, result)

    # Print report
    passed = result.print_report()
    return 0 if passed else 1


if __name__ == '__main__':
    exit(main())
