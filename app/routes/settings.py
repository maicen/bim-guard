"""Application settings page routes."""

from __future__ import annotations

from fasthtml.common import P, Title
from monsterui.all import (
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    Container,
    Div,
    Form,
    FormLabel,
    Input,
)

from app.components.layout import DashboardLayout
from app.components.ui import Alert, AlertT, SubmitButton
from app.logging_config import current_level_name, set_log_level
from app.services.settings_service import SettingsService
from app.utils import redirect_see_other

_settings = SettingsService()


def _settings_form() -> Card:
    """Build the editable settings form using MonsterUI field primitives."""
    rows = []
    for item in _settings.list_settings():
        key = str(item.get("key") or "")
        description = str(item.get("description") or "")
        value = str(item.get("value") or "")
        control_id = f"setting_{key}"

        rows.append(
            Div(
                FormLabel(key, fr=control_id),
                Input(
                    id=control_id,
                    name=key,
                    value=value,
                    placeholder=description or key,
                ),
                P(description, cls="text-xs text-muted-foreground"),
                cls="space-y-1",
            )
        )

    return Card(
        CardHeader(CardTitle("Runtime Settings")),
        CardContent(
            Form(
                *rows,
                SubmitButton("Save Settings"),
                method="post",
                action="/settings",
                cls="space-y-4",
            )
        ),
    )


def setup_routes(rt):
    """Register settings read/write routes."""

    @rt("/settings")
    def settings_page(message: str = ""):
        alert = ()
        if message == "saved":
            alert = (Alert("Settings saved.", cls=AlertT.success),)

        return Title("Settings - BIM Guard"), DashboardLayout(
            Container(
                P(
                    "Manage runtime backend, storage, and model settings persisted in the database.",
                    cls="text-muted-foreground",
                ),
                P(
                    f"Active log level: {current_level_name()}",
                    cls="text-xs text-muted-foreground",
                ),
                *alert,
                _settings_form(),
                cls="space-y-4",
            )
        )

    @rt("/settings", methods=["POST"])
    async def settings_save(req):
        form = await req.form()
        for item in _settings.list_settings():
            key = str(item.get("key") or "")
            if not key:
                continue
            value = str(form.get(key) or "")
            _settings.set(key, value)
            if key == "BIM_GUARD_LOG_LEVEL" and value:
                set_log_level(value)

        return redirect_see_other("/settings?message=saved")
