"""LLM-only rule extraction service contracts."""

import asyncio
import subprocess
import sys

from app.modules.contracts import (
    BSDDClassItem,
    BSDDPropertyItem,
    ClauseMetadata,
    DocumentNodeContract,
    RuleCreateRequest,
    RuleExtractionDraft,
)
from app.services import extraction_progress
from app.services.rule_draft_service import RuleDraftService
from app.services.rule_extraction_service import RuleExtractionService


class FakeProvider:
    """Return duplicate rules while recording received source chunks."""

    def __init__(self) -> None:
        self.chunks = []

    async def extract_rules_from_text(
        self,
        text: str,
        *,
        chunk_index: int = 1,
        total_chunks: int = 1,
        model: str | None = None,
        organization_id: int | None = None,
    ) -> list[dict]:
        self.chunks.append((text, chunk_index, total_chunks))
        return [
            {"desc": "Wall shall comply", "target": "IfcWall"},
            {"desc": "Wall shall comply", "target": "IfcWall"},
        ]


def test_text_extraction_uses_only_provider_rules_and_deduplicates():
    provider = FakeProvider()

    result = asyncio.run(
        RuleExtractionService(provider=provider).extract_rules_from_text(
            "Walls shall comply."
        )
    )

    assert provider.chunks
    assert result.rules == [
        {
            "desc": "Wall shall comply",
            "target": "IfcWall",
            "ref": "REQ-AI-001",
        }
    ]
    assert result.warnings == []


def test_empty_text_does_not_call_provider():
    provider = FakeProvider()

    result = asyncio.run(
        RuleExtractionService(provider=provider).extract_rules_from_text("  ")
    )

    assert provider.chunks == []
    assert result.rules == []


def test_service_import_does_not_load_legacy_extraction_modules():
    source = """
import json
import sys
import app.services.rule_extraction_service
legacy = [
    name for name in sys.modules
    if name.endswith((
        "unstructured_extractor",
        "table_rule_builder",
        "keyword_filter",
        "dependency_parser",
        "confidence_scorer",
        "tfidf_analyzer",
        "bert_classifier",
        "nlp_annotation",
    ))
]
print(json.dumps(legacy))
"""

    result = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )

    assert result.stdout.strip().splitlines()[-1] == "[]"


class FakeBSDDClient:
    """Returns a fixed set of property matches, recording the query received."""

    def __init__(self, matches: list[BSDDPropertyItem]) -> None:
        self.matches = matches
        self.queries: list[str] = []

    def search_properties(self, query: str, dictionary_uri=None, limit: int = 8):
        self.queries.append(query)
        return self.matches


class FakeOntology:
    """Returns a fixed set of local-ontology property matches, recording the query received."""

    def __init__(self, matches: list[BSDDPropertyItem]) -> None:
        self.matches = matches
        self.queries: list[str] = []

    def search_properties(self, query: str, limit: int = 8):
        self.queries.append(query)
        return self.matches


def _draft(
    property_set: str | None,
    property_name: str | None,
    *,
    target_ifc_class: str = "IfcDoor",
    clause_id: str | None = None,
) -> RuleExtractionDraft:
    return RuleExtractionDraft(
        source_document_id=1,
        clause=ClauseMetadata(clause_id=clause_id, source_document_id=1) if clause_id else None,
        proposed_rule=RuleCreateRequest(
            rule_id="REQ-1",
            description="Doors shall be wide enough",
            target_ifc_class=target_ifc_class,
            property_set=property_set,
            property_name=property_name,
            severity="mandatory",
        ),
    )


def test_bsdd_grounding_corrects_invented_property_set():
    """A local-ontology match grounds the draft without ever touching the live client."""
    ontology = FakeOntology(
        [BSDDPropertyItem(uri="urn:x", name="OverallWidth", property_set="Pset_DoorCommon")]
    )
    bsdd = FakeBSDDClient([])
    service = RuleExtractionService(ontology=ontology, bsdd_client=bsdd)
    draft = _draft(property_set="Pset_Door", property_name="OverallWidth")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.property_set == "Pset_DoorCommon"
    assert grounded.proposed_rule.property_name == "OverallWidth"
    assert "bSDD grounding" in (grounded.review_notes or "")
    assert ontology.queries == ["OverallWidth"]
    assert bsdd.queries == []  # local match found -- live fallback never called


