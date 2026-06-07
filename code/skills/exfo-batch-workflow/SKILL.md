---
name: exfo-batch-workflow
description: "Use the MCP tools exposed by exfo_agent efficiently for the high-throughput CSV workflow. Use when the exfo_agent MCP server is loaded and the user wants extraction, optional no-passivation extraction, deduplication, ML validation, or batch status checks performed in a reliable order."
---

# Exfo Batch Workflow

## Overview
Use this skill only after the `exfo_agent` MCP server has been loaded from `exfo_agent/server.py`.
This skill does not replace MCP tools. It tells the model which MCP tools to call, in what order, and with what output conventions.

Default project root: `exfo_agent`

## Tool Order
1. Choose extraction mode.
Use `batch_process_csv` by default.
Use `batch_process_csv_no_passivation` only when the user explicitly wants raw extracted surfaces.

2. Run extraction first.
Always write both an extraction CSV and a summary CSV.
Keep file names run-scoped and reproducible.

3. Deduplicate extracted candidates unless the user explicitly wants raw candidates.
Call `deduplicate_structures` on the extraction CSV.
If deduplication succeeds, use the deduplicated CSV as the ML input.

4. Run ML validation when requested.
Call `batch_ml_validation` with the requested threshold.

5. Read summary state.
Call `check_batch_status` on the summary CSV after extraction or after the full pipeline.

## Expected MCP Calls
For a normal batch run:
1. `batch_process_csv(input_csv_path, save_csv_path, summary_path, top_k)`
2. `deduplicate_structures(input_csv=save_csv_path, output_csv=dedup_csv)`
3. `batch_ml_validation(input_csv=dedup_csv_or_extraction_csv, save_csv=ml_csv, threshold=...)`
4. `check_batch_status(summary_csv=summary_path)`

For a no-passivation run:
1. `batch_process_csv_no_passivation(...)`
2. `deduplicate_structures(...)`
3. `batch_ml_validation(...)`
4. `check_batch_status(...)`

For a single CIF:
1. Prefer `smart_exfoliate_single`
2. Use lower-level tools only when the user explicitly wants diagnostic steps or route-specific control

## Rules
- Keep all output files in one run-specific directory or run-specific filename prefix.
- Prefer deduplication before ML validation for cost control.
- Fail fast when required input files are missing.
- Use MCP tools as the execution surface; do not bypass them with local helper scripts unless debugging the codebase itself.
- Do not modify algorithm internals in `tools/` when only execution parameters need to change.
- Prefer this skill for normal batch runs; edit `tools/` only when changing extraction or ML logic itself.
- When the user asks to "run the pipeline", choose output paths explicitly and state them.

## Resources
- Reference: `references/pipeline-map.md`
