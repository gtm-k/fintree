"""Search endpoints — full-text search and autocomplete."""

from fastapi import APIRouter, Query
from typing import Optional

from fintree_api.deps import get_search_index

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search_nodes(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    node_type: Optional[str] = None,
    level: Optional[int] = Query(None, ge=1, le=5),
):
    """Search nodes by keyword. Returns ranked results."""
    index = get_search_index()
    results = index.search(q, limit=limit, node_type=node_type, level=level)
    return {
        "query": q,
        "total": len(results),
        "results": [
            {
                "id": n.id,
                "label": n.label,
                "level": n.level,
                "node_type": n.node_type,
                "definition": n.definition[:200] if n.definition else "",
                "parent_id": n.parent_id,
                "is_leaf": n.is_leaf,
            }
            for n in results
        ],
    }


@router.get("/suggest")
def suggest(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
):
    """Autocomplete suggestions for node labels."""
    index = get_search_index()
    return {"query": q, "suggestions": index.suggest(q, limit=limit)}
