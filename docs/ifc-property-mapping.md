# IFC Property Mapping Reference

How BIM-Guard rule `property_name` values map to standard IFC property sets and what
Revit actually exports. Use this to diagnose `MISSING_DATA` results.

**Status key**
- ✅ Match — property name identical, data flows automatically
- ⚠️ Mismatch — property exists in IFC but under a different name
- ❌ Missing — no standard IFC property exists; needs custom Shared Parameter

---

## Table 1 — Rule → Standard IFC → How to Fix

*Starting from a BIM-Guard rule that returns `MISSING_DATA`, find the standard IFC
equivalent and what action closes the gap.*

| IFC Class | Rule `property_name` | Standard IFC Property | Standard Pset / Source | Revit Exports It? | How to Fix |
|---|---|---|---|---|---|
| IfcStairFlight | `Width` | *(none standard)* | — | ❌ Missing | Add Revit Shared Param named `Width` mapped to a custom Pset via user-defined Psets file |
| IfcStairFlight | `RiserHeight` | `RiserHeight` | Pset_StairFlightCommon | ✅ Yes | Nothing — should appear automatically |
| IfcStairFlight | `TreadDepth` | `TreadLength` | Pset_StairFlightCommon | ⚠️ Name mismatch | Update rule `property_name` → `TreadLength` |
| IfcStairFlight | `HeadroomClearance` | `RequiredHeadroom` | Pset_StairFlightCommon | ⚠️ Name mismatch | Update rule `property_name` → `RequiredHeadroom` |
| IfcStairFlight | `FlightHeight` | *(none standard)* | — | ❌ Missing | Add Shared Param `FlightHeight` mapped to custom Pset |
| IfcStairFlight | `WinderTurnAngle` | *(none standard)* | — | ❌ Missing | Add Shared Param `WinderTurnAngle` |
| IfcStairFlight | `IndividualWinderAngle` | *(none standard)* | — | ❌ Missing | Add Shared Param `IndividualWinderAngle` |
| IfcStairFlight | `WinderSetSeparation` | *(none standard)* | — | ❌ Missing | Add Shared Param `WinderSetSeparation` |
| IfcStairFlight | `Name` | `Name` | Direct attribute | ✅ Yes | Nothing needed |
| IfcDoor | `ClearWidth` | `OverallWidth` *(closest)* | Direct attribute | ⚠️ Name mismatch | Update rule → `OverallWidth` (note: overall ≠ clear, but best available) OR add Shared Param `ClearWidth` |
| IfcDoor | `Height` | `Height` / `OverallHeight` | Qto_DoorBaseQuantities / Direct | ✅ Partial | Ensure **Export base quantities** is on; or update rule → `OverallHeight` |
| IfcDoor | `Width` | `Width` / `OverallWidth` | Qto_DoorBaseQuantities / Direct | ✅ Partial | Ensure **Export base quantities** is on |
| IfcWindow | `ClearOpeningArea` | *(none standard)* | — | ❌ Missing | Add Shared Param `ClearOpeningArea` OR update rule → `Area` (Qto_WindowBaseQuantities) |
| IfcWindow | `ClearOpeningHeight` | `OverallHeight` *(closest)* | Direct attribute | ⚠️ Name mismatch | Add Shared Param `ClearOpeningHeight` OR update rule → `OverallHeight` |
| IfcWindow | `ClearOpeningWidth` | `OverallWidth` *(closest)* | Direct attribute | ⚠️ Name mismatch | Add Shared Param `ClearOpeningWidth` OR update rule → `OverallWidth` |
| IfcRailing | `Height` | *(none standard)* | — | ❌ Missing | Add Shared Param `Height` mapped to custom Pset `Pset_BIMGuardRailing` |
| IfcRailing | `HandrailHeight` | *(none standard)* | — | ❌ Missing | Add Shared Param `HandrailHeight` mapped to custom Pset |
| IfcSlab | `HeadroomClearance` | *(none standard)* | — | ❌ Missing | Add Shared Param `HeadroomClearance` mapped to custom Pset |
| IfcSlab | `Width` | `Width` | Qto_SlabBaseQuantities | ⚠️ Partial | Ensure **Export base quantities** is on |
| IfcSlab | `MaxSlope` | `PitchAngle` *(closest)* | Pset_SlabCommon | ⚠️ Name mismatch | Update rule `property_name` → `PitchAngle` (same concept, different name) |
| IfcWall | `FireRating` | `FireRating` | Pset_WallCommon | ✅ Yes | Nothing — fill the Fire Rating parameter in Revit |
| IfcWall | `LimitingDistance` | *(none standard)* | — | ❌ Missing | Pre-calculate in Revit and store as Shared Param `LimitingDistance` |
| IfcRamp | `Slope` | `RequiredSlope` | Pset_RampCommon | ⚠️ Name mismatch | Update rule `property_name` → `RequiredSlope` |
| IfcRamp | `Width` | *(none in Pset)* | Qto_RampBaseQuantities *(may vary)* | ❌ Likely missing | Add Shared Param `Width` mapped to custom Pset |
| IfcSpace | `Width` | *(none standard)* | — | ❌ Missing | Add Shared Param `Width` |
| IfcSpace | `Height` | `Height` | Qto_SpaceBaseQuantities | ✅ Partial | Ensure **Export base quantities** is on |
| IfcSpace | `LongName` | `LongName` | Direct attribute | ✅ Yes | Nothing — fill the room name in Revit |

