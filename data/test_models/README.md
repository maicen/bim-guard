# Test models

IFC models downloaded on demand from [`maicen/bimguard-test-models`](https://github.com/maicen/bimguard-test-models)
by `scripts/fetch_test_model.py`. The models are large (the upstream repository
is ~950 MB); they are gitignored and never committed here. Only this README is
tracked.

```bash
python scripts/fetch_test_model.py --list      # catalogue with measured stats
python scripts/fetch_test_model.py --set clinic
python scripts/run_full_pipeline.py --model data/test_models/Clinic_Plumbing.ifc --auto-extra
```

## Upstream material metadata is fabricated — verify before relying on it

**No upstream metadata about materials in this repository has been found to be
accurate.** Check any model yourself before using it to exercise a
material-dependent engine.

Verified by inspecting the downloaded files directly:

| Model | `IfcMaterial` entities present | Upstream claim |
| --- | --- | --- |
| `Clinic_Plumbing.ifc` | **1** — `Chrome - DELTA - Polished` | `Copper_C12200:480; CarbonSteel:48` |
| `Clinic_HVAC.ifc` | **0** | `Aluminium:442; Copper_C12200:39; GalvanisedSteel:15` |
| `Clinic_Structural.ifc` | 9 — concrete, decking, steel (structural, not piping) | none |

The literal tokens `Copper_C12200` and `CarbonSteel` appear **zero** times in
`Clinic_Plumbing.ifc`. A GC-001 run over it produces 0 findings, correctly:
BIMGUARD's parser reports 6584 of 6587 elements as having an unidentified
material, and the model genuinely does.

Check a candidate model like this before trusting any published figure:

```bash
grep -oiE "IFCMATERIAL\('[^']*'" data/test_models/<model>.ifc | sort -u
```

### What is and is not trustworthy

- `metadata/models-manifest.json` — **not trustworthy at all.** 33 of its 34
  `sha256` fields are not valid digests (32 or 40 characters instead of 64,
  several being the repeated string `1928374e`, one value shared verbatim by six
  different files). Its material columns are invented.
- `metadata/piping_profile.json` — **material figures are also unreliable**,
  contradicted by direct inspection of the files. Not read for material data.
- `metadata/download_results.json` — **checksums are genuine.** All 38 SHA-256
  digests are real and unique, and downloads verify against them byte for byte.
  This is the only upstream field `fetch_test_model.py` relies on.

The `mat%` column shown by `--list` comes from the piping profile and should be
treated as an upstream claim, not a measurement.
