"""Non-GAAP measure endpoints."""

from fastapi import APIRouter, HTTPException

from fintree_api.deps import get_tree

router = APIRouter(prefix="/api/non-gaap", tags=["non-gaap"])


@router.get("")
def list_measures():
    """List all non-GAAP measures."""
    tree = get_tree()
    measures = tree.all_measures()
    return {
        "measures": [
            {
                "id": m.id,
                "label": m.label,
                "formula": m.formula,
                "component_count": len(m.components),
            }
            for m in measures
        ]
    }


@router.get("/detail")
def get_measure(id: str):
    """Get full details for a non-GAAP measure including reconciliation."""
    tree = get_tree()
    measure = tree.get_measure(id)
    if not measure:
        raise HTTPException(404, f"Non-GAAP measure '{id}' not found")

    # Enrich components with node labels
    components = []
    for comp in measure.components:
        node = tree.get(comp.node_id)
        components.append({
            "node_id": comp.node_id,
            "operation": comp.operation,
            "label": comp.label_override or (node.label if node else comp.node_id),
            "node_exists": node is not None,
        })

    return {
        "id": measure.id,
        "label": measure.label,
        "description": measure.description.strip(),
        "formula": measure.formula,
        "components": components,
        "sec_regulation_g": measure.sec_regulation_g.strip(),
        "common_adjustments": measure.common_adjustments,
        "notes": measure.notes.strip(),
    }
