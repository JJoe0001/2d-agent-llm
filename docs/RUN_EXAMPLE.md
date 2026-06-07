# Minimal example

The minimal example is provided to document the expected input and output schemas without requiring the full production dataset.

## Input

```text
examples/minimal_run/sample_parent_input.csv
```

This file contains five Materials Project parent structures with columns:

```text
original_file, formula, cif_content, formation_energy, ehull, spacegroup
```

The `cif_content` column stores the parent CIF text directly, so the example is self-contained.

## Expected labels

The expected parent-level labels for the five structures are:

```text
examples/minimal_run/expected_parent_labels.csv
```

The expected candidate-level subset for positive parents is:

```text
examples/minimal_run/expected_candidate_subset.csv
```

These files are extracted from the full processed dataset and are intended for schema validation.

## Running through the MCP service

After installing dependencies, start the server from the package root:

```bash
python code/exfo_agent/server.py
```

In an MCP-enabled client, use the batch tools described in:

```text
code/skills/exfo-batch-workflow/SKILL.md
```

For a standard run, the intended call order is:

1. `batch_process_csv` or `batch_process_csv_no_passivation`
2. `deduplicate_structures`
3. `batch_ml_validation` if CHGNet validation is requested
4. `check_batch_status`

## Notes

The example expected-label files are not meant to be a deterministic re-run benchmark for all three routes, because route-level outputs may depend on chosen thresholds, installed dependency versions, and whether optional CHGNet validation is enabled. They are provided to document the exact schema and representative labels used in the manuscript data.
