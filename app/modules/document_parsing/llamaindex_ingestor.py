"""
document_parsing/llamaindex_ingestor.py
------------------------------------------
LlamaIndex-based document ingestion: layout-aware chunking with clause
provenance, plus typed deontic ("shall"/"must"/"should"/"may") entity
extraction.

This module does NOT reimplement PDF/table parsing. It layers on top of
the existing ``document_extractor.extract_document_text()`` (Unstructured
Workflow/Jobs API, falling back to LightExtractor) and the existing
``SectionChunker`` heading detector, then wraps each detected section as a
LlamaIndex node carrying clause metadata (clause id, page number, parent
section, section path).

Deontic statement extraction uses a LlamaIndex Pydantic program backed by
the same LiteLLM transport already used elsewhere in the app
(``app.modules.config.DEFAULT_LLM_MODEL``), so no second LLM API surface
is introduced.

Usage:
    from app.modules.document_parsing.llamaindex_ingestor import LlamaIndexIngestor
    ingestor = LlamaIndexIngestor()
    nodes = ingestor.ingest(filename, content, source_document_id=42)
    statements = await ingestor.extract_deontic_statements(nodes)
"""

import re
import uuid

from app.logging_config import get_logger
from app.modules.contracts import ClauseMetadata, DeonticStatement, DocumentNodeContract
from app.modules.document_parsing.document_extractor import extract_document_text
from app.modules.document_parsing.section_chunker import SectionChunker

logger = get_logger(__name__)

# A section number with >=1 dot ("9.8.2") reads as a clause reference; a bare
# top-level number ("9") is a chapter/heading, not a checkable clause.
_CLAUSE_ID_PATTERN = re.compile(r"^\d+(?:\.\d+)+")

_DEONTIC_KEYWORDS = ("shall", "must", "should", "may")


class LlamaIndexIngestor:
    """Layout-aware ingestion producing clause-annotated document nodes."""

    def __init__(self, *, chunker: SectionChunker | None = None) -> None:
        """Initialize with an injectable section chunker (Dependency Inversion)."""
        self._chunker = chunker or SectionChunker()

    def ingest(
        self, filename: str, content: bytes, *, source_document_id: int, parser: str = "auto"
    ) -> list[DocumentNodeContract]:
        """Extract text via the existing pipeline, then split into clause-annotated nodes.

        Args:
            filename: Original filename, used to pick the format reader.
            content: Raw file bytes.
            source_document_id: FK to the persisted ``documents`` row.
            parser: Forwarded to ``extract_document_text`` ("auto" | "unstructured" | "light").

        Returns:
            One DocumentNodeContract per detected section/clause.
        """
        text, _tables, _pages = extract_document_text(filename, content, parser=parser)
        return self.nodes_from_text(text, source_document_id=source_document_id)

    def nodes_from_text(self, text: str, *, source_document_id: int) -> list[DocumentNodeContract]:
        """Split already-extracted text into clause-annotated nodes.

        Reuses SectionChunker's heading detection so ingestion sees the same
        section boundaries as the existing rule-extraction chunking path,
        instead of a second, divergent splitter.
        """
        if not text or not text.strip():
            return []

        section_chunks = self._chunker.chunk(text)
        if not section_chunks:
            section_chunks = [{"section_number": None, "section_name": None, "text": text}]

        nodes: list[DocumentNodeContract] = []
        section_path: list[str] = []
        for chunk in section_chunks:
            chunk_text = str(chunk.get("text") or "").strip()
            if not chunk_text:
                continue

            section_number = chunk.get("section_number")
            section_name = chunk.get("section_name")
            node_type = "table" if self._looks_like_table(chunk_text) else "paragraph"

            if section_number:
                section_path = self._update_section_path(section_path, str(section_number))

            metadata = ClauseMetadata(
                clause_id=section_number if section_number and _CLAUSE_ID_PATTERN.match(str(section_number)) else None,
                page_number=None,  # UnstructuredExtractor's table/layout output does not
                # currently surface page numbers through extract_document_text's
                # (text, tables) tuple; wire this through once it does.
                parent_section=section_name,
                section_path=list(section_path) if section_path else ([str(section_number)] if section_number else []),
                node_type=node_type,
                source_document_id=source_document_id,
            )
            nodes.append(
                DocumentNodeContract(
                    node_id=str(uuid.uuid4()),
                    text=chunk_text,
                    metadata=metadata,
                )
            )

        logger.info(
            "LlamaIndexIngestor produced nodes document_id=%d count=%d",
            source_document_id,
            len(nodes),
        )
        return nodes

    @staticmethod
    def _update_section_path(current: list[str], section_number: str) -> list[str]:
        """Maintain a dotted-heading breadcrumb, e.g. ['5'] -> ['5', '5.3']."""
        if "." not in section_number:
            return [section_number]
        return current + [section_number] if current else [section_number]

    @staticmethod
    def _looks_like_table(chunk_text: str) -> bool:
        """Heuristic: many short, multi-column lines in a row reads as a table."""
        lines = [line for line in chunk_text.split("\n") if line.strip()]
        if len(lines) < 3:
            return False
        multi_column = sum(1 for line in lines if len(re.split(r"\s{2,}|\t", line.strip())) >= 3)
        return multi_column / len(lines) > 0.5

    async def extract_deontic_statements(
        self, nodes: list[DocumentNodeContract]
    ) -> list[DeonticStatement]:
        """Extract typed 'shall/must/should/may' obligations from each node.

        Only nodes containing a deontic keyword are sent to the LLM, since
        most clause text (definitions, examples, headings) contains none.
        """
        candidates = [node for node in nodes if self._contains_deontic_keyword(node.text)]
        if not candidates:
            return []

        from app.modules.document_parsing.llamaindex_program import extract_deontic_statement

        statements: list[DeonticStatement] = []
        for node in candidates:
            try:
                statement = await extract_deontic_statement(node.text, clause=node.metadata)
            except Exception as exc:  # noqa: BLE001 - a single bad node must not abort the batch
                logger.warning(
                    "Deontic extraction failed node_id=%s error=%s", node.node_id, exc
                )
                continue
            if statement is not None:
                statements.append(statement)
                node.deontic_statements.append(statement)

        return statements

    @staticmethod
    def _contains_deontic_keyword(text: str) -> bool:
        lowered = text.lower()
        return any(f" {keyword} " in f" {lowered} " for keyword in _DEONTIC_KEYWORDS)
