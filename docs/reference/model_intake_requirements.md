# Exporting an IFC model for a piping corrosion audit

**For whoever produces the IFC file.** This is what the model needs to carry for the audit to
return findings rather than "not enough data". Nothing here asks you to change the design — only
what the export writes out.

A machine-readable version of everything below is the IDS file
[`data/ids/bimguard_piping_intake.ids`](../../data/ids/bimguard_piping_intake.ids)
(buildingSMART IDS 1.0). Most checkers and several authoring tools can validate a model against
it directly.

**You can check your own model before sending it:**

```bash
uv run scripts/check_model_intake.py their_model.ifc
```

It prints how many elements carry each item and what the audit will be able to say about them.
It always exits 0 — it is a report, not a gate, and a model that fails items is still worth
sending.

**What this checker cannot see.** Two things it reports are narrower than what the audit actually
reads, so read a failure on either as "worth checking", not as "missing". First, an IDS rule can
name only one property set, and the names cannot be OR-ed together: a property written under a
differently named set reads here as missing even though the audit will find it, because the audit
matches on the property name and ignores the set. Second, port connectivity cannot be expressed in
IDS at all, so the check that looks for dissimilar metals meeting at a junction has an input this
report cannot audit — connectivity has to be confirmed by opening the model.

---

## 1. Which entities to export

Export pipework as **distribution flow elements**, not as generic geometry:

`IfcPipeSegment`, `IfcPipeFitting`, `IfcDuctSegment`, `IfcDuctFitting`, `IfcValve`, `IfcPump`,
`IfcFilter`, `IfcTank`, `IfcHeatExchanger`, `IfcAirTerminal`, and the generic
`IfcFlowSegment` / `IfcFlowFitting` / `IfcFlowController` / `IfcFlowMovingDevice` /
`IfcFlowTerminal` / `IfcFlowStorageDevice` / `IfcFlowTreatmentDevice` / `IfcDistributionElement`.

Anything exported as a proxy, a generic model element or pure geometry is not read at all. It is
not reported as a problem — it is simply invisible.

**IFC2x3 and IFC4 are both fine.** Send whichever your tool produces natively; there is no need to
upgrade a model for this.

## 2. What each element must carry

Every real MEP model received so far has carried element names (100%), system assignments (99.9%)
and storeys (100%) but **0% material** — measured across the 8,539 piping elements of
`west_riverside_hospital_plumb_ifc4.ifc` — and material is the one property without which no
corrosion check can reach a verdict at all.

### Required

| Item | What it is | If it is missing |
| --- | --- | --- |
| **Material** | A material associated with the element (or its type), named in recognisable text — `Copper`, `Copper - Type L`, `ASTM B88`, `316L`, `Galvanised steel`, `PVC`, `Ductile iron`. | This is the single biggest cause of an empty report. Without it the corrosion checks return "undetermined" for that element instead of a verdict. A material called `Default`, `Material 3`, `N/A` or a bare vendor part code resolves to nothing and counts as missing. |
| **System assignment** | The element assigned to a named system or distribution system — `Domestic Hot Water`, `Chilled Water Return`, `Fire Sprinkler`, `Medical Gas — Oxygen`. | The audit cannot tell what is inside the pipe, which removes one whole axis of the assessment. An element with neither a material nor a system cannot be recovered at all. |
| **Name** | A non-empty element name. | Used as the fallback for classifying the system where no system assignment exists, and for identifying fittings and joints. |

### Worth including — each one adds a check that is otherwise skipped

