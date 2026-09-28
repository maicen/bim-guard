"""Synchronize and enrich Neo4j graph database with models, documents, and rules.

This script executes the complete graph enrichment workflow:
1. Cleans stale/flat document 1185 data and re-ingests it using the 21-chapter
   hierarchical Smart TOC tree from Supabase, computing dense 1536-dim vector
   embeddings for all sections so the HNSW vector index is fully populated.
2. Ingests all 84 active architectural rules, standards, clauses, and requirements
   into Neo4j via RegulatoryGraphService.
3. Re-ingests Project 8 (BUILDING_R4.ifc) and Project 21 (Golden Model v3) with
   enriched voids, fills, hosted-in, space boundary, and class bridging relationships.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from app.logging_config import configure_logging, get_logger
from app.modules.ifc_reader.ifc_graph import ingest_ifc_to_graph
from app.services.document_graph_service import DocumentGraphService
from app.services.embedding_service import EmbeddingService
from app.services.graph_database import GraphService
from app.services.neo4j_provider import Neo4jDatabaseProvider
from app.services.regulatory_graph_service import RegulatoryGraphService
from app.services.rules_service import RuleService
from supabase import create_client

load_dotenv()
configure_logging()
logger = get_logger("bimguard.scripts.sync_neo4j_graph")


def main() -> None:
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    username = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "bimguardpassword")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")

    logger.info("Connecting to Neo4j at %s...", uri)
    provider = Neo4jDatabaseProvider(
        uri=uri,
        username=username,
        password=password,
        database=database,
    )
    if not provider.verify_connectivity():
        logger.error("Could not connect to Neo4j at %s", uri)
        return

    graph_service = GraphService(provider=provider)
    embedding_service = EmbeddingService()

    # Ensure Neo4j indexes exist
    provider.ensure_vector_index("document_section_vector", "DocumentSection", "embedding", 1536)
    provider.ensure_fulltext_index("document_section_fulltext", "DocumentSection", ["section_number", "section_name", "summary"])
    provider.ensure_fulltext_index("ifc_product_fulltext", "IfcProduct", ["name", "guid", "ifc_type", "tag"])
    provider.ensure_index("IfcProduct", "id")
    provider.ensure_index("IfcProduct", "guid")
    provider.ensure_index("IfcProduct", "project_id")
    provider.ensure_index("IfcClass", "id")
    provider.ensure_index("IfcClass", "class_name")

    # Connect to Supabase
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_KEY")
    supabase = create_client(sb_url, sb_key)

    # -------------------------------------------------------------------------
    # 1. RESYNC DOCUMENT 1185 (SBC-201-2007)
    # -------------------------------------------------------------------------
    logger.info("=== 1. Resyncing Document 1185 (SBC-201-2007) ===")
    res = supabase.table("documents").select("id, filename, file_path, toc_tree, doc_type").eq("id", 1185).single().execute()
    doc_data = res.data
    toc = doc_data.get("toc_tree") or {}
    tree = toc.get("tree", [])
    sections = toc.get("sections", [])

    if tree and sections:
        # Clean old stale sections for doc 1185
        clean_cypher = """
        MATCH (d:Document {id: 'doc_1185'})
        OPTIONAL MATCH (d)-[:HAS_ROOT_SECTION|PARENT_OF*0..]->(s:DocumentSection)
        DETACH DELETE s, d
        """
        graph_service.execute(clean_cypher)
        logger.info("Removed old uncurated sections for doc_1185")

        doc_graph_service = DocumentGraphService(graph_service, embedding_service)
        doc_stats = doc_graph_service.ingest_document_tree(
            document_id=1185,
            tree=tree,
            flat=sections,
            document_title="Saudi Building Code (SBC-201-2007)",
            filename=doc_data.get("filename"),
            file_path=doc_data.get("file_path"),
            compute_embeddings=True,
        )
        logger.info("Ingested Document 1185 with embeddings: %s", doc_stats)
    else:
        logger.warning("No TOC tree found in Supabase for document 1185")

    # -------------------------------------------------------------------------
    # 2. INGEST REGULATORY KNOWLEDGE GRAPH (84 RULES)
    # -------------------------------------------------------------------------
    logger.info("=== 2. Ingesting Regulatory Knowledge Graph ===")
    rules_service = RuleService()
    reg_service = RegulatoryGraphService(rules_service=rules_service, graph_service=graph_service)
    reg_stats = reg_service.ingest_regulatory_graph()
    logger.info("Ingested Regulatory Knowledge Graph: %s", reg_stats)

    # -------------------------------------------------------------------------
    # 3. RE-INGEST MODELS (Project 8 & Project 21) WITH ENRICHED TOPOLOGY
    # -------------------------------------------------------------------------
    logger.info("=== 3. Re-ingesting Models with Enriched Relationships ===")
    import ifcopenshell

    # Model 1: Project 8 (BUILDING_R4.ifc)
    p8_path = Path("data/cache/supabase-storage/uploads/ifc/93ce691468c34b51955f5239bd33ec23_BUILDING_R4.ifc")
    if p8_path.exists():
        logger.info("Re-ingesting Project 8 (%s)...", p8_path.name)
        m8 = ifcopenshell.open(str(p8_path))
        p8_stats = ingest_ifc_to_graph(
            m8,
            graph_service,
            project_id="8",
            bridge_classes=True,
        )
        logger.info("Project 8 ingested: %s", p8_stats)

    # Model 2: Project 21 (bimguard_golden_model_v3.ifc)
    # Check cache or Supabase download
    p21_files = list(Path("data").rglob("*golden_model_v3*.ifc"))
    if p21_files and p21_files[0].exists():
        p21_path = p21_files[0]
        logger.info("Re-ingesting Project 21 (%s)...", p21_path.name)
        m21 = ifcopenshell.open(str(p21_path))
        p21_stats = ingest_ifc_to_graph(
            m21,
            graph_service,
            project_id="21",
            bridge_classes=True,
        )
        logger.info("Project 21 ingested: %s", p21_stats)
    else:
        logger.info("Checking other golden model files...")
        other_golden = list(Path(".").rglob("*golden_model*.ifc"))
        if other_golden:
            logger.info("Found model: %s", other_golden[0])
            m = ifcopenshell.open(str(other_golden[0]))
            stats = ingest_ifc_to_graph(m, graph_service, project_id="21", bridge_classes=True)
            logger.info("Ingested model to project 21: %s", stats)

    # -------------------------------------------------------------------------
    # 4. FINAL VERIFICATION & AUDIT
    # -------------------------------------------------------------------------
    logger.info("=== 4. Final Graph Audit ===")
    with provider.driver.session() as session:
        labels = [r["label"] for r in session.run("CALL db.labels() YIELD label RETURN label")]
        print(f"\nAll Labels in Neo4j ({len(labels)}): {labels}")

        rel_types = [r["relationshipType"] for r in session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")]
        print(f"All Relationship Types ({len(rel_types)}): {rel_types}")

        # Check isolated nodes
        isolated_cnt = session.run("MATCH (n) WHERE NOT (n)--() RETURN count(n) as c").single()["c"]
        print(f"Isolated Nodes: {isolated_cnt} (was 524)")

        # Check section embeddings
        emb_cnt = session.run("MATCH (s:DocumentSection) WHERE s.embedding IS NOT NULL RETURN count(s) as c").single()["c"]
        total_sec = session.run("MATCH (s:DocumentSection) RETURN count(s) as c").single()["c"]
        print(f"DocumentSection Nodes with 1536-dim Embedding: {emb_cnt} / {total_sec}")

        # Check root sections
        root_cnt = session.run("MATCH (d:Document)-[:HAS_ROOT_SECTION]->(s) RETURN count(s) as c").single()["c"]
        print(f"Direct Document HAS_ROOT_SECTION Count: {root_cnt} (was 457)")

        # Check voids and fills
        voids_cnt = session.run("MATCH ()-[r:HAS_VOID]->() RETURN count(r) as c").single()["c"]
        fills_cnt = session.run("MATCH ()-[r:FILLED_BY]->() RETURN count(r) as c").single()["c"]
        hosted_cnt = session.run("MATCH ()-[r:HOSTED_IN]->() RETURN count(r) as c").single()["c"]
        bounds_cnt = session.run("MATCH ()-[r:BOUNDED_BY]->() RETURN count(r) as c").single()["c"]
        print("Enriched Relationships:")
        print(f"  HAS_VOID: {voids_cnt}")
        print(f"  FILLED_BY: {fills_cnt}")
        print(f"  HOSTED_IN: {hosted_cnt}")
        print(f"  BOUNDED_BY: {bounds_cnt}")

        # Check bridge between Document and Model
        bridge_test = session.run("""
            MATCH (s:DocumentSection)-[:APPLIES_TO]->(c:IfcClass)<-[:INSTANCE_OF]-(p:IfcProduct)
            RETURN c.class_name as class_name, count(DISTINCT s) as section_count, count(DISTINCT p) as product_count
            ORDER BY product_count DESC
            LIMIT 5
        """).data()
        print("\nDocumentSection -> IfcClass -> IfcProduct Bridge Verification:")
        for bt in bridge_test:
            print(f"  {bt['class_name']}: {bt['section_count']} sections govern {bt['product_count']} model elements")


if __name__ == "__main__":
    main()
