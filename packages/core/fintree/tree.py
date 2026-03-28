"""TreeGraph — load and traverse the FinTree P&L hierarchy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fintree.models import IndustryOverlay, Node, NonGAAPMeasure, TreeData


# Default path to bundled tree.json
_DEFAULT_TREE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "tree.json"


class TreeGraph:
    """In-memory representation of the FinTree P&L hierarchy.

    Usage::

        tree = TreeGraph()           # loads bundled tree.json
        tree = TreeGraph("path.json")  # loads custom file

        node = tree.get("fintree:NetIncome")
        children = tree.children("fintree:OperatingExpenses")
        ancestors = tree.ancestors("fintree:DigitalAdvertising")
        subtree = tree.subtree("fintree:GrossRevenue")
    """

    def __init__(self, tree_path: str | Path | None = None):
        path = Path(tree_path) if tree_path else _DEFAULT_TREE_PATH
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self._data = TreeData.model_validate(raw)
        self._nodes: dict[str, Node] = {n.id: n for n in self._data.nodes}
        self._overlays: dict[str, IndustryOverlay] = {
            o.industry: o for o in self._data.industry_overlays
        }
        self._measures: dict[str, NonGAAPMeasure] = {
            m.id: m for m in self._data.non_gaap_measures
        }

    # -- Properties --

    @property
    def data(self) -> TreeData:
        return self._data

    @property
    def root(self) -> Node:
        return self._nodes[self._data.root_node_id]

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    # -- Node access --

    def get(self, node_id: str) -> Optional[Node]:
        return self._nodes.get(node_id)

    def all_nodes(self) -> list[Node]:
        return list(self._data.nodes)

    def children(self, node_id: str) -> list[Node]:
        node = self._nodes.get(node_id)
        if not node:
            return []
        return [self._nodes[cid] for cid in node.children_ids if cid in self._nodes]

    def parent(self, node_id: str) -> Optional[Node]:
        node = self._nodes.get(node_id)
        if not node or not node.parent_id:
            return None
        return self._nodes.get(node.parent_id)

    def ancestors(self, node_id: str) -> list[Node]:
        """Return list of ancestors from immediate parent up to root."""
        result = []
        current = self._nodes.get(node_id)
        if not current:
            return result
        visited = set()
        while current and current.parent_id and current.parent_id not in visited:
            visited.add(current.id)
            parent = self._nodes.get(current.parent_id)
            if parent:
                result.append(parent)
                current = parent
            else:
                break
        return result

    def subtree(self, node_id: str) -> list[Node]:
        """Return all descendants of a node (BFS), including the node itself."""
        root = self._nodes.get(node_id)
        if not root:
            return []
        result = []
        queue = [root]
        while queue:
            node = queue.pop(0)
            result.append(node)
            for cid in node.children_ids:
                child = self._nodes.get(cid)
                if child:
                    queue.append(child)
        return result

    def siblings(self, node_id: str) -> list[Node]:
        node = self._nodes.get(node_id)
        if not node or not node.parent_id:
            return []
        parent = self._nodes.get(node.parent_id)
        if not parent:
            return []
        return [
            self._nodes[cid]
            for cid in parent.children_ids
            if cid != node_id and cid in self._nodes
        ]

    def path_to_root(self, node_id: str) -> list[Node]:
        """Return path from node up to root (inclusive)."""
        node = self._nodes.get(node_id)
        if not node:
            return []
        return [node] + self.ancestors(node_id)

    # -- Industry overlays --

    def overlay_names(self) -> list[str]:
        return list(self._overlays.keys())

    def get_overlay(self, industry: str) -> Optional[IndustryOverlay]:
        return self._overlays.get(industry)

    def apply_overlay(self, industry: str) -> list[Node]:
        """Return all nodes with overlay applied (suppressed nodes removed, renames applied)."""
        overlay = self._overlays.get(industry)
        if not overlay:
            return self.all_nodes()

        suppressed = set(overlay.modifications.suppress)
        renames = overlay.modifications.rename

        result = []
        for node in self._data.nodes:
            if node.id in suppressed:
                continue
            if node.id in renames:
                renamed = node.model_copy()
                renamed.label = renames[node.id]
                result.append(renamed)
            else:
                result.append(node)
        return result

    def emphasized_nodes(self, industry: str) -> list[Node]:
        overlay = self._overlays.get(industry)
        if not overlay:
            return []
        emphasized_ids = set(overlay.modifications.emphasize)
        return [self._nodes[nid] for nid in emphasized_ids if nid in self._nodes]

    # -- Non-GAAP measures --

    def measure_ids(self) -> list[str]:
        return list(self._measures.keys())

    def get_measure(self, measure_id: str) -> Optional[NonGAAPMeasure]:
        return self._measures.get(measure_id)

    def all_measures(self) -> list[NonGAAPMeasure]:
        return list(self._data.non_gaap_measures)

    # -- Stats --

    def stats(self) -> dict:
        return self._data.stats.model_dump()

    def level_nodes(self, level: int) -> list[Node]:
        return [n for n in self._data.nodes if n.level == level]
