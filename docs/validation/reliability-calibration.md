# Reliability calibration: grade from names vs coverage in real models

Does the name-based reliability grade match how often real models actually carry the property?
Observed tier = mean per-model coverage: **high >= 90%**, **medium >= 50%**, else **low**.
These thresholds are report parameters, not product rules. Coverage = share of sampled elements
carrying a non-empty value.

## Models surveyed

| Model | Schema | Classes (elements) | Seconds |
|---|---|---|---|
| b7f15bece7ce6f672d2c6c3222d84990_Clinic_Architectural.ifc | IFC2X3 | IfcDoor 254, IfcWindow 58, IfcWall 1080, IfcSlab 3, IfcStair 3, IfcRailing 9, IfcBuildingStorey 4 | 1.5 |
| 93ce691468c34b51955f5239bd33ec23_BUILDING_R4.ifc | IFC4 | IfcDoor 129, IfcWindow 167, IfcWall 1234, IfcSlab 118, IfcStair 4, IfcBuildingStorey 6 | 1.6 |
| de07748de84648558f605a78e586f15a_Pacific Continental Residence Sample IFC 2x3 Coordination View 2.0.ifc | IFC2X3 | IfcDoor 24, IfcWindow 23, IfcWall 104, IfcSlab 25, IfcStair 1, IfcRailing 2, IfcBuildingStorey 3 | 1.3 |
| 7589fcfc61b849f38c286efebd251ec2_Pacific Continental Residence Sample IFC4.3 Reference View ARCH.ifc | IFC4X3 | IfcDoor 24, IfcWindow 23, IfcWall 104, IfcSlab 25, IfcStair 1, IfcRailing 2, IfcBuildingStorey 3 | 1.3 |
| 28434343986045eb86e2a58fd8f44b30_Building-Architecture.ifc | IFC4 | IfcWall 4, IfcSlab 3, IfcBuildingStorey 1 | 0.0 |

## Predicted (from the name) vs observed (from the models)

597 distinct class/property pairs observed. Rows = predicted grade, columns = observed tier.

| predicted \ observed | high | medium | low |
|---|---|---|---|
| **high** | 54 | 26 | 39 |
| **medium** | 8 | 13 | 18 |
| **low** | 0 | 0 | 439 |

- Exact agreement: **506/597 (85%)**
- Over-confident (predicted higher than observed): **83** (14%)
- Under-confident (predicted lower than observed): **8** (1%)

## The rules that were actually extracted

A property missing from every element of a class that *is* in the models counts as 0% coverage; a class that is not in the models has no evidence and is marked n/a.

| Rule | Class | Property set / property | Predicted | Coverage | Models | Observed | Match |
|---|---|---|---|---|---|---|---|
| DR-001 | IfcDoor | Attributes / GlobalId | high | 100% | 4 | high | yes |
| DR-002 | IfcDoor | - / IfcClass | high | 100% | 4 | high | yes |
| DR-003 | IfcDoor | Attributes / Name | high | 100% | 4 | high | yes |
| DR-004 | IfcDoor | - / PredefinedType | high | 50% | 2 | medium | over-confident |
| DR-005 | IfcDoor | - / StoreyGlobalId | high | 100% | 4 | high | yes |
| DR-006 | IfcBuildingStorey | - / StoreyName | high | 100% | 5 | high | yes |
| DR-007 | IfcDoor | - / PlacementMatrix | high | 100% | 4 | high | yes |
| DR-008 | IfcDoor | - / OpeningGlobalId | high | 99% | 4 | high | yes |
| DR-009 | IfcOpeningElement | - / OpeningIfcClass | high | no IfcOpeningElement in the models | 0 | no data | n/a |
| DR-010 | IfcOpeningElement | - / HostGlobalId | high | no IfcOpeningElement in the models | 0 | no data | n/a |
| DR-011 | IfcDoor | - / HostIfcClass | high | 99% | 4 | high | yes |
| DR-012 | IfcDoor | Attributes / OverallWidth | high | 100% | 4 | high | yes |
| DR-013 | IfcDoor | Attributes / OverallHeight | high | 100% | 4 | high | yes |
| DR-014 | IfcDoor | Qto_DoorBaseQuantities / QtoWidth | high | 0% | 0 | low | over-confident |
| DR-015 | IfcDoor | Qto_DoorBaseQuantities / QtoHeight | high | 0% | 0 | low | over-confident |
| DR-016 | IfcDoor | Qto_DoorBaseQuantities / Perimeter | high | 4% | 1 | low | over-confident |
| DR-017 | IfcDoor | Qto_DoorBaseQuantities / Area | high | 50% | 2 | medium | over-confident |
| DR-018 | IfcDoor | - / RepresentationIds | low | 0% | 0 | low | yes |
| DR-019 | IfcDoorType | - / OperationType | high | no IfcDoorType in the models | 0 | no data | n/a |
| DR-020 | IfcDoor | - / OpeningDirectionAxis | low | 0% | 0 | low | yes |
| DR-021 | IfcDoor | Attributes / Tag | high | 100% | 4 | high | yes |
| DR-022 | IfcDoor | - / TypeGlobalId | high | 100% | 4 | high | yes |
| DR-023 | IfcDoorType | Pset_DoorPanelProperties / PanelOperation | medium | no IfcDoorType in the models | 0 | no data | n/a |
| DR-024 | IfcDoor | Pset_DoorCommon / FireRating | medium | 75% | 3 | medium | yes |
| DR-025 | IfcDoor | Pset_DoorCommon / IsExternal | medium | 100% | 4 | high | under-confident |
| DR-026 | IfcDoor | Pset_DoorCommon / ThermalTransmittance | medium | 0% | 0 | low | over-confident |
| DR-027 | IfcDoor | Pset_DoorCommon / HandicapAccessible | medium | 0% | 0 | low | over-confident |
| DR-028 | IfcDoor | Pset_DoorCommon / FireExit | medium | 0% | 0 | low | over-confident |
| DR-029 | IfcDoor | Pset_DoorCommon / SelfClosing | medium | 0% | 0 | low | over-confident |
| DR-030 | IfcDoor | Pset_DoorCommon / SmokeStop | low | 0% | 0 | low | yes |

