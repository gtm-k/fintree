"""Pydantic models for FinTree data structures."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class VariancePlaybook(BaseModel):
    if_increased: str = ""
    if_decreased: str = ""


class VarianceDrivers(BaseModel):
    tags: list[str] = Field(default_factory=list)
    playbook: VariancePlaybook = Field(default_factory=VariancePlaybook)


class ComparabilityExample(BaseModel):
    company: str
    treatment: str


class Comparability(BaseModel):
    variations: str = ""
    examples: list[ComparabilityExample] = Field(default_factory=list)


class CoaMapping(BaseModel):
    quickbooks: str = ""
    netsuite: str = ""
    sap: str = ""


class Node(BaseModel):
    """A single node in the FinTree P&L hierarchy."""

    id: str
    label: str
    short_label: str = ""
    level: int = 1
    node_type: str = "LINE_ITEM"
    parent_id: Optional[str] = None
    children_ids: list[str] = Field(default_factory=list)
    pl_order: int = 9999
    aggregation_type: str = "LEAF"
    formula_human: str = ""
    formula_machine: str = ""
    definition: str = ""
    example: str = ""
    normal_balance: str = ""
    sign_convention: str = "+1"
    xbrl_tag: str = ""
    asc_reference: str = ""
    industry_variants: list[str] = Field(default_factory=list)
    is_leaf: bool = False
    is_decision_node: bool = False
    is_non_gaap: bool = False
    below_the_line: bool = False
    non_recurring: bool = False
    ai_context_tags: list[str] = Field(default_factory=list)
    classification_notes: str = ""
    variance_drivers: Optional[VarianceDrivers] = None
    comparability: Optional[Comparability] = None
    coa_mapping: Optional[CoaMapping] = None

    model_config = {"extra": "allow"}


class OverlayModifications(BaseModel):
    suppress: list[str] = Field(default_factory=list)
    emphasize: list[str] = Field(default_factory=list)
    rename: dict[str, str] = Field(default_factory=dict)
    add: list[dict[str, Any]] = Field(default_factory=list)


class IndustryOverlay(BaseModel):
    """An industry-specific overlay that modifies tree visibility."""

    industry: str
    label: str
    description: str = ""
    modifications: OverlayModifications = Field(default_factory=OverlayModifications)
    notes: str = ""


class NonGAAPComponent(BaseModel):
    node_id: str
    operation: str  # start, add_back, subtract, adjust
    label_override: str = ""


class NonGAAPMeasure(BaseModel):
    """A non-GAAP financial measure with reconciliation components."""

    id: str
    label: str
    description: str = ""
    formula: str = ""
    components: list[NonGAAPComponent] = Field(default_factory=list)
    sec_regulation_g: str = ""
    common_adjustments: list[str] = Field(default_factory=list)
    notes: str = ""


class TreeStats(BaseModel):
    total_nodes: int = 0
    leaf_nodes: int = 0
    decision_nodes: int = 0
    non_gaap_nodes: int = 0
    industry_overlays: int = 0
    non_gaap_measures: int = 0
    by_level: dict[str, int] = Field(default_factory=dict)


class TreeData(BaseModel):
    """The complete compiled tree structure."""

    version: str = "2.0.0"
    gaap_standard: str = "US GAAP"
    generated_at: str = ""
    root_node_id: str = "fintree:NetIncome"
    stats: TreeStats = Field(default_factory=TreeStats)
    nodes: list[Node] = Field(default_factory=list)
    edges: list[dict[str, str]] = Field(default_factory=list)
    industry_overlays: list[IndustryOverlay] = Field(default_factory=list)
    non_gaap_measures: list[NonGAAPMeasure] = Field(default_factory=list)
