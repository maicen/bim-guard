# PD-001 Proximity / Drip-Path — source manifest

Capture run for the seventh piping engine, **PD-001 Proximity / Drip-Path** (corrosion of a
pipe caused by a nearby but unjoined pipe of another material). Every file listed here was
fetched with `scripts/fetch_standards.py ... --corrosion` on 2026-09-08 and lands in
`docs/scraped_standards/`, which `scripts/compile_for_notebooklm.py` routes to the Corrosion
NotebookLM corpus on the `corrosion` substring in the filename.

Notes in the last column are the page's own first heading, description or first paragraph,
quoted or lightly trimmed — not a description written for this manifest.

## Status column

`fetch_standards.py` refuses any response Firecrawl reports outside 2xx, and refuses any page
whose title reads as an error, but it does not write the numeric status into the provenance
header. Every saved file below therefore passed that check; the code itself is not recoverable
from the artefact, so it is recorded as `2xx (accepted)` rather than invented.

## Sources

| # | Stem | URL | Status | Bytes | Tables (`\|---\|`) | Note (from the page) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `corrosion_pd001_aga_contact_other_metals` | https://galvanizeit.org/hot-dip-galvanizing/how-long-does-hdg-last/in-contact-with-other-metals | 2xx (accepted) | 9,538 | no | "In Contact with Other Metals" — "The extent of the corrosion depends upon the position of the other metal relative to zinc in the galvanic series, and to a lesser degree on the relative size of the surface area of the two metals in contact." |
| 2 | `corrosion_pd001_et_heat_loss_insulation` | https://www.engineeringtoolbox.com/heat-loss-pipes-tanks-t_15.html | 2xx (accepted) | 10,956 | yes | "Heat Loss and Insulation" — "Heat loss from pipes, tubes and tanks - with and without insulation. Use of materials lke foam, fiberglass, mineral wool and more." |
| 3 | `corrosion_pd001_et_expansion_coefficients` | https://www.engineeringtoolbox.com/pipes-temperature-expansion-coefficients-d_48.html | 2xx (accepted) | 5,204 | yes | "Piping Materials - Temperature Expansion Coefficients" — "Temperature expansion coefficients for materials used in pipes and tubes like aluminum, carbon steel, cast iron, PVC, HDPE and more." |
| 4 | `corrosion_pd001_et_expansion_formula` | https://www.engineeringtoolbox.com/thermal-expansion-pipes-d_283.html | 2xx (accepted) | 5,873 | yes | "Pipes and Tubes - Temperature Expansion" — "Pipes expands when heated and contracts when cooled and the expansion can be expressed with the expansion equation." |
| 5 | `corrosion_pd001_et_expansion_by_material` | https://www.engineeringtoolbox.com/thermal-expansion-pipes-d_931.html | 2xx (accepted) | 5,668 | yes | "Copper, Ductile Iron, Carbon Steel, Stainless Steel and Aluminum Piping Materials - Temperature Expansion" — "Thermal expansion of typical piping materials." |
| 6 | `corrosion_pd001_et_corrosion_glossary` | https://www.engineeringtoolbox.com/corrosions-terms-d_566.html | 2xx (accepted) | 2,935 | yes (layout only) | "Glossary of Corrosion Related Terms" — "Commonly used terms related corrosion." |
| 7 | `corrosion_pd001_nzbc_g12_landing` | https://www.building.govt.nz/building-code-compliance/g-services-and-facilities/g12-water-supplies | 2xx (accepted) | 11,181 | no | "G12 Water supplies" — "Requires the safe supply, storage, reticulation and delivery of hot and cold water." |
| 8 | `corrosion_pd001_nzbc_g12as3_codehub` | https://codehub.building.govt.nz/resources/g12as3-first-edition-inc-in-amd-13 | 2xx (accepted) | 12,306 | no | "Acceptable Solution G12/AS3: Water Supplies" — "The new Acceptable Solution G12/AS3 is the Standard AS/NZS 3500, parts 1 and 4, as modified by Paragraphs 1.0.3 and 1.0.4, for the design and installation of cold and heated water supply systems." |
| 9 | `corrosion_pd001_nzbc_g12as1_amd14` | https://www.building.govt.nz/assets/Uploads/building-code-compliance/g-services-and-facilities/g12-water-supplies/asvm/g12-water-supplies-3rd-edition-amendment-14.pdf | **GAP** — bot-blocked | — | — | Link found in the scraped G12 landing page (line 70): "3rd edition amendment 14 \[PDF 5.5 MB\] Effective on 2 November 2024". Not retrievable — see MISMATCH 1. |
| 10 | `corrosion_pd001_cda_copper_tube_handbook` | https://copper.org/markets-and-applications/building-construction/strengthening-plumbing-systems/copper-tube-handbook/ | 2xx (accepted) | 5,871 | no | "Copper Tube Handbook" — "Today, nearly 5,000 years after Cheops, copper developments continue as the industry pioneers broader uses for copper tube in engineered plumbing systems for new and retrofitted residential, industrial and commercial installations." |
| 11 | `corrosion_pd001_nickel_institute_scc_316` | https://nickelinstitute.org/en/download/?mediaUrl=%2Fmedia%2F1662%2Fcorrosionresistanceoftheausteniticchromium_nickelstainlesssteelsinchemicalenvironments_2828_.pdf | 2xx (accepted) | 2,237 | no | "Download" — "To download **corrosionresistanceoftheausteniticchromium_nickelstainlesssteelsinchemicalenvironments_2828_**, please complete the form below." |
| 12 | AS/NZS 3500.1 | https://www.standards.govt.nz/ (MBIE-sponsored download) | **GAP** — login | — | — | Known unscriptable; recorded for Shane, not attempted. Named as the substance of G12/AS3 by source 8. |
| 13 | CIBSE Guide G | — | **GAP** — paywalled | — | — | Known unscriptable; recorded for Shane, not attempted. |
| 14 | SEMI F-series | — | **GAP** — paywalled | — | — | Known unscriptable; recorded for Shane, not attempted. |

