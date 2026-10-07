# Where the language model enters the workflow

This document maps the released code to the manuscript's language-model claims. It describes the implementation visible in this repository; without historical client transcripts, it cannot reconstruct the exact production sequence of model requests.

| Component | Code location | What the model could do | What the code does |
| --- | --- | --- | --- |
| Client instruction | `code/skills/exfo-batch-workflow/SKILL.md`, `agents/openai.yaml` | Read a proposed order of MCP calls and choose file paths or requested options | Gives a runbook; it is not an LLM API client or a production prompt transcript. |
| MCP interface | `code/exfo_agent/server.py` | Invoke registered tools with arguments and receive their results | `FastMCP` exposes Python functions. There is no `openai` import, model initialization, token counter, or API request in this repository. |
| High-throughput extraction | `server.py:48-96`, `tools/batch_utils.py:505-509`, `tools/batch_utils_no_passivation.py` | Supply input/output CSV paths and `top_k` in a batch tool call | Python reads rows, runs scientific algorithms in workers, and writes CSV files. It does not call the model once per parent structure. |
| Existing-route extraction | `server.py:107-156`, `tools/literature_methods.py` | Trigger AiiDA-style or 2DMatPedia-style batch tools | Route functions and worker pools process the CSV. |
| Deduplication and ML | `server.py:159-178,217-237`, `tools/batch_utils.py:669-674` | Invoke deduplication, then CHGNet validation | Pymatgen matching and CHGNet determine results. The ML call is synchronous. |
| Status | `server.py:180-211` | Ask for counts from a summary CSV | Reads existing file and counts worker states; it does not inspect GPT/API status. |
| Single-structure tools | `server.py:40-45,243-371` | Supply a CIF or choose diagnostic calls | The Python workflow selects the geometric or bond-deletion branch by computed dimensionality; plane ranking and delta scan are also in Python. Single-structure replies can include full CIF text and could enlarge a client conversation. |

`tools/route.py:35-76` is a fixed rule-based router, not model reasoning. The comment in `tools/parse.py:117-124` says the LLM could use a structured parse error to regenerate input, but no automatic prompt correction or retry is implemented. The published skill gives a four-call batch sequence (extraction, deduplication, ML, status), but its presence is not evidence that this exact prompt or call count was used in the historical run.

## Context length, latency, and recovery

- A batch request passes file paths, while parent CIF contents remain in local CSV processing. This design avoids one LLM request per structure. It does **not** prove that the original model session never exceeded its context window; no client-side token or context telemetry survives.
- Repeated tool responses, especially single-structure results containing CIF text, can accumulate in a model conversation. The repository contains no context-size guard, history compaction, conversation restart policy, or model API retry/backoff code. GPT-side JSON errors, API timeouts, rate limits, and context overflows cannot be counted from the available logs.
- `batch_process_csv` and `batch_ml_validation` call long-running Python routines synchronously. Their worker timeout and crash labels are local Python states, not API timeout recovery. A client-side tool-call timeout may interrupt a long batch; no asynchronous job ID or client reconnection mechanism is implemented here.
- `tools/batch_utils.py:329-356` logs and returns when input CSV reading fails, while `batch_process_csv_impl` still returns a generic completed string. `server.py:159-177` likewise wraps the ML implementation's error string in a `Completed` status. Therefore the tool response alone cannot certify success; output files and summary tables must be checked.
- The batch routine writes result and summary CSVs incrementally and skips IDs already in a summary on restart. This supports manual resumption of local work. It is not an automatic GPT/API failure recovery loop; existing `ERROR`/`TIMEOUT` rows may also be skipped by the resume logic.

Original local `system.log` and batch logs document server startup, Python worker progress, and computational failures. They do not contain a model ID, prompts, API request IDs, token usage, API error codes, or per-tool-call latency. The authors recall GPT-5.4, but its exact historical API snapshot cannot be verified from these files. Neither the percentage of affected model calls nor an LLM-to-script runtime overhead can be estimated from this evidence. Report no measured efficiency benefit from the LLM layer.

## Historical evidence and its limits

The original project (outside this compact Git archive) contains `.mcp.json` configuring an `exfoliation-agent` MCP server and `code/exfo_agent/logs/system.log`. The first lines of the latter record an MCP server initialization at `2026-03-13 14:52:42`, followed by a no-passivation CSV batch start at `2026-03-13 15:24:17`, a 300-second worker limit, and five Python workers. The original configuration and log SHA-256 values are `ab63ae8cb84c5aca5b9a722bf9ea332442f0daff0c31016ce6196a53516e25d8` and `759862d3729c84206c88324ab414dab041600c9586929fb4f5d52effffd2adce`, respectively. These files support the fact that the MCP service and local batch program were configured and run. They **do not** identify the client that initiated the run or prove a particular GPT tool-call sequence. The assertion that GPT-5.4 was used to initiate tools is based on author recollection.

For a reviewer-facing evidence package, cite the MCP configuration, registered tool definitions, batch implementation, current workflow instruction, and dated runtime-log excerpt separately. Label the current instruction as a reproducibility guide, not a verbatim historical prompt. Do not report a historical tool-call count, context-overflow count, or runtime gain without the missing client/API record.
