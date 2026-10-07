# Exfo 批处理流程映射

项目根目录：`exfo_agent`。MCP 服务入口：`exfo_agent/server.py`。

## 输入 CSV 列

提取阶段最低需要 `original_file`、`formula`、`cif_content`；可继续携带 `formation_energy`、`ehull`、`spacegroup` 等元数据。

## 阶段与工具

1. 单结构主入口：`smart_exfoliate_single`。
2. 带钝化提取：`batch_process_csv`。
3. 无钝化提取：`batch_process_csv_no_passivation`。
4. 去重：`deduplicate_structures`。
5. 机器学习验证：`batch_ml_validation`。
6. 汇总状态：`check_batch_status`。

典型输出名为 `*_02_csv_extraction.csv`、`*_02_csv_summary.csv`、`*_02_candidates_unique.csv`、`*_03_ml_validation.csv`。

实际可调用工具以 `server.py` 注册的 MCP 工具为准；本指引不是替代运行时。`server.py` 对进程型 MCP 客户端默认使用 stdio；单独管理 HTTP 服务时使用 `--transport http --port 8000`。
