# IFC Export Setting (Revit → BIM Guard)

This folder holds the two files served from the app's **IFC Export Setting**
page for preparing a Revit model for a BIM Guard audit (doors, windows,
stairs, railings).

## Files

- **`IFC_Export_Setting.json`** — a Revit IFC export setup profile. Import it
  once per project via Revit: **File → Export → IFC → Modify Setup... →
  Load existing setup...**
- **`BIMGuard_UserDefinedPsets.txt`** — **optional.** A companion property
  mapping file for the handful of fields BIM Guard checks that have no
  standard IFC property (door `ClearWidth`; window
  `ClearOpeningArea/Height/Width`; stair flight `Width`, `FlightHeight`,
  winder angles; railing `Height`/`HandrailHeight`; slab
  `HeadroomClearance`). It only takes effect if you've also created matching
  Shared Parameters on the Door, Window, Stair, Stair Component and Railing
  categories in the Revit project — the mapping file just tells the exporter
  which Revit parameter feeds which IFC property, it doesn't create the
  parameters for you. Skip it if you're not maintaining those Shared
  Parameters: the rules that read those specific fields will resolve as
  `MISSING_DATA` instead of failing, and nothing else is affected.

## How to use it

1. Download `IFC_Export_Setting.json`. Download
   `BIMGuard_UserDefinedPsets.txt` too only if you're using the optional
   Shared Parameters mapping above.
2. Load `IFC_Export_Setting.json` as the active setup in Revit's Modify
   Setup dialog. If you downloaded the `.txt` file, also go to
   **Property Sets → User-defined Property Sets** and point the file path
   at wherever you saved it — the JSON ships with that path hard-coded to
   the machine it was authored on
   (`C:\Users\Malak\OneDrive\Desktop\BIMGuard_UserDefinedPsets.txt`), which
   won't exist on yours. If you're skipping the `.txt` file, un-tick
   **Export user-defined property sets** in that same panel rather than
   leaving it pointed at a path that doesn't resolve.
3. In the Modify Setup dialog, set **Phase to export** to the phase you're
   auditing (see below — this can't be baked into the shared JSON).
4. Export to IFC as normal.

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

## Check the exported file is IFC4

Open the exported `.ifc` file in a text editor. Near the top it should read:

```
FILE_SCHEMA(('IFC4'));
```

If it says `IFC2X3` instead, Revit exported with a different setup. In the
IFC export dialog, pick this profile in the **Current setup** dropdown and
export again.

## Phase to export: pick it per-project, it isn't baked in

The profile ships with **`ActivePhaseId: -1`** ("Default Phase"), not a
specific phase — Revit phases are project-specific, so there's no value that
would be safe to hard-code into a shared setup file. Before every export,
confirm the **Phase to export** dropdown in Revit's Modify Setup dialog is
set to the phase you're actually auditing, not whatever the model happened
to default to. Exporting the wrong phase won't error or show `MISSING_DATA`
— it just silently audits a different set of elements than the one you
meant to check.

## Material Property Sets

**Property Sets → Export material property sets** should stay ticked. This
checkbox controls exporting material properties such as material **density**
(`Pset_MaterialCommon` / `IfcMaterialProperties.MassDensity`) and fire rating
attributes associated via `IfcRelAssociatesMaterial`. Leaving this enabled
ensures architectural evaluations and mass/specification checks have access to
complete material definitions.

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
