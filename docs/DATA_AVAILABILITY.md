# Data availability and provenance

## Parent structures

The parent structures originate from the Materials Project database after filtering for structures with energy above hull less than or equal to 0.5 eV per atom. The compact parent table contains 143,259 parent structures:

```text
data/parents/parent_level_metadata.csv.gz
```

The package includes parent identifiers, parent-level MP quantities, route labels, candidate counts, and aggregated energy statistics. It does not include all parent CIF files as individual files. A five-structure self-contained example with CIF text is included in `examples/minimal_run/sample_parent_input.csv`.

## Generated 2D candidates

The manuscript workflow generated 76,852 candidate CIFs before cross-route deduplication and 73,105 unique 2D candidate structures after deduplication. The compact processed candidate table is included as:

```text
data/final_2d_candidates/final_2d_candidates.csv.gz
```

This table contains candidate filenames, parent IDs, route source flags, CHGNet formation energies, relaxation status, validation status, candidate formula, and deduplication status.

## Computed results included

The parent-level exfoliability labels and dataset-level summary are included as:

```text
data/computed_results/parent_exfoliability_labels.csv.gz
data/computed_results/dataset_summary.json
```

These files provide the parent-level binary label, route-specific labels, candidate counts, and global parent/candidate count summaries.

Additional revision audit inputs are now packaged:

```text
data/route_outputs/merged_candidate_manifest.csv.gz
data/dimensionality/no_pass_dimensionality_post_ml.csv.gz
data/dimensionality/passivated_dimensionality_post_ml.csv.gz
data/computed_results/revision_screening_summary.json
```

The route manifest gives filename-level provenance for all 76,852 pre-deduplication candidates. The two dimensionality tables give post-CHGNet morphology labels for all 73,105 unique candidates. `scripts/revision_audit.py` recomputes and checks the summary; see `docs/REVISION_FINDINGS.md` for definitions and data caveats. A small VASP input selection of 16 derived CIFs is available in `examples/dft_validation/`; this is not the complete candidate archive and contains no DFT outputs.

The repository also includes a 48-parent planar-gap sensitivity panel with 336 run records and two rerun worked-example summaries in `data/computed_results/`. Those examples reference MP parent CIFs by ID and SHA-256; the parent CIFs themselves are not redistributed here.

## Large files not embedded

The complete parent CIF library, route-specific and deduplicated candidate CIF libraries, and relaxed CIF library are not available through this repository. No external archive URL or DOI has been assigned yet. The planned organization is documented in:

```text
data/external_large_files/README.md
```

The `candidate_cif_missing: 0` and `parent_cif_missing: 0` fields in `dataset_summary.json` refer to the original local processing environment. They do **not** mean the individual CIFs are included in this GitHub repository.

## Data included

The data included here are limited to parent records, pre-deduplication route provenance, deduplicated candidate records, dimensionality labels, and computed screening results. Full route-stage output structures, figure-generation tables and scripts, and production LLM/tool-call traces are not included. These omissions prevent independent reproduction of all manuscript figures from the repository alone.

## Data citation

Before submitting the revision, deposit the missing archives and figure inputs in a persistent repository, add versioned URLs and DOIs here, and put matching details in the manuscript Data Availability Statement. Do not cite this page as a substitute for a deposited dataset.
