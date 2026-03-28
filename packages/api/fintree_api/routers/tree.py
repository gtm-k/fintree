"""Tree endpoints — stats, structure, and full tree data."""

from fastapi import APIRouter, Query
from typing import Optional

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


# P&L section definitions in correct financial statement order
PL_SECTIONS = [
    {
        "key": "revenue",
        "label": "Revenue",
        "icon": "📈",
        "color": "#10b981",
        "root_ids": ["fintree:NetRevenue", "fintree:GrossRevenue", "fintree:RevenueDeductions"],
        "type": "section",
    },
    {
        "key": "cogs",
        "label": "Cost of Revenue",
        "icon": "⚙️",
        "color": "#ef4444",
        "root_ids": ["fintree:CostOfGoodsSoldCostOfRevenue", "fintree:Cogs"],
        "type": "section",
    },
    {
        "key": "gross_profit",
        "label": "Gross Profit",
        "formula": "Revenue − Cost of Revenue",
        "node_id": "fintree:GrossProfit",
        "type": "subtotal",
    },
    {
        "key": "opex",
        "label": "Operating Expenses",
        "icon": "💼",
        "color": "#f59e0b",
        "root_ids": [
            "fintree:OperatingExpenses",
            "fintree:SellingExpenses",
            "fintree:GeneralAdministrativeExpenses",
            "fintree:ResearchDevelopment",
            "fintree:DepreciationAmortization",
        ],
        "type": "section",
    },
    {
        "key": "ebit",
        "label": "Operating Income (EBIT)",
        "formula": "Gross Profit − Operating Expenses",
        "node_id": "fintree:OperatingIncome",
        "type": "subtotal",
    },
    {
        "key": "nonop",
        "label": "Non-Operating Income & Expenses",
        "icon": "📊",
        "color": "#64748b",
        "root_ids": ["fintree:NonoperatingIncomeExpenses", "fintree:NonoperatingIncome", "fintree:NonoperatingExpenses"],
        "type": "section",
    },
    {
        "key": "ebt",
        "label": "Pre-Tax Income (EBT)",
        "formula": "EBIT ± Non-Operating Items",
        "node_id": "fintree:PretaxIncome",
        "type": "subtotal",
    },
    {
        "key": "tax",
        "label": "Income Tax Expense",
        "icon": "🏛️",
        "color": "#f87171",
        "root_ids": ["fintree:IncomeTaxExpense", "fintree:CurrentTaxExpense", "fintree:DeferredTaxExpense"],
        "type": "section",
    },
    {
        "key": "net_income",
        "label": "Net Income",
        "formula": "EBT − Income Tax Expense",
        "node_id": "fintree:NetIncome",
        "type": "bottom_line",
    },
    {
        "key": "btl",
        "label": "Below-the-Line Items",
        "icon": "📋",
        "color": "#475569",
        "root_ids": ["fintree:BelowthelineItems", "fintree:DiscontinuedOperations", "fintree:ExtraordinaryItems", "fintree:CumulativeEffectOfAccountingChanges"],
        "type": "section",
    },
]


def _collect_section_nodes(tree, root_ids: list[str], suppressed: set, emphasized: set, renames: dict) -> list[dict]:
    """Collect all descendant nodes for a P&L section."""
    seen = set()
    nodes = []
    for rid in root_ids:
        for n in tree.subtree(rid):
            if n.id in seen or n.id in root_ids:
                seen.add(n.id)
                continue
            seen.add(n.id)
            label = renames.get(n.id, n.label)
            nodes.append({
                "id": n.id,
                "label": label,
                "level": n.level,
                "node_type": n.node_type,
                "is_leaf": n.is_leaf,
                "parent_id": n.parent_id,
                "suppressed": n.id in suppressed,
                "emphasized": n.id in emphasized,
            })
    return nodes


@router.get("/pl-sections")
def pl_sections(industry: Optional[str] = Query(None)):
    """Return P&L structure in financial statement order, grouped by section."""
    tree = get_tree()

    suppressed = set()
    emphasized = set()
    renames = {}
    if industry:
        overlay = tree.get_overlay(industry)
        if overlay:
            suppressed = set(overlay.modifications.suppress)
            emphasized = set(overlay.modifications.emphasize)
            renames = overlay.modifications.rename

    sections = []
    for sec in PL_SECTIONS:
        entry = {"key": sec["key"], "label": sec["label"], "type": sec["type"]}

        if sec["type"] == "section":
            entry["icon"] = sec["icon"]
            entry["color"] = sec["color"]
            nodes = _collect_section_nodes(tree, sec["root_ids"], suppressed, emphasized, renames)
            entry["nodes"] = nodes
            entry["total"] = len(nodes)
            entry["visible"] = len([n for n in nodes if not n["suppressed"]])
            entry["emphasized_count"] = len([n for n in nodes if n["emphasized"]])
            # Include first valid root_id so frontend can show detail on header click
            for rid in sec["root_ids"]:
                if tree.get(rid):
                    entry["node_id"] = rid
                    break
        elif sec["type"] in ("subtotal", "bottom_line"):
            entry["formula"] = sec["formula"]
            node = tree.get(sec["node_id"])
            if node:
                entry["node_id"] = sec["node_id"]
                entry["label"] = renames.get(node.id, node.label)

        sections.append(entry)

    return {
        "industry": industry,
        "sections": sections,
        "stats": {
            "total_nodes": tree.node_count,
            "suppressed": len(suppressed),
            "visible": tree.node_count - len([s for s in suppressed if tree.get(s)]),
            "emphasized": len([e for e in emphasized if tree.get(e)]),
        },
    }
