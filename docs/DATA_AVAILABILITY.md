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

## Large files not embedded

The complete parent CIF library, generated candidate CIF library, and relaxed CIF library are large generated artifacts and should be deposited in an external repository such as Zenodo, Figshare, institutional storage, or the journal-recommended data repository. The main package records their expected organization in:

```text
data/external_large_files/README.md
```

## Data included

The data included in this archive are limited to parent records, final deduplicated 2D candidate records, and computed screening results. Intermediate route-stage temporary files and plotting-specific summary tables are intentionally excluded from the compact CPC submission package.

## Data citation

Before final submission, replace this placeholder with the DOI or accession information for the external full-CIF archive, if deposited.
