# BIMGUARD AI — Client Q&A Library

Twenty client-facing questions with expert answers, written for the people who
receive a BIMGUARD report: project managers, BIM coordinators, MEP engineers,
structural engineers and architects.

Every answer is written against the shipped implementation, not against a
roadmap. Where the software does not yet do something, the answer says so.

| # | Question | Domain |
| --- | --- | --- |
| [Q01](Q01_What_Is_Piping_Corrosion_Analysis.md) | What is Piping Corrosion Analysis and why do I need it? | Piping |
| [Q02](Q02_Interpreting_GC001_Galvanic_Findings.md) | How do I interpret GC-001 (Galvanic Corrosion) findings? | Piping |
| [Q03](Q03_MM001_Material_Media_Versus_Other_Engines.md) | What is the difference between MM-001 and the other engines? | Piping |
| [Q04](Q04_Detecting_Copper_To_Carbon_Steel_Couples.md) | Can BIMGUARD detect copper-to-carbon-steel couples? | Piping |
| [Q05](Q05_Exporting_Piping_Findings_For_MEP.md) | How do I export Piping findings for my MEP engineer? | Piping |
| [Q06](Q06_What_Does_Seismic_Clearance_Check.md) | What does Seismic Clearance (Blue Halo) check? | Seismic |
| [Q07](Q07_Clearance_Around_Beams_And_Columns.md) | How much clearance does my piping need around structure? | Seismic |
| [Q08](Q08_DIN_4149_Versus_EN_1998_1.md) | What is the difference between DIN 4149 and EN 1998-1? | Seismic |
| [Q09](Q09_Interpreting_SB001_Findings.md) | How do I interpret SB-001 findings on my model? | Seismic |
| [Q10](Q10_Exporting_Seismic_Findings_To_BIM_Tools.md) | Can I export seismic findings to Revit or other BIM tools? | Seismic |
| [Q11](Q11_What_Does_Architecture_Compliance_Check.md) | What does ARCH Compliance check? | Architecture |
| [Q12](Q12_Which_Building_Codes_Does_BIMGUARD_Reference.md) | Which building codes does BIMGUARD reference? | Architecture |
| [Q13](Q13_How_To_Fix_Non_Compliant_Rooms.md) | How do I fix non-compliant rooms? | Architecture |
| [Q14](Q14_Customising_The_Architecture_Ruleset.md) | Can I customise the architecture ruleset? | Architecture |
| [Q15](Q15_Accuracy_By_Building_Type.md) | How accurate is room compliance for my building type? | Architecture |
| [Q16](Q16_Run_All_Three_Analyses.md) | How do I run all three analyses on the same model? | Workflow |
| [Q17](Q17_Supported_IFC_Versions.md) | Which IFC versions does BIMGUARD support? | Workflow |
| [Q18](Q18_Selecting_Which_Corrosion_Engines_Run.md) | Can I select which corrosion engines to run? | Workflow |
| [Q19](Q19_Analysis_Runtime_On_Large_Models.md) | How long does analysis take on a large model? | Workflow |
| [Q20](Q20_What_A_BCF_Export_Contains.md) | What does a BCF export contain? | Workflow |

## A standing note on the NotebookLM prompts

Every document ends with a NotebookLM prompt. Those prompts exist for **rule
authoring** — sourcing clause text, thresholds and tables out of published
standards so a human reviewer can turn them into a rule pack.

They are **not** for compliance decisions. NotebookLM does not see your model,
does not run the engines, and its output is not a compliance verdict. A rule
enters BIMGUARD only after a named reviewer signs the pack (`approval` block in
the ruleset JSON), and every finding cites the clause the rule came from so the
chain back to the source stays auditable.
