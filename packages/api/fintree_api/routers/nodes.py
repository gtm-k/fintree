"""Node endpoints — browse, inspect, and traverse the P&L hierarchy."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from fintree_api.deps import get_tree

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


def _node_summary(node) -> dict:
    """Compact node representation for list views."""
    return {
        "id": node.id,
        "label": node.label,
        "level": node.level,
        "node_type": node.node_type,
        "parent_id": node.parent_id,
        "is_leaf": node.is_leaf,
        "children_count": len(node.children_ids),
    }


def _node_detail(node) -> dict:
    """Full node representation."""
    data = node.model_dump(exclude_none=True)
    for key in list(data.keys()):
        val = data[key]
        if val == "" or val == [] or val == {} or val is None:
            del data[key]
    return data


@router.get("")
def list_nodes(
    level: Optional[int] = Query(None, ge=1, le=5),
    node_type: Optional[str] = None,
    parent_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List all nodes with optional filters."""
    tree = get_tree()
    nodes = tree.all_nodes()
    if level is not None:
        nodes = [n for n in nodes if n.level == level]
    if node_type:
        nodes = [n for n in nodes if n.node_type == node_type]
    if parent_id:
        nodes = [n for n in nodes if n.parent_id == parent_id]
    total = len(nodes)
    nodes = nodes[offset : offset + limit]
    return {"total": total, "nodes": [_node_summary(n) for n in nodes]}


@router.get("/detail")
def get_node(id: str = Query(..., description="Node ID (e.g. fintree:NetIncome)")):
    """Get full details for a single node."""
    tree = get_tree()
    node = tree.get(id)
    if not node:
        raise HTTPException(404, f"Node '{id}' not found")
    return _node_detail(node)


@router.get("/children")
def get_children(id: str = Query(...)):
    """Get children of a node."""
    tree = get_tree()
    node = tree.get(id)
    if not node:
        raise HTTPException(404, f"Node '{id}' not found")
    children = tree.children(id)
    return {"parent_id": id, "children": [_node_summary(c) for c in children]}


@router.get("/ancestors")
def get_ancestors(id: str = Query(...)):
    """Get ancestor chain from node to root."""
    tree = get_tree()
    node = tree.get(id)
    if not node:
        raise HTTPException(404, f"Node '{id}' not found")
    ancestors = tree.ancestors(id)
    return {"node_id": id, "ancestors": [_node_summary(a) for a in ancestors]}


@router.get("/subtree")
def get_subtree(id: str = Query(...)):
    """Get all descendants of a node."""
    tree = get_tree()
    node = tree.get(id)
    if not node:
        raise HTTPException(404, f"Node '{id}' not found")
    subtree = tree.subtree(id)
    return {"root_id": id, "total": len(subtree), "nodes": [_node_summary(n) for n in subtree]}
