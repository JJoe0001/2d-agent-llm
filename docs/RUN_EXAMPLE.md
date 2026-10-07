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

After installing dependencies, start the stdio server through an MCP client using the template in `mcp_config/mcp_server_relative.json`. Replace `${PACKAGE_ROOT}` and `python` as described in `docs/INSTALL.md`. For an HTTP client, run the server separately:

```bash
.venv/bin/python code/exfo_agent/server.py --transport http --port 8000
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

The expected-label files are historical outputs provided for schema inspection. They are not a validated end-to-end regression benchmark: route outputs depend on parameters and dependency versions, and CHGNet validation is optional. The repository currently has no recorded clean-environment run that reproduces these labels exactly. Run `python scripts/verify_package.py` to verify the published compact tables independently of the scientific dependencies.
