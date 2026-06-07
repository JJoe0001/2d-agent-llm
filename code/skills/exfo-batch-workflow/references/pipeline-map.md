# Exfo Batch Pipeline Map

Project root:
- `exfo_agent`

MCP server entrypoint:
- `exfo_agent/server.py`

## Input CSV columns
Minimum required columns for extraction stage:
- `original_file`
- `formula`
- `cif_content`

Optional metadata columns carried forward:
- `formation_energy`
- `ehull`
- `spacegroup`

## Stage mapping
1. Single-structure main entry:
- `smart_exfoliate_single`

2. Extraction with passivation:
- `batch_process_csv`

3. Extraction without passivation:
- `batch_process_csv_no_passivation`

4. Deduplication:
- `deduplicate_structures`

5. ML validation:
- `batch_ml_validation`

6. Summary status:
- `check_batch_status`

## Typical output files
- `*_02_csv_extraction.csv`
- `*_02_csv_summary.csv`
- `*_02_candidates_unique.csv`
- `*_03_ml_validation.csv`

## Notes
- The active tool surface should be MCP tools registered in `server.py`.
- The skill is a usage guide for those MCP tools, not a replacement runtime.
- `server.py` currently starts the MCP service with HTTP transport on port `8000`.
