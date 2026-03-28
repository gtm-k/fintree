"""Tree endpoints — stats, structure, and full tree data."""

from fastapi import APIRouter

from fintree_api.deps import get_tree

router = APIRouter(prefix="/api/tree", tags=["tree"])


@router.get("/stats")
def tree_stats():
    """Get tree statistics."""
    tree = get_tree()
    return tree.stats()


@router.get("/root")
def tree_root():
    """Get the root node with its immediate children."""
    tree = get_tree()
    root = tree.root
    children = tree.children(root.id)
    return {
        "root": {
            "id": root.id,
            "label": root.label,
            "level": root.level,
            "children_count": len(root.children_ids),
        },
        "children": [
            {
                "id": c.id,
                "label": c.label,
                "level": c.level,
                "node_type": c.node_type,
                "children_count": len(c.children_ids),
                "is_leaf": c.is_leaf,
            }
            for c in children
        ],
    }


@router.get("/full")
def tree_full():
    """Get the full tree structure (compact format for frontend rendering)."""
    tree = get_tree()

    def build_tree_node(node) -> dict:
        children = tree.children(node.id)
        result = {
            "id": node.id,
            "label": node.label,
            "level": node.level,
            "node_type": node.node_type,
            "is_leaf": node.is_leaf,
            "is_decision_node": node.is_decision_node,
            "normal_balance": node.normal_balance,
            "aggregation_type": node.aggregation_type,
        }
        if children:
            result["children"] = [build_tree_node(c) for c in children]
        return result

    return build_tree_node(tree.root)
