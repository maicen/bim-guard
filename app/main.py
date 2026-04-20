from fasthtml.common import FileResponse, Title, fast_app
from monsterui.all import (
    Container,
    DivLAligned,
    H1,
    Subtitle,
)
from app.components.layout import DashboardLayout
from app.components.themed_ui import SiteTheme
from app.components.ui import ViewAction
from app.utils import load_env_file

load_env_file()

from app.routes import analyze, dashboard, library, projects, viewer


APP_HEADERS = SiteTheme()

app, rt = fast_app(
    hdrs=APP_HEADERS,
    cls="antialiased",
)


# Serve static files
@rt("/static/{path:path}")
def serve_static(path: str):
    return FileResponse(f"static/{path}")


# Compatibility endpoint for stale browser tabs that still attempt FastHTML's
# old live-reload websocket. We keep Uvicorn reload as the actual dev reload
# mechanism and simply accept these connections to avoid repeated 403 noise.
@app.ws("/live-reload")
async def live_reload_compat(msg: str, send):
    return None


def _backfill_obc_metadata(svc) -> None:
    """Add mechanism/ruleset metadata to legacy OBC seed rules that predate the meta columns."""
    for rule in svc.list_rules():
        if rule.get("extraction_method") == "seed" and not rule.get("ruleset_id"):
            svc._rules.update(
                updates={
                    "mechanism":     "OBC",
                    "ruleset_id":    "OBC-PART9",
                    "rule_category": "property_check",
                },
                pk_values=rule["id"],
            )


def _seed_library() -> None:
    """Populate the rule library with OBC baseline rules and engine rulesets."""
    try:
        from app.services.rules_service import RuleService
        from app.services.ruleset_seeder import seed_engine_rulesets
        from app.modules.module3_rule_builder.obc_seed_rules import OBC_SEED_RULES

        svc = RuleService()

        # Backfill any legacy OBC rules that lack classification metadata
        _backfill_obc_metadata(svc)

        # Seed OBC Part 9 property-check rules (idempotent via ruleset_id check)
        if not svc.has_ruleset("OBC-PART9"):
            for rule in OBC_SEED_RULES:
                svc.create_rule(
                    reference=str(rule.get("ref") or "OBC"),
                    rule_type=str(rule.get("rule_type") or "numeric_comparison"),
                    description=str(rule.get("desc") or ""),
                    target_ifc_class=str(rule.get("target") or "Unspecified"),
                    source_text=str(rule.get("source_text") or ""),
                    property_set=str(rule.get("property_set") or ""),
                    property_name=str(rule.get("property_name") or ""),
                    fallback_property=str(rule.get("fallback_property") or ""),
                    operator=str(rule.get("operator") or ""),
                    check_value=rule.get("check_value"),
                    value_min=rule.get("value_min"),
                    value_max=rule.get("value_max"),
                    unit=str(rule.get("unit") or ""),
                    applies_when=rule.get("applies_when") or {},
                    severity=str(rule.get("severity") or "mandatory"),
                    keyword=str(rule.get("keyword") or ""),
                    compliance_type=str(rule.get("compliance_type") or ""),
                    exceptions=rule.get("exceptions") or [],
                    related_refs=rule.get("related_refs") or [],
                    overridden_by=str(rule.get("overridden_by") or ""),
                    confidence=float(rule.get("confidence") or 0.8),
                    extraction_method="seed",
                    needs_review=bool(rule.get("needs_review", False)),
                    mechanism="OBC",
                    ruleset_id="OBC-PART9",
                    rule_category="property_check",
                )

        # Seed GC-001 / CC-001 / MC-001 engine rulesets (each idempotent)
        seed_engine_rulesets(svc)

    except Exception:
        pass  # never crash startup over seeding


def _setup_routes() -> None:
    viewer.setup_routes(rt)
    analyze.setup_routes(rt)
    dashboard.setup_routes(rt)
    library.setup_routes(rt)
    projects.setup_routes(rt)


_seed_library()
_setup_routes()


@rt("/")
def get():
    return Title("BIM Guard"), DashboardLayout(
        Container(
            H1("Welcome to BIM Guard"),
            Subtitle("Open the IFC viewer to start a new compliance workflow."),
            DivLAligned(ViewAction(href="/viewer", title="Go to Viewer")),
        )
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", reload=True)