## Largest disagreements (by elements sampled)

| Class | Set / property | Predicted | Observed | Mean coverage | Models | Basis |
|---|---|---|---|---|---|---|
| IfcWall | Attributes / ObjectType | high | medium | 60% | 3 | standard_attribute |
| IfcWall | Pset_WallCommon / LoadBearing | medium | high | 100% | 5 | property_set |
| IfcWall | Pset_WallCommon / IsExternal | medium | high | 100% | 5 | property_set |
| IfcWall | Pset_WallCommon / FireRating | medium | low | 1% | 1 | property_set |
| IfcWall | (derived) / TypeGlobalId | high | medium | 80% | 4 | relationship |
| IfcWall | Pset_ReinforcementBarPitchOfWall / Description | high | medium | 59% | 3 | standard_attribute |
| IfcWall | Qto_WallBaseQuantities / Height | high | low | 34% | 2 | quantity |
| IfcWall | Qto_WallBaseQuantities / Length | high | medium | 60% | 3 | quantity |
| IfcWall | Qto_WallBaseQuantities / Width | high | medium | 60% | 3 | quantity |
| IfcWall | Qto_WallBaseQuantities / GrossFootprintArea | high | low | 34% | 2 | quantity |
| IfcWall | Qto_WallBaseQuantities / GrossVolume | high | low | 34% | 2 | quantity |
| IfcWall | Qto_WallBaseQuantities / GrossSideArea | high | low | 34% | 2 | quantity |
| IfcWall | Qto_WallBaseQuantities / NetSideArea | high | medium | 54% | 3 | quantity |
| IfcWall | Qto_WallBaseQuantities / NetVolume | high | medium | 60% | 3 | quantity |
| IfcWall | Pset_EnvironmentalImpactIndicators / Reference | medium | low | 40% | 2 | property_set |
| IfcWall | Pset_WallCommon / ThermalTransmittance | medium | low | 40% | 2 | property_set |
| IfcWall | Qto_BodyGeometryValidation / NetSurfaceArea | high | low | 20% | 1 | quantity |
| IfcWall | Qto_BodyGeometryValidation / NetVolume | high | low | 20% | 1 | quantity |
| IfcWall | Attributes / Description | high | low | 20% | 1 | standard_attribute |
| IfcWall | Pset_WallCommon / Status | medium | low | 20% | 1 | property_set |
| IfcDoor | Attributes / ObjectType | high | medium | 50% | 2 | standard_attribute |
| IfcDoor | Pset_DoorCommon / Reference | medium | high | 100% | 4 | property_set |
| IfcDoor | Pset_DoorCommon / IsExternal | medium | high | 100% | 4 | property_set |
| IfcDoor | Attributes / PredefinedType | high | medium | 50% | 2 | standard_attribute |
| IfcDoor | Qto_DoorBaseQuantities / Width | high | medium | 50% | 2 | quantity |

## Limits

- A handful of models, mostly Revit-exported samples: coverage reflects their authoring habits.
- The two Pacific Continental Residence files are the same building in two IFC schemas, so they
  are one independent model, not two.
- Quantity and property-set names an extraction invented (e.g. `QtoWidth`) show as 0% because no
  model can carry a property that does not exist; that is a finding about the extraction, not the models.
- Elements are sampled (capped per class per model); classes with few elements are ignored.
- Coverage measures *presence*, not correctness of the value.