def test_bsdd_grounding_leaves_already_correct_rule_untouched():
    ontology = FakeOntology(
        [BSDDPropertyItem(uri="urn:x", name="OverallWidth", property_set="Pset_DoorCommon")]
    )
    service = RuleExtractionService(ontology=ontology, bsdd_client=FakeBSDDClient([]))
    draft = _draft(property_set="Pset_DoorCommon", property_name="OverallWidth")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft
    assert grounded.review_notes is None


def test_bsdd_grounding_falls_back_to_live_bsdd_when_local_ontology_has_no_match():
    """A name the local ontology hasn't crawled still grounds via the live bSDD client."""
    ontology = FakeOntology([])
    bsdd = FakeBSDDClient(
        [BSDDPropertyItem(uri="urn:x", name="OverallWidth", property_set="Pset_DoorCommon")]
    )
    service = RuleExtractionService(ontology=ontology, bsdd_client=bsdd)
    draft = _draft(property_set="Pset_Door", property_name="OverallWidth")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.property_set == "Pset_DoorCommon"
    # The camelCase name is retried in spaced form against the local
    # ontology (bSDD's own property names are often space-separated) before
    # falling through to the live client.
    assert ontology.queries == ["OverallWidth", "Overall Width"]
    assert bsdd.queries == ["OverallWidth"]


def test_bsdd_grounding_never_writes_a_spaced_display_name_into_property_name():
    """A bSDD hit whose only name is a human-readable label must not overwrite property_name.

    The audit engine (app/modules/comparator/compliance_runner.py) looks up
    property_name as a literal IFC attribute key on the parsed model
    (`prop_name in info`, `hasattr(element, prop_name)`) -- a spaced label
    like "Fire Rating" would never match the real "FireRating" key, so
    grounding must leave the rule untouched rather than "fix" it into
    something the audit can no longer find.
    """
    ontology = FakeOntology(
        [BSDDPropertyItem(uri="urn:x", name="Fire Rating", property_set="Pset_DoorCommon")]
    )
    service = RuleExtractionService(ontology=ontology, bsdd_client=FakeBSDDClient([]))
    draft = _draft(property_set=None, property_name="FireRating")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.property_name == "FireRating"
    assert grounded.proposed_rule.property_set is None
    assert grounded.review_notes is None


def test_bsdd_grounding_prefers_code_over_spaced_display_name():
    """When bSDD's `code` is the clean identifier, it -- not `name` -- is written back.

    Mirrors the real local ontology's IFC 4.3 entries, where `name` is a
    human-readable label ("Fire Rating") but `code` is the actual
    machine-actionable IFC attribute key ("FireRating").
    """
    ontology = FakeOntology(
        [BSDDPropertyItem(uri="urn:x", name="Fire Rating", code="FireRating", property_set="Pset_DoorCommon")]
    )
    service = RuleExtractionService(ontology=ontology, bsdd_client=FakeBSDDClient([]))
    draft = _draft(property_set="Pset_Door", property_name="FireRating")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.property_name == "FireRating"
    assert grounded.proposed_rule.property_set == "Pset_DoorCommon"
    assert "bSDD grounding" in (grounded.review_notes or "")


def test_bsdd_grounding_falls_back_to_name_when_code_is_a_dictionary_guid():
    """A `code` that is a raw dictionary GUID (e.g. ACCORD) is skipped in favor of a clean `name`.

    Mirrors a real local-ontology ACCORD entry: `code` is a GUID, `name`
    ("ClearWidth") is itself already a clean identifier, so it is the safe
    fallback -- property_set still gets corrected, property_name doesn't
    change because it already equals the canonical form.
    """
    ontology = FakeOntology(
        [
            BSDDPropertyItem(
                uri="urn:x",
                name="ClearWidth",
                code="122f5ab6-de6f-4bec-b198-3f6a2ddfd827",
                property_set="Pset_DoorCommon",
            )
        ]
    )
    service = RuleExtractionService(ontology=ontology, bsdd_client=FakeBSDDClient([]))
    draft = _draft(property_set=None, property_name="ClearWidth")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.property_name == "ClearWidth"
    assert grounded.proposed_rule.property_set == "Pset_DoorCommon"
    assert "bSDD grounding" in (grounded.review_notes or "")


