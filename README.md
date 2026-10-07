# Route-aware high-throughput exfoliation workflow for 2D materials discovery

This repository contains the code and compact processed tables accompanying *A multi-route high-throughput workflow for 2D materials discovery*. It is being prepared for the revision of the manuscript submitted to *Digital Discovery*.

The repository includes the MCP service, three exfoliation-route implementations, workflow instructions, processed labels, and a five-parent example. The full structure archives and figure-reproduction inputs are not yet published here; see [data availability](docs/DATA_AVAILABILITY.md) for the exact scope and outstanding deposits.

## Package layout

```text
code/
  exfo_agent/                  MCP server and exfoliation-route source code
  skills/exfo-batch-workflow/  Agent-facing workflow instructions
data/
  parents/                     Parent-structure metadata and parent-level MP quantities
  final_2d_candidates/         Final deduplicated 2D candidate labels and CHGNet results
  computed_results/            Parent exfoliability labels and dataset-level summary
  dimensionality/               Post-CHGNet 2D morphology labels, with and without passivation
  route_outputs/                Pre-deduplication filename and route manifest
  external_large_files/        Notes for large CIF archives not included in the main package
docs/
  PROGRAM_SUMMARY.md           Program summary
  INSTALL.md                   Environment and dependency instructions
  RUN_EXAMPLE.md               Minimal example and expected outputs
  DATA_AVAILABILITY.md         Data provenance and large-file policy
  CODE_INVENTORY.md            Source-code inventory
  exfoliation_parameters_summary.xlsx
examples/
  minimal_run/                 Small parent-structure CSV and expected label outputs
checks/
  python_syntax_check.txt      Syntax-check output generated for this archive
scripts/
  verify_package.py            Verify compact tables, checksums, and manifest
  revision_audit.py             Recompute route, survival, and diversity counts
```

## Main code entry point

The MCP server entry point is:

```bash
code/exfo_agent/server.py
```

The three exfoliation routes are implemented as:

- Topological route: `code/exfo_agent/tools/literature_routes/aiida_exfo_test.py`
- Layered route: `code/exfo_agent/tools/literature_routes/exfo_2dmatpedia.py`
- Hybrid route: `code/exfo_agent/tools/workflow.py`, `planar_gap.py`, `bond_del.py`, and `xcp_potential.py`

## Main data files

- `data/parents/parent_level_metadata.csv.gz`: parent-level metadata, MP formation/hull energies, route flags, candidate counts, and aggregated 2D-candidate energy statistics.
- `data/final_2d_candidates/final_2d_candidates.csv.gz`: final deduplicated 2D candidate labels, parent mapping, route sources, relaxation status, and CHGNet formation-energy results.
- `data/computed_results/parent_exfoliability_labels.csv.gz`: parent-level binary exfoliability labels and route labels for 143,259 MP parent structures.
- `data/computed_results/dataset_summary.json`: summary of parent/candidate counts and route-label distributions.
- `data/route_outputs/merged_candidate_manifest.csv.gz`: all 76,852 pre-deduplication candidate names and routes.
- `data/dimensionality/*.csv.gz`: dimensionality assessments for every unique candidate.
- `data/computed_results/revision_screening_summary.json`: reproducible revision audit. See [revision findings](docs/REVISION_FINDINGS.md).

Intermediate plotting tables, route-stage temporary outputs, full CIF libraries, and production agent traces are not included in this compact repository. Do not use `candidate_cif_missing: 0` in `dataset_summary.json` as evidence that these CIFs are present here: that field was computed against the original local archive. See `docs/DATA_AVAILABILITY.md` and `data/external_large_files/README.md`.

## Minimal example

The example input is:

```bash
examples/minimal_run/sample_parent_input.csv
```

The expected parent/candidate labels for those structures are:

```bash
examples/minimal_run/expected_parent_labels.csv
examples/minimal_run/expected_candidate_subset.csv
```

See `docs/INSTALL.md` and `docs/RUN_EXAMPLE.md` for setup and the limits of the current example. Run `python scripts/verify_package.py` to verify checksums and compact-table row counts.

For first-principles validation, see the [VASP protocol](docs/VASP_VALIDATION_PROTOCOL.md), the selected paired CIFs, and prepared POSCAR/KPOINTS files in `examples/dft_validation/`. DFT results have not yet been added.
For implemented thresholds and the sensitivity rerun design, see [parameter audit](docs/PARAMETER_AUDIT.md).
For source-backed failure handling and the limits of the available agent logs, see [orchestration audit](docs/AGENT_FAILURE_AUDIT.md).
For the planned versioned 2DMatPedia, MC2D, and C2DB recovery benchmark, see [database benchmark protocol](docs/DATABASE_BENCHMARK_PROTOCOL.md).

## License

See `LICENSE`. The included third-party concepts and scientific methods are cited in the manuscript; the implementation code in this archive is provided for academic review and reproducibility.
