# 最小运行示例

示例用于展示输入和输出数据模式，无需完整生产数据。

**输入：**`examples/minimal_run/sample_parent_input.csv`，含 5 个 Materials Project 母体，列为 `original_file, formula, cif_content, formation_energy, ehull, spacegroup`。`cif_content` 直接保存 CIF 文本，因此样本可独立读取。

**历史预期标签：**五个母体见 `examples/minimal_run/expected_parent_labels.csv`；阳性母体的候选子集见 `examples/minimal_run/expected_candidate_subset.csv`。二者摘自完整处理数据，主要用于核查表结构。

安装后可用 `mcp_config/mcp_server_relative.json` 从 MCP 客户端启动 stdio 服务；路径和 Python 解释器配置见 `docs/INSTALL.md`。HTTP 客户端先单独运行：

```bash
.venv/bin/python code/exfo_agent/server.py --transport http --port 8000
```

按 `code/skills/exfo-batch-workflow/SKILL.md` 指导，通常依次调用：① `batch_process_csv`（不钝化时用 `batch_process_csv_no_passivation`）；② `deduplicate_structures`；③ 需要 CHGNet 时调用 `batch_ml_validation`；④ `check_batch_status`。

这些标签是历史输出，供检查数据模式，**不是**已验证的端到端回归基准。路线输出受参数和依赖版本影响，CHGNet 验证也可选；目前没有干净环境的运行记录证明能逐项精确复现。`python scripts/verify_package.py` 可独立核查已发布的精简表。