def test_bsdd_grounding_skips_when_neither_code_nor_name_is_safe():
    """When `code` is a GUID and `name` is a spaced display label, no correction is made at all."""
    ontology = FakeOntology(
        [
            BSDDPropertyItem(
                uri="urn:x",
                name="Clear Width",
                code="122f5ab6-de6f-4bec-b198-3f6a2ddfd827",
                property_set="Pset_DoorCommon",
            )
        ]
    )
    service = RuleExtractionService(ontology=ontology, bsdd_client=FakeBSDDClient([]))
    draft = _draft(property_set=None, property_name="ClearWidth")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.property_name == "ClearWidth"
    assert grounded.proposed_rule.property_set is None
    assert grounded.review_notes is None


def test_bsdd_grounding_skips_when_no_match_found():
    service = RuleExtractionService(ontology=FakeOntology([]), bsdd_client=FakeBSDDClient([]))
    draft = _draft(property_set="Pset_Door", property_name="TotallyMadeUpProperty")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft


def test_bsdd_grounding_survives_lookup_failure():
    """Both the local ontology and the live fallback failing must not crash extraction."""

    class ExplodingOntology:
        def search_properties(self, *args, **kwargs):
            raise RuntimeError("local ontology load failed")

    class ExplodingBSDDClient:
        def search_properties(self, *args, **kwargs):
            raise RuntimeError("bSDD unreachable")

    service = RuleExtractionService(ontology=ExplodingOntology(), bsdd_client=ExplodingBSDDClient())
    draft = _draft(property_set="Pset_Door", property_name="OverallWidth")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft


def test_bsdd_grounding_skips_when_no_property_name():
    service = RuleExtractionService(ontology=FakeOntology([]), bsdd_client=FakeBSDDClient([]))
    draft = _draft(property_set=None, property_name=None)

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft


class FakeClassOntology:
    """Returns fixed search_classes/get_class_by_uri results, recording queries received."""

    def __init__(
        self,
        search_matches: list[BSDDClassItem] | None = None,
        by_uri: dict[str, BSDDClassItem] | None = None,
        property_matches: dict[str, list[BSDDClassItem]] | None = None,
    ) -> None:
        self.search_matches = search_matches or []
        self.by_uri = by_uri or {}
        self.property_matches = property_matches or {}
        self.search_queries: list[str] = []
        self.uri_queries: list[str] = []
        self.property_class_queries: list[str] = []

    def search_classes(self, query: str, limit: int = 5):
        self.search_queries.append(query)
        return self.search_matches

    def get_class_by_uri(self, uri: str):
        self.uri_queries.append(uri)
        return self.by_uri.get(uri)

    def search_properties(self, query: str, limit: int = 8):
        return []

    def classes_for_property(self, property_name: str, limit: int = 20):
        self.property_class_queries.append(property_name)
        return self.property_matches.get(property_name, [])


class FakeClauseGrounding:
    """Returns fixed clause_id -> trusted class URIs / property hints, recording queries received."""

    def __init__(
        self, classes_by_clause: dict[str, list[str]] | None = None, properties_by_clause: dict[str, list[dict]] | None = None
    ) -> None:
        self.classes_by_clause = classes_by_clause or {}
        self.properties_by_clause = properties_by_clause or {}
        self.class_queries: list[str | None] = []
        self.property_queries: list[str | None] = []

    def class_uris_for(self, clause_id):
        self.class_queries.append(clause_id)
        return self.classes_by_clause.get(clause_id, []) if clause_id else []

    def property_hints_for(self, clause_id):
        self.property_queries.append(clause_id)
        return self.properties_by_clause.get(clause_id, []) if clause_id else []


