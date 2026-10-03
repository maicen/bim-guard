"""Parameterized, server-scoped Cypher presets for the GraphRAG query console.

The property graph `GraphService`/`ingest_ifc_to_graph()` populates (Neo4j)
has no per-project partitioning the way `GraphTriplestoreService` has
for the triplestore (`named_graphs` scoping) -- every provider just stamps a
`project_id` property onto each node. Free-form Cypher would therefore leak
every project's nodes to whoever ran it (`MATCH (n) RETURN n` has no
boundary to respect). Rather than accept that, this module is the ONLY way
the query console reaches the property graph: a small library of preset
queries, each parameterized by `project_id`, which the caller always injects
server-side (see `app.api.graph_routes.run_graph_query_preset`) -- it is
never a value the request body can supply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.graph_database import GraphService


@dataclass(frozen=True)
class GraphQueryPreset:
    """One named, parameterized Cypher query.

    Attributes:
        key: Stable identifier, used in the route path and as the request's
            selector -- never treated as trusted Cypher itself.
        label: Human-readable name for the console's preset picker.
        description: What the preset shows and why.
        cypher: The query text. Always references `$project_id`; may
            reference additional `$`-prefixed params declared in `params`.
        params: Extra parameter names (besides `project_id`) the caller must
            supply, e.g. `["guid"]` for a query scoped to one element.
    """

    key: str
    label: str
    description: str
    cypher: str
    params: tuple[str, ...] = field(default_factory=tuple)


GRAPH_QUERY_PRESETS: tuple[GraphQueryPreset, ...] = (
    GraphQueryPreset(
        key="element-counts-by-type",
        label="Element counts by type",
        description="How many nodes of each IFC type this project's graph holds.",
        cypher=(
            "MATCH (n) WHERE n.project_id = $project_id "
            "RETURN n.ifc_type AS type, count(n) AS count "
            "ORDER BY count DESC"
        ),
    ),
    GraphQueryPreset(
        key="elements-by-ifc-class",
        label="Elements of one IFC class",
        description=(
            "Elements of the given IFC class (e.g. IfcDoor, case-insensitive) with "
            "their GUID and name, capped at 100."
        ),
        cypher=(
            "MATCH (n) WHERE n.project_id = $project_id "
            "AND toLower(n.ifc_type) = toLower($ifc_class) "
            "RETURN n.guid AS guid, n.name AS name, n.ifc_type AS type "
            "ORDER BY n.name LIMIT 100"
        ),
        params=("ifc_class",),
    ),
    GraphQueryPreset(
        key="most-connected-elements",
        label="Most-connected elements",
        description=(
            "Elements with the most relationships (degree) -- structural or "
            "distribution hubs a change to would ripple furthest from."
        ),
        cypher=(
            "MATCH (n)-[r]-(m) WHERE n.project_id = $project_id "
            "RETURN n.name AS name, n.ifc_type AS type, count(r) AS degree "
            "ORDER BY degree DESC LIMIT 20"
        ),
    ),
    GraphQueryPreset(
        key="element-neighbors",
        label="Elements connected to one element",
        description="Every node directly connected to the given element (by GUID).",
        cypher=(
            "MATCH (n {guid: $guid})-[r]-(m) WHERE n.project_id = $project_id "
            "RETURN m.name AS name, m.ifc_type AS type LIMIT 50"
        ),
        params=("guid",),
    ),
    GraphQueryPreset(
        key="decision-causal-lineage",
        label="Decision causal lineage",
        description="Trace the upstream building code standard, rule, and evaluated element for a compliance finding.",
        cypher=(
            "MATCH (v:ComplianceVerdict {project_id: $project_id, issue_id: $issue_id}) "
            "OPTIONAL MATCH (v)-[:TRIGGERED_BY]->(r:Rule) "
            "OPTIONAL MATCH (v)-[:EVALUATED_ELEMENT]->(e) "
            "RETURN v.id AS verdict_id, v.outcome AS outcome, v.risk_band AS risk_band, "
            "v.score AS score, r.rule_id AS rule_id, r.standard AS standard, "
            "r.clause AS clause, e.guid AS element_guid, e.name AS element_name, e.ifc_type AS element_type"
        ),
        params=("issue_id",),
    ),
    GraphQueryPreset(
        key="compliance-findings-by-rule",
        label="Findings grouped by building code rule",
        description="Aggregate compliance failures by building code rule and clause.",
        cypher=(
            "MATCH (v:ComplianceVerdict {project_id: $project_id})-[:TRIGGERED_BY]->(r:Rule) "
            "RETURN r.rule_id AS rule_id, r.standard AS standard, r.clause AS clause, "
            "count(v) AS failure_count "
            "ORDER BY failure_count DESC"
        ),
    ),
    # -------------------------------------------------------------------------
    # Pre-Flight Model Health & Data Quality Checks (Cypher Audit Presets)
    # -------------------------------------------------------------------------
    GraphQueryPreset(
        key="model-health-doors-missing-fire-rating",
        label="Doors missing fire rating",
        description="Doors without a defined fire rating property (critical egress safety requirement).",
        cypher=(
            "MATCH (n) WHERE n.project_id = $project_id AND (n.ifc_type = 'IfcDoor' OR n:IfcDoor) "
            "AND (n.fire_rating IS NULL OR n.fire_rating = '' OR NOT EXISTS(n.fire_rating)) "
            "RETURN n.guid AS guid, n.name AS name, n.ifc_type AS type LIMIT 100"
        ),
    ),
    GraphQueryPreset(
        key="model-health-unassigned-storeys",
        label="Elements without storey assignment",
        description="Physical elements not contained within any building storey (spatial hierarchy defect).",
        cypher=(
            "MATCH (n) WHERE n.project_id = $project_id "
            "AND NOT n.ifc_type IN ['IfcProject', 'IfcSite', 'IfcBuilding', 'IfcBuildingStorey', 'IfcSpace'] "
            "OPTIONAL MATCH (s)-[:CONTAINS]-(n) WHERE s.project_id = $project_id AND s.ifc_type = 'IfcBuildingStorey' "
            "WITH n, count(s) AS storeys "
            "WHERE storeys = 0 "
            "RETURN n.guid AS guid, n.name AS name, n.ifc_type AS type LIMIT 100"
        ),
    ),
    GraphQueryPreset(
        key="model-health-spaces-missing-attributes",
        label="Spaces missing name or number",
        description="Spaces lacking required identification attributes for zone and occupancy checking.",
        cypher=(
            "MATCH (s) WHERE s.project_id = $project_id AND s.ifc_type = 'IfcSpace' "
            "AND (s.name IS NULL OR s.name = '' OR s.name = 'IfcSpace') "
            "RETURN s.guid AS guid, s.name AS name, s.ifc_type AS type LIMIT 100"
        ),
    ),
    GraphQueryPreset(
        key="model-health-elements-without-psets",
        label="Elements without property sets",
        description="Physical building elements missing property sets (metadata completeness).",
        cypher=(
            "MATCH (n) WHERE n.project_id = $project_id "
            "AND NOT n.ifc_type IN ['IfcProject', 'IfcSite', 'IfcBuilding', 'IfcBuildingStorey'] "
            "AND (n.has_psets = false OR n.pset_count = 0) "
            "RETURN n.guid AS guid, n.name AS name, n.ifc_type AS type LIMIT 100"
        ),
    ),
    GraphQueryPreset(
        key="model-health-empty-property-values",
        label="Elements with blank or empty names",
        description="Elements where essential identifier or name properties are empty whitespace.",
        cypher=(
            "MATCH (n) WHERE n.project_id = $project_id AND (n.name IS NULL OR trim(n.name) = '') "
            "RETURN n.guid AS guid, n.ifc_type AS type LIMIT 100"
        ),
    ),
    GraphQueryPreset(
        key="model-health-categories-with-most-incomplete-data",
        label="Categories with most uncontained elements",
        description="Aggregated count of elements lacking storey containment grouped by IFC class.",
        cypher=(
            "MATCH (n) WHERE n.project_id = $project_id "
            "AND NOT n.ifc_type IN ['IfcProject', 'IfcSite', 'IfcBuilding', 'IfcBuildingStorey', 'IfcSpace'] "
            "OPTIONAL MATCH (s)-[:CONTAINS]-(n) WHERE s.project_id = $project_id AND s.ifc_type = 'IfcBuildingStorey' "
            "WITH n.ifc_type AS type, count(n) AS total, count(s) AS with_storey "
            "RETURN type, total, (total - with_storey) AS unassigned_count "
            "ORDER BY unassigned_count DESC"
        ),
    ),
    GraphQueryPreset(
        key="model-health-possible-duplicates",
        label="Possible duplicate elements",
        description="Elements sharing identical names and IFC types, indicating potential duplicate geometry.",
        cypher=(
            "MATCH (n) WHERE n.project_id = $project_id AND n.name IS NOT NULL AND n.name <> '' "
            "WITH n.name AS name, n.ifc_type AS type, collect(n.guid) AS guids, count(n) AS instances "
            "WHERE instances > 1 AND NOT type IN ['IfcProject', 'IfcSite', 'IfcBuilding', 'IfcBuildingStorey', 'IfcOpeningElement'] "
            "RETURN name, type, instances, guids LIMIT 50"
        ),
    ),
    GraphQueryPreset(
        key="model-health-isolated-elements",
        label="Isolated / unconnected elements",
        description="Physical elements with zero graph edges (disconnected floating elements).",
        cypher=(
            "MATCH (n) WHERE n.project_id = $project_id "
            "AND NOT n.ifc_type IN ['IfcProject', 'IfcSite', 'IfcBuilding', 'IfcBuildingStorey'] "
            "OPTIONAL MATCH (n)-[r]-() "
            "WITH n, count(r) AS degree "
            "WHERE degree = 0 "
            "RETURN n.guid AS guid, n.name AS name, n.ifc_type AS type LIMIT 100"
        ),
    ),
)

_PRESETS_BY_KEY = {preset.key: preset for preset in GRAPH_QUERY_PRESETS}


def get_preset(key: str) -> GraphQueryPreset | None:
    """Look up one preset by key, or None if unknown."""
    return _PRESETS_BY_KEY.get(key)


def run_preset(
    graph_service: GraphService, preset: GraphQueryPreset, *, project_id: int, params: dict[str, Any]
) -> list[dict[str, Any]]:
    """Execute `preset` against `graph_service`, `project_id` always server-supplied.

    `params` must cover exactly `preset.params` -- an extra or missing key is
    a caller bug, not a query the preset was written to accept, so it raises
    rather than silently running with a wrong/absent value.
    """
    missing = set(preset.params) - set(params)
    if missing:
        raise ValueError(f"Preset {preset.key!r} is missing required params: {sorted(missing)}")
    extra = set(params) - set(preset.params)
    if extra:
        raise ValueError(f"Preset {preset.key!r} does not accept params: {sorted(extra)}")

    query_params = {"project_id": str(project_id), **params}
    return graph_service.execute(preset.cypher, query_params)
