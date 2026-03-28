"""SearchIndex — full-text search over FinTree nodes."""

from __future__ import annotations

import re
from typing import Optional

from fintree.models import Node


class SearchIndex:
    """Simple text search index over FinTree nodes.

    Supports keyword search across labels, definitions, tags, and XBRL tags.
    No external dependencies — uses basic token matching with relevance scoring.

    Usage::

        from fintree import TreeGraph, SearchIndex
        tree = TreeGraph()
        index = SearchIndex(tree.all_nodes())
        results = index.search("depreciation")
    """

    def __init__(self, nodes: list[Node]):
        self._nodes = {n.id: n for n in nodes}
        self._index: dict[str, set[str]] = {}  # token -> set of node IDs
        self._build_index()

    def _tokenize(self, text: str) -> list[str]:
        """Lowercase and split into alphanumeric tokens."""
        return re.findall(r"[a-z0-9]+", text.lower())

    def _build_index(self):
        """Build inverted index from node fields."""
        for node in self._nodes.values():
            # Concatenate searchable fields
            searchable = " ".join(
                filter(
                    None,
                    [
                        node.label,
                        node.short_label,
                        node.definition,
                        node.xbrl_tag,
                        node.asc_reference,
                        node.node_type,
                        node.classification_notes,
                        " ".join(node.ai_context_tags),
                        " ".join(node.industry_variants),
                    ],
                )
            )
            tokens = self._tokenize(searchable)
            for token in set(tokens):  # dedupe per node
                if token not in self._index:
                    self._index[token] = set()
                self._index[token].add(node.id)

    def search(
        self,
        query: str,
        limit: int = 20,
        node_type: Optional[str] = None,
        level: Optional[int] = None,
    ) -> list[Node]:
        """Search nodes by keyword query.

        Returns nodes ranked by number of matching tokens (simple relevance).
        Optional filters: node_type, level.
        """
        tokens = self._tokenize(query)
        if not tokens:
            return []

        # Score each node by number of matching query tokens
        scores: dict[str, float] = {}
        for token in tokens:
            # Exact token match
            if token in self._index:
                for nid in self._index[token]:
                    scores[nid] = scores.get(nid, 0) + 1.0

            # Prefix match (partial word) — lower weight
            for idx_token, nids in self._index.items():
                if idx_token.startswith(token) and idx_token != token:
                    for nid in nids:
                        scores[nid] = scores.get(nid, 0) + 0.3

        if not scores:
            return []

        # Boost exact label matches
        query_lower = query.lower()
        for nid, node in self._nodes.items():
            if nid in scores and query_lower in node.label.lower():
                scores[nid] += 3.0

        # Sort by score descending
        ranked = sorted(scores.keys(), key=lambda nid: scores[nid], reverse=True)

        # Apply filters
        results = []
        for nid in ranked:
            node = self._nodes[nid]
            if node_type and node.node_type != node_type:
                continue
            if level is not None and node.level != level:
                continue
            results.append(node)
            if len(results) >= limit:
                break

        return results

    def suggest(self, prefix: str, limit: int = 10) -> list[str]:
        """Return node labels matching a prefix (for autocomplete)."""
        prefix_lower = prefix.lower()
        matches = []
        for node in self._nodes.values():
            if node.label.lower().startswith(prefix_lower):
                matches.append(node.label)
            if len(matches) >= limit:
                break
        return sorted(matches)
