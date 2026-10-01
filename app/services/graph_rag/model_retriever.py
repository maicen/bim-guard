"""IFC BIM Model graph retriever supporting spatial hierarchy, hub suppression, and model inventory."""

from typing import Any, Optional

from app.logging_config import get_logger
from app.modules.contracts.graph import GraphRagCitation, GraphRagToolCall
from app.services.graph_database import GraphService
from app.services.models_service import ModelsService

logger = get_logger(__name__)


class ModelGraphRetriever:
    """Traverse IFC model entities with degree penalization, spatial containment, and model inventory."""

    def __init__(
        self,
        graph_service: GraphService,
        models_service: Optional[ModelsService] = None,
        projects_service: Optional[Any] = None,
    ):
        self.graph_service = graph_service
        self.models_service = models_service or ModelsService()
        self.projects_service = projects_service

    def ensure_project_model_ingested(self, project_id: int) -> None:
        """Auto-ingest the primary IFC model into Neo4j if graph element count is 0."""
        if not self.graph_service or not self.graph_service.provider:
            return

        pid_str = str(project_id)
        try:
            check_cypher = "MATCH (elem {project_id: $pid}) RETURN count(elem) as cnt LIMIT 1"
            rows = self.graph_service.execute(check_cypher, {"pid": pid_str})
            if rows and rows[0].get("cnt", 0) > 0:
                return
        except Exception:
            pass

        try:
            models = self.models_service.list_models(project_id) or []
            if not models:
                return

            primary_model = next((m for m in models if m.get("is_primary")), models[0])
            storage_path = primary_model.get("storage_path") or primary_model.get("file_path")
            if not storage_path:
                return

            from app.services.object_storage import ObjectStorageService

            storage = ObjectStorageService()
            local_path = storage.materialize_local_path(storage_path)
            if not local_path or not local_path.exists():
                return

            from app.modules.ifc_reader.ifc_graph import ingest_ifc_to_graph

            logger.info("Auto-ingesting primary IFC model into graph for project %d: %s", project_id, local_path)
            ingest_ifc_to_graph(local_path, self.graph_service, project_id=project_id)
            logger.info("Auto-ingestion completed for project %d", project_id)
        except Exception as exc:
            logger.warning("Auto-ingesting IFC model failed for project %d: %s", project_id, exc)

    def retrieve(
        self,
        project_id: int,
        query: str,
        target_classes: Optional[list[str]] = None,
        element_guids: Optional[list[str]] = None,
        retrieval_mode: str = "hybrid_rrf",
        intent_type: str = "compliance_check",
    ) -> dict[str, Any]:
        """Traverse IFC model entities with hub suppression, spatial containment, and inventory retrieval."""
        pid_str = str(project_id)
        citations: list[GraphRagCitation] = []
        cypher = ""

        # 1. Specialized handling for Model Inventory
        is_model_query = intent_type == "model_inventory" or (
            not target_classes
            and any(term in query.lower() for term in [
                "how many models", "count of models", "number of models",
                "total models", "list models", "what models", "model inventory",
                "which model is primary", "ifc files", "attached models", "models in this project",
                "models in the project"
            ])
        )

        if is_model_query:
            models = []
            try:
                models = self.models_service.list_models(project_id) or []
            except Exception as exc:
                logger.warning("Error querying project models: %s", exc)

            graph_element_count = 0
            graph_class_count = 0
            if self.graph_service and self.graph_service.provider:
                try:
                    cypher_summary = """
                    MATCH (elem {project_id: $pid})
                    WHERE elem.ifc_type IS NOT NULL
                    RETURN count(elem) as total_elements, count(DISTINCT elem.ifc_type) as class_count
                    """
                    c_res = self.graph_service.execute(cypher_summary, {"pid": pid_str})
                    if c_res:
                        graph_element_count = c_res[0].get("total_elements", 0)
                        graph_class_count = c_res[0].get("class_count", 0)
                except Exception as exc:
                    logger.debug("Notice querying neo4j element counts: %s", exc)

            text_lines = []
            nodes: list[dict[str, Any]] = []

            if models:
                text_lines.append(f"### Project IFC Model Inventory (Total: {len(models)} model{'s' if len(models) != 1 else ''}):")
                for idx, m in enumerate(models, start=1):
                    file_name = m.get("file_name") or f"Model_{idx}.ifc"
                    model_id = m.get("id") or idx
                    is_primary = bool(m.get("is_primary"))
                    role = m.get("role") or ("primary" if is_primary else "model")
                    cde_state = m.get("cde_state") or "WIP"
                    uploaded_at = m.get("uploaded_at") or "N/A"
                    rev = m.get("revision_code") or "N/A"
                    primary_desc = "Yes (Governing model)" if is_primary else "No"
                    ref_tag = f"IFC: {file_name} | ID: {model_id}"

                    text_lines.append(
                        f"- [{ref_tag}] Name: '{file_name}', Primary: {primary_desc}, "
                        f"Role: {role}, CDE State: {cde_state}, Revision: {rev}, Uploaded: {uploaded_at}"
                    )
                    citations.append(
                        GraphRagCitation(
                            id=f"model_inv_{model_id}",
                            source_type="model",
                            title=f"IFC Model: {file_name}",
                            reference=str(model_id),
                            snippet=f"Model '{file_name}', Role: {role}, Primary: {is_primary}, CDE: {cde_state}.",
                            element_guid=str(model_id),
                            ifc_type="IfcProject",
                            properties={
                                "model_id": model_id,
                                "file_name": file_name,
                                "is_primary": is_primary,
                                "role": role,
                                "cde_state": cde_state,
                            },
                            score=2.0,
                            retrieval_method="graph",
                        )
                    )
                    nodes.append({"id": f"model_{model_id}", "label": file_name, "type": "IfcModel"})

                if graph_element_count > 0:
                    text_lines.append(
                        f"Knowledge Graph Status: {graph_element_count} building elements across {graph_class_count} IFC classes ingested."
                    )
            else:
                text_lines.append(f"### Project IFC Model Inventory:\nTotal attached models: 0.\nNo IFC models are currently attached to project {project_id}.")

            output_summary = f"Identified {len(models)} attached IFC model(s) for project {project_id}."
            cypher_str = "MATCH (elem {project_id: $pid}) RETURN count(elem)" if graph_element_count > 0 else ""
            return {
                "text": "\n".join(text_lines),
                "citations": citations,
                "tool_call": GraphRagToolCall(
                    tool_name="query_model_inventory",
                    arguments={"project_id": project_id, "total_models": len(models)},
                    output_summary=output_summary,
                    cypher_query=cypher_str,
                    status="success",
                ),
                "cypher": cypher_str,
                "element_count": len(models),
                "nodes": nodes,
                "edges": [],
            }

        # 2. Specialized handling for Project Metadata
        if intent_type == "project_metadata":
            proj = None
            if self.projects_service:
                try:
                    proj = self.projects_service.get_project(project_id)
                except Exception as exc:
                    logger.debug("Notice querying project metadata: %s", exc)

            total_models = 0
            if self.models_service:
                try:
                    total_models = len(self.models_service.list_models(project_id) or [])
                except Exception:
                    pass

            total_docs = 0
            if self.projects_service:
                try:
                    total_docs = len(self.projects_service.get_client_documents_by_project(project_id) or [])
                except Exception:
                    pass

            text_lines = ["### Project Metadata & Overview:"]
            if proj:
                text_lines.append(f"- **Project Name**: {proj.get('name') or f'Project {project_id}'}")
                if proj.get("client_name"):
                    text_lines.append(f"- **Client**: {proj.get('client_name')}")
                if proj.get("project_code"):
                    text_lines.append(f"- **Project Code**: {proj.get('project_code')}")
                if proj.get("status"):
                    text_lines.append(f"- **Status**: {proj.get('status')}")
                if proj.get("description"):
                    text_lines.append(f"- **Description**: {proj.get('description')}")
                if proj.get("country"):
                    text_lines.append(f"- **Location**: {proj.get('country')}")
            else:
                text_lines.append(f"- **Project ID**: {project_id}")

            text_lines.append(f"- **Attached Models**: {total_models} IFC file(s)")
            text_lines.append(f"- **Attached Documents**: {total_docs} specification document(s)")

            citation = GraphRagCitation(
                id=f"proj_meta_{project_id}",
                source_type="model",
                title=f"Project: {proj.get('name') if proj else project_id}",
                reference=f"Project #{project_id}",
                snippet=f"Project {proj.get('name') if proj else project_id}, Client: {proj.get('client_name') if proj else 'N/A'}, Status: {proj.get('status') if proj else 'Active'}",
                score=2.0,
                retrieval_method="graph",
            )
            return {
                "text": "\n".join(text_lines),
                "citations": [citation],
                "tool_call": GraphRagToolCall(
                    tool_name="query_project_metadata",
                    arguments={"project_id": project_id},
                    output_summary=f"Retrieved metadata for project {project_id}.",
                    status="success",
                ),
                "cypher": "",
                "element_count": 1,
                "nodes": [],
                "edges": [],
            }

        self.ensure_project_model_ingested(project_id)

        if not self.graph_service or not self.graph_service.provider:
            return {
                "text": "Model graph persistence provider not connected.",
                "citations": citations,
                "tool_call": GraphRagToolCall(
                    tool_name="query_ifc_model_graph",
                    arguments={"project_id": project_id},
                    output_summary="Provider offline",
                    status="error",
                ),
                "cypher": None,
                "element_count": 0,
                "nodes": [],
                "edges": [],
            }

        # Global Search Mode: Map-Reduce Summary Report (Microsoft GraphRAG / DRIFT)
        if retrieval_mode == "global":
            cypher = """
            MATCH (elem {project_id: $pid})
            WHERE elem.ifc_type IS NOT NULL
            OPTIONAL MATCH (storey:IfcBuildingStorey {project_id: $pid})-[:CONTAINS*1..2]->(elem)
            RETURN elem.ifc_type as ifc_type,
                   count(elem) as total_count,
                   count(elem.fire_rating) as fire_rated_count,
                   collect(DISTINCT storey.name)[..3] as storeys
            ORDER BY total_count DESC
            LIMIT 12
            """
            try:
                summary_records = self.graph_service.execute(cypher, {"pid": pid_str}) or []
                text_lines = ["### Model Architectural Distribution Summary:"]
                for r in summary_records:
                    text_lines.append(
                        f"- **{r.get('ifc_type')}**: {r.get('total_count')} elements "
                        f"({r.get('fire_rated_count')} fire rated) across {', '.join(r.get('storeys', [])) or 'Model'}."
                    )
                return {
                    "text": "\n".join(text_lines),
                    "citations": [],
                    "tool_call": GraphRagToolCall(
                        tool_name="global_model_summary",
                        arguments={"project_id": project_id, "mode": "global"},
                        output_summary=f"Generated global model summary across {len(summary_records)} IFC categories.",
                        cypher_query=cypher.strip(),
                        status="success",
                    ),
                    "cypher": cypher.strip(),
                    "element_count": sum(r.get("total_count", 0) for r in summary_records),
                    "nodes": [],
                    "edges": [],
                }
            except Exception as exc:
                logger.warning("Global model summary query error: %s", exc)

        # Local & Hybrid Search Mode: Targeted traversal with hub suppression
        primary_class = target_classes[0] if target_classes else "IfcProduct"

        # Specialized handling for building storeys / levels
        if primary_class == "IfcBuildingStorey":
            cypher = """
            MATCH (storey:IfcBuildingStorey {project_id: $pid})
            OPTIONAL MATCH (storey)-[:CONTAINS]->(child)
            RETURN storey.guid as guid, storey.name as name, storey.ifc_type as ifc_type,
                   count(DISTINCT child) as element_count,
                   collect(DISTINCT child.ifc_type)[..5] as element_types
            ORDER BY storey.name ASC
            """
            try:
                storeys_found = self.graph_service.execute(cypher, {"pid": pid_str}) or []
            except Exception as exc:
                logger.warning("Building storey graph query error: %s", exc)
                storeys_found = []

            if not storeys_found:
                # Fallback matching on property if label indexing differs
                cypher = """
                MATCH (storey {project_id: $pid})
                WHERE storey.ifc_type = 'IfcBuildingStorey'
                RETURN storey.guid as guid, storey.name as name, storey.ifc_type as ifc_type,
                       0 as element_count, [] as element_types
                ORDER BY storey.name ASC
                """
                try:
                    storeys_found = self.graph_service.execute(cypher, {"pid": pid_str}) or []
                except Exception:
                    storeys_found = []

            text_lines = [f"Total Building Storeys (Floors) in model: {len(storeys_found)}"]
            nodes = []
            citations = []
            for s in storeys_found:
                guid = s.get("guid") or "UnknownGUID"
                name = s.get("name") or "Storey"
                elem_count = s.get("element_count", 0)
                elem_types = s.get("element_types", [])
                types_str = f" (Contains elements: {', '.join(elem_types)})" if elem_types else ""
                ref = f"Storey ({name})"
                citation_id = f"ifc_{guid}"

                citations.append(
                    GraphRagCitation(
                        id=citation_id,
                        source_type="model",
                        title=f"Building Storey: {name}",
                        reference=ref,
                        snippet=f"Building Storey / Level '{name}' containing {elem_count} building elements{types_str}.",
                        element_guid=guid,
                        ifc_type="IfcBuildingStorey",
                        properties={
                            "name": name,
                            "element_count": elem_count,
                            "contained_types": elem_types,
                        },
                        score=1.5,
                        retrieval_method="graph",
                    )
                )

                nodes.append({
                    "id": guid,
                    "label": f"Storey: {name}",
                    "type": "IfcBuildingStorey",
                })
                text_lines.append(
                    f"- [IFC: IfcBuildingStorey ({name}) | GUID: {guid}] Storey Name: '{name}', "
                    f"Contained Elements: {elem_count}{types_str}"
                )

            return {
                "text": "\n".join(text_lines),
                "citations": citations,
                "tool_call": GraphRagToolCall(
                    tool_name="query_building_storeys",
                    arguments={"project_id": project_id, "primary_class": "IfcBuildingStorey"},
                    output_summary=f"Located {len(storeys_found)} building storeys (floors) in model.",
                    cypher_query=cypher.strip(),
                    status="success",
                ),
                "cypher": cypher.strip(),
                "element_count": len(storeys_found),
                "nodes": nodes,
                "edges": [],
            }

        # Targeted query matching specific element GUIDs
        if element_guids:
            cypher = """
            MATCH (elem {project_id: $pid})
            WHERE elem.guid IN $guids
            OPTIONAL MATCH (space:IfcSpace {project_id: $pid})-[:CONTAINS]->(elem)
            OPTIONAL MATCH (storey:IfcBuildingStorey {project_id: $pid})-[:CONTAINS*1..2]->(elem)
            RETURN elem.guid as guid, elem.name as name, elem.ifc_type as ifc_type,
                   elem.fire_rating as fire_rating, elem.is_external as is_external,
                   space.name as space_name, storey.name as storey_name
            """
            params: dict[str, Any] = {"pid": pid_str, "guids": element_guids}
        elif primary_class != "IfcProduct":
            cypher = f"""
            MATCH (elem:{primary_class} {{project_id: $pid}})
            OPTIONAL MATCH (space:IfcSpace {{project_id: $pid}})-[:CONTAINS]->(elem)
            OPTIONAL MATCH (storey:IfcBuildingStorey {{project_id: $pid}})-[:CONTAINS*1..2]->(elem)
            RETURN elem.guid as guid, elem.name as name, elem.ifc_type as ifc_type,
                   elem.fire_rating as fire_rating, elem.is_external as is_external,
                   space.name as space_name, storey.name as storey_name
            LIMIT 15
            """
            params = {"pid": pid_str}
        else:
            cypher = """
            MATCH (elem:IfcProduct {project_id: $pid})
            OPTIONAL MATCH (space:IfcSpace {project_id: $pid})-[:CONTAINS]->(elem)
            OPTIONAL MATCH (storey:IfcBuildingStorey {project_id: $pid})-[:CONTAINS*1..2]->(elem)
            RETURN elem.guid as guid, elem.name as name, elem.ifc_type as ifc_type,
                   elem.fire_rating as fire_rating, elem.is_external as is_external,
                   space.name as space_name, storey.name as storey_name
            LIMIT 15
            """
            params = {"pid": pid_str}

        try:
            elements_found = self.graph_service.execute(cypher, params) or []
        except Exception as exc:
            logger.warning("Targeted model graph query error: %s", exc)
            elements_found = []

        if not elements_found and primary_class != "IfcProduct":
            # Fallback property match when Neo4j nodes have generic labels
            cypher_prop = """
            MATCH (elem {project_id: $pid})
            WHERE elem.ifc_type = $cls
            OPTIONAL MATCH (space:IfcSpace {project_id: $pid})-[:CONTAINS]->(elem)
            OPTIONAL MATCH (storey:IfcBuildingStorey {project_id: $pid})-[:CONTAINS*1..2]->(elem)
            RETURN elem.guid as guid, elem.name as name, elem.ifc_type as ifc_type,
                   elem.fire_rating as fire_rating, elem.is_external as is_external,
                   space.name as space_name, storey.name as storey_name
            LIMIT 15
            """
            try:
                elements_found = self.graph_service.execute(cypher_prop, {"pid": pid_str, "cls": primary_class}) or []
                if elements_found:
                    cypher = cypher_prop
            except Exception:
                pass

        text_lines = []
        nodes = []
        edges: list[dict[str, Any]] = []

        if elements_found:
            for elem in elements_found:
                guid = elem.get("guid") or "UnknownGUID"
                name = elem.get("name") or "Element"
                ifc_t = elem.get("ifc_type") or primary_class
                fire = elem.get("fire_rating") or "Not rated"
                space = elem.get("space_name") or "Common"
                storey = elem.get("storey_name") or "Model"

                ref_tag = f"{ifc_t} ({name})"
                citation_id = f"ifc_{guid}"
                citations.append(
                    GraphRagCitation(
                        id=citation_id,
                        source_type="model",
                        title=f"{ifc_t}: {name}",
                        reference=guid,
                        snippet=f"Instance {name} on {storey}, space: {space}, fire rating: {fire}.",
                        element_guid=guid,
                        ifc_type=ifc_t,
                        properties={
                            "name": name,
                            "fire_rating": fire,
                            "space": space,
                            "storey": storey,
                        },
                        score=1.0,
                        retrieval_method="graph",
                    )
                )

                nodes.append({
                    "id": guid,
                    "label": f"{ifc_t}: {name[:18]}",
                    "type": ifc_t,
                })

                text_lines.append(
                    f"- [IFC: {ref_tag} | GUID: {guid}] Storey: '{storey}', Space: '{space}', Fire Rating: '{fire}'"
                )
        else:
            text_lines.append("No specific model elements located matching the target classification.")

        output_summary = f"Traversed {len(elements_found)} IFC element nodes in model."
        return {
            "text": "\n".join(text_lines),
            "citations": citations,
            "tool_call": GraphRagToolCall(
                tool_name="hub_suppressed_model_traversal",
                arguments={"project_id": project_id, "primary_class": primary_class},
                output_summary=output_summary,
                cypher_query=cypher.strip(),
                status="success",
            ),
            "cypher": cypher.strip(),
            "element_count": len(elements_found),
            "nodes": nodes,
            "edges": edges,
        }
