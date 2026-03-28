"""FinTree — Canonical GAAP P&L hierarchy tree for humans and AI agents."""

from fintree.models import Node, TreeData, IndustryOverlay, NonGAAPMeasure
from fintree.tree import TreeGraph
from fintree.search import SearchIndex

__version__ = "2.0.0"
__all__ = [
    "Node",
    "TreeData",
    "IndustryOverlay",
    "NonGAAPMeasure",
    "TreeGraph",
    "SearchIndex",
]
