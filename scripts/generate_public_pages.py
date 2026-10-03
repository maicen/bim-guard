"""Generate BIM Guard's crawlable public pages and ``sitemap.xml``.

The Svelte app is a hash-routed SPA behind login, so search engines cannot index
anything inside it. These pages are plain, server-rendered-equivalent HTML served
at clean paths (``/features``, ``/docs`` ...) by ``serve_spa`` in ``app/main.py``,
which resolves ``/<name>`` to ``<name>.html`` inside ``frontend/dist``.

This script is the single source of truth for the pages and the sitemap. Edit the
``PAGES`` data below and rerun it -- never hand-edit the generated HTML:

    uv run python scripts/generate_public_pages.py          # write files
    uv run python scripts/generate_public_pages.py --check  # exit 1 if stale

Output goes to ``frontend/public/`` (copied into ``frontend/dist`` by Vite). The
sitemap is also mirrored to ``static/`` because ``_resolve_public_html`` falls back
to that folder when the frontend has not been built.

Copy must stay factual: describe only capabilities documented in README.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT / "frontend" / "public"
STATIC_DIR = ROOT / "static"
SITE = "https://bim-guard.xyz"
OG_IMAGE = f"{SITE}/og-image.png"

# Pages that are not generated here but belong in the sitemap.
EXISTING_PAGES = [
    {"path": "/", "lastmod": "2026-10-04", "changefreq": "weekly", "priority": "1.0"},
    {"path": "/privacy", "lastmod": "2026-09-15", "changefreq": "monthly", "priority": "0.6"},
    {"path": "/terms", "lastmod": "2026-09-15", "changefreq": "monthly", "priority": "0.6"},
]

# Each section is (heading, [paragraph | ("ul", [items])]).
PAGES = [
    {
        "slug": "features",
        "title": "Features - BIM Guard OpenBIM Compliance Platform",
        "h1": "BIM Guard features",
        "description": (
            "Automated architectural code compliance for IFC models, ISO 19650 CDE "
            "governance, BCF issue coordination, IDS validation and bSDD classification."
        ),
        "lastmod": "2026-10-04",
        "intro": (
            "BIM Guard is an OpenBIM compliance platform. Upload IFC models and "
            "regulatory documents, extract rules, run audits and route the findings "
            "as BCF issues, with every step tracked under ISO 19650."
        ),
        "sections": [
            (
                "Architectural code compliance",
                [
                    "Compliance engines read the IFC model directly and evaluate it "
                    "against rules stored in the database, so thresholds are data, "
                    "not hardcoded constants.",
                    ("ul", [
                        "<strong>Means of egress</strong> - topological graph traversal "
                        "from habitable spaces to exterior exits, checking travel "
                        "distance and exit-count thresholds.",
                        "<strong>Daylight</strong> - window glazing area against room "
                        "floor area, checked against configurable ratio thresholds.",
                    ]),
                ],
            ),
            (
                "Rules from your own standards",
                [
                    "Upload PDF building codes and standards. They are parsed with "
                    "structured layout analysis, rules are extracted with an LLM, and "
                    "each rule is reviewed and grounded against its source clause "
                    "before it joins your rule catalog.",
                ],
            ),
            (
                "ISO 19650 and CDE governance",
                [
                    "Validate container naming and metadata, and guard workflow state "
                    "transitions (WIP, SHARED, PUBLISHED, ARCHIVED).",
                    "Read more: <a href=\"/iso-19650-cde\">ISO 19650 and CDE governance</a>.",
                ],
            ),
            (
                "BCF, IDS and bSDD",
                [
                    "Findings export as BCF issues. Information requirements can be "
                    "checked against buildingSMART IDS specifications, and "
                    "classifications are validated against the buildingSMART Data "
                    "Dictionary.",
                    "Read more: <a href=\"/bcf-and-ids\">BCF issue management and IDS validation</a>.",
                ],
            ),
            (
                "Live progress and reporting",
                [
                    "Audits stream stage-by-stage progress in real time, and results "
                    "are available as reports and exports for your team.",
                ],
            ),
        ],
    },
    {
        "slug": "ifc-compliance-checking",
        "title": "IFC Compliance Checking - Automated Building Code Audits | BIM Guard",
        "h1": "Automated IFC compliance checking",
        "description": (
            "Check IFC models against architectural building-code rules automatically: "
            "egress travel distance, exit counts and daylight ratios, with results as BCF issues."
        ),
        "lastmod": "2026-10-04",
        "intro": (
            "Manual code review of a building model is slow and hard to repeat. BIM "
            "Guard reads your IFC file, applies rules from a managed catalog and "
            "reports each finding against the element that caused it."
        ),
        "sections": [
            (
                "How an audit works",
                [
                    ("ul", [
                        "<strong>Create a project</strong> and attach an IFC model "
                        "(IFC2X3, IFC4 or IFC4.3).",
                        "<strong>Choose a ruleset</strong> - an existing catalog or one "
                        "extracted from your own code document.",
                        "<strong>Run the audit.</strong> Progress streams live while the "
                        "model is validated, parsed, checked and scored.",
                        "<strong>Review findings</strong> in the report and 3D viewer, "
                        "then export them as BCF issues.",
                    ]),
                ],
            ),
            (
                "What gets checked",
                [
                    ("ul", [
                        "<strong>Egress</strong> - the shortest path from each habitable "
                        "space to an exterior exit is computed over the building's "
                        "space-boundary graph, then compared with travel-distance and "
                        "exit-count limits from the active ruleset.",
                        "<strong>Daylight</strong> - glazing area relative to room floor "
                        "area, compared with the ruleset's ratio threshold.",
                    ]),
                    "Thresholds come from the rule database, so switching jurisdiction "
                    "or code edition means switching ruleset, not changing code.",
                ],
            ),
            (
                "Model quality gate",
                [
                    "Before analysis, an IFC pre-flight service checks STEP syntax, "
                    "schema compatibility and core buildingSMART rules such as a "
                    "single project root, valid 22-character GUIDs, spatial "
                    "containment and material association.",
                ],
            ),
            (
                "Related",
                [
                    "<a href=\"/features\">All features</a> · "
                    "<a href=\"/bcf-and-ids\">BCF and IDS</a> · "
                    "<a href=\"/docs\">Documentation</a>",
                ],
            ),
        ],
    },
    {
        "slug": "iso-19650-cde",
        "title": "ISO 19650 CDE Governance and Naming Validation | BIM Guard",
        "h1": "ISO 19650 and CDE governance",
        "description": (
            "Validate ISO 19650 container naming, suitability and revision codes, and "
            "enforce CDE state transitions from WIP to SHARED, PUBLISHED and ARCHIVED."
        ),
        "lastmod": "2026-10-04",
        "intro": (
            "ISO 19650 asks teams to manage information in a Common Data Environment "
            "with consistent naming and controlled status changes. BIM Guard enforces "
            "both so the rules are applied by the system rather than by memory."
        ),
        "sections": [
            (
                "Container naming and metadata",
                [
                    "Project and document names are validated against the field "
                    "structure <code>[Project]-[Originator]-[Volume]-[Level]-[Type]-[Role]-[Number]</code> "
                    "(UK National Annex).",
                    ("ul", [
                        "Suitability codes: <code>S0</code>-<code>S4</code> and <code>A1</code>-<code>A4</code>.",
                        "Revision codes such as <code>P01.01</code> and <code>C01</code>.",
                    ]),
                ],
            ),
            (
                "CDE state machine",
                [
                    "Workflow state moves through <strong>WIP</strong>, "
                    "<strong>SHARED</strong>, <strong>PUBLISHED</strong> and "
                    "<strong>ARCHIVED</strong>. Transitions are validated by a state "
                    "machine, and database triggers restrict changes to published "
                    "models.",
                ],
            ),
            (
                "Metadata carried into issues",
                [
                    "BCF issue reports are enriched with the ISO 19650 container "
                    "label, suitability code and revision tag, so coordination "
                    "issues stay traceable to the exact information container.",
                ],
            ),
            (
                "Related",
                [
                    "<a href=\"/features\">All features</a> · "
                    "<a href=\"/bcf-and-ids\">BCF and IDS</a> · "
                    "<a href=\"/docs\">Documentation</a>",
                ],
            ),
        ],
    },
    {
        "slug": "bcf-and-ids",
        "title": "BCF Issue Management and IDS Validation | BIM Guard",
        "h1": "BCF issue management and IDS validation",
        "description": (
            "Export compliance findings as BCF issues, expose a BCF REST API, and "
            "generate, import and audit buildingSMART IDS specifications."
        ),
        "lastmod": "2026-10-04",
        "intro": (
            "Findings are only useful if they reach the people who fix the model. BIM "
            "Guard speaks the buildingSMART exchange formats so results flow into the "
            "tools your team already uses."
        ),
        "sections": [
            (
                "BCF issues",
                [
                    "Audit findings export as BCF topics with viewpoints, comments and "
                    "snapshots. A BCF REST API (v2.1 and v3.0) exposes topics, "
                    "viewpoints, comments and snapshot binaries for bidirectional "
                    "exchange.",
                ],
            ),
            (
                "IDS - Information Delivery Specification",
                [
                    "Generate, import and audit buildingSMART IDS (0.9.6 and 1.0) XML "
                    "specifications to verify the level of information need.",
                    ("ul", [
                        "Facets: entity, property, classification, material and part-of.",
                        "Numerical tolerance checks on property values.",
                    ]),
                ],
            ),
            (
                "bSDD classification",
                [
                    "Material definitions, classifications (Uniclass, OmniClass) and "
                    "property sets are validated against the buildingSMART Data "
                    "Dictionary, with offline resilience when the service is "
                    "unreachable.",
                ],
            ),
            (
                "Related",
                [
                    "<a href=\"/features\">All features</a> · "
                    "<a href=\"/iso-19650-cde\">ISO 19650 and CDE</a> · "
                    "<a href=\"/docs\">Documentation</a>",
                ],
            ),
        ],
    },
    {
        "slug": "docs",
        "title": "Documentation - BIM Guard User Manual and Guides",
        "h1": "BIM Guard documentation",
        "description": (
            "Guides for BIM Guard: getting started, projects, documents and rule "
            "extraction, running compliance audits, reports and administration."
        ),
        "lastmod": "2026-10-04",
        "intro": (
            "BIM Guard checks IFC building models against architectural code rules, "
            "tracks the results as BCF issues and reports, and keeps project documents "
            "under ISO 19650 governance."
        ),
        "sections": [
            (
                "Typical workflow",
                [
                    ("ul", [
                        "Create a <strong>project</strong> and attach an IFC model.",
                        "Upload a code <strong>document</strong> and extract "
                        "<strong>rules</strong> from it, or pick an existing ruleset.",
                        "Run a <strong>compliance audit</strong>.",
                        "Review results, the 3D view, and <strong>reports and "
                        "exports</strong> (BCF, PDF, Excel, CSV).",
                    ]),
                ],
            ),
            (
                "Topics",
                [
                    ("ul", [
                        "<a href=\"/features\">Features overview</a>",
                        "<a href=\"/ifc-compliance-checking\">Automated IFC compliance checking</a>",
                        "<a href=\"/iso-19650-cde\">ISO 19650 and CDE governance</a>",
                        "<a href=\"/bcf-and-ids\">BCF issue management and IDS validation</a>",
                    ]),
                ],
            ),
            (
                "Full manual",
                [
                    "The complete illustrated manual covers every page of the app, "
                    "from the dashboard and rule extraction studio to the 3D viewer, "
                    "reports and the admin portal. It is available in the repository "
                    "at <a href=\"https://github.com/maicen/bim-guard/blob/main/docs/manual/user-manual.md\" "
                    "rel=\"noopener\">docs/manual/user-manual.md</a>.",
                ],
            ),
        ],
    },
]

CSS = """
    :root{--bg:#090d16;--card:#0f172a;--border:#1e293b;--fg:#f8fafc;--fg2:#94a3b8;--accent:#3b82f6}
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;background:var(--bg);color:var(--fg);line-height:1.65;-webkit-font-smoothing:antialiased;padding:0 1rem}
    .container{max-width:800px;margin:0 auto;padding:2.5rem 0 5rem}
    header.site-header{display:flex;flex-wrap:wrap;gap:1rem;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);padding-bottom:1.5rem;margin-bottom:2.5rem}
    .brand{color:var(--fg);text-decoration:none;font-weight:700;font-size:1.15rem}
    nav a{color:var(--fg2);text-decoration:none;margin-left:1.1rem;font-size:.95rem}
    nav a:hover{color:var(--fg)}
    h1{font-size:2.1rem;line-height:1.2;margin-bottom:1rem}
    h2{font-size:1.35rem;margin:2.2rem 0 .7rem}
    p,ul{color:var(--fg2);margin-bottom:1rem}
    ul{padding-left:1.4rem}li{margin-bottom:.5rem}
    strong{color:var(--fg)}
    a{color:var(--accent)}
    code{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:.05rem .35rem;font-size:.9em}
    .cta{display:inline-block;margin-top:1.5rem;padding:.7rem 1.4rem;background:var(--accent);color:#fff;border-radius:8px;text-decoration:none;font-weight:600}
    footer{border-top:1px solid var(--border);margin-top:3rem;padding-top:1.5rem;font-size:.9rem}
    footer a{color:var(--fg2);margin-right:1.2rem;text-decoration:none}
"""

NAV = [
    ("/features", "Features"),
    ("/ifc-compliance-checking", "Compliance checking"),
    ("/iso-19650-cde", "ISO 19650"),
    ("/bcf-and-ids", "BCF & IDS"),
    ("/docs", "Docs"),
]


def _render_section(heading: str, blocks: list) -> str:
    out = [f"<h2>{escape(heading)}</h2>"]
    for block in blocks:
        if isinstance(block, tuple):
            items = "".join(f"<li>{item}</li>" for item in block[1])
            out.append(f"<ul>{items}</ul>")
        else:
            out.append(f"<p>{block}</p>")
    return "\n    ".join(out)


def render_page(page: dict) -> str:
    """Return the full HTML document for one entry of ``PAGES``."""
    url = f"{SITE}/{page['slug']}"
    title = escape(page["title"])
    desc = escape(page["description"], quote=True)
    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "@id": f"{url}#webpage",
                "url": url,
                "name": page["title"],
                "description": page["description"],
                "isPartOf": {"@type": "WebSite", "name": "BIM Guard", "url": SITE},
                "dateModified": page["lastmod"],
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "BIM Guard", "item": SITE + "/"},
                    {"@type": "ListItem", "position": 2, "name": page["h1"], "item": url},
                ],
            },
        ],
    }
    nav = "".join(f'<a href="{href}">{escape(label)}</a>' for href, label in NAV)
    sections = "\n    ".join(_render_section(h, b) for h, b in page["sections"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <meta name="description" content="{desc}" />
  <meta name="robots" content="index, follow, max-image-preview:large" />
  <meta name="theme-color" content="#090d16" />
  <link rel="canonical" href="{url}" />
  <link rel="icon" type="image/x-icon" href="/favicon.ico" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="{url}" />
  <meta property="og:site_name" content="BIM Guard" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{desc}" />
  <meta property="og:image" content="{OG_IMAGE}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{title}" />
  <meta name="twitter:description" content="{desc}" />
  <meta name="twitter:image" content="{OG_IMAGE}" />
  <script type="application/ld+json">{json.dumps(jsonld, indent=2)}</script>
  <style>{CSS}</style>
</head>
<body>
  <div class="container">
    <header class="site-header">
      <a class="brand" href="/">BIM Guard</a>
      <nav aria-label="Main">{nav}</nav>
    </header>
    <main>
    <h1>{escape(page["h1"])}</h1>
    <p>{page["intro"]}</p>
    {sections}
    <a class="cta" href="/">Open BIM Guard</a>
    </main>
    <footer>
      <a href="/privacy">Privacy Policy</a><a href="/terms">Terms of Service</a><a href="/sitemap.xml">Sitemap</a>
    </footer>
  </div>
</body>
</html>
"""


def render_sitemap() -> str:
    """Return ``sitemap.xml`` covering the landing page, legal pages and generated pages."""
    entries = list(EXISTING_PAGES) + [
        {"path": f"/{p['slug']}", "lastmod": p["lastmod"], "changefreq": "monthly", "priority": "0.8"}
        for p in PAGES
    ]
    urls = "".join(
        f"  <url>\n    <loc>{SITE}{e['path']}</loc>\n    <lastmod>{e['lastmod']}</lastmod>\n"
        f"    <changefreq>{e['changefreq']}</changefreq>\n    <priority>{e['priority']}</priority>\n  </url>\n"
        for e in entries
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n"
    )


def outputs() -> dict[Path, str]:
    """Map every file this script owns to its expected content."""
    files = {PUBLIC_DIR / f"{p['slug']}.html": render_page(p) for p in PAGES}
    sitemap = render_sitemap()
    files[PUBLIC_DIR / "sitemap.xml"] = sitemap
    files[STATIC_DIR / "sitemap.xml"] = sitemap
    return files


def main() -> int:
    """Write the generated files, or with ``--check`` report whether they are stale."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if any file is out of date")
    args = parser.parse_args()

    stale = []
    for path, content in outputs().items():
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            stale.append(path)
            if not args.check:
                path.write_text(content, encoding="utf-8")
    rel = [str(p.relative_to(ROOT)) for p in stale]
    if args.check:
        if rel:
            print("Out of date (run scripts/generate_public_pages.py):", *rel, sep="\n  ")
            return 1
        print("Public pages are up to date.")
        return 0
    print("Updated:", *rel, sep="\n  ") if rel else print("Nothing to update.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
