# External large files

The following generated artifacts are not included in this repository and do not yet have a public download location:

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

The compact tables in `../parents/`, `../final_2d_candidates/`, and `../computed_results/` preserve identifiers and labels, but they cannot reconstruct every structure. The archive should include a manifest mapping each published candidate to its parent, route, relaxation status, and checksum. Add verified archive URLs and DOIs here after deposit.
