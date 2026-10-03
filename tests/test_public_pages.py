"""Guards the generated public SEO pages and sitemap against drift."""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("generate_public_pages", ROOT / "scripts" / "generate_public_pages.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def test_generated_files_are_up_to_date():
    for path, content in gen.outputs().items():
        assert path.read_text(encoding="utf-8") == content, f"{path} is stale; run scripts/generate_public_pages.py"


def test_every_page_has_unique_seo_basics():
    titles, descriptions = set(), set()
    for page in gen.PAGES:
        html = gen.render_page(page)
        assert html.count("<h1>") == 1
        assert f'<link rel="canonical" href="{gen.SITE}/{page["slug"]}"' in html
        assert 40 <= len(page["description"]) <= 170
        titles.add(page["title"])
        descriptions.add(page["description"])
    assert len(titles) == len(descriptions) == len(gen.PAGES)


def test_sitemap_lists_every_page_and_internal_links_resolve():
    sitemap = gen.render_sitemap()
    slugs = {p["slug"] for p in gen.PAGES}
    for slug in slugs:
        assert f"<loc>{gen.SITE}/{slug}</loc>" in sitemap
    known = slugs | {"features", "privacy", "terms"}
    for page in gen.PAGES:
        for href in re.findall(r'href="/([a-z0-9-]*)"', gen.render_page(page)):
            assert href == "" or href in known, f"{page['slug']} links to unknown /{href}"
