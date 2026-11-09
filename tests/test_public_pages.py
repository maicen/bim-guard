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


def test_markdown_twins_and_llms_txt_cover_every_page():
    llms = gen.render_llms_txt()
    for page in gen.PAGES:
        md = gen.render_markdown(page)
        assert md.startswith(f"# {page['h1']}")
        assert "<" not in md, f"{page['slug']} markdown still contains HTML"
        assert f'<link rel="alternate" type="text/markdown" href="{gen.SITE}/{page["slug"]}.md"' in gen.render_page(page)
        if page["slug"] != "docs":
            assert f"{gen.SITE}/{page['slug']}.md" in llms
    assert llms.startswith("# BIM Guard\n\n> ")


def test_manual_mirror_has_no_dangling_relative_links():
    for rel, text in gen._manual_files().items():
        for target in re.findall(r"\]\(([^)\s]+)\)", text):
            if re.match(r"^([a-z]+:|/|#)", target):
                continue
            resolved = (Path(rel).parent / target.split("#")[0]).as_posix()
            assert resolved in gen.MANUAL_PAGES, f"{rel} links to unpublished {target}"


def test_every_json_ld_block_parses_and_links_to_site_graph():
    import json

    blocks = [gen.render_page(p) for p in gen.PAGES] + [(ROOT / "frontend" / "index.html").read_text(encoding="utf-8")]
    for html in blocks:
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            data = json.loads(raw)
            assert data["@context"] == "https://schema.org"
            assert data["@graph"], "empty @graph"
