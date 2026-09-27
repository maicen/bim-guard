"""Service for formatting, filtering, sorting, and paginating compliance analysis results."""

from __future__ import annotations

from typing import Any, Literal

from app.logging_config import get_logger
from app.modules.contracts import (
    AnalysisResultContract,
    AuditIssueContract,
    IssueStatsContract,
    ResultPageContract,
)
from app.services.models_service import ModelsService
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

#: Band ranking used when ordering a page, mirroring ``SEVERITY_WEIGHTS`` in
#: ``AnalyzeView.svelte``. An unrecognised band ranks last rather than raising,
#: the same as the page's ``?? 0``.
BAND_WEIGHT: dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}

PageSort = Literal[
    "band_then_score",
    "score_desc",
    "natural",
    "band_asc",
    "score_asc",
]

IssueBand = Literal["critical", "high", "medium", "low", "data_quality"]

DATA_QUALITY_TOKEN = "DATA_QUALITY"


class AnalysisResultService:
    """Orchestrates formatting, filtering, pagination, and file provenance for compliance analysis."""

    @staticmethod
    def issue_stats(issues: list) -> dict[str, int]:
        """Count ``issues`` by band, keeping data-quality notes out of the totals."""
        stats = {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0, "data_quality": 0}
        for issue in issues:
            if getattr(issue, "mechanism", None) == "data_quality":
                stats["data_quality"] += 1
                continue
            stats["total"] += 1
            band = getattr(getattr(issue, "band", None), "value", str(getattr(issue, "band", ""))).lower()
            if band in stats:
                stats[band] += 1
        return stats

    @classmethod
    def format_result(cls, slug: str, project_id: int, result: dict) -> AnalysisResultContract:
        """Format raw analysis result dictionary into strict Pydantic model."""
        raw_issues = result.get("audit_issues", [])
        issues: list[AuditIssueContract] = []
        for i in raw_issues:
            band_val = getattr(i.band, "value", str(i.band)).lower()
            raw_citations = getattr(i, "citations", []) or []
            citations: list[dict[str, str]] = []
            for c in raw_citations:
                if isinstance(c, dict):
                    citations.append({
                        "standard": c.get("standard", ""),
                        "clause": c.get("clause", ""),
                        "reason": c.get("reason", ""),
                    })
                elif hasattr(c, "standard"):
                    citations.append({
                        "standard": getattr(c, "standard", ""),
                        "clause": getattr(c, "clause", ""),
                        "reason": getattr(c, "reason", ""),
                    })

            issues.append(
                AuditIssueContract(
                    id=i.id,
                    element_id=i.element_id,
                    rule_id=i.rule_id,
                    title=i.title,
                    band=band_val,
                    score=getattr(i, "score", 0.0) or 0.0,
                    mechanism=i.mechanism,
                    description=i.description or "",
                    mitigation=i.mitigation or "",
                    assignee_role=getattr(i, "assignee_role", "BIM coordinator") or "BIM coordinator",
                    citations=citations,
                    details=dict(i.metadata) if hasattr(i, "metadata") and i.metadata else {},
                )
            )

        raw_stats = result.get("issue_stats", {})
        stats = IssueStatsContract(
            total=raw_stats.get("total", len([i for i in issues if i.mechanism != "data_quality"])),
            critical=raw_stats.get("critical", 0),
            high=raw_stats.get("high", 0),
            medium=raw_stats.get("medium", 0),
            low=raw_stats.get("low", 0),
            data_quality=raw_stats.get("data_quality", sum(1 for i in issues if i.mechanism == "data_quality")),
        )

        element_count = result.get("ifc_element_count") or len(issues)

        return AnalysisResultContract(
            pipeline="audit",
            project_id=project_id,
            slug=slug,
            element_count=element_count,
            audit_issues=issues,
            issue_stats=stats,
            compliance_error=result.get("compliance_error"),
            compliance_is_demo=result.get("compliance_is_demo", False),
            cached=result.get("cached", False),
            shacl_issues=result.get("shacl_issues", []),
            shacl_error=result.get("shacl_error"),
        )

    @staticmethod
    def source_files_for(project_id: int) -> list[dict]:
        """Return the project's attached models for a BCF export's ``Header``."""
        try:
            resolved, _missing = ModelsService(
                project_mirror=ProjectsService()
            ).resolve_all_paths(project_id)
        except Exception:
            logger.warning("Could not resolve model filenames for project %s", project_id)
            return []
        files: list[dict] = []
        for row, _path in resolved:
            name = str((row or {}).get("file_name") or "").strip()
            if not name:
                continue
            files.append({"filename": name, "date": str((row or {}).get("uploaded_at") or "")})
        return files

    @staticmethod
    def band_of(issue: Any) -> str:
        """Return an issue's band as a lowercase string, enum or not."""
        return getattr(getattr(issue, "band", None), "value", str(getattr(issue, "band", ""))).lower()

    @staticmethod
    def is_data_quality(issue: Any) -> bool:
        """Report whether a finding describes unassessable data, not a verdict."""
        return getattr(issue, "mechanism", None) in ("data_quality", "Data Quality")

    @classmethod
    def search_haystack(cls, issue: Any) -> list[str]:
        """Return the text ``q`` matches against."""
        fields = [
            getattr(issue, "title", "") or "",
            getattr(issue, "rule_id", "") or "",
            getattr(issue, "element_id", "") or "",
            getattr(issue, "mechanism", "") or "",
        ]
        for citation in getattr(issue, "citations", None) or []:
            if isinstance(citation, dict):
                fields.append(citation.get("standard", ""))
                fields.append(citation.get("clause", ""))
            elif hasattr(citation, "standard"):
                fields.append(getattr(citation, "standard", ""))
                fields.append(getattr(citation, "clause", ""))
        return fields

    @classmethod
    def select_issues(
        cls,
        issues: list,
        *,
        bands: list[str] | None,
        mechanisms: list[str] | None,
        include_data_quality: bool,
        query: str | None = None,
    ) -> list:
        """Narrow ``issues`` to what a page should list."""
        selected = issues

        if not include_data_quality:
            selected = [i for i in selected if not cls.is_data_quality(i)]

        if bands:
            wanted_bands = {b.lower() for b in bands}
            notes_wanted = "data_quality" in wanted_bands
            selected = [
                i
                for i in selected
                if (notes_wanted if cls.is_data_quality(i) else cls.band_of(i) in wanted_bands)
            ]

        if mechanisms:
            tokens = {m.upper() for m in mechanisms}
            notes_wanted = DATA_QUALITY_TOKEN in tokens
            prefixes = tuple(t for t in tokens if t != DATA_QUALITY_TOKEN)
            selected = [
                i
                for i in selected
                if (notes_wanted and cls.is_data_quality(i))
                or (prefixes and getattr(i, "rule_id", "").upper().startswith(prefixes))
            ]

        if query:
            needle = query.strip().lower()
            if needle:
                selected = [
                    i
                    for i in selected
                    if any(needle in (field or "").lower() for field in cls.search_haystack(i))
                ]

        return selected

    @classmethod
    def sort_issues(cls, issues: list, sort: PageSort) -> list:
        """Order ``issues`` deterministically for slicing."""
        if sort == "natural":
            return issues
        if sort == "score_desc":
            return sorted(issues, key=lambda i: (-(getattr(i, "score", 0.0) or 0.0), getattr(i, "id", 0)))
        if sort == "band_asc":
            return sorted(
                issues,
                key=lambda i: (
                    cls.is_data_quality(i),
                    BAND_WEIGHT.get(cls.band_of(i), 0),
                    getattr(i, "score", 0.0) or 0.0,
                    getattr(i, "id", 0),
                ),
            )
        if sort == "score_asc":
            return sorted(
                issues,
                key=lambda i: (cls.is_data_quality(i), getattr(i, "score", 0.0) or 0.0, getattr(i, "id", 0)),
            )
        return sorted(
            issues,
            key=lambda i: (
                -BAND_WEIGHT.get(cls.band_of(i), 0),
                -(getattr(i, "score", 0.0) or 0.0),
                getattr(i, "id", 0),
            ),
        )

    @classmethod
    def paginate_result(
        cls,
        result: dict,
        *,
        limit: int | None,
        offset: int,
        bands: list[str] | None,
        mechanisms: list[str] | None,
        include_data_quality: bool,
        sort: PageSort,
        query: str | None = None,
    ) -> tuple[dict, ResultPageContract]:
        """Return ``result`` with ``audit_issues`` narrowed to one page."""
        all_issues = result.get("audit_issues", [])
        matching = cls.select_issues(
            all_issues,
            bands=bands,
            mechanisms=mechanisms,
            include_data_quality=include_data_quality,
            query=query,
        )
        ordered = cls.sort_issues(matching, sort)

        window = ordered[offset:] if limit is None else ordered[offset : offset + limit]

        page = ResultPageContract(
            limit=limit,
            offset=offset,
            returned=len(window),
            total_matching=len(ordered),
            has_more=offset + len(window) < len(ordered),
        )

        narrowed = {
            **result,
            "audit_issues": window,
            "issue_stats": result.get("issue_stats") or cls.issue_stats(all_issues),
            "ifc_element_count": result.get("ifc_element_count") or len(all_issues),
        }
        return narrowed, page
