# Route-aware high-throughput exfoliation workflow for 2D materials discovery

This archive contains the code and processed data accompanying the manuscript submitted to *Computer Physics Communications*.

The package is organized for review and reproducibility. It includes the MCP service used to expose the exfoliation workflow, the three exfoliation-route implementations, the workflow skill instructions, processed labels/results used in the manuscript, and a minimal example input with expected outputs.

## Package layout

```text
code/
  exfo_agent/                  MCP server and exfoliation-route source code
  skills/exfo-batch-workflow/  Agent-facing workflow instructions
data/
  parents/                     Parent-structure metadata and parent-level MP quantities
  final_2d_candidates/         Final deduplicated 2D candidate labels and CHGNet results
  computed_results/            Parent exfoliability labels and dataset-level summary
  external_large_files/        Notes for large CIF archives not included in the main package
docs/
  PROGRAM_SUMMARY.md           CPC-style program summary
  INSTALL.md                   Environment and dependency instructions
  RUN_EXAMPLE.md               Minimal example and expected outputs
  DATA_AVAILABILITY.md         Data provenance and large-file policy
  CODE_INVENTORY.md            Source-code inventory
  exfoliation_parameters_summary.xlsx
examples/
  minimal_run/                 Small parent-structure CSV and expected label outputs
checks/
  python_syntax_check.txt      Syntax-check output generated for this archive
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

Intermediate plotting tables and route-stage temporary outputs are intentionally not included. The full CIF libraries are not embedded in this small submission package because they are large generated artifacts. See `docs/DATA_AVAILABILITY.md` and `data/external_large_files/README.md`.

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

See `docs/RUN_EXAMPLE.md` for details.

## License

See `LICENSE`. The included third-party concepts and scientific methods are cited in the manuscript; the implementation code in this archive is provided for academic review and reproducibility.