**Attempted 11 · saved 10 · GAP 4** (one attempted and failed, three not attempted).

## MISMATCH log

Reported, not repaired.

1. **G12/AS1 amendment 14 PDF is not fetchable by script.** The amendment-14 link *was* found in
   the scraped landing page, so the amendment-12 fallback condition never triggered — but
   `--local-pdf` failed with `did not return a PDF (magic bytes b'<html')`. A direct `curl` shows
   both the amd-14 URL and the amd-12 fallback URL return HTTP 200 with `content_type: text/html`
   and a 212-byte Imperva/Incapsula bot-protection stub (`<script src="/_Incapsula_Resource?...">`).
   The document is not paywalled — it is bot-blocked. No amendment of G12/AS1 was saved. It will
   need to be downloaded by hand in a browser and passed to a local ingest, or fetched from a
   client the site accepts.
2. **`docs/scraped_standards/*` is gitignored** (`.gitignore:90`, "transient RAG retrieval artifacts,
   regenerable"). The `corrosion_pd001_*` files and this manifest were therefore staged with
   `git add -f`, following the precedent of the two scraped files already tracked
   (`corrosion_mil_std_889_galvanic.md`, `seismic_fema_e74_official.md`). `.gitignore` was not edited.
3. **Source 8 is a superseded resource.** The CodeHub page states "This resource is no longer current"
   and points to *G12/AS3 (Amd 14)* at https://codehub.building.govt.nz/resources/g12as3-amd-14.
   The URL as specified was fetched unchanged.
4. **Source 6 carries no glossary.** The scraped body of the Engineering ToolBox corrosion-terms page
   contains no terms — only the sentence "Commonly used terms related corrosion." and an outbound
   link to `http://www.hghouston.com/a.html`. The `|---|` tables it does contain are site chrome
   (search box, unit converter), not data.
5. **Source 2 is a category index, not a technical page.** It is a list of links to child articles
   (bare and insulated pipe heat loss, insulation thickness, k-values). No condensation, drip or
   insulation-contact mechanism text is present in the scraped body.
6. **Source 10 is the handbook landing page, not the handbook.** The top search hit's domain matched
   `copper.org` so it was saved per the rule, but the body is a chapter index plus cookie markup.
   Its "Download the PDF" target (`https://copper.org/resource-library/a4015-copper-tube-handbook/`)
   returns `text/html`, not a PDF, so the "re-fetch a copper.org PDF link with `--local-pdf`" rule
   did not trigger. No copper-tube corrosion or clearance text was captured.
7. **This manifest itself routes to `shared`, not `corrosion`.** `compile_for_notebooklm.py --list`
   confirms all ten `corrosion_pd001_*.md` files route to `corrosion` via
   `docs/scraped_standards/*corrosion*`, and none route elsewhere. But `pd001_sources.md` has no
   `corrosion` substring in its name, so it falls to `<default>` and is appended to *both* corpora;
   `docs/planning/pd001_mechanism_table_draft.md` does the same. The filenames were kept as
   specified. Renaming the manifest to `corrosion_pd001_sources.md` would route it to the Corrosion
   corpus only, if that is what is wanted.
8. **Source 11 is an email-gated download form.** The top search hit's domain matched
   `nickelinstitute.org` so it was saved per the rule, but the body is the download gate
   ("please complete the form below") for
   *Corrosion Resistance of the Austenitic Chromium-Nickel Stainless Steels in Chemical Environments*,
   not the publication. No stress-corrosion-cracking content was captured.

## Consequence for the mechanism table

Of the ten saved files, exactly one — source 1, the AGA page — contains dissimilar-metal
corrosion mechanism text. Every row in `docs/planning/pd001_mechanism_table_draft.md` is
therefore cited to that single file. Sources 3, 4 and 5 supply expansion data only; sources 2,
6, 7, 8, 10 and 11 supply no citable mechanism passage at all.
