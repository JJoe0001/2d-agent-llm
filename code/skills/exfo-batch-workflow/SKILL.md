---
name: exfo-batch-workflow
description: "在 exfo_agent MCP 服务已加载、需要按顺序执行 CSV 提取、可选无钝化提取、去重、ML 验证或状态检查时使用。"
---

# Exfo 批处理工作流

## 用途

仅在 `exfo_agent/server.py` 的 MCP 服务已加载后使用。此文件不替代 MCP 工具，而是说明模型应按什么顺序调用工具、采用什么输出约定。默认项目根目录为 `exfo_agent`。它是当前复现指引，**不应称作历史生产提示词的逐字记录**。

## 工具顺序

1. 选择提取方式。默认 `batch_process_csv`；仅在用户明确需要未钝化表面时选 `batch_process_csv_no_passivation`。
2. 先运行提取。始终写出提取 CSV 和汇总 CSV；文件名带本次运行标识，便于复现。
3. 除非用户明确要原始候选，否则调用 `deduplicate_structures` 去重。去重成功后将去重 CSV 用作 ML 输入。
4. 用户需要机器学习验证时，调用 `batch_ml_validation` 并指定阈值。
5. 提取后或完整流程后，调用 `check_batch_status` 读取汇总状态；另需核查实际输出文件，不能只相信“completed”消息。

## 预期 MCP 调用

一般批次：

1. `batch_process_csv(input_csv_path, save_csv_path, summary_path, top_k)`
2. `deduplicate_structures(input_csv=save_csv_path, output_csv=dedup_csv)`
3. `batch_ml_validation(input_csv=dedup_csv_or_extraction_csv, save_csv=ml_csv, threshold=...)`
4. `check_batch_status(summary_csv=summary_path)`

无钝化批次：`batch_process_csv_no_passivation` → `deduplicate_structures` → `batch_ml_validation` → `check_batch_status`。

单个 CIF：优先 `smart_exfoliate_single`；仅在用户要求诊断细节或指定路线时调用底层工具。

## 使用规则

- 输出文件放在同一运行目录，或使用一致的运行前缀。
- 为节省 CHGNet 计算成本，优先去重再验证。
- 必需输入缺失时立即报错；核查输出和汇总表是否真正生成。
- 常规执行以 MCP 工具为入口；只有调试代码本身时才直接运行辅助脚本。
- 仅改执行参数时不要改 `tools/` 的算法内部；算法／ML 逻辑变化才改源码。
- 用户要求“运行工作流”时，明确选定并报告输出路径。

参考：`references/pipeline-map.md`。
