# BIMGUARD AI — Streamlit App Extensions
## Integration Guide

Four new modules extend the existing Streamlit application. Drop them into
your `modules/` directory alongside `ifc_parser.py`, `compliance_runner.py`,
`bcf_generator.py`, and `schedule_impact.py`.

---

## Module 1 — `cost_model.py` (User-configurable cost rates)

### What it does
Replaces the hardcoded cost and duration impact model with a user-uploadable
CSV file. Falls back to built-in UK commercial MEP defaults if no CSV is
uploaded. The built-in defaults cover all three engines (GC/CC/MC) across
all four risk bands.

### Installation
```bash
# No additional dependencies beyond existing Streamlit + pandas
```

### Integration (Schedule & Cost Impact page)
```python
from modules.cost_model import CostModel

# In session state init
if "cost_model" not in st.session_state:
    st.session_state.cost_model = CostModel()

# CSV upload widget
uploaded = st.file_uploader("Upload custom cost rates (CSV)", type=["csv"])
if uploaded:
    success, msg = st.session_state.cost_model.load_from_upload(uploaded)
    st.success(msg) if success else st.error(msg)

# Template download
st.download_button(
    "Download CSV template",
    CostModel.generate_template(),
    "bimguard_cost_template.csv",
    "text/csv"
)

# Calculate impact
impact = st.session_state.cost_model.calculate_impact(
    st.session_state.compliance_results
)
```

### CSV format
Headers: `risk_band, mechanism, material_group, cost_per_item_gbp, duration_days, remediation_description, contractor_type`

`mechanism` values: `GC`, `CC`, `MC`
`risk_band` values: `Critical`, `High`, `Medium`, `Low`
`material_group`: any string — use `default` as a catch-all

---

## Module 2 — `report_generator.py` (Word report export)

### What it does
Generates a formatted Word (.docx) compliance report including: cover page
with project metadata, executive summary, risk distribution table, full issue
register with colour-coded bands, methodology section, and disclaimer.
Ready for client delivery or regulatory submission.

### Installation
```bash
pip install python-docx
```

### Integration (add to BCF Issue Manager or create a Reports page)
```python
from modules.report_generator import generate_word_report

project_meta = {
    "project_name": st.text_input("Project name"),
    "client":       st.text_input("Client"),
    "prepared_by":  st.text_input("Prepared by"),
    "ifc_file":     st.text_input("IFC file"),
    "revision":     st.text_input("Revision", value="P01"),
}

if st.button("Generate Word report"):
    docx_bytes = generate_word_report(
        st.session_state.compliance_results,
        st.session_state.cost_model.calculate_impact(st.session_state.compliance_results),
        project_meta
    )
    st.download_button(
        "Download report (.docx)",
        docx_bytes,
        "BIMGUARD_Report.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
```

---

## Module 3 — `ifc_geometry.py` (Actual area calculations)

### What it does
Improves surface area calculations for the GC-001 area ratio check by
reading actual geometric mesh data from IFC elements via ifcopenshell.geom,
rather than estimating from nominal diameter alone. Falls back gracefully
to nominal-diameter estimation when geometry is not available.

Also provides:
- `nps_to_od_m()` — NPS to actual OD lookup per ASME B36.10M
- `dn_to_od_m()` — DN to actual OD lookup per EN 10220

### Installation
```bash
# Already uses ifcopenshell — no new dependencies
```

### Integration (in ifc_parser.py, replace area estimation)
```python
from modules.ifc_geometry import IFCGeometryExtractor, estimate_surface_area

# After loading IFC model
extractor = IFCGeometryExtractor(ifc_model)

# For each element
area_data = extractor.get_external_surface_area(
    element=ifc_element,
    nominal_diameter_m=od / 2,
    insulation_thickness_m=ins_m,
)
area_m2 = area_data["area_m2"]
method  = area_data["method"]   # "geometry" | "quantity_set" | "estimated"

# Use in GC-001 area ratio calculation
ratio, band = extractor.calculate_area_ratio(
    anode_area_m2=anode_area,
    cathode_area_m2=cathode_area,
)
```

---

## Module 4 — `issue_tracker.py` (Issue history tracking)

### What it does
Tracks issues across multiple compliance runs — recording when each element
was first flagged, how its risk band has changed over time, and when it was
resolved. Persists history to a local JSON file (`bimguard_issue_history.json`)
between Streamlit sessions. Provides the data source for the BCF issue history
field in markup.bcf.

### Installation
```bash
# No additional dependencies
```

### Integration (BCF Issue Manager page)
```python
from modules.issue_tracker import IssueTracker

if "issue_tracker" not in st.session_state:
    st.session_state.issue_tracker = IssueTracker()

tracker = st.session_state.issue_tracker

# After a compliance run
summary = tracker.record_run(
    st.session_state.compliance_results,
    run_comment="IFC rev P03"
)

# Display stats
stats = tracker.get_statistics()
st.metric("Open issues", stats["open"])
st.metric("Resolved",    stats["resolved"])

# Add manual note
tracker.add_note(global_id, "Contractor confirmed reroute scheduled", author="User")

# Mark resolved
tracker.mark_resolved(global_id, author="User", comment="Reroute completed")
```

---

## Recommended app.py changes

Add to your Streamlit sidebar or page navigation:

```python
# In app.py navigation
pages = [
    "Data ingestion",
    "Model overview",
    "Corrosion compliance",
    "Point cloud comparison",
    "BCF issue manager",
    "Schedule & cost impact",
    "Reports",          # NEW — triggers report_generator
]
```

Add to session state initialisation block:

```python
from modules.cost_model    import CostModel
from modules.issue_tracker import IssueTracker

if "cost_model"    not in st.session_state:
    st.session_state.cost_model    = CostModel()
if "issue_tracker" not in st.session_state:
    st.session_state.issue_tracker = IssueTracker()
```

---

## Testing the extensions

```bash
# Test cost model
python -c "
from modules.cost_model import CostModel
m = CostModel()
results = [{'risk_band':'Critical','mechanism':'GC','material':'carbon_steel','global_id':'TEST-001'}]
impact = m.calculate_impact(results)
print(f'Cost: £{impact.total_cost_gbp:,.0f} | Days: {impact.total_days}')
"

# Test issue tracker
python -c "
from modules.issue_tracker import IssueTracker
t = IssueTracker('test_history.json')
results = [{'global_id':'TEST-001','risk_band':'Critical','composite_score':0.92,
            'element_type':'IfcPipeSegment','system_type':'DOMESTICCOLDWATER','material':'carbon_steel'}]
summary = t.record_run(results, run_comment='Test run')
print(summary)
t.clear()
"
```

---

## Compatibility

All four modules are compatible with the existing `bimguard_app/` structure.
They do not modify existing modules — they extend the app by adding new
functionality alongside the existing code.

Dependencies summary:
| Module           | New dependencies |
|------------------|-----------------|
| cost_model.py    | none (uses pandas already in requirements) |
| report_generator.py | `pip install python-docx` |
| ifc_geometry.py  | none (uses ifcopenshell already in requirements) |
| issue_tracker.py | none (stdlib only) |