def _class_item(uri: str, code: str, name: str = "") -> BSDDClassItem:
    return BSDDClassItem(uri=uri, code=code, name=name or code, dictionary_uri="urn:dict/ifc/4.3")


def test_kg_clause_grounding_corrects_an_unconfirmed_class_name():
    """A clause covered by a promoted KG index can correct a class name spelling alone can't fix.

    Unlike the plain substring path (which only ever corrects casing/spelling
    of an already-real bSDD code), this fires when the LLM's proposed class
    isn't a real bSDD class/code at all -- the local ontology genuinely has
    no match -- but the clause is one bim-guard-evaluation's knowledge-graph
    pipeline scored and an LLM verified as being about a specific bSDD class.
    """
    ontology = FakeClassOntology(
        search_matches=[],  # local substring search finds nothing for "Building System"
        by_uri={"urn:kg/1": _class_item("urn:kg/1", "IfcBuildingSystem", "Building System")},
    )
    clause_grounding = FakeClauseGrounding(classes_by_clause={"A-1.1.2.7": ["urn:kg/1"]})
    service = RuleExtractionService(
        ontology=ontology, bsdd_client=FakeBSDDClient([]), clause_grounding=clause_grounding
    )
    draft = _draft(
        property_set=None, property_name=None, target_ifc_class="Building System", clause_id="A-1.1.2.7"
    )

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.target_ifc_class == "IfcBuildingSystem"
    assert "KG clause grounding" in (grounded.review_notes or "")
    assert clause_grounding.class_queries == ["A-1.1.2.7"]


def test_kg_clause_grounding_does_not_override_a_confirmed_spelling_match():
    """When the plain substring path already resolves the class, the KG override never runs.

    Ordering matters: an exact/near-exact bSDD code match is stronger
    evidence than a clause-level KG judgment, so the conservative
    spelling-only correction always wins when it applies at all.
    """
    ontology = FakeClassOntology(
        search_matches=[_class_item("urn:local/1", "IfcDoor")],
        by_uri={"urn:kg/1": _class_item("urn:kg/1", "IfcBuildingSystem")},
    )
    clause_grounding = FakeClauseGrounding(classes_by_clause={"A-1.1.2.7": ["urn:kg/1"]})
    service = RuleExtractionService(
        ontology=ontology, bsdd_client=FakeBSDDClient([]), clause_grounding=clause_grounding
    )
    draft = _draft(property_set=None, property_name=None, target_ifc_class="ifcdoor", clause_id="A-1.1.2.7")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.target_ifc_class == "IfcDoor"
    assert "bSDD grounding" in (grounded.review_notes or "")
    assert "KG clause grounding" not in (grounded.review_notes or "")


def test_kg_clause_grounding_is_a_noop_outside_a_promoted_clause():
    """A miss on a clause the loaded index doesn't cover behaves exactly as before (untouched)."""
    ontology = FakeClassOntology(search_matches=[])
    clause_grounding = FakeClauseGrounding(classes_by_clause={"A-1.1.2.7": ["urn:kg/1"]})
    service = RuleExtractionService(
        ontology=ontology, bsdd_client=FakeBSDDClient([]), clause_grounding=clause_grounding
    )
    draft = _draft(
        property_set=None, property_name=None, target_ifc_class="Something Unconfirmed", clause_id="H999"
    )

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft


def test_kg_clause_grounding_is_a_noop_without_a_clause_id():
    """A draft with no clause metadata at all never touches the KG index (no crash, no correction)."""
    ontology = FakeClassOntology(search_matches=[])
    clause_grounding = FakeClauseGrounding(classes_by_clause={"A-1.1.2.7": ["urn:kg/1"]})
    service = RuleExtractionService(
        ontology=ontology, bsdd_client=FakeBSDDClient([]), clause_grounding=clause_grounding
    )
    draft = _draft(property_set=None, property_name=None, target_ifc_class="Something Unconfirmed")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft
    assert clause_grounding.class_queries == [None]


