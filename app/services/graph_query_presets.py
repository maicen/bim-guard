"""Parameterized, server-scoped Cypher presets for the GraphRAG query console.

The property graph `GraphService`/`ingest_ifc_to_graph()` populate (Neo4j or
Kùzu) has no per-project partitioning the way `GraphTriplestoreService` has
for the triplestore (`named_graphs` scoping) -- every provider just stamps a
`project_id` property onto each node. Free-form Cypher would therefore leak
every project's nodes to whoever ran it (`MATCH (n) RETURN n` has no
boundary to respect). Rather than accept that, this module is the ONLY way
the query console reaches the property graph: a small library of preset
queries, each parameterized by `project_id`, which the caller always injects
server-side (see `app.api.graph_routes.run_graph_query_preset`) -- it is
never a value the request body can supply.

Every preset here is written in Cypher syntax portable across both
providers this repo supports; notably it avoids Neo4j's `type(rel)` /
Kùzu's `label(rel)` relationship-type functions, which are NOT
interchangeable between the two dialects (verified against embedded Kùzu),
rather than special-casing the query text per provider.
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
