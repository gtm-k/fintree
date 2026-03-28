"""Shared dependencies for the FinTree API."""

from functools import lru_cache

from fintree.tree import TreeGraph
from fintree.search import SearchIndex


@lru_cache(maxsize=1)
def get_tree() -> TreeGraph:
    return TreeGraph()


@lru_cache(maxsize=1)
def get_search_index() -> SearchIndex:
    tree = get_tree()
    return SearchIndex(tree.all_nodes())