def test_kg_clause_grounding_fires_even_when_llm_named_no_class_at_all():
    """The KG override no longer requires a starting (even if wrong) class name.

    Regression coverage for the gap _ground_target_class used to have: it
    returned immediately whenever the LLM left target_ifc_class blank,
    skipping the clause-keyed KG path even though that path never depended
    on having a class name to correct in the first place.
    """
    ontology = FakeClassOntology(
        search_matches=[],
        by_uri={"urn:kg/1": _class_item("urn:kg/1", "IfcBuildingSystem", "Building System")},
    )
    clause_grounding = FakeClauseGrounding(classes_by_clause={"A-1.1.2.7": ["urn:kg/1"]})
    service = RuleExtractionService(
        ontology=ontology, bsdd_client=FakeBSDDClient([]), clause_grounding=clause_grounding
    )
    draft = _draft(property_set=None, property_name=None, target_ifc_class="", clause_id="A-1.1.2.7")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.target_ifc_class == "IfcBuildingSystem"
    assert "KG clause grounding" in (grounded.review_notes or "")


def test_infers_target_class_from_property_when_llm_named_no_class():
    """Unstructured prose that names a property but no entity still resolves.

    E.g. "Private stairs shall have a maximum riser height of 200mm" gives
    the LLM a clean property_name (RiserHeight) but no "Entity" column to
    read a class from -- bSDD scoping RiserHeight to IfcStairFlight alone is
    enough to fill target_ifc_class without a KG-promoted clause at all.
    """
    ontology = FakeClassOntology(
        property_matches={"RiserHeight": [_class_item("urn:p/1", "IfcStairFlight")]},
    )
    service = RuleExtractionService(ontology=ontology, bsdd_client=FakeBSDDClient([]))
    draft = _draft(property_set=None, property_name="RiserHeight", target_ifc_class="")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.target_ifc_class == "IfcStairFlight"
    assert grounded.proposed_rule.needs_review == 0
    assert "inferred target IFC class IfcStairFlight" in (grounded.review_notes or "")
    assert ontology.property_class_queries == ["RiserHeight"]


def test_ambiguous_property_class_inference_is_not_guessed():
    """A property genuinely shared by multiple classes is left for a human, not guessed."""
    ontology = FakeClassOntology(
        property_matches={
            "FireRating": [_class_item("urn:p/1", "IfcDoor"), _class_item("urn:p/2", "IfcWindow")]
        },
    )
    service = RuleExtractionService(ontology=ontology, bsdd_client=FakeBSDDClient([]))
    draft = _draft(property_set=None, property_name="FireRating", target_ifc_class="")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.target_ifc_class == ""
    assert grounded.proposed_rule.needs_review == 1
    assert "Could not infer a unique target IFC class" in (grounded.review_notes or "")
    assert "flagged for manual review" in (grounded.review_notes or "")


def test_unresolvable_target_class_forces_review_instead_of_staying_silently_blank():
    """No class, no property, no KG match: still never leaves the draft looking clean."""
    ontology = FakeClassOntology()
    service = RuleExtractionService(ontology=ontology, bsdd_client=FakeBSDDClient([]))
    draft = _draft(property_set=None, property_name=None, target_ifc_class="")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.target_ifc_class == ""
    assert grounded.proposed_rule.needs_review == 1
    assert "No target IFC class could be determined" in (grounded.review_notes or "")


def test_kg_property_hint_appended_when_not_already_applied():
    """The clause's KG-trusted property names surface as an advisory note, never as an auto-correction."""
    ontology = FakeClassOntology(search_matches=[_class_item("urn:local/1", "IfcDoor")])
    clause_grounding = FakeClauseGrounding(
        properties_by_clause={"A-1.1.2.7": [{"uri": "urn:p/1", "name": "Fire Protection Class", "score": 0.85}]}
    )
    service = RuleExtractionService(
        ontology=ontology, bsdd_client=FakeBSDDClient([]), clause_grounding=clause_grounding
    )
    draft = _draft(property_set=None, property_name=None, target_ifc_class="ifcdoor", clause_id="A-1.1.2.7")

    grounded = service._ground_draft_with_bsdd(draft)

    assert "KG clause grounding also flags as relevant: Fire Protection Class" in (grounded.review_notes or "")
    assert "property_set unconfirmed" in (grounded.review_notes or "")


