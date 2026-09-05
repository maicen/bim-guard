# IFC Export Setting (Revit → BIM Guard)

This folder holds the two files served from the app's **IFC Export Setting**
page for preparing a Revit model for a BIM Guard audit (doors, windows,
stairs, railings).

## Files

- **`IFC_Export_Setting.json`** — a Revit IFC export setup profile. Import it
  once per project via Revit: **File → Export → IFC → Modify Setup... →
  Load existing setup...**
- **`BIMGuard_UserDefinedPsets.txt`** — a companion property mapping file for
  the handful of fields BIM Guard checks that have no standard IFC property
  (door `ClearWidth`; window `ClearOpeningArea/Height/Width`; stair flight
  `Width`, `FlightHeight`, winder angles; railing `Height`/`HandrailHeight`;
  slab `HeadroomClearance`). It only takes effect if you've also created
  matching Shared Parameters on the Door, Window, Stair, Stair Component and
  Railing categories in the Revit project — the mapping file just tells the
  exporter which Revit parameter feeds which IFC property, it doesn't create
  the parameters for you.

## How to use it

1. Download both files.
2. In Revit's Modify Setup dialog, under **Property Sets → User-defined
   Property Sets**, point the file path at wherever you saved
   `BIMGuard_UserDefinedPsets.txt` on your machine, then save/load
   `IFC_Export_Setting.json` as the active setup.
3. Export to IFC as normal.

Before relying on the `.txt` mapping, cross-check its header syntax against
the sample template shipped with your installed Revit's IFC exporter
(`...\ApplicationPlugins\IFC 20xx.bundle\...`) — Autodesk's own
documentation of this file format is thin, so it's worth a quick sanity
check the first time.

## IFC version: make sure it's Design Transfer View, not Reference View

The profile ships set to **IFC4 Design Transfer View [IFC4DTV]**. This
matters: IFC4 has two common export flavors, and only one of them keeps the
property/quantity data BIM Guard reads.

- **Design Transfer View (DTV)** — full property sets and quantities.
  **This is what BIM Guard needs.**
- **Reference View (RV)** — a leaner, coordination/viewing-only flavor that
  is allowed to drop property sets and quantities that aren't needed just to
  see the geometry.

If you ever see `MISSING_DATA` on rules that should resolve, the first thing
to check is the **IFC Version** dropdown at the top of Revit's Modify Setup
dialog — confirm it reads "IFC4 Design Transfer View [IFC4DTV]" and not
"IFC4 Reference View [IFC4RV]". If it's on Reference View, switch it to
Design Transfer View and re-save the setup (this rewrites the setting
correctly from Revit's own UI, which is safer than hand-editing the number
in the JSON).

## Linked Revit files are NOT exported by default

This profile only exports the **host file** — the one Revit file you run
Export to IFC from. If any doors, windows, or stairs live in a separate,
linked Revit model (e.g. a linked architectural or shell-and-core model),
they are silently left out of the IFC file entirely, not exported with
missing data. There's no warning for this; the elements just won't be there.

**To include them:** this is a per-file decision, not something baked into
the shared JSON profile (Revit's handling of linked files changed to a
multi-option setting in the 2024 exporter, so a hard-coded value here isn't
safe across Revit versions). For any specific file that has linked-in
elements, open Revit's own Modify Setup dialog before exporting that file
and, on the Links-related tab, change the linked-file handling from "Don't
export links" to the option that merges linked models into the same IFC
file (labelled along the lines of "export linked files as part of the host
file" / "same IfcProject", not "export as separate files" — that produces
multiple .ifc files instead of one combined file BIM Guard can read as a
single model).
