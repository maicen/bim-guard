# Scraped standards

Markdown captured from public standards pages by `fetch_standards.py`
(Firecrawl `scrape` endpoint). Filenames carry the corpus category so
`compile_for_notebooklm.py` routes each file to the right NotebookLM
workspace: `*seismic*` -> Seismic, `*corrosion*` / `*iso*` -> Corrosion.

    python scripts/fetch_standards.py <url> <output_stem> --seismic|--corrosion