| Item | Property names accepted (any one) | What it buys |
| --- | --- | --- |
| Operating temperature (°C) | `OperatingTemperature`, `WorkingTemperature`, `FluidTemperature`, `DesignTemperature`, `MediumTemperature` | Temperature drives corrosion rate, and around 60 °C the behaviour of galvanised steel changes character rather than merely degree. Without a stated value the audit falls back to a design convention for the service and says so. |
| Flow velocity (m/s) | `FlowVelocity`, `Velocity`, `FluidVelocity`, `DesignFlowVelocity`, `AverageVelocity` | Low and stagnant flow is what drives the microbiological check. **Do not write 0 to mean "unknown"** — 0 m/s is read as genuinely stagnant, which is the worst case. Leave the property out instead. |
| Dead-leg length (m) | `DeadLegLength`, `StagnationLength`, `DeadLegLengthM` | Identifies stagnant branches. `0` is meaningful here — it states the run is through-flow. |
| Dead-leg flag | `IsDeadLeg`, `Stagnant`, `IsStagnant` (boolean) | For tools that can flag a dead leg but not measure one. Prefer the length where you have it. |
| Nominal bore (mm) | `NominalDiameter`, `NominalDiameterMM`, `DN`, `Size` | Dead legs are judged on length against bore, so a diameter sharpens that. **Note:** `InnerDiameter` / `OuterDiameter` alone are *not* read for this — one of the four names above is needed. |
| Second material at a junction | `SecondaryMaterial`, `SupportMaterial`, `BracketMaterial`, `FixingMaterial` | The bracket, hanger, support or fixing the pipe touches. IFC has no standard way to say this and it cannot be derived from the pipe's own material, so a bimetallic junction is invisible unless the model declares it. |
| Environment class | `EnvironmentClass`, `EnvironmentalClass`, `CorrosivityCategory`, `AtmosphericEnvironment` | The atmosphere around the pipe, not the fluid in it. Accepts `T0`–`T5`, or a code with a descriptor such as `T3 chloride`. Without it the audit infers from room and level names and otherwise assumes a mild indoor atmosphere — flagged as an assumption. |

**Property set names do not matter.** The audit reads the property *name* and ignores which set it
sits in. The IDS names one set per item only because the IDS format requires one; if your exporter
puts these somewhere else, they will still be read. If you have no preference, use
`Pset_BimGuardHydraulics` for velocity and dead-leg values, `Pset_BimGuardCouple` for the second
material, and the standard `Pset_PipeSegmentOccurrence` for temperature.

### Also useful

- **Storey and space containment.** Put elements in a named `IfcBuildingStorey`, and in a named
  `IfcSpace` where you have spaces. Room names carry most of the environmental signal — *pool*,
  *plant*, *basement*, *external*, *roof*, *kitchen*, *shower* all resolve. Most MEP discipline
  models carry no spaces at all, which is why this is worth doing.
- **Ports and connection relationships.** Where two runs of different metal meet, the audit needs
  to know they are connected. Revit, ARCHICAD and Tekla can all export connectivity, but it is
  frequently lost or partial in a coordination export configured for geometry only. Where
  connectivity cannot be established, the audit falls back to geometric proximity and says so.

## 3. Where these live in common tools

| Tool | Notes |
| --- | --- |
| **Revit** | Values that are not standard IFC properties go in as **shared parameters**, exported through a **user-defined property sets file** in the IFC export setup. Also turn **Export Base Quantities** on. The material alias list already covers a wide range of Revit and manufacturer naming conventions, so ordinary Revit material names generally resolve without renaming. |
| **ARCHICAD** | Confirmed only for connectivity: ARCHICAD can export ports and connection relationships. For property mapping, **confirm in your exporter** — map the property names above through your IFC translator's property mapping. |
| **AutoCAD Plant 3D** | **Confirm in your exporter.** The property names above are what matters; where your line list holds them is your choice. |
| **AVEVA E3D / PDMS** | **Confirm in your exporter.** |
| **Bentley OpenPlant** | **Confirm in your exporter.** |

For any tool: the names in the tables above are the whole contract. If your export writes those
names with sensible values, the audit will read them.

## 4. Federated models — one file per discipline

For the **seismic and clearance** side of the audit, send **one IFC per discipline** (mechanical,
plumbing, structural, architectural) rather than a single merged file, and name each file for its
discipline. Clearance is a question about the building, not about one file: the brace is in the
mechanical model and the beam it has to clear is in the structural one. A single-discipline model
can only find the clashes that discipline has with itself.

The corrosion side is the opposite and is assessed per model, so no merging is needed there.

Each element also needs readable geometry — an element with no usable shape representation is
reported as a data-quality item rather than assessed.

## 5. File size

The application accepts files up to 512 MB, but the project's Supabase storage rejects anything
over roughly 50 MB, so 50 MB is the effective limit; split large models by discipline or system.

## 6. Confidentiality

Your model is **held locally in a private repository**. It is **never committed to the application
repository**, and it can be **anonymised on request** — project and element naming stripped before
it is used for anything beyond your own audit. If a model is commercially sensitive, say so when
you send it and it will be handled that way by default.

---

*Questions about a specific export, or a property you cannot write from your tool: send the model
anyway with a note about what is missing. A model with gaps still produces a useful report — it
simply says "undetermined" where the data was not there, and never guesses.*
