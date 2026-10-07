# External 2D database recovery benchmark

This protocol defines the missing reference comparison requested in review. A recovery percentage must use a versioned reference denominator and the same structural matching rule for every database. The reference CIFs and version manifests are not yet packaged, so no three-database recovery claim is made here.

## Reference snapshots

- **2DMatPedia:** obtain its deposited JSON and CIF snapshot, preserve source URL/DOI, retrieval date, and entry IDs. The [dataset publication](https://www.nature.com/articles/s41597-019-0097-3) describes a downloadable JSON and Figshare structural files.
- **MC2D:** choose a single archived release and identify whether the denominator includes every candidate, only relaxed structures, or a stability-filtered subset. The [official MC2D portal](https://mc2d.materialscloud.org/) provides data DOIs and current APIs; mixing archived and live counts would make the percentage ambiguous.
- **C2DB:** archive a specific downloadable database version, entry IDs, and structural data. Record whether prototype-generated and experimentally derived entries are both included. The [DTU C2DB portal](https://c2db.fysik.dtu.dk/) is the source for this snapshot.

## Matching hierarchy

1. Exclude records without parseable atomic coordinates, but report the exclusion count and retain their IDs in the raw manifest.
2. Normalize each slab's vacuum axis and center its atoms; preserve chemistry and distinguish raw versus DFT-relaxed reference structures. Match against the **68,089 successfully relaxed, unpassivated 2D-classified** candidate subset for the primary recovery rate. Repeat against all 73,105 candidate records as a coverage sensitivity result.
3. Compare reduced chemical composition, then candidate geometry: in-plane area per formula unit within 5%, layer thickness within 20%, followed by `StructureMatcher(ltol=0.2, stol=0.3, angle_tol=5°)` on appropriately normalized cells. For suspected matches, inspect polymorph, termination, and layer count; one formula can have multiple distinct 2D structures.
4. Classify each reference entry as `structure_match`, `formula_geometry_only`, `formula_only`, or `no_formula_match`. Also compare **chemical system** separately. Report `structure_match / reference entries parsed` and the union across databases with cross-database duplicates resolved.
5. For selected candidates in Table 1, report three different claims explicitly: previously known composition, structurally matched known phase, and absent from the versioned databases searched. “No direct match” means only the latter when the exact datasets, matching rule, and negative search result are recorded; it is not proof of a new material.

An older local analysis in `papers/literature_db_comparison` compared 73,105 candidates against 6,351 2DMatPedia CIFs and reported 526 structure matches (8.28%), using area/thickness prefilters and StructureMatcher. Its database snapshot, normalization quality, and relation to the new relaxed-2D denominator have not been independently verified; MC2D and C2DB were not covered together. Treat this only as a historical pilot, not the manuscript's final recall metric.
