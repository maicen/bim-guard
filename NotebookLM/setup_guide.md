# BIMGUARD AI — NotebookLM Setup Guide

## Prerequisites

- A Google account (free or Workspace)
- Access to NotebookLM at [notebooklm.google.com](https://notebooklm.google.com)
- The source URL list from `sources.md` in this directory
- The master prompt from `master_prompt.md` in this directory

Estimated setup time: 30–45 minutes

---

## Step 1 — Create a new notebook

1. Go to [notebooklm.google.com](https://notebooklm.google.com) and sign in with your Google account
2. Click **New notebook** (top left or centre of the screen)
3. Name the notebook: `BIMGUARD AI — Technical Reference Library`
4. Click **Create**

---

## Step 2 — Load the sources

This is the most important step. The notebook's accuracy depends entirely on having all 36 sources loaded correctly.

1. In your new notebook, click **Add source** on the left panel
2. Select **Website** from the source type options
3. Paste the first URL from `sources.md` and click **Add**
4. Wait for NotebookLM to confirm the source has been indexed (a tick will appear)
5. Repeat for every URL in `sources.md`

**Important notes:**
- Load sources one at a time — do not paste multiple URLs simultaneously
- If a URL fails to load, try refreshing the page and attempting it again
- Some pages may take 30–60 seconds to index — wait for the tick before adding the next one
- If a source consistently fails, note it and try an alternative URL for the same content

**Recommended loading order:**
Load the modules in the order they appear in `sources.md` — spacing sources first, then dimensions, then flanges, then thermal, then galvanic, then IFC schema, then ISO 19650. This order mirrors the BIMGUARD phase sequence and makes it easier to verify coverage.

---

## Step 3 — Verify source coverage

Once all sources are loaded, run the following verification queries to confirm the notebook has indexed the key data correctly. Each should return a specific numerical answer from the sources — if the notebook cannot answer, the relevant source may not have loaded correctly.

**Verification query 1 — spacing formula**
> What is the standard formula for calculating minimum centre-to-centre pipe spacing, and what is the minimum clearance gap between insulation faces?

Expected answer: The formula is C-to-C = OD₁/2 + T_ins1 + 25mm + T_ins2 + OD₂/2. The minimum gap is 25mm.

**Verification query 2 — ASME flange OD**
> What is the outside diameter of an NPS 4 Class 150 weld neck flange in millimetres?

Expected answer: Approximately 229mm (9.00 inches) per ASME B16.5.

**Verification query 3 — galvanic threshold**
> What voltage difference between two metals is considered acceptable in a normal building services environment according to NASA-STD-6012?

Expected answer: 0.25V maximum for a normal environment.

**Verification query 4 — IFC entity**
> What property set contains the outer diameter of a pipe in an IFC 4.3 model?

Expected answer: Pset_PipeSegmentOccurrence, attribute OuterDiameter (or NominalDiameter as fallback).

**Verification query 5 — thermal expansion**
> What is the coefficient of linear thermal expansion for carbon steel in metric units?

Expected answer: Approximately 11.7 × 10⁻⁶ mm/mm/°C (or 12.1 × 10⁻³ mm/m/°C).

If all five queries return correct answers, the notebook is ready for use.

---

## Step 4 — Apply the master prompt

Before beginning any technical queries, configure the notebook's behaviour by pasting the master prompt from `master_prompt.md` as your first message.

The master prompt tells the notebook:
- What role it is playing (BIMGUARD AI Technical Auditor)
- The priority order for resolving conflicts between sources
- The voltage thresholds to apply for galvanic compatibility checks
- The output format requirements (metric and imperial, formula-first)

You only need to paste the master prompt once per session. If you close and reopen the notebook in a new session, paste it again before your first query.

---

## Step 5 — Share the notebook

To share the notebook with your supervisor, examiner, or project group:

1. Click the **Share** icon in the top right of the notebook
2. Select **Anyone with the link can view**
3. Copy the generated link
4. Paste it into the `README.md` file in this directory where indicated

The share link gives view-only access — recipients can read sources and submit queries but cannot modify the notebook or add new sources.

---

## Step 6 — Commit to GitHub

Once the notebook is set up and the share link is added to `README.md`, commit all four files in this directory to your GitHub repository:

```
git add notebooklm/README.md
git add notebooklm/sources.md
git add notebooklm/master_prompt.md
git add notebooklm/setup_guide.md
git commit -m "Add NotebookLM reference library documentation"
git push
```

This gives your repository a complete, reproducible record of the notebook — anyone with the setup guide can rebuild an identical notebook from scratch, satisfying academic reproducibility requirements even though the live notebook itself cannot be exported as a file.

---

## Troubleshooting

**A URL fails to load**
Some pages use JavaScript rendering that NotebookLM cannot index. If this happens, try finding a PDF version of the same content, or copy the key tables from the page into a Google Doc, upload the Doc as a source instead, and note the substitution in your repository.

**The notebook gives a wrong answer**
Check which source it is citing. If it is citing a source from the wrong module (e.g. using a galvanic source to answer a spacing question), rephrase the query to specify the source explicitly: "Using the pipe spacing formula from whatispiping.com, calculate..."

**The notebook cannot find a specific value**
NotebookLM indexes page text but may not extract data from images or embedded PDFs within pages. If a table is image-based, the data will not be available. In this case, manually enter the specific value in your query: "The ASME B16.5 Class 300 NPS 4 flange has an OD of 254mm. Using this value, calculate..."

**Sources become unavailable**
Web pages change. If a source URL becomes a 404, search for an equivalent page on the same domain or an alternative engineering reference site, add the new URL as a replacement source, and update `sources.md` in the repository with the new URL and a note of the change date.

---

## Maintenance

The notebook should be reviewed and updated at the following trigger points:

- When a new version of IFC is published by buildingSMART
- When ASME B16.5 or EN 1092-1 is revised
- When the BIMGUARD rulesets (GC-001, CC-001) are updated with new standards references
- When the project scope expands to cover additional corrosion mechanisms (MIC module, fire compartmentation module)

Each update should be reflected in `sources.md` with the date of change noted against the affected URL.
