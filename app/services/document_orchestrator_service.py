"""Thin service layer extracted from ``app/api/documents.py``.

Owns the logic that used to live as private router-module helpers:

* :func:`row_to_detail_response` — maps a raw ``documents`` row to the
  ``DocumentDetailResponse`` contract without any FastAPI involvement.
* :func:`build_and_persist_smart_toc` — asynchronous Smart-TOC
  generation/enhancement/persistence orchestration previously inlined in
  the router as ``_build_and_persist_smart_toc``.
* :func:`resolve_llm_organization_id` — picks the correct organization whose
  LLM-provider settings an AI call should be billed to.

These helpers are kept here so the router endpoints themselves stay thin
``Depends``-annotated dispatchers.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from app.services.document_service import DocumentService
    from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)


class DocumentOrchestratorService:
    """Static helpers for document orchestration logic."""

    # ------------------------------------------------------------------
    # Row → contract shaping
    # ------------------------------------------------------------------

    @staticmethod
    def row_to_detail_response(row: dict, service: "DocumentService") -> Any:
        """Build a ``DocumentDetailResponse`` from a ``documents`` row dict.

        Kept here rather than on :class:`DocumentService` because it imports
        the Pydantic response contract, which the persistence service should
        not need to know about.
        """
        from app.modules.contracts import DocumentDetailResponse

        text = service.get_document_text(row)
        return DocumentDetailResponse(
            id=row["id"],
            filename=row.get("filename", "document"),
            doc_type=row.get("doc_type") or "Specification",
            file_path=row.get("file_path"),
            upload_date=row.get("upload_date"),
            text=text,
            char_count=len(text),
            doclang_storage_path=row.get("doclang_storage_path"),
            doclang_archive_path=row.get("doclang_archive_path"),
            doclang_xml=service.get_doclang_content(row),
            project_code=row.get("project_code", ""),
            originator=row.get("originator", ""),
            volume_system=row.get("volume_system", ""),
            level=row.get("level", ""),
            type=row.get("type", ""),
            role=row.get("role", ""),
            number=row.get("number", ""),
            suitability_code=row.get("suitability_code", "S0"),
            revision_code=row.get("revision_code", "P01.01"),
            cde_state=row.get("cde_state") or "WIP",
        )

    # ------------------------------------------------------------------
    # LLM organization resolution
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_llm_organization_id(
        document_id: int,
        doc: dict,
        requested_org_id: Optional[int],
        x_org_id: Optional[str],
        user_id: str,
        user_org_ids: list[int],
        is_superadmin: bool,
        org_grants_fn: Any,
    ) -> Optional[int]:
        """Pick the organization whose LLM provider settings an AI call uses.

        This is a pure-logic extraction of the router's ``_resolve_llm_organization_id``
        helper.  The caller passes pre-fetched values so this function needs no
        FastAPI dependency objects — it can therefore be tested without a request
        context.

        Raises:
            fastapi.HTTPException: 403 if the caller requests an organization
                they do not belong to.
        """
        from fastapi import HTTPException, status

        org_id = requested_org_id
        if org_id is None and x_org_id and x_org_id.strip().isdigit():
            org_id = int(x_org_id.strip())

        if org_id is not None:
            if not is_superadmin and org_id not in user_org_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You do not belong to organization {org_id}.",
                )
            return org_id

        granted = [oid for oid in user_org_ids if document_id in org_grants_fn(oid)]
        if len(granted) == 1:
            return granted[0]
        return doc.get("organization_id")

    # ------------------------------------------------------------------
    # Smart-TOC build + persist
    # ------------------------------------------------------------------

    @staticmethod
    async def build_and_persist_smart_toc(
        document_id: int,
        doc: dict,
        service: "DocumentService",
        graph_service: "GraphService",
    ) -> Any:
        """Generate, enhance, persist in DB, and ingest into Graph RAG the Smart TOC.

        This is the async orchestration extracted from the router's private
        ``_build_and_persist_smart_toc`` coroutine.  It has no FastAPI imports
        and no awareness of request/response objects.

        Returns:
            ``DocumentSectionTreeResponse`` populated with the generated tree.
        """
        from app.modules.contracts import DocumentSection, DocumentSectionTreeResponse
        from app.modules.document_parsing.doclang_chunker import DocLangChunker
        from app.modules.document_parsing.section_tree_enhancer import enhance_section_tree
        from app.modules.document_parsing.smart_toc_generator import (
            build_smart_toc,
            calibrate_page_offsets,
            resolve_page_ranges,
            smooth_page_numbers,
        )
        from app.services.cache import cache_service
        from app.services.document_graph_service import DocumentGraphService
        from app.services.document_pages_service import DocumentPagesService

        doclang_xml = service.get_doclang_content(doc).strip()
        chunks = DocLangChunker().chunk(doclang_xml) if doclang_xml else []
        tree, flat = build_smart_toc(chunks)

        # Optional, one-shot AI label-cleanup pass
        tree, enhanced = await enhance_section_tree(tree, flat)
        if enhanced:
            id_to_name: dict[str, str] = {}

            def _collect_names(nodes: list[dict]) -> None:
                for n in nodes:
                    id_to_name[n["id"]] = n["section_name"]
                    if n.get("children"):
                        _collect_names(n["children"])

            _collect_names(tree)
            for chunk in flat:
                chunk["section_name"] = id_to_name.get(chunk["id"], chunk["section_name"])

        # Attach page numbers for any chunks where not already resolved
        unresolved_indices = [i for i, chunk in enumerate(flat) if chunk.get("page_number") is None]
        if unresolved_indices:
            pages = DocumentPagesService().get_pages(document_id)
            if pages:
                snippets = [flat[i]["text"][:250] for i in unresolved_indices]
                matched_pages = DocumentPagesService.find_best_matching_pages(
                    pages, snippets, sequential=True
                )
                for idx, page_num in zip(unresolved_indices, matched_pages, strict=False):
                    flat[idx]["page_number"] = page_num

                # Smooth any spurious non-monotonic page jumps
                smooth_page_numbers(flat)

                id_to_page = {f["id"]: f.get("page_number") for f in flat}

                def _sync_page(nodes: list[dict]) -> None:
                    for n in nodes:
                        if n.get("id") in id_to_page:
                            n["page_number"] = id_to_page[n["id"]]
                        if n.get("children"):
                            _sync_page(n["children"])

                _sync_page(tree)
                # Recompute bounded page spans with smoothed page numbers
                resolve_page_ranges(tree, flat)
                # Calibrate logical-to-physical page offsets
                calibrate_page_offsets(tree, flat)

        # Ingest Smart TOC into graph database for Graph RAG (best-effort, non-blocking)
        if graph_service:
            try:
                doc_title = (
                    getattr(doc, "name", None)
                    or getattr(doc, "title", None)
                    or f"Document {document_id}"
                )
                # Synchronous: batch embeddings (provider round trips) plus Neo4j
                # writes. In a thread so this async endpoint does not freeze the
                # worker's event loop for the duration (up to ~60s before).
                await asyncio.to_thread(
                    DocumentGraphService(graph_service).ingest_document_tree,
                    document_id,
                    tree,
                    flat,
                    document_title=doc_title,
                )
            except Exception as exc:
                logger.warning("Graph RAG tree ingestion failed for doc %d: %s", document_id, exc)

        response = DocumentSectionTreeResponse(
            document_id=document_id,
            tree=tree,
            sections=[DocumentSection(**chunk) for chunk in flat],
            enhanced=enhanced,
        )
        # Persist in DB so it doesn't recalculate unless regenerate is requested
        service.save_toc_tree(document_id, response.model_dump())
        cache_key = f"section_tree:{document_id}"
        cache_service.set(cache_key, response.model_dump())
        return response
