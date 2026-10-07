# 二维材料发现的多路线高通量剥离工作流

本仓库包含论文《A multi-route high-throughput workflow for 2D materials discovery》配套的代码、处理表及部分结构归档，正用于向 *Digital Discovery* 提交返修。包内有 MCP 服务、三条剥离路线、工具调用说明、处理标签、五母体示例及 73,105 个去重候选的 CIF 归档。完整历史母体、去重前分路线结构与部分绘图输入尚未公开；准确范围见[数据可用性说明](docs/DATA_AVAILABILITY.md)。

## 目录

```text
code/exfo_agent/                  MCP 服务与剥离路线源码
code/skills/exfo-batch-workflow/  面向工具调用的流程说明
data/parents/                     母体元数据及 MP 物理量
data/final_2d_candidates/         去重后候选与 CHGNet 结果
data/computed_results/            母体标签、审计及敏感性结果
data/dimensionality/              钝化与未钝化的形貌标签
data/route_outputs/               去重前路线来源清单
data/external_large_files/        候选及松弛结构归档、逐文件校验清单
docs/                             安装、方法审计、VASP 等中文说明
examples/minimal_run/             五母体样本与历史预期标签
examples/dft_validation/          8 对结构与预备 VASP 输入
scripts/                          包核验、审计与复算脚本
```

## 程序入口与路线

MCP 服务入口：`code/exfo_agent/server.py`。拓扑路线见 `tools/literature_routes/aiida_exfo_test.py`；层状路线见 `tools/literature_routes/exfo_2dmatpedia.py`；混合路线见 `tools/workflow.py`、`planar_gap.py`、`bond_del.py` 与 `xcp_potential.py`。上述相对路径均位于 `code/exfo_agent/` 下。LLM 负责批次级工具调用；材料算法在 Python 中执行，详见 [LLM 代码定位](docs/LLM_CODE_MAP.md)。

## 核心数据

- `data/parents/parent_level_metadata.csv.gz`：母体信息、路线标志、候选数与能量汇总。
- `data/final_2d_candidates/final_2d_candidates.csv.gz`：73,105 条去重候选及松弛、CHGNet 结果。
- `data/computed_results/parent_exfoliability_labels.csv.gz`：143,259 个 MP 母体的可剥离与路线标签。
- `data/computed_results/dataset_summary.json`：总体数量汇总。
- `data/route_outputs/merged_candidate_manifest.csv.gz`：76,852 条去重前候选与路线。
- `data/dimensionality/*.csv.gz`：所有唯一候选的形貌判定。
- `data/computed_results/revision_screening_summary.json`：可重算的返修审计，定义见[审计结果](docs/REVISION_FINDINGS.md)。
- `data/external_large_files/`：去重候选、未钝化及钝化 CHGNet 松弛 CIF 归档，附逐文件和整包 SHA-256；见[归档说明](data/external_large_files/README.md)。

完整母体、去重前分路线 CIF、中间绘图表及历史模型调用轨迹仍未提供。`dataset_summary.json` 的 `candidate_cif_missing: 0` 是在原始本地库中计算，不能代替仓库实际内容审计；见[数据范围](docs/DATA_AVAILABILITY.md)。

## 示例与核验

`examples/minimal_run/sample_parent_input.csv` 是示例输入，`expected_parent_labels.csv` 与 `expected_candidate_subset.csv` 是历史预期标签。环境与限制见[安装](docs/INSTALL.md)和[运行示例](docs/RUN_EXAMPLE.md)。运行 `python scripts/verify_package.py` 核查校验和与核心表行数。

DFT 准备见[VASP 方案](docs/VASP_VALIDATION_PROTOCOL.md)、`examples/dft_validation/` 中的配对 CIF、POSCAR 与 KPOINTS；尚无 DFT 结果。其余返修资料：

- [参数审计](docs/PARAMETER_AUDIT.md)、[扩展参数敏感性复算](docs/参数敏感性_扩展复算_中文.md)、[混合路线实例](docs/HYBRID_WORKED_EXAMPLES.md)。
- [编排故障审计](docs/AGENT_FAILURE_AUDIT.md)与[LLM 代码及证据](docs/LLM_CODE_MAP.md)。
- [外部数据库基准方案](docs/DATABASE_BENCHMARK_PROTOCOL.md)。

## 许可

软件许可见 `LICENSE`。它不自动覆盖来自 Materials Project 的结构及其衍生数据；部分 GNoME 来源记录受非商业许可约束，详见[归档说明](data/external_large_files/README.md)。势参数的原始来源及文件校验见[参数审计](docs/PARAMETER_AUDIT.md)。
