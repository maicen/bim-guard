"""LLM-only compliance rule extraction from pre-extracted document text."""

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Protocol

from app.logging_config import get_logger
from app.modules import contracts
from app.modules.document_parsing.llamaindex_ingestor import LlamaIndexIngestor
from app.modules.document_parsing.section_chunker import SectionChunker
from app.modules.rule_builder.llamaindex_rule_generator import LlamaIndexRuleGenerator
from app.services import extraction_progress
from app.services.bsdd_client import DEFAULT_BSDD_CLIENT, BSDDClient
from app.services.bsdd_ontology_repository import (
    BSDDOntologyRepository,
    get_bsdd_ontology_repository,
)
from app.services.clause_grounding_index import ClauseGroundingIndex, get_clause_grounding_index
from app.services.document_pages_service import DocumentPagesService

#: Node-level LLM calls to run concurrently during draft extraction. Bounded
#: rather than unbounded asyncio.gather so a 100-section document doesn't
#: fire 100 simultaneous requests at the LLM provider.
_MAX_CONCURRENT_NODES = 4

logger = get_logger(__name__)

# Comfortably under the LLM provider's ~1MB single-request part limit, so a
# document with no detected section headings (one giant chunk) or a single
# oversized section still reaches the provider instead of failing with
# "Part exceeded maximum size of 1024KB".
_MAX_CHUNK_CHARS = 400_000

_CAMEL_WORD_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")
_NON_ALNUM = re.compile(r"[^a-z0-9]")

# Provider error text is shown to the user verbatim, so anything shaped like an
# API key or bearer token is masked first -- providers occasionally echo the
# (possibly partial) credential back in the error body.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}"),
)


class RuleGenerationFailedError(RuntimeError):
    """Every clause of a document failed at the AI model, so nothing was extracted.

    Raised only when *all* clauses fail (a bad or missing API key, no credit,
    an unavailable model); a single failing clause is still dropped and the
    rest returned. Its message is written for the end user and shown as-is.
    """


