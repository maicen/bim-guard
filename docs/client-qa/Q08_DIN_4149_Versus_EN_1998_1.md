# Q08: What is the difference between DIN 4149 and EN 1998-1 seismic codes?

## The Question

> "Our German partner keeps referring to DIN 4149 and our internal standards team
> keeps referring to Eurocode 8. I have been told they are the same thing and
> also that they are different. Which one does BIMGUARD apply, and does it matter
> for a project in Cologne?"

## The Answer

They are not two live codes to choose between. **DIN 4149:2005-04** was the German
standard for buildings in German earthquake zones. It has been **withdrawn** and
replaced by **DIN EN 1998-1:2010-12** (the German adoption of Eurocode 8 Part 1)
together with its National Annex, **DIN EN 1998-1/NA:2011-01**, updated as
**DIN EN 1998-1/NA:2018-10**. DIN 4149 is therefore historical only; a partner
naming it is usually referring to the German seismic zoning and detailing
tradition it carried, which now lives in the National Annex.

**EN 1998-1** is Eurocode 8 Part 1, current edition **EN 1998-1:2004 +A1:2013**.
Its second generation is being published as BS EN 1998-1-1:2024 and
BS EN 1998-1-2:2026. For a Cologne project the governing framework is
EN 1998-1 with the German National Annex, as determined by the structural
engineer of record.

For non-structural MEP restraint specifically, the important point is what these
documents do **not** contain. EN 1998-1 addresses non-structural elements in
**§4.3.5**, which gives the framework for designing their anchorage against
seismic action. **Neither EN 1998-1 nor the German National Annex gives brace
spacing, brace angles or clearance dimensions for pipe, duct or cable-tray
distribution systems.** There is no EN-versus-DIN table of such values to compare.

## What BIMGUARD Applies

BIMGUARD's seismic clearance check (SB-001) runs from one configuration file,
`data/rulesets/sb001_seismic_clearance.json`. Earlier versions of that file and of
this answer described it as a combined profile of an EN 1998-1 edition dated 2020
and a DIN 4149 edition dated 2022, with per-standard values. That was wrong: neither edition exists, and the
per-standard values attributed to them were not taken from either standard. The
file was corrected on 2026-09-13 (schema 1.1.0); the full account is in
`docs/planning/sb001_provenance_2026-09-13.md`. The brace angle was re-sourced to
the Hilti Seismic Manual on 2026-09-16 (schema 1.2.0), and the brace spacing was
re-sourced to the same manual later the same day (schema 1.3.0). The pipe
diameter threshold was checked against the same fabrication pattern at that
point too: it carries it, but no sourced replacement exists, so it is now
labelled unsourced rather than authored.

Every threshold in the file now carries a provenance block with a `status`:

| Threshold | Value | Status | Basis |
| --- | --- | --- | --- |
| Importance factor, hospital / standard | 1.5 / 1.0 | sourced | FEMA E-74 §5.3.1; ASCE/SEI 7-10 §13.1.3 |
| Duct area bracing threshold | 0.557 m² (6 sq ft) | sourced | FEMA E-74 §6.4.6.1 |
| Clearance from structure | 200 mm | authored | No source gives a braced-service clearance |
| Restraint spacing, transverse / longitudinal | 12 m / 24 m | sourced | Hilti Seismic Manual (05/2022), citing NFPA 13 / EN 12845 Annex E |
| Pipe diameter threshold | 63 mm | unsourced | Same fabrication pattern as the former angle and spacing values; no sourced replacement found |
| Brace angle | 30°–60° from horizontal | sourced | Hilti Seismic Manual (05/2022), Annex A: nominal 45° ± 15° on the horizontal level (vendor manual applying EN 1998-1, not a code) |
| Ideal angle / tolerance | 45° / 15° | sourced | The same manual's stated nominal angle and tolerance |
| Seismic-zone, hospital and adjacent-system additions | 0 mm | authored | No source gives a clearance addition |

**Authored** means BIMGUARD screening calibration, not a code value. **Unsourced**
means neither a code value nor a BIMGUARD calibration — an unverified figure kept
only because no sourced replacement is available. SB-001 is a screening tool; it
is not a substitute for design to ASCE/SEI 7-10 §13.6 or EN 1998-1.

## When Each Applies

- **Germany** — EN 1998-1 with DIN EN 1998-1/NA. DIN 4149 is withdrawn.
- **Elsewhere in the EU/EFTA** — EN 1998-1 with the relevant National Annex, which
  sets nationally determined parameters such as hazard values.
- **Projects where DIN 4149 arrives contractually** — raise it with the structural
  engineer; a contract citing a withdrawn standard is worth correcting.
- **Outside the EU** — neither applies statutorily. In the US, ASCE/SEI 7 Chapter 13
  (§13.6 for distribution systems) governs non-structural components, with
  prescriptive guidance in documents such as FEMA E-74 and NFPA 13 for sprinklers.

In every case the MEP bracing dimensions come from a bracing design or a certified
restraint system, not from EN 1998-1 or its National Annexes.

## What the Report Contains

Every seismic finding cites **FEMA E-74 (4th ed., December 2012)** and
**ASCE/SEI 7-10 §13.6**, with the clause text naming the SB-001 screening
calibration and the clearance applied. The configuration's `governing_codes`
block lists EN 1998-1:2004+A1:2013 and DIN EN 1998-1/NA:2018-10 and states that
neither supplies the dimensions. The citation on a finding does not yet say
whether that particular threshold is sourced or authored; read the provenance
block in the configuration for that.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "From EN 1998-1:2004+A1:2013 §4.3.5 and DIN EN 1998-1/NA:2018-10, list every
> provision that applies to the seismic restraint of non-structural mechanical and
> electrical distribution systems. For each, give the clause, the quantity
> governed, and whether a numeric dimension (spacing, clearance, angle, size
> threshold) is stated. State explicitly where no such dimension is given — do not
> infer one and do not supply values from other documents."

**Purpose.** Confirm from the clause text that no MEP dimensional rule exists in
the Eurocode framework, so that any future SB-001 threshold marked `sourced` is
sourced to a document that actually states it.

**Not for.** Deciding which code governs your project. That determination belongs
to the structural engineer of record and the building control authority.

## Export Options

- **BCF 2.1**, **CSV** and **JSON** — identical to the other analyses. Attach the
  configuration file to any submission; its provenance blocks are the audit trail.

## Next Steps for Your Project

1. Get the structural engineer of record to confirm the governing framework in
   writing — for Cologne, EN 1998-1 with DIN EN 1998-1/NA.
2. Treat SB-001 findings as screening. The 200 mm clearance is authored
   calibration and the 12/24 m spacing is sourced to a vendor manual, not a
   code; either way, your bracing designer's calculations govern.
3. If a contract cites DIN 4149, raise it: the standard is withdrawn.
4. Attach the configuration file to any submission, and quote its
   `provenance_summary` statement alongside the findings.
