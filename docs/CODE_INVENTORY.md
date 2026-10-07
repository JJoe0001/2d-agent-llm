# Exfoliation Strategy Code Inventory

Generated: 2026-04-26

This is a historical source-bundle snapshot; paths and sizes below are not the current repository inventory. Use `FILE_MANIFEST.tsv` and `SHA256SUMS` for current paths and checksums, and run `python scripts/verify_package.py` to validate them. The current MCP template is `mcp_config/mcp_server_relative.json`; the current server defaults to stdio and supports optional HTTP transport.

| Bundle path | Source note | Note | Size |
|---|---|---|---:|
| `exfo_agent/__init__.py` | bundled package file | MCP service / package metadata | 0 bytes |
| `exfo_agent/server.py` | bundled package file | MCP service entrypoint | 15,006 bytes |
| `exfo_agent/pyproject.toml` | bundled package file | package metadata | 343 bytes |
| `mcp_config/.mcp.json` | bundled config | MCP launch configuration | 302 bytes |
| `exfo_agent/core/__init__.py` | bundled package file | core runtime dependency | 0 bytes |
| `exfo_agent/core/config.py` | bundled core module | core runtime dependency | 1,120 bytes |
| `exfo_agent/core/store.py` | bundled core module | core runtime dependency | 1,666 bytes |
| `exfo_agent/core/utils.py` | bundled core module | core runtime dependency | 18,704 bytes |
| `exfo_agent/tools/__init__.py` | bundled package file | tools package marker | 0 bytes |
| `exfo_agent/tools/parse.py` | bundled tools module | CIF parsing dependency | 5,528 bytes |
| `exfo_agent/tools/debug_utils.py` | bundled tools module | route debugging utility | 5,056 bytes |
| `exfo_agent/tools/dimensionality.py` | bundled tools module | topological dimensionality judgement | 3,633 bytes |
| `exfo_agent/tools/route.py` | bundled tools module | route helpers | 2,763 bytes |
| `exfo_agent/tools/planar_gap.py` | bundled tools module | geometric slicing route | 5,682 bytes |
| `exfo_agent/tools/extract_layer.py` | bundled tools module | geometric layer extraction | 5,608 bytes |
| `exfo_agent/tools/bond_del.py` | bundled tools module | bond-deletion route | 21,305 bytes |
| `exfo_agent/tools/xcp_potential.py` | bundled tools module | XCP potential helper | 6,510 bytes |
| `exfo_agent/tools/workflow.py` | bundled tools module | hybrid route workflow | 7,014 bytes |
| `exfo_agent/tools/batch_utils.py` | bundled tools module | batch wrapper for the hybrid route | 27,954 bytes |
| `exfo_agent/tools/batch_utils_no_passivation.py` | bundled tools module | batch wrapper without passivation | 17,207 bytes |
| `exfo_agent/tools/surface_passivation.py` | bundled tools module | surface passivation | 27,036 bytes |
| `exfo_agent/tools/literature_methods.py` | bundled tools module | wrappers for the two literature-inspired routes | 10,809 bytes |
| `exfo_agent/tools/POTDATA_morse_yukawa_2025` | bundled data file | XCP parameter table | 1,044,302 bytes |
| `exfo_agent/tools/literature_routes/__init__.py` | generated | package marker for bundled literature routes | 0 bytes |
| `exfo_agent/tools/literature_routes/aiida_exfo_test.py` | bundled literature route | topology-inspired route implementation | 10,788 bytes |
| `exfo_agent/tools/literature_routes/exfo_2dmatpedia.py` | bundled literature route | layered-supercell route implementation | 10,517 bytes |
| `skills/exfo-batch-workflow/SKILL.md` | bundled skill | project-side Codex skill wrapper | 2,782 bytes |
| `skills/exfo-batch-workflow/agents/openai.yaml` | bundled skill | agent config | 278 bytes |
| `skills/exfo-batch-workflow/references/pipeline-map.md` | bundled skill reference | batch workflow map | 1,092 bytes |
| `installed_skill_snapshot/exfo-batch-workflow/SKILL.md` | bundled snapshot | installed skill snapshot | 2,782 bytes |
| `installed_skill_snapshot/exfo-batch-workflow/agents/openai.yaml` | bundled snapshot | installed agent config | 278 bytes |
| `installed_skill_snapshot/exfo-batch-workflow/references/pipeline-map.md` | bundled snapshot | installed workflow map | 1,092 bytes |
| `exfo_agent/tools/deduplicate_utils.py` | bundled tools module | structure deduplication (StructureMatcher) | 8,979 bytes |
| `exfo_agent/tools/analysis_utils.py` | bundled tools module | true-2D geometry filter and visualization | 8,940 bytes |
| `exfo_agent/tools/ml_ops.py` | bundled tools module | CHGNet relaxation and formation energy evaluation | 7,147 bytes |
