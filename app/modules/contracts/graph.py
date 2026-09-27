"""Knowledge graph, proof graph DAG, spatial trees, and SPARQL query contracts."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

__all__ = ['ProofNodeType', 'ProofEdgeType', 'ProofNodeContract', 'ProofEdgeContract', 'IssueProofGraphContract', 'DecisionCausalChainResponse', 'RuleImpactResponse', 'GraphStatusContract', 'SpatialTreeNodeContract', 'SpatialTreeResponse', 'ElementRelationEdge', 'ElementRelationshipsResponse', 'GraphQueryPresetSummary', 'GraphQueryPresetListResponse', 'GraphQueryResultResponse', 'CodeToIfcTraceEntry', 'CodeToIfcTraceResponse', 'GraphHealResponse', 'InspectorQueryRequest', 'InspectorToolCallContract', 'InspectorResponse']

# ---------------------------------------------------------------------------
# Explainability Proof Graph & Graph Intelligence Contracts
# ---------------------------------------------------------------------------

ProofNodeType = Literal["asserted_fact", "rule_axiom", "inference_step", "verdict"]

ProofEdgeType = Literal["satisfies", "violates", "infers", "applies"]

class ProofNodeContract(BaseModel):
    """A node in an explainable compliance proof DAG."""

    id: str = Field(..., description="Unique node identifier in proof graph")
    label: str = Field(..., description="Human-readable node description")
    node_type: ProofNodeType = Field(..., description="Classification of proof node")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Supporting node properties/values"
    )

class ProofEdgeContract(BaseModel):
    """A directed edge in an explainable compliance proof DAG."""

    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    label: ProofEdgeType = Field("infers", description="Semantic relationship type")

class IssueProofGraphContract(BaseModel):
    """An explainable Directed Acyclic Graph proving why an issue was flagged."""

    issue_id: str = Field(..., description="Unique issue identifier")
    rule_id: str = Field(..., description="Target rule or check identifier")
    element_id: str = Field(..., description="Target element GUID")
    nodes: list[ProofNodeContract] = Field(default_factory=list, description="Proof DAG nodes")
    edges: list[ProofEdgeContract] = Field(default_factory=list, description="Proof DAG edges")
    explanation: str = Field(..., description="Concise textual derivation summary")

class DecisionCausalChainResponse(BaseModel):
    """Causal ancestry and decision lineage for a compliance finding."""

    project_id: int
    issue_id: str
    verdict: dict[str, Any] = Field(default_factory=dict)
    rule: dict[str, Any] = Field(default_factory=dict)
    element: dict[str, Any] = Field(default_factory=dict)
    lineage_nodes: list[dict[str, Any]] = Field(default_factory=list)
    lineage_edges: list[dict[str, Any]] = Field(default_factory=list)
    prov_summary: str = ""

class RuleImpactResponse(BaseModel):
    """Impact analysis showing all elements and verdicts governed by a building code rule."""

    project_id: int
    rule_id: str
    total_elements_evaluated: int = 0
    total_findings: int = 0
    impacted_elements: list[dict[str, Any]] = Field(default_factory=list)

class GraphStatusContract(BaseModel):
    """Operational status and intelligence metrics for a project's graph."""

    project_id: int = Field(..., description="Project database ID")
    node_count: int = Field(0, description="Total nodes in relationship graph")
    edge_count: int = Field(0, description="Total edges in relationship graph")
    has_spatial_boundaries: bool = Field(False, description="Whether spatial boundaries are mapped")
    is_geometric_fallback: bool = Field(False, description="Whether boundaries used geometric fallback")
    centrality_summary: dict[str, Any] = Field(
        default_factory=dict, description="Top centrality metrics and distribution"
    )

class SpatialTreeNodeContract(BaseModel):
    """One node of the IFC spatial containment tree (Project->Site->Building->Storey->Space->Element)."""

    guid: str = Field(..., description="IFC GlobalId, or a synthetic id for non-product nodes")
    label: str = Field(..., description="Human-readable name")
    ifc_type: str = Field(..., description="IFC entity type, e.g. IfcBuildingStorey")
    children: list["SpatialTreeNodeContract"] = Field(default_factory=list)
    truncated_count: int = Field(
        0, description="Children omitted beyond the per-node cap, if any"
    )