def test_kg_property_hint_skipped_when_already_reflected_in_applied_property():
    """No redundant advisory note when the applied property already matches the KG's own hint."""
    ontology = FakeClassOntology(search_matches=[_class_item("urn:local/1", "IfcDoor")])
    bsdd = FakeBSDDClient([BSDDPropertyItem(uri="urn:x", name="FireRating", property_set="Pset_DoorCommon")])
    clause_grounding = FakeClauseGrounding(
        properties_by_clause={"A-1.1.2.7": [{"uri": "urn:p/1", "name": "FireRating", "score": 0.85}]}
    )
    service = RuleExtractionService(ontology=ontology, bsdd_client=bsdd, clause_grounding=clause_grounding)
    draft = _draft(
        property_set="Pset_Door", property_name="FireRating", target_ifc_class="ifcdoor", clause_id="A-1.1.2.7"
    )

    grounded = service._ground_draft_with_bsdd(draft)

    assert "KG clause grounding also flags" not in (grounded.review_notes or "")


class FakeDraftsTable:
    """Minimal in-memory stand-in for a PersistenceService table adapter."""

    def __init__(self) -> None:
        self._rows: dict[int, dict] = {}
        self._next_id = 1

    @property
    def rows(self):
        return list(self._rows.values())

    def insert(self, payload: dict) -> dict:
        row = {"id": self._next_id, **payload}
        self._rows[self._next_id] = row
        self._next_id += 1
        return dict(row)

    def get(self, pk):
        row = self._rows.get(pk)
        return dict(row) if row is not None else None

    def update(self, *, updates: dict, pk_values):
        row = self._rows.get(pk_values)
        if row is not None:
            row.update(updates)


class FakeIngestor:
    """Returns a fixed set of nodes without touching document_extractor/LLM."""

    def __init__(self, node_count: int) -> None:
        self._nodes = [
            DocumentNodeContract(
                node_id=f"node-{i}",
                text=f"Clause {i} text",
                metadata=ClauseMetadata(node_type="paragraph", source_document_id=1),
            )
            for i in range(node_count)
        ]

    def nodes_from_text(self, text: str, *, source_document_id: int, pages=None):
        return self._nodes

    async def extract_deontic_statements(self, nodes, *, organization_id=None):
        return []


class FakePagesService:
    """No-op DocumentPagesService double -- keeps tests off the real table."""

    def get_pages(self, document_id: int) -> list[dict]:
        return []


class FakeGenerator:
    """Returns one draft per node; records concurrency depth reached."""

    def __init__(self) -> None:
        self.in_flight = 0
        self.max_in_flight = 0
        self.calls = 0

    async def generate_drafts_from_node(self, node, *, deontic=None, model=None, organization_id=None):
        self.calls += 1
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0)  # yield so overlapping calls actually overlap
        self.in_flight -= 1
        return [
            RuleExtractionDraft(
                source_document_id=node.metadata.source_document_id,
                source_node_id=node.node_id,
                proposed_rule=RuleCreateRequest(
                    rule_id=f"REQ-{node.node_id}",
                    description="A rule",
                    severity="mandatory",
                ),
            )
        ]


def _service_with_fakes(node_count: int, *, max_concurrent_nodes: int = 4) -> RuleExtractionService:
    return RuleExtractionService(
        ingestor=FakeIngestor(node_count),
        generator=FakeGenerator(),
        bsdd_client=FakeBSDDClient([]),
        draft_service=RuleDraftService(drafts_repo=FakeDraftsTable()),
        pages_service=FakePagesService(),
        max_concurrent_nodes=max_concurrent_nodes,
    )


def test_extract_rule_drafts_saves_one_draft_per_node():
    extraction_progress.STORE.clear()
    service = _service_with_fakes(node_count=5)

    drafts = asyncio.run(service.extract_rule_drafts(document_id=1, text="irrelevant"))

    assert len(drafts) == 5
    assert all(d.id is not None for d in drafts)


