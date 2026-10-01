"""Knowledge graph, proof graph DAG, spatial trees, and SPARQL query contracts."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

__all__ = [
    'ProofNodeType',
    'ProofEdgeType',
    'ProofNodeContract',
    'ProofEdgeContract',
    'IssueProofGraphContract',
    'DecisionCausalChainResponse',
    'RuleImpactResponse',
    'GraphStatusContract',
    'SpatialTreeNodeContract',
    'SpatialTreeResponse',
    'ElementRelationEdge',
    'ElementRelationshipsResponse',
    'GraphQueryPresetSummary',
    'GraphQueryPresetListResponse',
    'GraphQueryResultResponse',
    'CodeToIfcTraceEntry',
    'CodeToIfcTraceResponse',
    'GraphHealResponse',
    'InspectorQueryRequest',
    'InspectorToolCallContract',
    'InspectorResponse',
    'ModelHealthCheckItem',
    'ModelHealthAuditReport',
    'RegulatoryClauseNode',
    'RegulatoryRequirementItem',
    'RegulatoryGraphContextResponse',
    'GoverningRequirementsResponse',
    'GraphRagScope',
    'GraphRagCitation',
    'GraphRagToolCall',
    'GraphRagStep',
    'GraphRagQueryRequest',
    'GraphRagQueryResponse',
    'GraphRagContextSummary',
]

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


# ---------------------------------------------------------------------------
# Pre-Flight Model Health Audit Contracts (Data Quality via Cypher)
# ---------------------------------------------------------------------------

class ModelHealthCheckItem(BaseModel):
    """One automated IFC data-quality audit check result."""

    key: str = Field(..., description="Unique check identifier (e.g. doors-missing-fire-rating)")
    name: str = Field(..., description="Human-readable title of the quality check")
    description: str = Field(..., description="Description of the quality rule being evaluated")
    severity: Literal["info", "warning", "critical"] = Field(
        "warning", description="Severity classification of the audit finding"
    )
    passed: bool = Field(..., description="True if no elements violated the quality rule")
    violation_count: int = Field(0, description="Number of elements failing this check")
    details: list[dict[str, Any]] = Field(
        default_factory=list, description="Sample of violating elements with GUID, Name, and issue context"
    )
    recommendation: str = Field(
        "", description="Actionable remediation advice for the BIM author or coordinator"
    )


class ModelHealthAuditReport(BaseModel):
    """Comprehensive Model Data Health & Hygiene Audit Report."""

    project_id: int = Field(..., description="Project database ID")
    health_score: float = Field(
        ..., description="Overall model health completeness score (0.0 to 100.0)"
    )
    grade: Literal["A", "B", "C", "D", "F"] = Field(
        ..., description="Letter grade reflecting model readiness for downstream compliance engines"
    )
    total_elements_audited: int = Field(0, description="Total physical elements inspected")
    total_violations: int = Field(0, description="Total violation instances across all checks")
    checks: list[ModelHealthCheckItem] = Field(
        default_factory=list, description="Individual quality checks evaluated"
    )
    evaluated_at: str = Field(..., description="ISO 8601 timestamp of evaluation")


# ---------------------------------------------------------------------------
# Regulatory Knowledge Graph Contracts (GraphRAG for Building Standards)
# ---------------------------------------------------------------------------

class RegulatoryClauseNode(BaseModel):
    """A clause node in the regulatory knowledge graph."""

    clause_id: str = Field(..., description="Standard-scoped clause identifier, e.g. IBC-1017.2")
    standard: str = Field(..., description="Building code standard, e.g. IBC 2024, NFPA 101, ADA 2010")
    section: str = Field(..., description="Parent section number or title")
    title: str = Field(..., description="Descriptive title of the regulatory requirement")
    text: str = Field("", description="Full or excerpted regulatory text")
    target_ifc_types: list[str] = Field(
        default_factory=list, description="IFC entity classes governed by this clause"
    )
    cross_references: list[str] = Field(
        default_factory=list, description="Referenced clause IDs cited in text"
    )


class RegulatoryRequirementItem(BaseModel):
    """An atomic measurable requirement extracted from a regulatory standard."""

    rule_id: Optional[int] = None
    standard: str
    clause: str
    target_ifc_type: str
    parameter: str
    operator: str
    value: Any
    unit: Optional[str] = None
    severity: str = "critical"
    description: str = ""


class RegulatoryGraphContextResponse(BaseModel):
    """Full regulatory graph context for a specific clause or standard."""

    clause: RegulatoryClauseNode
    parent_section: Optional[str] = None
    cross_referenced_clauses: list[RegulatoryClauseNode] = Field(default_factory=list)
    governed_ifc_types: list[str] = Field(default_factory=list)
    extracted_requirements: list[RegulatoryRequirementItem] = Field(default_factory=list)


class GoverningRequirementsResponse(BaseModel):
    """All regulatory requirements governing a given IFC class across standards."""

    ifc_type: str
    total_requirements: int = 0
    standards_covered: list[str] = Field(default_factory=list)
    requirements: list[RegulatoryRequirementItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Graph-RAG Question Answering Contracts (Documents + BIM Models)
# ---------------------------------------------------------------------------

GraphRagScope = Literal["document", "model", "hybrid"]


class GraphRagCitation(BaseModel):
    """A grounded reference cited by Graph-RAG (Document clause, IFC element, or Rule)."""

    id: str = Field(..., description="Unique citation token or reference id")
    source_type: Literal["document", "model", "rule"] = Field(
        ..., description="Provenance domain of the citation"
    )
    title: str = Field(..., description="Human-readable citation title or element name")
    reference: str = Field(..., description="Clause number, document name, or element type")
    snippet: str = Field("", description="Text excerpt, property summary, or requirement spec")
    page_number: Optional[int] = Field(None, description="Page number if from document")
    element_guid: Optional[str] = Field(None, description="IFC GlobalId if from model")
    ifc_type: Optional[str] = Field(None, description="IFC class name if from model")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Supporting properties or attributes"
    )
    score: Optional[float] = Field(None, description="Relevance or similarity score")
    retrieval_method: Optional[Literal["vector", "bm25", "graph", "hybrid_rrf"]] = Field(
        None, description="Primary retrieval stream that surfaced this citation"
    )
    rrf_score: Optional[float] = Field(None, description="Composite Reciprocal Rank Fusion score")


class GraphRagToolCall(BaseModel):
    """An analytical tool or graph traversal action recorded during Graph-RAG."""

    tool_name: str = Field(..., description="Name of the executed tool or retriever")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Input parameters passed to the tool"
    )
    output_summary: str = Field("", description="Brief human-readable summary of the output")
    cypher_query: Optional[str] = Field(
        None, description="Cypher query executed against Neo4j, if applicable"
    )
    status: Literal["running", "success", "error"] = Field(
        "success", description="Execution status of the tool call"
    )


class GraphRagStep(BaseModel):
    """A milestone in the Graph-RAG chain-of-thought or multi-step execution."""

    step_index: int = Field(..., description="Zero-based sequence order")
    title: str = Field(..., description="Step headline (e.g. 'Analyzing Query Intent')")
    description: str = Field("", description="Detailed explanation of what the step discovered")
    status: Literal["pending", "running", "done", "failed"] = Field(
        "done", description="Execution state of the step"
    )
    data: Optional[dict[str, Any]] = Field(
        None, description="Optional telemetry or intermediate metrics"
    )


class GraphRagQueryRequest(BaseModel):
    """Natural-language question and execution scope for Graph-RAG."""

    query: str = Field(..., min_length=1, description="Question about documents, models, or both")
    scope: GraphRagScope = Field(
        "hybrid", description="Target knowledge scope: document, model, or hybrid"
    )
    document_id: Optional[int] = Field(
        None, description="Optional specific document to focus retrieval on"
    )
    element_class: Optional[str] = Field(
        None, description="Optional IFC entity class to filter model traversal (e.g. IfcDoor)"
    )
    model_name: Optional[str] = Field(
        None, description="Optional LLM model override (defaults to org LLM config)"
    )
    temperature: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Sampling temperature override"
    )


class GraphRagQueryResponse(BaseModel):
    """Grounded answer, explainability trace, and citations from Graph-RAG."""

    project_id: int = Field(..., description="Project database ID")
    scope: GraphRagScope = Field(..., description="Scope used for retrieval")
    answer: str = Field(..., description="Synthesized Markdown answer with inline citations")
    citations: list[GraphRagCitation] = Field(
        default_factory=list, description="All grounded evidence sources"
    )
    tool_calls: list[GraphRagToolCall] = Field(
        default_factory=list, description="Tool calls and Cypher executions"
    )
    reasoning_steps: list[GraphRagStep] = Field(
        default_factory=list, description="Chain-of-thought execution steps"
    )
    cypher_queries: list[str] = Field(
        default_factory=list, description="All Cypher queries executed during retrieval"
    )
    suggested_followups: list[str] = Field(
        default_factory=list, description="Recommended follow-up prompts"
    )
    subgraph_data: dict[str, Any] = Field(
        default_factory=dict, description="Nodes and edges for visual artifact display"
    )
    retrieval_mode: Optional[str] = Field(
        "hybrid_rrf", description="Retrieval mode used: local, global, or hybrid_rrf"
    )
    rrf_metrics: Optional[dict[str, Any]] = Field(
        default_factory=dict, description="Diagnostic RRF scoring metrics"
    )


class GraphRagContextSummary(BaseModel):
    """Available document and IFC model entities available for Graph-RAG in a project."""

    project_id: int
    project_name: Optional[str] = None
    client_name: Optional[str] = None
    project_code: Optional[str] = None
    status: Optional[str] = None
    has_ifc_model: bool
    total_elements: int = 0
    total_storeys: int = 0
    total_spaces: int = 0
    ifc_classes: list[dict[str, Any]] = Field(default_factory=list)
    storeys: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    rulesets: list[str] = Field(default_factory=list)
    models: list[dict[str, Any]] = Field(default_factory=list)


