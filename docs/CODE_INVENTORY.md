# 剥离策略代码清单

生成日期：2026 年 4 月 26 日

下表是历史源码打包快照，路径与大小不代表当前仓库实际清单。当前文件及哈希以 `FILE_MANIFEST.tsv` 和 `SHA256SUMS` 为准，可运行 `python scripts/verify_package.py` 核验。当前 MCP 模板是 `mcp_config/mcp_server_relative.json`；服务默认使用 stdio，也可选 HTTP。

| 打包路径 | 来源说明 | 用途 | 字节数 |
|---|---|---|---:|
| `exfo_agent/__init__.py` | 打包的程序文件 | MCP 服务／包元数据 | 0 字节 |
| `exfo_agent/server.py` | 打包的程序文件 | MCP 服务入口 | 15,006 字节 |
| `exfo_agent/pyproject.toml` | 打包的程序文件 | 包元数据 | 343 字节 |
| `mcp_config/.mcp.json` | 打包的配置 | MCP 启动配置 | 302 字节 |
| `exfo_agent/core/__init__.py` | 打包的程序文件 | 核心运行依赖 | 0 字节 |
| `exfo_agent/core/config.py` | 打包的核心模块 | 核心运行依赖 | 1,120 字节 |
| `exfo_agent/core/store.py` | 打包的核心模块 | 核心运行依赖 | 1,666 字节 |
| `exfo_agent/core/utils.py` | 打包的核心模块 | 核心运行依赖 | 18,704 字节 |
| `exfo_agent/tools/__init__.py` | 打包的程序文件 | 工具包标记 | 0 字节 |
| `exfo_agent/tools/parse.py` | 打包的工具模块 | CIF 解析依赖 | 5,528 字节 |
| `exfo_agent/tools/debug_utils.py` | 打包的工具模块 | 路线调试工具 | 5,056 字节 |
| `exfo_agent/tools/dimensionality.py` | 打包的工具模块 | 拓扑维度判定 | 3,633 字节 |
| `exfo_agent/tools/route.py` | 打包的工具模块 | 路线辅助函数 | 2,763 字节 |
| `exfo_agent/tools/planar_gap.py` | 打包的工具模块 | 几何切层路线 | 5,682 字节 |
| `exfo_agent/tools/extract_layer.py` | 打包的工具模块 | 几何层提取 | 5,608 字节 |
| `exfo_agent/tools/bond_del.py` | 打包的工具模块 | 断键路线 | 21,305 字节 |
| `exfo_agent/tools/xcp_potential.py` | 打包的工具模块 | XCP 势辅助函数 | 6,510 字节 |
| `exfo_agent/tools/workflow.py` | 打包的工具模块 | 混合路线流程 | 7,014 字节 |
| `exfo_agent/tools/batch_utils.py` | 打包的工具模块 | 混合路线批处理封装 | 27,954 字节 |
| `exfo_agent/tools/batch_utils_no_passivation.py` | 打包的工具模块 | 无钝化批处理封装 | 17,207 字节 |
| `exfo_agent/tools/surface_passivation.py` | 打包的工具模块 | 表面钝化 | 27,036 字节 |
| `exfo_agent/tools/literature_methods.py` | 打包的工具模块 | 两条文献路线的封装 | 10,809 字节 |
| `exfo_agent/tools/POTDATA_morse_yukawa_2025` | 打包的数据文件 | XCP 参数表 | 1,044,302 字节 |
| `exfo_agent/tools/literature_routes/__init__.py` | 生成文件 | package marker for 打包的文献路线s | 0 字节 |
| `exfo_agent/tools/literature_routes/aiida_exfo_test.py` | 打包的文献路线 | 拓扑路线实现 | 10,788 字节 |
| `exfo_agent/tools/literature_routes/exfo_2dmatpedia.py` | 打包的文献路线 | 层状超胞路线实现 | 10,517 字节 |
| `skills/exfo-batch-workflow/SKILL.md` | 打包的技能 | 项目侧 Codex 技能封装 | 2,782 字节 |
| `skills/exfo-batch-workflow/agents/openai.yaml` | 打包的技能 | agent 配置 | 278 字节 |
| `skills/exfo-batch-workflow/references/pipeline-map.md` | 打包的技能参考 | 批处理流程图 | 1,092 字节 |
| `installed_skill_snapshot/exfo-batch-workflow/SKILL.md` | 打包的快照 | 已安装技能快照 | 2,782 字节 |
| `installed_skill_snapshot/exfo-batch-workflow/agents/openai.yaml` | 打包的快照 | installed agent 配置 | 278 字节 |
| `installed_skill_snapshot/exfo-batch-workflow/references/pipeline-map.md` | 打包的快照 | 已安装流程图 | 1,092 字节 |
| `exfo_agent/tools/deduplicate_utils.py` | 打包的工具模块 | 结构去重（StructureMatcher） | 8,979 字节 |
| `exfo_agent/tools/analysis_utils.py` | 打包的工具模块 | 真 2D 几何筛选与可视化 | 8,940 字节 |
| `exfo_agent/tools/ml_ops.py` | 打包的工具模块 | CHGNet 松弛与形成能评估 | 7,147 字节 |