---

## Table 2 — Standard Pset → Rule → How to Fix

*Starting from what Revit actually exports, find which rule uses it (or doesn't) and
what action maps it correctly.*

| Standard Pset / Source | IFC Class | Standard Property Name | Rule Uses | Status | How to Fix |
|---|---|---|---|---|---|
| Pset_StairFlightCommon | IfcStairFlight | `RiserHeight` | `RiserHeight` | ✅ Match | None |
| Pset_StairFlightCommon | IfcStairFlight | `TreadLength` | `TreadDepth` | ⚠️ Mismatch | Update rule `property_name` → `TreadLength` |
| Pset_StairFlightCommon | IfcStairFlight | `RequiredHeadroom` | `HeadroomClearance` | ⚠️ Mismatch | Update rule `property_name` → `RequiredHeadroom` |
| Pset_StairFlightCommon | IfcStairFlight | `NumberOfRiser` | *(not used)* | — | Consider adding a rule to verify riser count |
| Pset_StairFlightCommon | IfcStairFlight | `NumberOfTreads` | *(not used)* | — | Consider adding a rule |
| Pset_StairFlightCommon | IfcStairFlight | `NosingLength` | *(not used)* | — | — |
| Pset_DoorCommon | IfcDoor | `FireRating` | *(not used)* | — | Consider adding a fire door rule |
| Pset_DoorCommon | IfcDoor | `HandicapAccessible` | *(not used)* | — | — |
| Pset_DoorCommon | IfcDoor | `IsExternal` | *(not used)* | — | — |
| Qto_DoorBaseQuantities | IfcDoor | `Width` | `Width` | ✅ Match via Qto | Ensure **Export base quantities** is on |
| Qto_DoorBaseQuantities | IfcDoor | `Height` | `Height` | ✅ Match via Qto | Ensure **Export base quantities** is on |
| Direct — IfcDoor | IfcDoor | `OverallWidth` | `ClearWidth` | ⚠️ Mismatch | Update rule → `OverallWidth` |
| Direct — IfcDoor | IfcDoor | `OverallHeight` | `Height` | ⚠️ Partial | Qto `Height` is preferred; also available as direct `OverallHeight` |
| Pset_WindowCommon | IfcWindow | `FireRating` | *(not used)* | — | — |
| Pset_WindowCommon | IfcWindow | `GlazingAreaFraction` | *(not used)* | — | — |
| Pset_WindowCommon | IfcWindow | `ThermalTransmittance` | *(not used)* | — | — |
| Direct — IfcWindow | IfcWindow | `OverallWidth` | `ClearOpeningWidth` | ⚠️ Mismatch | Update rule → `OverallWidth` (overall ≠ clear) OR add Shared Param |
| Direct — IfcWindow | IfcWindow | `OverallHeight` | `ClearOpeningHeight` | ⚠️ Mismatch | Update rule → `OverallHeight` OR add Shared Param |
| Qto_WindowBaseQuantities | IfcWindow | `Area` | `ClearOpeningArea` | ⚠️ Mismatch | Update rule → `Area` (gross area, not clear opening) OR add Shared Param |
| Pset_WallCommon | IfcWall | `FireRating` | `FireRating` | ✅ Match | None — fill Fire Rating in Revit |
| Pset_WallCommon | IfcWall | `IsLoadBearing` | *(not used)* | — | — |
| Pset_WallCommon | IfcWall | `IsExternal` | *(not used)* | — | — |
| Pset_WallCommon | IfcWall | `ThermalTransmittance` | *(not used)* | — | — |
| Pset_RailingCommon | IfcRailing | `Reference` | *(not used)* | — | — |
| Pset_RailingCommon | IfcRailing | `IsExternal` | *(not used)* | — | — |
| *(no standard)* | IfcRailing | — | `Height` | ❌ No standard | Add Shared Param `Height` → custom Pset `Pset_BIMGuardRailing` |
| *(no standard)* | IfcRailing | — | `HandrailHeight` | ❌ No standard | Add Shared Param `HandrailHeight` → custom Pset |
| Pset_RampCommon | IfcRamp | `RequiredSlope` | `Slope` | ⚠️ Mismatch | Update rule `property_name` → `RequiredSlope` |
| Pset_RampCommon | IfcRamp | `RequiredHeadroom` | *(not used)* | — | — |
| Pset_SlabCommon | IfcSlab | `PitchAngle` | `MaxSlope` | ⚠️ Mismatch | Update rule `property_name` → `PitchAngle` |
| Pset_SlabCommon | IfcSlab | `FireRating` | *(not used)* | — | — |
| Qto_SlabBaseQuantities | IfcSlab | `Width` | `Width` | ✅ Match via Qto | Ensure **Export base quantities** is on |
| Qto_SlabBaseQuantities | IfcSlab | `Depth` | *(not used)* | — | — |
| Pset_SpaceCommon | IfcSpace | `GrossPlannedArea` | *(not used)* | — | — |
| Pset_SpaceCommon | IfcSpace | `NetPlannedArea` | *(not used)* | — | — |
| Qto_SpaceBaseQuantities | IfcSpace | `Height` | `Height` | ✅ Match via Qto | Ensure **Export base quantities** is on |
| Qto_SpaceBaseQuantities | IfcSpace | `GrossFloorArea` | *(not used)* | — | Consider adding a min floor area rule |
| Direct — IfcSpace | IfcSpace | `LongName` | `LongName` | ✅ Match | None |

---

## Quick Fix Summary

### Fix in rules.db (rename `property_name` in the rule — no Revit changes needed)

| Change | Rule ref |
|---|---|
| `TreadDepth` → `TreadLength` | Table 9.8.4.1 |
| `HeadroomClearance` → `RequiredHeadroom` | 9.8.2.2.(3) |
| `ClearWidth` → `OverallWidth` | CODE 9.6.4 |
| `Slope` → `RequiredSlope` | CODE 3.8.3.4 |
| `MaxSlope` → `PitchAngle` | 9.8.6.3 |
| `ClearOpeningHeight` → `OverallHeight` | CODE 9.7.2 |
| `ClearOpeningWidth` → `OverallWidth` | CODE 9.7.2 |
| `ClearOpeningArea` → `Area` | CODE 9.7.2 |

### Fix in Revit (add Shared Parameters → export via user-defined Psets file)

| Shared Param to add | IFC Class | Maps to custom Pset |
|---|---|---|
| `Width` | IfcStairFlight, IfcRamp, IfcSpace | `Pset_BIMGuardStair`, `Pset_BIMGuardRamp`, `Pset_BIMGuardSpace` |
| `Height` | IfcRailing | `Pset_BIMGuardRailing` |
| `HandrailHeight` | IfcRailing | `Pset_BIMGuardRailing` |
| `HeadroomClearance` | IfcSlab | `Pset_BIMGuardSlab` |
| `LimitingDistance` | IfcWall | `Pset_BIMGuardWall` |
| `FlightHeight` | IfcStairFlight | `Pset_BIMGuardStair` |
| `ClearOpeningArea` | IfcWindow | `Pset_BIMGuardWindow` *(if true clear area needed)* |

### Ensure Export Base Quantities is ON in Revit IFC setup

Required for: `IfcDoor.Width`, `IfcDoor.Height`, `IfcWindow.Area`,
`IfcSlab.Width`, `IfcSpace.Height` — all come from `Qto_*` quantity sets.
The BIMGuard IFC4 Export config already has this enabled.

---

## Stair / railing / landing property notes

Aliases now resolved automatically (no rule or Revit change needed) — a rule
authored with any of the left-hand names now also tries the right-hand ones:

| Rule `property_name` | Also tries | IFC Class |
|---|---|---|
| `NosingLength` | `Nosing`, `NosingProjection`, `NosingDepth` | IfcStairFlight, IfcStair |
| `WaistThickness` | `Waist`, `StairWaist` | IfcStairFlight, IfcStair |
| `HandicapAccessible` | `Accessible`, `IsAccessible`, `AccessibleRoute` | IfcStair |
| `HasNonSkidSurface` | `NonSkidSurface`, `SlipResistant`, `SlipResistance`, `AntiSlip` | IfcStair |
| `Headroom` | `RequiredHeadroom`, `HeadroomClearance`, `ClearHeight`, `ClearanceHeight` | IfcStair (reverse of the existing `RequiredHeadroom` alias, for rules that ask using the flight-level name against the stair container) |
| `WalkingLineOffset` | `WalklineOffset`, `WalkLineOffset` | IfcStairFlight, IfcStair |
| `FireExit` | `IsFireExit`, `EmergencyExit` | IfcStair |

Stairs and railings exported as generic `IfcBuildingElementProxy` (bad
export, or an authoring tool that doesn't model a proper `IfcStair`/
`IfcRailing`) are now recovered the same way doors/windows already were —
matched by `Name`/`ObjectType`/`Tag` containing "stair"/"step"/"flight" or
"railing"/"handrail"/"guard"/"balustrade" respectively.

### ⚠️ Landmine: landing clear width vs. `Qto_SlabBaseQuantities.Width`

`Qto_SlabBaseQuantities.Width` means **slab thickness**, on every `IfcSlab`
including a landing (`PredefinedType = LANDING`) — never the landing's clear
walking width. A rule asking for `Width` on a landing will silently get the
slab thickness back, not what it likely wants.

**Do not** author a landing clear-width rule with `property_name: Width`.
Use `property_name: ClearWidth` instead — that name is *not* aliased to
`Width` for this reason, and instead falls through to the geometry-derived
corridor-width calculation (`ifc_geometry.get_corridor_width_mm`), which
computes the landing's actual minimum clear plan dimension from its mesh.
