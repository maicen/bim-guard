# BIM-Guard

## Project Overview

**BIM Guard** is a BIM compliance application built with FastHTML (Python) and MonsterUI. It lets users upload IFC models, define compliance rules from documents, and generate reports.

**Tech stack:** FastHTML · MonsterUI · FastLite (SQLite) · IfcOpenShell · HTMX

## Getting Started

```bash
# Install dependencies
uv sync

# Run the app
uv run uvicorn main:app --reload

```

## UI Theme

ThemePicker(color=True, radii=True, shadows=True, font=True, mode=True, cls='p-4', custom_themes=[])

## IFC JS Dependencies

<https://cdn.jsdelivr.net/npm/@thatopen/fragments@3.3.6/+esm>
<https://cdn.jsdelivr.net/npm/@thatopen/components@3.3.3/+esm>

<https://cdn.jsdelivr.net/npm/@thatopen/ui@3.3.3/+esm>
<https://cdn.jsdelivr.net/npm/@thatopen/ui@3.3.3/dist/index.min.js>
<https://cdn.jsdelivr.net/npm/@thatopen/ui-obc@3.3.3/+esm>
<https://cdn.jsdelivr.net/npm/web-ifc@0.0.77/+esm>
<https://cdn.jsdelivr.net/npm/web-ifc@0.0.77/web-ifc-api-node.min.js>