def _redact_secrets(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("***", text)
    return text


def _describe_generation_failures(failures: list[Exception], total: int) -> str:
    """Build the user-facing message for a run where every clause's model call failed."""
    first = failures[0]
    reason = _redact_secrets(str(first)).strip()[:400] or type(first).__name__
    lowered = f"{type(first).__name__} {reason}".lower()
    hint = ""
    if any(marker in lowered for marker in ("authentication", "401", "api key", "no auth credentials")):
        hint = (
            " This usually means the API key for the selected model's provider is missing or "
            "invalid -- check it under Admin → External Providers → LLM Providers."
        )
    clause_word = "clause" if total == 1 else "clauses"
    return f"The AI model failed on all {total} {clause_word}, so no rules were extracted. Reason: {reason}{hint}"


def _camel_to_spaced(name: str) -> str:
    """Split camelCase into words, e.g. 'FireRating' -> 'Fire Rating'.

    Lets a camelCase query substring-match bSDD's human-readable spaced
    property names (e.g. "Fire Rating", "Riser Height") the same way it
    matches bSDD's own camelCase names (e.g. "ClearWidth") -- the local
    ontology mixes both naming conventions depending on which dictionary a
    property came from.
    """
    return _CAMEL_WORD_BOUNDARY.sub(" ", name).strip()


def _normalize_property_key(name: str) -> str:
    """Case/space/punctuation-insensitive key, e.g. 'FireRating' and 'Fire Rating' both -> 'firerating'.

    Used to compare an LLM-proposed IFC-style property identifier against a
    bSDD property name regardless of which of the two naming conventions
    either side happens to use.
    """
    return _NON_ALNUM.sub("", name.lower())


_GUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def _is_safe_property_identifier(value: str | None) -> bool:
    """Whether `value` looks like a real IFC attribute key rather than a display label or a GUID.

    Downstream compliance engines (e.g.
    app/modules/comparator/compliance_runner.py's `prop_name in info` /
    `info["psets"][pset][prop_name]` / `hasattr(element, prop_name)`) match
    property_name against a parsed IFC model's actual attribute keys by
    exact, case-sensitive string -- production rules always store the
    clean identifier form (e.g. "FireRating", "RiserHeight"), never a
    spaced display label or a dictionary GUID.
    """
    return bool(value) and " " not in value and not _GUID_RE.match(value)


def _canonical_property_name(match: contracts.BSDDPropertyItem) -> str | None:
    """Resolve the machine-actionable identifier for a matched bSDD property, or None if unsafe.

    bSDD's own `code` column is usually that identifier (e.g.
    "FireRating" for an IFC 4.3 entry whose `name` is the human-readable
    "Fire Rating"), but some dictionaries (e.g. ACCORD) store a GUID as
    `code` and keep the real identifier in `name` instead -- so both are
    checked, and a correction is only made when one of them is confirmed
    safe to write back into a rule.
    """
    if _is_safe_property_identifier(match.code):
        return match.code
    if _is_safe_property_identifier(match.name):
        return match.name
    return None


def _split_oversized(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """Split text too large for one LLM request into paragraph-bounded pieces."""
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in text.split("\n\n"):
        piece_len = len(paragraph) + 2
        if current and current_len + piece_len > max_chars:
            pieces.append("\n\n".join(current))
            current, current_len = [], 0
        if piece_len > max_chars:
            for i in range(0, len(paragraph), max_chars):
                pieces.append(paragraph[i : i + max_chars])
            continue
        current.append(paragraph)
        current_len += piece_len
    if current:
        pieces.append("\n\n".join(current))
    return pieces


class RuleExtractionProvider(Protocol):
    """Protocol used by RuleExtractionService (Dependency Inversion)."""

    async def extract_rules_from_text(
        self,
        text: str,
        *,
        chunk_index: int = 1,
        total_chunks: int = 1,
        model: str | None = None,
        organization_id: int | None = None,
    ) -> list[dict]:
        """Extract structured rule dicts from one text chunk."""
        ...


class ExtractionResult:
    """Holds the rules list and any non-fatal warnings from the pipeline."""

    def __init__(self, rules: list[dict], warnings: list[str]):
        self.rules = rules
        self.warnings = warnings


class RuleDraftGenerator(Protocol):
    """Protocol for the node-level draft generator used by extract_rule_drafts."""

    async def generate_drafts_from_node(
        self,
        node: contracts.DocumentNodeContract,
        *,
        deontic: contracts.DeonticStatement | None = None,
        model: str | None = None,
        organization_id: int | None = None,
    ) -> list[contracts.RuleExtractionDraft]:
        """Generate zero or more rule drafts from one clause-annotated node."""
        ...


class RuleExtractionService:
    """Extract and deduplicate rules using only an LLM provider."""

    def __init__(
        self,
        *,
        provider: RuleExtractionProvider | None = None,
        ingestor: LlamaIndexIngestor | None = None,
        bsdd_client: BSDDClient | None = None,
        ontology: BSDDOntologyRepository | None = None,
        clause_grounding: ClauseGroundingIndex | None = None,
        generator: RuleDraftGenerator | None = None,
        draft_service: Any | None = None,
        pages_service: DocumentPagesService | None = None,
        max_concurrent_nodes: int = _MAX_CONCURRENT_NODES,
    ):
        """Initialize the extraction provider dependency.

        Args:
            draft_service: Injectable RuleDraftService, for tests -- kept
                Any-typed and resolved lazily (real default constructed only
                when actually needed) rather than imported at module load,
                matching the existing local-import convention for that
                service elsewhere in this class.
            pages_service: Injectable DocumentPagesService (resolves each
                ingested clause node's page_number), for tests that inject
                fakes for the ingestor/generator too and shouldn't otherwise
                hit the real `document_pages` table.
            ontology: Injectable BSDDOntologyRepository -- bSDD grounding
                (_ground_draft_with_bsdd) checks this local, in-process
                ontology first and only falls back to the live `bsdd_client`
                on a local miss, the same local-first-then-live pattern
                BSDDOntologyRepository.get_class_cached already uses.
            clause_grounding: Injectable ClauseGroundingIndex -- an optional
                document-specific overlay on top of `ontology`: when the
                clause being grounded matches an entry bim-guard-evaluation's
                knowledge-graph pipeline promoted into
                data/reference/clause_grounding/, its LLM-verified bSDD class
                candidates are tried before the local ontology's plain
                substring search. A no-op (falls straight through to
                `ontology`) for any clause/document not covered by a
                promoted index.
        """
        self._provider = provider or LlamaIndexRuleGenerator()
        self._ingestor = ingestor or LlamaIndexIngestor()
        self._bsdd_client = bsdd_client or DEFAULT_BSDD_CLIENT
        self._ontology = ontology or get_bsdd_ontology_repository()
        self._clause_grounding = clause_grounding or get_clause_grounding_index()
        self._generator = generator or LlamaIndexRuleGenerator()
        self._draft_service = draft_service
        self._pages_service = pages_service or DocumentPagesService()
        self._max_concurrent_nodes = max_concurrent_nodes

    def _search_properties_grounded(self, prop_name: str) -> list[contracts.BSDDPropertyItem]:
        """Local ontology first (in-process DuckDB, <1ms, offline), live bSDD only on a local miss.

        Mirrors BSDDOntologyRepository.get_class_cached's local-first-then-live
        pattern: the curated/previously-cached ontology answers the common
        case instantly and without a network round trip, and only a name bSDD
        knows about but this app hasn't crawled falls through to the live API.

        The LLM emits IFC-style camelCase identifiers (e.g. "FireRating",
        per the extraction prompt's own example) but a large share of the
        local ontology's property names are bSDD's human-readable
        space-separated form (e.g. "Fire Rating") -- a plain substring
        search on the raw camelCase query never matches those, so a spaced
        variant is tried as a fallback before treating it as a genuine miss.
        """
        try:
            local_matches = self._ontology.search_properties(prop_name, limit=5)
            if not local_matches:
                spaced = _camel_to_spaced(prop_name)
                if spaced != prop_name:
                    local_matches = self._ontology.search_properties(spaced, limit=5)
        except Exception as exc:  # noqa: BLE001 - a lookup failure must not block extraction
            logger.warning("Local bSDD ontology lookup failed property_name=%s error=%s", prop_name, exc)
            local_matches = []
        if local_matches:
            return local_matches

        try:
            return self._bsdd_client.search_properties(prop_name, limit=5)
        except Exception as exc:  # noqa: BLE001 - a lookup failure must not block extraction
            logger.warning("bSDD grounding lookup failed property_name=%s error=%s", prop_name, exc)
            return []

    def _kg_classes_grounded(self, clause_id: str | None) -> list[contracts.BSDDClassItem]:
        """Resolve the clause's promoted knowledge-graph class candidates (if any) to full BSDDClassItems.

        The clause grounding index only stores trusted URIs (see
        ClauseGroundingIndex), not full bSDD records, so each is resolved
        against the same local ontology `_search_classes_grounded` uses --
        this never duplicates bSDD data. Resolved via `get_class_by_uri` so
        the result carries a real `properties` list (with `property_set`),
        the same as any other ontology-sourced BSDDClassItem, which is what
        lets a KG-corrected class_name flow straight into
        `_class_properties_grounded`'s exact-match search below with no
        separate wiring needed there.
        """
        uris = self._clause_grounding.class_uris_for(clause_id)
        if not uris:
            return []
        items: list[contracts.BSDDClassItem] = []
        for uri in uris:
            try:
                item = self._ontology.get_class_by_uri(uri)
            except Exception as exc:  # noqa: BLE001 - a lookup failure must not block extraction
                logger.warning("Clause grounding class lookup failed uri=%s error=%s", uri, exc)
                continue
            if item is not None:
                items.append(item)
        return items

    def _search_classes_grounded(self, class_name: str) -> list[contracts.BSDDClassItem]:
        """Local ontology first, live bSDD only on a local miss.

        The local ontology (in-process DuckDB, <1ms, offline) includes the
        full IFC 4.3 entity hierarchy ingested by
        scripts/ingest_ifc_release.py. Mirrors
        _search_properties_grounded's local-first-then-live pattern.
        """
        try:
            local_matches = self._ontology.search_classes(class_name, limit=5)
        except Exception as exc:  # noqa: BLE001 - a lookup failure must not block extraction
            logger.warning("Local bSDD ontology class lookup failed class_name=%s error=%s", class_name, exc)
            local_matches = []
        if local_matches:
            return local_matches

        try:
            return self._bsdd_client.search_classes(class_name, limit=5).classes
        except Exception as exc:  # noqa: BLE001 - a lookup failure must not block extraction
            logger.warning("bSDD class grounding lookup failed class_name=%s error=%s", class_name, exc)
            return []

    def _ground_target_class(
        self, rule: contracts.RuleCreateRequest, *, clause_id: str | None = None
    ) -> tuple[contracts.RuleCreateRequest, str | None]:
        """Correct an extracted rule's target_ifc_class against bSDD.

        Two independent correction paths, tried in order:

        1. Spelling/casing (unchanged, applies to every document): the LLM
           is prompted for a real IFC entity type (e.g. "IfcDoor") but
           sometimes drifts on casing ("ifcdoor") or spelling. When bSDD's
           own class search has a case-insensitive exact code match, that
           canonical spelling replaces whatever the LLM produced.

        2. Knowledge-graph override (only when `clause_id` is covered by a
           promoted grounding index, see ClauseGroundingIndex): this only
           runs when path 1 found *no* exact match at all -- i.e. the LLM's
           proposed class isn't a real, confirmable bSDD class/code, not
           merely mis-cased. In that situation a clause-aware LLM judgment
           (kg.correct_graph.py's verification pass, run once per document
           in bim-guard-evaluation and promoted here) is a much stronger
           signal than leaving an unconfirmed, possibly-invented class name
           in place, so its top trusted candidate is applied instead.

        Path 1 alone still leaves the rule untouched on a miss outside any
        promoted index, for the reason _search_properties_grounded does: a
        miss is not itself evidence the class is wrong, only that it could
        not be confirmed by spelling alone.
        """
        class_name = (rule.target_ifc_class or "").strip()
        if not class_name:
            return rule, None

        matches = self._search_classes_grounded(class_name)
        match = next((m for m in matches if m.code.strip().lower() == class_name.lower()), None)
        if match is not None:
            if match.code == class_name:
                return rule, None
            corrected_rule = rule.model_copy(update={"target_ifc_class": match.code})
            note = f"bSDD grounding: corrected target IFC class to {match.code} (was {class_name})."
            return corrected_rule, note

        kg_matches = self._kg_classes_grounded(clause_id)
        top = kg_matches[0] if kg_matches else None
        if top is not None and top.code.strip().lower() != class_name.lower():
            corrected_rule = rule.model_copy(update={"target_ifc_class": top.code})
            note = f'KG clause grounding: corrected target IFC class to {top.code} (was unconfirmed "{class_name}").'
            return corrected_rule, note

        return rule, None

    def _class_properties_grounded(self, class_name: str) -> list[contracts.BSDDPropertyItem]:
        """Property list -- each carrying a real property_set -- for one bSDD/IFC class.

        `property_set` is a class-property *relation* attribute in bSDD, not
        a property attribute: a bare property-name search (local or live)
        structurally can never carry one (see BSDDClient.get_property's own
        docstring). Only a class's own property list, assembled from its
        class-property edges, does. This is the one place that list is
        available to a name search.

        Takes only `class_name`, not `clause_id`: by the time this runs,
        `class_name` is `_ground_target_class`'s own output for this rule
        (see `_ground_property` below), so any knowledge-graph class
        correction it already applied is already reflected here -- no
        separate KG wiring needed in this function.
        """
        matches = self._search_classes_grounded(class_name)
        target = next((c for c in matches if c.code.strip().lower() == class_name.strip().lower()), None)
        return target.properties if target is not None else []

    def _ground_property(
        self, rule: contracts.RuleCreateRequest
    ) -> tuple[contracts.RuleCreateRequest, str | None]:
        """Correct an extracted rule's property_set/property_name against bSDD.

        The LLM frequently invents or misnames property sets (e.g.
        "Pset_Door" instead of the real "Pset_DoorCommon", or "DoorWidth"
        instead of "OverallWidth"). Resolution goes through the rule's own
        (already-grounded) target_ifc_class first, since that is the only
        place bSDD actually attaches a property_set to a property name; a
        flat cross-class property search is tried only as a fallback, and
        can at most confirm a name exists somewhere in bSDD; it essentially
        never carries a property_set to correct with (an offline fallback
        catalog entry is the sole exception). Leaves the rule untouched
        when nothing resolves — that is not itself evidence the property is
        wrong, only that it could not be confirmed.
        """
        prop_name = (rule.property_name or "").strip()
        if not prop_name:
            return rule, None
        prop_key = _normalize_property_key(prop_name)

        class_name = (rule.target_ifc_class or "").strip()
        if class_name:
            class_props = self._class_properties_grounded(class_name)
            match = next(
                (p for p in class_props if p.property_set and _normalize_property_key(p.name) == prop_key),
                None,
            )
            if match is not None:
                return self._apply_property_match(rule, match)

        matches = self._search_properties_grounded(prop_name)
        match = next((m for m in matches if _normalize_property_key(m.name) == prop_key), None)
        if match is None or not match.property_set:
            return rule, None
        return self._apply_property_match(rule, match)

    def _apply_property_match(
        self, rule: contracts.RuleCreateRequest, match: contracts.BSDDPropertyItem
    ) -> tuple[contracts.RuleCreateRequest, str | None]:
        # match.name is bSDD's own display label and is sometimes spaced
        # ("Fire Rating") -- never safe to write into property_name, which
        # the audit engine looks up as a literal IFC attribute key. Skip
        # the correction entirely (rather than only half-applying it)
        # when neither candidate resolves to a safe identifier.
        canonical_name = _canonical_property_name(match)
        if canonical_name is None:
            return rule, None
        if rule.property_set == match.property_set and rule.property_name == canonical_name:
            return rule, None

        corrected_rule = rule.model_copy(
            update={"property_set": match.property_set, "property_name": canonical_name}
        )
        note = (
            f"bSDD grounding: corrected property to {match.property_set}.{canonical_name} "
            f"(was {rule.property_set or '—'}.{rule.property_name or '—'})."
        )
        return corrected_rule, note

    def _kg_property_hint_note(self, clause_id: str | None, applied_property_name: str | None) -> str | None:
        """Advisory note listing this clause's KG-trusted properties, when not already applied.

        The clause grounding index's property candidates (unlike its class
        candidates) never carry a property_set -- see
        ClauseGroundingIndex.property_hints_for and
        _class_properties_grounded's docstring for why that can't be fixed
        by wiring alone -- so they can never be safely auto-applied the way
        `_ground_property` applies a class-scoped match. Surfacing them as a
        review note instead still gets the LLM-verified signal in front of
        the human reviewer, who can confirm the right property_set by hand.
        """
        hints = self._clause_grounding.property_hints_for(clause_id)
        if not hints:
            return None
        names = sorted({h["name"] for h in hints if h.get("name")})
        if not names:
            return None
        applied_key = _normalize_property_key(applied_property_name) if applied_property_name else None
        if applied_key is not None and applied_key in {_normalize_property_key(n) for n in names}:
            return None  # already reflected in the applied correction -- nothing new to flag
        listed = ", ".join(names[:3])
        return f"KG clause grounding also flags as relevant: {listed} (property_set unconfirmed -- verify manually)."

    def _ground_draft_with_bsdd(self, draft: contracts.RuleExtractionDraft) -> contracts.RuleExtractionDraft:
        """Correct an extracted rule's target_ifc_class and property_set/property_name against bSDD.

        A note of each correction actually made is attached to
        review_notes so a reviewer can see why the draft changed; the draft
        is returned untouched (no review_notes) when nothing resolves.

        When `draft.clause.clause_id` is covered by a promoted
        knowledge-graph grounding index (data/reference/clause_grounding/,
        see ClauseGroundingIndex), _ground_target_class also gets a chance
        to use it as a same-document, clause-aware override on top of the
        two args' pure spelling/substring corrections -- see
        _ground_target_class's own docstring for exactly when that fires.
        """
        rule = draft.proposed_rule
        clause_id = draft.clause.clause_id if draft.clause else None
        notes: list[str] = []

        rule, class_note = self._ground_target_class(rule, clause_id=clause_id)
        if class_note:
            notes.append(class_note)

        rule, property_note = self._ground_property(rule)
        if property_note:
            notes.append(property_note)

        hint_note = self._kg_property_hint_note(clause_id, rule.property_name)
        if hint_note:
            notes.append(hint_note)

        if not notes:
            return draft
        return draft.model_copy(update={"proposed_rule": rule, "review_notes": " ".join(notes)})

    async def extract_rules_from_text(
        self, text: str, *, model: str | None = None, organization_id: int | None = None
    ) -> ExtractionResult:
        """Extract compliance rules from pre-extracted document text.

        Args:
            model: Extraction LLM override, threaded down to the provider
                (e.g. from the Rule Extraction UI's model selector).
            organization_id: Resolves the API key from that org's configured
                LLM provider instance first, falling back to the provider's
                env var — see ``llamaindex_program.build_llm``.
        """
        if not text or not text.strip():
            logger.warning("Skipped rule extraction for empty extracted text")
            return ExtractionResult(rules=[], warnings=[])

        logger.info("Starting rule extraction from text chars=%d", len(text))
        structured_chunks = SectionChunker().chunk(text)
        chunks = structured_chunks or [{"text": text}]
        extracted_rules: list[dict] = []
        total = len(chunks)

        for idx, chunk in enumerate(chunks, start=1):
            chunk_text = chunk.get("text", "").strip()
            if not chunk_text:
                continue
            for sub_text in _split_oversized(chunk_text):
                chunk_rules = await self._provider.extract_rules_from_text(
                    sub_text,
                    chunk_index=idx,
                    total_chunks=total,
                    model=model,
                    organization_id=organization_id,
                )
                extracted_rules.extend(chunk_rules)

        rules = self._deduplicate(extracted_rules)
        logger.info(
            "LLM rule extraction complete chunks=%d extracted_rules=%d unique_rules=%d",
            len(chunks),
            len(extracted_rules),
            len(rules),
        )
        return ExtractionResult(rules=rules, warnings=[])

    async def ingest_with_llamaindex(
        self, document_id: int, text: str, *, organization_id: int | None = None
    ) -> list[contracts.DocumentNodeContract]:
        """Ingest document text into clause-annotated nodes with deontic statements.

        Does not report through the shared pipeline_tracker: that tracker is
        keyed by project_id against a fixed engine registry, so binding it
        here under a document_id would either collide with an in-flight
        analysis run that happens to share the same id, or raise on an engine
        code ("LLAMA-INGEST") the registry does not know. Document ingestion
        has no engine-progress contract of its own yet, so this stays plain
        (unstreamed) for now.
        """
        pages = self._pages_service.get_pages(document_id)
        nodes = self._ingestor.nodes_from_text(text, source_document_id=document_id, pages=pages)
        statements = await self._ingestor.extract_deontic_statements(nodes, organization_id=organization_id)

        logger.info(
            "LlamaIndex ingestion complete document_id=%d nodes=%d deontic_statements=%d",
            document_id,
            len(nodes),
            len(statements),
        )
        return nodes

    async def extract_rule_drafts(
        self,
        document_id: int,
        text: str,
        *,
        model: str | None = None,
        organization_id: int | None = None,
    ) -> list[contracts.RuleExtractionDraft]:
        """Ingest a document and generate reviewable rule drafts via LlamaIndex.

        Runs ingestion (clause-annotated nodes + deontic statements), then
        the draft generator over each node with bounded concurrency
        (`_MAX_CONCURRENT_NODES` at a time, rather than one LLM round-trip
        after another), and persists the results as `pending_review` drafts
        via RuleDraftService — the entry point for
        `POST /api/documents/{id}/rules/extract-drafts`.

        Progress is reported through `app.services.extraction_progress`
        (not `pipeline_tracker` — see that module's docstring for why) so
        `GET /api/documents/{id}/rules/extract-progress` can be polled while
        a large document is still processing.

        Args:
            model: Extraction LLM override (e.g. from the UI's model
                selector), applied to every node in this document.
        """
        draft_service = self._draft_service
        if draft_service is None:
            from app.services.rule_draft_service import RuleDraftService

            draft_service = RuleDraftService()

        nodes = await self.ingest_with_llamaindex(document_id, text, organization_id=organization_id)
        deontic_by_node = {
            node.node_id: (node.deontic_statements[0] if node.deontic_statements else None)
            for node in nodes
        }

        # One ruleset per extraction run, named after when it ran, so every
        # draft this call produces (however many nodes/clauses it spans)
        # stays grouped and identifiable as a batch -- overrides whatever
        # ruleset_id the LLM itself proposed per-node.
        batch_ruleset_id = f"EXTRACTED-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"

        extraction_progress.start(document_id, total=len(nodes))
        semaphore = asyncio.Semaphore(self._max_concurrent_nodes)
        failures: list[Exception] = []

        async def process_node(node: contracts.DocumentNodeContract) -> list[contracts.RuleExtractionDraft]:
            async with semaphore:
                try:
                    from app.services.llm_call_context import llm_call_context

                    with llm_call_context(
                        context="rule_extraction",
                        organization_id=organization_id,
                        metadata={"document_id": document_id},
                    ):
                        node_drafts = await self._generator.generate_drafts_from_node(
                            node,
                            deontic=deontic_by_node.get(node.node_id),
                            model=model,
                            organization_id=organization_id,
                        )
                except Exception as exc:  # noqa: BLE001 - one bad node must not abort the batch
                    logger.warning("Rule generation failed node_id=%s error=%s", node.node_id, exc)
                    failures.append(exc)
                    return []
                finally:
                    extraction_progress.increment(document_id)
                return [
                    self._ground_draft_with_bsdd(
                        draft.model_copy(
                            update={
                                "source_snippet": node.text,
                                "proposed_rule": draft.proposed_rule.model_copy(
                                    update={"ruleset_id": batch_ruleset_id}
                                ),
                            }
                        )
                    )
                    for draft in node_drafts
                ]

        try:
            per_node_drafts = await asyncio.gather(*(process_node(node) for node in nodes))
        except Exception as exc:
            extraction_progress.fail(document_id, str(exc))
            raise
        drafts = [draft for node_drafts in per_node_drafts for draft in node_drafts]

        # A lone failing clause is tolerated above, but if the model failed on
        # every clause the run is a failure, not an empty result -- returning
        # [] here surfaced as a vague "no valid rules" with the real cause
        # (e.g. a rejected API key) visible only in the server log.
        if nodes and len(failures) == len(nodes):
            message = _describe_generation_failures(failures, len(nodes))
            extraction_progress.fail(document_id, message)
            raise RuleGenerationFailedError(message) from failures[0]

        saved_drafts = draft_service.save_drafts(drafts)
        extraction_progress.complete(document_id)
        logger.info(
            "LlamaIndex rule-draft extraction complete document_id=%d nodes=%d drafts=%d",
            document_id,
            len(nodes),
            len(saved_drafts),
        )
        return saved_drafts

    # ── Private: deduplication ────────────────────────────────────────────────

    def _deduplicate(self, rules: list[dict]) -> list[dict]:
        deduplicated: list[dict] = []
        seen: set[tuple] = set()

        for rule in rules:
            desc = str(rule.get("desc") or "").strip()
            target = str(rule.get("target") or "Unspecified").strip()
            if not desc:
                continue

            key = (desc.casefold(), target.casefold())
            if key in seen:
                continue
            seen.add(key)

            ref = str(rule.get("ref") or "").strip()
            deduplicated.append(
                {
                    **rule,
                    "ref": ref or f"REQ-AI-{len(deduplicated) + 1:03d}",
                    "target": target,
                }
            )

        return deduplicated
