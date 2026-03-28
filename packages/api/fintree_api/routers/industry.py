"""Industry overlay endpoints."""

from fastapi import APIRouter, HTTPException

from fintree_api.deps import get_tree

router = APIRouter(prefix="/api/industry", tags=["industry"])


@router.get("")
def list_overlays():
    """List all available industry overlays."""
    tree = get_tree()
    overlays = []
    for name in tree.overlay_names():
        overlay = tree.get_overlay(name)
        mods = overlay.modifications
        overlays.append({
            "industry": overlay.industry,
            "label": overlay.label,
            "description": overlay.description.strip(),
            "suppress_count": len(mods.suppress),
            "emphasize_count": len(mods.emphasize),
            "rename_count": len(mods.rename),
            "add_count": len(mods.add),
        })
    return {"overlays": overlays}


@router.get("/{industry}")
def get_overlay(industry: str):
    """Get full details for an industry overlay."""
    tree = get_tree()
    overlay = tree.get_overlay(industry)
    if not overlay:
        raise HTTPException(404, f"Industry overlay '{industry}' not found")
    return overlay.model_dump()


@router.get("/{industry}/tree")
def get_industry_tree(industry: str):
    """Get the full tree with industry overlay applied (suppressed nodes removed)."""
    tree = get_tree()
    overlay = tree.get_overlay(industry)
    if not overlay:
        raise HTTPException(404, f"Industry overlay '{industry}' not found")

    suppressed = set(overlay.modifications.suppress)
    emphasized = set(overlay.modifications.emphasize)
    renames = overlay.modifications.rename

    def build_node(node) -> dict | None:
        if node.id in suppressed:
            return None
        children = tree.children(node.id)
        child_nodes = []
        for c in children:
            cn = build_node(c)
            if cn:
                child_nodes.append(cn)

        label = renames.get(node.id, node.label)
        result = {
            "id": node.id,
            "label": label,
            "level": node.level,
            "node_type": node.node_type,
            "is_leaf": node.is_leaf,
            "emphasized": node.id in emphasized,
        }
        if child_nodes:
            result["children"] = child_nodes
        return result

    return {
        "industry": overlay.industry,
        "label": overlay.label,
        "tree": build_node(tree.root),
    }