def test_extract_rule_drafts_reports_progress_to_completion():
    extraction_progress.STORE.clear()
    service = _service_with_fakes(node_count=5)

    asyncio.run(service.extract_rule_drafts(document_id=42, text="irrelevant"))

    snap = extraction_progress.snapshot(42)
    assert snap.total == 5
    assert snap.completed == 5
    assert snap.status == "complete"


def test_extract_rule_drafts_bounds_concurrency():
    extraction_progress.STORE.clear()
    generator = FakeGenerator()
    service = RuleExtractionService(
        ingestor=FakeIngestor(node_count=10),
        generator=generator,
        bsdd_client=FakeBSDDClient([]),
        draft_service=RuleDraftService(drafts_repo=FakeDraftsTable()),
        pages_service=FakePagesService(),
        max_concurrent_nodes=3,
    )

    asyncio.run(service.extract_rule_drafts(document_id=7, text="irrelevant"))

    assert generator.calls == 10
    assert generator.max_in_flight <= 3


def test_extract_rule_drafts_survives_one_node_failing():
    class FlakyGenerator(FakeGenerator):
        async def generate_drafts_from_node(self, node, *, deontic=None, model=None, organization_id=None):
            if node.node_id == "node-1":
                raise RuntimeError("LLM blew up")
            return await super().generate_drafts_from_node(node, deontic=deontic, model=model)

    extraction_progress.STORE.clear()
    service = RuleExtractionService(
        ingestor=FakeIngestor(node_count=3),
        generator=FlakyGenerator(),
        bsdd_client=FakeBSDDClient([]),
        draft_service=RuleDraftService(drafts_repo=FakeDraftsTable()),
        pages_service=FakePagesService(),
    )

    drafts = asyncio.run(service.extract_rule_drafts(document_id=9, text="irrelevant"))

    assert len(drafts) == 2  # node-1's failure is dropped, not fatal
    snap = extraction_progress.snapshot(9)
    assert snap.completed == 3
    assert snap.status == "complete"


def _service_with_generator(generator, node_count: int) -> RuleExtractionService:
    return RuleExtractionService(
        ingestor=FakeIngestor(node_count),
        generator=generator,
        bsdd_client=FakeBSDDClient([]),
        draft_service=RuleDraftService(drafts_repo=FakeDraftsTable()),
        pages_service=FakePagesService(),
    )


def test_extract_rule_drafts_raises_the_models_reason_when_every_node_fails():
    import pytest

    from app.services.rule_extraction_service import RuleGenerationFailedError

    class RejectingGenerator(FakeGenerator):
        async def generate_drafts_from_node(self, node, *, deontic=None, model=None, organization_id=None):
            raise RuntimeError(
                'OpenrouterException - {"error":{"message":"No cookie auth credentials found","code":401}}'
            )

    extraction_progress.STORE.clear()
    service = _service_with_generator(RejectingGenerator(), node_count=3)

    with pytest.raises(RuleGenerationFailedError) as exc_info:
        asyncio.run(service.extract_rule_drafts(document_id=11, text="irrelevant"))

    message = str(exc_info.value)
    assert "failed on all 3 clauses" in message
    assert "No cookie auth credentials found" in message
    assert "LLM Providers" in message  # points at where the key is fixed
    snap = extraction_progress.snapshot(11)
    assert snap.status == "failed"


def test_extract_rule_drafts_error_never_echoes_an_api_key():
    import pytest

    from app.services.rule_extraction_service import RuleGenerationFailedError

    class LeakyGenerator(FakeGenerator):
        async def generate_drafts_from_node(self, node, *, deontic=None, model=None, organization_id=None):
            raise RuntimeError("Incorrect API key provided: sk-or-v1-abcdef1234567890abcdef")

    extraction_progress.STORE.clear()
    service = _service_with_generator(LeakyGenerator(), node_count=1)

    with pytest.raises(RuleGenerationFailedError) as exc_info:
        asyncio.run(service.extract_rule_drafts(document_id=12, text="irrelevant"))

    assert "sk-or-v1-abcdef1234567890abcdef" not in str(exc_info.value)
    assert "failed on all 1 clause," in str(exc_info.value)