class SpatialTreeResponse(BaseModel):
    """The project's IFC spatial containment tree, rooted at IfcProject."""

    project_id: int = Field(..., description="Project database ID")
    root: Optional[SpatialTreeNodeContract] = Field(
        None, description="Root node, or None if the model has no IfcProject"
    )

class ElementRelationEdge(BaseModel):
    """One outgoing or incoming BOT/SAREF4BLDG relationship for an element."""

    predicate: str = Field(..., description="Local predicate name, e.g. adjacentZone, hasSpace")
    guid: str = Field(..., description="GlobalId of the element on the other end of the edge")
    label: str = Field(..., description="Human-readable name of that element")

class ElementRelationshipsResponse(BaseModel):
    """One element's BOT/SAREF4BLDG classification and graph relationships.

    Backs the Knowledge Graph-Enriched 3D Viewport: clicking an element
    queries the model's BOT graph for its spatial containment, boundary
    interfaces (adjacentZone/adjacentElement), and -- for MEP elements --
    SAREF4BLDG distribution-system typing.
    """

    project_id: int
    guid: str
    exists: bool = Field(..., description="Whether this GlobalId was found in the model's graph")
    ifc_type: Optional[str] = None
    label: Optional[str] = None
    bot_classes: list[str] = Field(default_factory=list, description="BOT classes, e.g. Space, Element")
    s4bldg_classes: list[str] = Field(
        default_factory=list, description="SAREF4BLDG classes for MEP/distribution elements"
    )
    outgoing: list[ElementRelationEdge] = Field(default_factory=list)
    incoming: list[ElementRelationEdge] = Field(default_factory=list)

class GraphQueryPresetSummary(BaseModel):
    """One available Cypher preset for the GraphRAG query console.

    Free-form Cypher is deliberately not exposed -- see
    `app.services.graph_query_presets` -- so the console can only ever run
    one of these, each already scoped to the requesting project server-side.
    """

    key: str
    label: str
    description: str
    params: list[str] = Field(
        default_factory=list, description="Extra parameter names the caller must supply to run this preset"
    )

class GraphQueryPresetListResponse(BaseModel):
    """Every Cypher preset the query console can run."""

    presets: list[GraphQueryPresetSummary] = Field(default_factory=list)

class GraphQueryResultResponse(BaseModel):
    """Result rows from running one Cypher preset."""

    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0

class CodeToIfcTraceEntry(BaseModel):
    """One rule (regulatory clause) traced to the IFC class it governs.

    The only faithful link between "a clause" and "a component" that exists
    today is a rule's `target_ifc_class` -- there is no dedicated
    code-document-to-BIM-element data model yet (see the SRS's GraphRAG
    section). `element_count` cross-references the project's actual model
    rather than the rule catalog alone, so the trace shows only clauses this
    project's model can actually be checked against.
    """

    rule_id: int
    reference: str
    description: str
    target_ifc_class: str
    element_count: int
    source_document_id: Optional[int] = None
    source_page_number: Optional[int] = None

class CodeToIfcTraceResponse(BaseModel):
    """Every rule in the catalog whose target IFC class this project's model contains."""

    project_id: int
    entries: list[CodeToIfcTraceEntry] = Field(default_factory=list)

class GraphHealResponse(BaseModel):
    """Response from reconciling and synthesizing missing spatial boundaries."""

    project_id: int = Field(..., description="Project database ID")
    healed_spaces: int = Field(0, description="Spaces with healed boundaries")
    created_boundaries: int = Field(0, description="Synthesized boundary relationships")
    total_boundaries: int = Field(0, description="Total boundaries in model post-heal")
    status: str = Field("success", description="Status code (success, already_healed, no_op)")
    message: str = Field(..., description="Human-readable operation summary")

# ---------------------------------------------------------------------------
# Digital Inspector (LangGraph agent) Contracts
# ---------------------------------------------------------------------------


class InspectorQueryRequest(BaseModel):
    """A natural-language query for the Digital Inspector agent."""

    query: str = Field(..., min_length=1, description="Free-text question about the project")

class InspectorToolCallContract(BaseModel):
    """One tool invocation recorded during an inspector run."""

    tool_name: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: Optional[dict[str, Any]] = None
    status: Literal["running", "success", "error"] = "running"

class InspectorResponse(BaseModel):
    """Final answer and tool-call trace from a Digital Inspector run."""

    project_id: int
    answer: str
    tool_calls: list[InspectorToolCallContract] = Field(default_factory=list)
