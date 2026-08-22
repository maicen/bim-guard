"""
Blue Halo — Module 2 producer package.

Houses the seismic bracing clearance ("Blue Halo") algorithm: generation of
3D clearance envelopes around braced MEP elements, clash detection against
neighbouring geometry, and export to IFC property sets / BCF 2.1 issues.

See halo_volume_generator.py for the Phase 1 (standard-agnostic) skeleton.
Jurisdiction-specific numeric data (spacing, clearance, angle limits) is
supplied at runtime via JSON configs — see load_clearance_config — and is
never hardcoded in this package.
"""
