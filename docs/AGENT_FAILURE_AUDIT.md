# Orchestration and failure-mode audit

The repository implements MCP tool endpoints in `code/exfo_agent/server.py`. Current evidence supports the following statements about the code, but does **not** quantify the behavior of the historical production LLM session. No production model identifier, prompt transcript, tool-call trace, token/context-window usage, or retry log is packaged.

| Layer | Failure condition | Implemented behavior | Evidence limit |
| --- | --- | --- | --- |
| CIF parser | Missing input, disallowed file path, invalid volume, empty structure, parser exception | Returns a structured error and writes a debug trace | Cannot infer how many production calls failed. |
| Per-candidate extraction | Layer extraction exception | Catches and logs that candidate; continues the other planes | A skipped layer may reduce yield. |
| Whole smart workflow | Uncaught exception | Returns an error dictionary and records a debug artifact | No guarantee of automatic retry. |
| Batch worker | Task exceeds 300 seconds | Records `TIMEOUT` summary row with source file | This is worker timeout, not an LLM API timeout. |
| Batch worker | Process crash | Records `CRASH` summary row with source file | Historical summary rows are not packaged. |
| Batch scheduling | Worker accumulation | Recreates the process pool every 1,000 parent rows | Does not imply failed jobs are retried. |
| MCP serialization | Tool message or JSON malformed at LLM side | No explicit repair/retry mechanism found in this code | Must not claim prompt self-correction. |
| Context window or API rate limit | Context overflow, request timeout, 429 | No explicit recovery mechanism found in this code | Must not claim autonomous completion through these failures. |

The final candidate table contains 256 `Error/Explosion`, 169 `Skipped (Too Large)`, and 103 `Skipped (Unstable)` validation labels. These are **post-generation CHGNet screening labels**, not LLM tool-call failure counts. The two dimensionality tables additionally contain parse and fragmentation labels; these refer to structural analysis, not agent JSON parsing.

To complete a production-level agent evaluation, preserve the actual model name and version/date, system/user prompts, model parameters, MCP tool schemas, timestamps, request/response status, retry IDs, token counts, parent IDs, and per-stage success/failure. Remove API keys and personal information before release. If these logs no longer exist, describe the MCP layer as an interface and orchestration aid, and present the deterministic route code and batch status handling as the reproducible contribution.
