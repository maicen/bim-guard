"""Query understanding, dual-level decomposition, intent routing, and relevance gating."""

import re
from typing import Any, Optional

from app.services.graph_rag.constants import (
    _IFC_KEYWORD_MAP,
    _THEME_KEYWORDS,
)


class GraphRagQueryRouter:
    """LightRAG dual-level query analyzer, intent classifier, and relevance router."""

    def detect_ifc_classes(self, query: str, explicit_class: Optional[str] = None) -> list[str]:
        """Extract IFC entity classes mentioned in query or specified explicitly."""
        detected = set()
        if explicit_class:
            detected.add(explicit_class if explicit_class.startswith("Ifc") else f"Ifc{explicit_class.capitalize()}")

        tokens = re.findall(r"\b[A-Za-z]+\b", query.lower())
        for token in tokens:
            if token in _IFC_KEYWORD_MAP:
                detected.add(_IFC_KEYWORD_MAP[token])

        for m in re.finditer(r"\bIfc[A-Z][a-zA-Z]+\b", query):
            detected.add(m.group(0))

        return sorted(detected)

    def analyze_query_dual_level(
        self, query: str, explicit_class: Optional[str] = None
    ) -> dict[str, Any]:
        """Extract concrete low-level entity seeds, high-level abstract themes, and classify domain intent."""
        target_classes = self.detect_ifc_classes(query, explicit_class)

        # Concrete clauses (e.g. 1017.2, 1005, 404, 7.2)
        clause_matches = re.findall(
            r"\b(?:Section|Clause|Item|Code|IBC|NFPA|ADA)?\s*([0-9]{3,4}(?:\.[0-9]+)?|[0-9]+\.[0-9]+(?:\.[0-9]+)?)\b",
            query,
            re.IGNORECASE,
        )
        concrete_clauses = [c.strip() for c in clause_matches if len(c.strip()) >= 3]

        # Explicit GUIDs (OpenBIM 22-char or standard UUIDs)
        guids = re.findall(r"\b[0-9a-zA-Z_$]{22}\b", query)

        # High-level abstract themes
        query_lower = query.lower().strip()
        active_themes: list[str] = []
        for theme_name, theme_words in _THEME_KEYWORDS.items():
            if any(w in query_lower for w in theme_words):
                active_themes.append(theme_name)

        # SOTA Domain Intent Classification & Relevance Gating
        is_model_inventory = bool(
            not target_classes
            and (
                re.search(
                    r"\b(?:how\s+many|count(?:\s+of)?|number\s+of|total|list|what|which|show|names?\s+of)\b.*\b(?:models?|ifc\s*files?|bim\s*models?)\b",
                    query_lower,
                )
                or re.search(
                    r"\b(?:models?|ifc\s*files?|bim\s*models?)\b.*\b(?:in\s+this\s+project|in\s+the\s+project|attached|uploaded|exist)\b",
                    query_lower,
                )
                or re.search(r"\b(?:which|what)\s+model\s+is\s+primary\b", query_lower)
                or re.search(r"\bmodel\s+inventory\b", query_lower)
                or query_lower in {"models", "models?", "list models", "models in project", "show models"}
            )
        )

        is_project_meta = bool(
            re.search(
                r"\b(?:tell\s+me\s+about|info\s+about|details\s+of|overview\s+of|describe|summary\s+of)\s+(?:this\s+)?project\b",
                query_lower,
            )
            or re.search(
                r"\b(?:what\s+is\s+the|who\s+is\s+the)\s+(?:project\s+name|client|project\s+size|project\s+status|country)\b",
                query_lower,
            )
            or re.search(r"\bproject\s+metadata\b", query_lower)
            or query_lower in {"project", "about project", "project info", "project summary"}
        )

        is_document_inventory = bool(
            re.search(
                r"\b(?:how\s+many|count(?:\s+of)?|number\s+of|total|list|what|which|show)\b.*\b(?:documents?|specifications?|standards?|guidelines?|client\s+documents?|pdfs?)\b",
                query_lower,
            )
            or re.search(
                r"\b(?:documents?|specifications?)\b.*\b(?:in\s+this\s+project|in\s+the\s+project|attached|uploaded)\b",
                query_lower,
            )
            or re.search(r"\bdocument\s+inventory\b", query_lower)
            or query_lower in {"documents", "documents?", "list documents"}
        )

        has_doc_indicators = bool(
            concrete_clauses
            or active_themes
            or re.search(
                r"\b(?:spec|specification|clause|section|requirement|standard|code|ibc|nfpa|ada|comply|compliance|fire\s+rating|egress|clearance)\b",
                query_lower,
            )
        )

        skip_document_search = False
        if is_model_inventory:
            intent_type = "model_inventory"
            retrieval_mode = "inventory"
            if not has_doc_indicators:
                skip_document_search = True
        elif is_project_meta:
            intent_type = "project_metadata"
            retrieval_mode = "inventory"
            if not has_doc_indicators:
                skip_document_search = True
        elif is_document_inventory:
            intent_type = "document_inventory"
            retrieval_mode = "inventory"
        elif target_classes and any(term in query_lower for term in ["how many", "count", "total", "number of"]):
            intent_type = "element_count"
            retrieval_mode = "local" if guids else "hybrid_rrf"
        elif any(term in query_lower for term in ["overall", "all ", "summary", "patterns", "primary risks", "audit overview", "across all"]):
            intent_type = "global_summary"
            retrieval_mode = "global"
        elif guids or (concrete_clauses and len(concrete_clauses) == 1 and not active_themes):
            intent_type = "compliance_check"
            retrieval_mode = "local"
        else:
            intent_type = "compliance_check"
            retrieval_mode = "hybrid_rrf"

        return {
            "target_classes": target_classes,
            "concrete_clauses": concrete_clauses,
            "element_guids": guids,
            "abstract_themes": active_themes,
            "retrieval_mode": retrieval_mode,
            "intent_type": intent_type,
            "skip_document_search": skip_document_search,
        }
