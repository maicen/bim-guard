# BCF exports

BCF 2.1 archives written by `app/services/bcf_exporter.py`. Each `.bcfzip`
carries `bcf.version`, `project.bcfp`, and one folder per topic holding
`markup.bcf`, `viewpoint.bcfv` and `snapshot.png` — the structure Revit,
Solibri, Archicad, BlenderBIM and BIMcollab expect on import.

Archives are generated output and are not tracked in git; only this README is.

```python
from app.services.bcf_exporter import BCFExporter

path = BCFExporter().export(issues, "galvanic_review")
```

`issues` is a list of `Issue` objects from
`app/modules/module4_comparator/issue_schema.py`, exactly as the Module 4
comparators emit them.

## Multi-element findings

`Issue` carries one `element_id`, but a galvanic couple (GC-001) implicates an
anode *and* a cathode. Extra IFC GUIDs go in `Issue.metadata`, and every one of
them is selected and coloured in the viewpoint:

| `metadata` key         | Role in the viewpoint |
| ---------------------- | --------------------- |
| `anode_guid`           | anode                 |
| `cathode_guid`         | cathode               |
| `clashing_element_id`  | clashing element      |
| `counterpart_guid`     | counterpart           |
| `related_element_ids`  | related (list)        |

`metadata["camera"] = {"x": .., "y": .., "z": ..}` aims the viewpoint camera at
the element centroid; without it the camera falls back to a fixed offset from
the origin.
