# External large files

The following large generated artifacts are not included in the compact CPC submission package:

- Full Materials Project parent CIF library used as workflow input.
- Route-specific generated CIF folders.
- Merged pre-deduplication candidate CIF library.
- Deduplicated unique 2D CIF library.
- CHGNet-relaxed structure outputs, if archived separately.

Recommended external archive layout:

```text
external_archive/
  parent_cifs/
  route_outputs/
    topological/
    layered/
    hybrid/
  merged_candidates/
  unique_2d_candidates/
  relaxed_candidates/
  checksums/
```

The compact data files in `../parents/`, `../final_2d_candidates/`, and `../computed_results/` preserve the mapping between parent IDs, candidate filenames, route labels, and energy-validation results.
