"""Document Graph Service for Graph RAG and Architectural Knowledge Graphs.

Projects hierarchical document Table of Contents (TOC) trees and their semantic
relationships into Neo4j graph database via GraphService:
  - Document & DocumentSection nodes
  - PARENT_OF & NEXT_SIBLING structural edges
  - CITES & REFERENCES cross-citation edges
  - APPLIES_TO IFC entity class edges (bridging text specs to BIM models)
"""

from __future__ import annotations

import re
from typing import Any, Optional

from app.logging_config import get_logger
from app.services.embedding_service import EmbeddingService, get_shared_embedding_service
from app.services.graph_database import GraphService

logger = get_logger(__name__)


class DocumentGraphService:
    """Service for managing document structure graphs and Graph RAG queries."""

    def __init__(
        self,
        graph_service: Optional[GraphService] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        """Initialize with an optional GraphService and EmbeddingService instance."""
        self.graph_service = graph_service
        self.embedding_service = embedding_service

    def is_available(self) -> bool:
        """Check if graph persistence provider is configured and available."""
        return self.graph_service is not None and self.graph_service.provider is not None

    def ingest_document_tree(
        self,
        document_id: int,
        tree: list[dict],
        flat: list[dict],
        *,
        document_title: str | None = None,
        filename: str | None = None,
        file_path: str | None = None,
        project_id: int | str | None = None,
        compute_embeddings: bool = True,
    ) -> dict[str, int]:
        """Ingest a Smart TOC tree into the graph database.

        Creates Document, DocumentSection, and IfcClass nodes with structural,
        cross-citation, and BIM domain edges.

        Args:
            document_id: Database ID of the source document.
            tree: Hierarchical section tree nodes.
            flat: Flat list of all section nodes with PageIndex enrichments.
            document_title: Optional human-readable document title.
            filename: Optional original filename.
            file_path: Optional storage object path.
            project_id: Optional project identifier for multi-tenant scoping.
            compute_embeddings: Whether to compute dense vector embeddings for sections.

        Returns:
            Dictionary with ingested node and edge counts.
        """
        if not self.is_available():
            logger.debug("DocumentGraphService: graph provider not available, skipping ingestion")
            return {"nodes": 0, "edges": 0}

        assert self.graph_service is not None

        doc_node_id = f"doc_{document_id}"
        # 1. Ensure Document node exists with comprehensive metadata
        doc_props: dict[str, Any] = {
            "id": doc_node_id,
            "document_id": document_id,
            "title": document_title or f"Document {document_id}",
            "filename": filename or "",
            "file_path": file_path or "",
            "total_sections": len(flat),
            "chunk_count": len(flat),
        }
        if project_id is not None:
            doc_props["project_id"] = str(project_id)

        self.graph_service.add_node("Document", doc_props)

        node_count = 1
        edge_count = 0

        # Number-to-section-id mapping for resolving citations like "Section 9.8.2" -> "s4"
        number_to_id: dict[str, str] = {}
        for item in flat:
            num = (item.get("section_number") or "").strip().rstrip(".")
            if num:
                number_to_id[num] = item["id"]
                # Also index normalized dotted forms
                norm_num = re.sub(r"[^\d.]", "", num)
                if norm_num and norm_num != num:
                    number_to_id[norm_num] = item["id"]

        # Compute dense vector embeddings for sections in batch if enabled
        embeddings: list[list[float]] | None = None
        if compute_embeddings:
            emb_svc = self.embedding_service or get_shared_embedding_service()
            texts_to_embed = [
                f"{item.get('section_number', '')} {item.get('section_name', '')}: {item.get('summary', '')}".strip()
                for item in flat
            ]
            try:
                embeddings = emb_svc.get_embeddings_batch_sync(texts_to_embed)
            except Exception as emb_err:
                logger.warning("Failed computing section embeddings for doc %d: %s", document_id, emb_err)
                embeddings = None

        # 2. Ingest DocumentSection nodes
        section_nodes_batch: list[dict[str, Any]] = []
        ifc_classes_seen: set[str] = set()

        for idx, item in enumerate(flat):
            sec_id = f"doc_{document_id}_{item['id']}"
            props = {
                "id": sec_id,
                "local_id": item["id"],
                "document_id": document_id,
                "section_number": item.get("section_number") or "",
                "section_name": item.get("section_name") or "",
                "summary": item.get("summary") or "",
                "page_number": item.get("page_number") or 0,
                "end_page_number": item.get("end_page_number") or item.get("page_number") or 0,
                "char_count": item.get("char_count") or 0,
                "node_type": item.get("node_type") or "section",
            }
            if project_id is not None:
                props["project_id"] = str(project_id)
            if embeddings and idx < len(embeddings):
                props["embedding"] = embeddings[idx]

            section_nodes_batch.append(props)
            node_count += 1

            # IFC classes
            for ifc_class in item.get("target_ifc_classes") or []:
                ifc_classes_seen.add(ifc_class)

        self.graph_service.add_nodes_batch("DocumentSection", section_nodes_batch)

        # Ingest IFC class nodes
        if ifc_classes_seen:
            ifc_nodes = [{"id": cls_name, "class_name": cls_name, "name": cls_name} for cls_name in ifc_classes_seen]
            self.graph_service.add_nodes_batch("IfcClass", ifc_nodes)
            node_count += len(ifc_nodes)

        # 3. Add Structural Hierarchy Edges (PARENT_OF) and Root Edges
        hierarchy_edges: list[dict[str, Any]] = []
        root_edges: list[dict[str, Any]] = []
        sibling_edges: list[dict[str, Any]] = []

        # Connect roots to Document
        for root in tree:
            root_id = f"doc_{document_id}_{root['id']}"
            root_edges.append({"source_id": doc_node_id, "target_id": root_id})
            edge_count += 1

        def _walk_hierarchy(parent_id: str | None, siblings: list[dict]) -> None:
            nonlocal edge_count
            for i, node in enumerate(siblings):
                curr_id = f"doc_{document_id}_{node['id']}"

                if parent_id is not None:
                    hierarchy_edges.append({"source_id": parent_id, "target_id": curr_id})
                    edge_count += 1

                # Sibling edge
                if i < len(siblings) - 1:
                    next_id = f"doc_{document_id}_{siblings[i + 1]['id']}"
                    sibling_edges.append({"source_id": curr_id, "target_id": next_id})
                    edge_count += 1

                # Recurse children
                children = node.get("children") or []
                if children:
                    _walk_hierarchy(curr_id, children)

        _walk_hierarchy(None, tree)

        if root_edges:
            self.graph_service.add_edges_batch(
                "HAS_ROOT_SECTION", root_edges, from_label="Document", to_label="DocumentSection"
            )
        if hierarchy_edges:
            self.graph_service.add_edges_batch(
                "PARENT_OF", hierarchy_edges, from_label="DocumentSection", to_label="DocumentSection"
            )
        if sibling_edges:
            self.graph_service.add_edges_batch(
                "NEXT_SIBLING", sibling_edges, from_label="DocumentSection", to_label="DocumentSection"
            )

        # 4. Add Cross-Citation Edges (CITES) and IFC Class Edges (APPLIES_TO)
        citation_edges: list[dict[str, Any]] = []
        ifc_edges: list[dict[str, Any]] = []

        for item in flat:
            curr_id = f"doc_{document_id}_{item['id']}"

            # Cross references to other sections in document
            for citation in item.get("citations") or []:
                m = re.search(r"Section\s+([\d.]+)", citation, re.IGNORECASE)
                if m:
                    target_sec_num = m.group(1).rstrip(".")
                    target_local_id = number_to_id.get(target_sec_num)
                    if target_local_id and target_local_id != item["id"]:
                        target_id = f"doc_{document_id}_{target_local_id}"
                        citation_edges.append({"source_id": curr_id, "target_id": target_id})
                        edge_count += 1

            # IFC class edges
            for ifc_class in item.get("target_ifc_classes") or []:
                ifc_edges.append({"source_id": curr_id, "target_id": ifc_class})
                edge_count += 1

        if citation_edges:
            self.graph_service.add_edges_batch(
                "CITES", citation_edges, from_label="DocumentSection", to_label="DocumentSection"
            )
        if ifc_edges:
            self.graph_service.add_edges_batch(
                "APPLIES_TO", ifc_edges, from_label="DocumentSection", to_label="IfcClass"
            )

        logger.info(
            "DocumentGraphService: ingested document %d into graph (%d nodes, %d edges)",
            document_id,
            node_count,
            edge_count,
        )
        return {"nodes": node_count, "edges": edge_count}

    def get_section_subgraph(self, document_id: int, local_section_id: str) -> dict[str, Any]:
        """Retrieve a section's Graph RAG context (ancestors, children, citations, and IFC classes)."""
        if not self.is_available():
            return {"nodes": [], "edges": []}

        assert self.graph_service is not None
        sec_id = f"doc_{document_id}_{local_section_id}"

        # Cypher query to retrieve 1-hop and 2-hop connected graph context
        cypher = """
        MATCH (s:DocumentSection {id: $sec_id})
        OPTIONAL MATCH (parent:DocumentSection)-[:PARENT_OF]->(s)
        OPTIONAL MATCH (s)-[:PARENT_OF]->(child:DocumentSection)
        OPTIONAL MATCH (s)-[:CITES]->(cited:DocumentSection)
        OPTIONAL MATCH (s)-[:APPLIES_TO]->(ifc:IfcClass)
        RETURN s, parent, collect(DISTINCT child) as children,
               collect(DISTINCT cited) as citations,
               collect(DISTINCT ifc) as ifc_classes
        """
        try:
            records = self.graph_service.execute(cypher, {"sec_id": sec_id})
            return {"records": records}
        except Exception as exc:
            logger.warning("get_section_subgraph failed for %s: %s", sec_id, exc)
            return {"records": []}
