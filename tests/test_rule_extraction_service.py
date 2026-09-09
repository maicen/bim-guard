"""LLM-only rule extraction service contracts."""

import asyncio
import subprocess
import sys

from app.modules.contracts import (
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
        self, text: str, *, chunk_index: int = 1, total_chunks: int = 1, model: str | None = None
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


def _draft(property_set: str | None, property_name: str | None) -> RuleExtractionDraft:
    return RuleExtractionDraft(
        source_document_id=1,
        proposed_rule=RuleCreateRequest(
            rule_id="REQ-1",
            description="Doors shall be wide enough",
            target_ifc_class="IfcDoor",
            property_set=property_set,
            property_name=property_name,
            severity="mandatory",
        ),
    )


def test_bsdd_grounding_corrects_invented_property_set():
    bsdd = FakeBSDDClient(
        [BSDDPropertyItem(uri="urn:x", name="OverallWidth", property_set="Pset_DoorCommon")]
    )
    service = RuleExtractionService(bsdd_client=bsdd)
    draft = _draft(property_set="Pset_Door", property_name="OverallWidth")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.property_set == "Pset_DoorCommon"
    assert grounded.proposed_rule.property_name == "OverallWidth"
    assert "bSDD grounding" in (grounded.review_notes or "")
    assert bsdd.queries == ["OverallWidth"]


def test_bsdd_grounding_leaves_already_correct_rule_untouched():
    bsdd = FakeBSDDClient(
        [BSDDPropertyItem(uri="urn:x", name="OverallWidth", property_set="Pset_DoorCommon")]
    )
    service = RuleExtractionService(bsdd_client=bsdd)
    draft = _draft(property_set="Pset_DoorCommon", property_name="OverallWidth")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft
    assert grounded.review_notes is None


def test_bsdd_grounding_skips_when_no_match_found():
    bsdd = FakeBSDDClient([])
    service = RuleExtractionService(bsdd_client=bsdd)
    draft = _draft(property_set="Pset_Door", property_name="TotallyMadeUpProperty")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft


def test_bsdd_grounding_survives_lookup_failure():
    class ExplodingBSDDClient:
        def search_properties(self, *args, **kwargs):
            raise RuntimeError("bSDD unreachable")

    service = RuleExtractionService(bsdd_client=ExplodingBSDDClient())
    draft = _draft(property_set="Pset_Door", property_name="OverallWidth")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft


def test_bsdd_grounding_skips_when_no_property_name():
    service = RuleExtractionService(bsdd_client=FakeBSDDClient([]))
    draft = _draft(property_set=None, property_name=None)

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft


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

    async def extract_deontic_statements(self, nodes):
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

    async def generate_drafts_from_node(self, node, *, deontic=None, model=None):
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
        async def generate_drafts_from_node(self, node, *, deontic=None, model=None):
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