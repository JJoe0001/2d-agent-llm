# 数据可用性与来源

## 母体和候选结构

母体来自 Materials Project，筛选条件为能量高于凸包不超过 0.5 eV/atom。`data/parents/parent_level_metadata.csv.gz` 含 143,259 个母体的 ID、MP 物理量、路线标志、候选数量和能量汇总；没有逐个打包全部母体 CIF。`examples/minimal_run/sample_parent_input.csv` 自带 5 个母体的 CIF 文本。

流程生成 76,852 个去重前候选 CIF、73,105 个去重后候选。`data/final_2d_candidates/final_2d_candidates.csv.gz` 含候选文件名、母体 ID、路线来源、CHGNet 形成能、松弛与验证状态、化学式及去重状态。

## 包中已有结果

- `data/computed_results/parent_exfoliability_labels.csv.gz` 与 `dataset_summary.json`：母体可剥离二元标签、路线标签、候选数和总计。
- `data/route_outputs/merged_candidate_manifest.csv.gz`：76,852 个去重前文件名与路线来源。
- `data/dimensionality/no_pass_dimensionality_post_ml.csv.gz`、`passivated_dimensionality_post_ml.csv.gz`：73,105 个唯一候选的 CHGNet 后形貌判定。
- `data/computed_results/revision_screening_summary.json`：由 `scripts/revision_audit.py` 重算，定义见 `docs/REVISION_FINDINGS.md`。
- `examples/dft_validation/`：8 对初始／松弛结构，共 16 个衍生 CIF；不是全库，不含 DFT 输出。
- `data/computed_results/`：48 母体、336 条平面间隙敏感性记录及两个混合路线复算实例。母体 CIF 仅以 MP ID 和 SHA-256 引用，未在此再分发。

## 尚缺数据与归档

完整母体 CIF、各路线及去重后候选 CIF、松弛 CIF 均不能通过此仓库取得；目前没有公开归档 URL 或 DOI。计划目录见 `data/external_large_files/README.md`。`dataset_summary.json` 中 `candidate_cif_missing: 0` 和 `parent_cif_missing: 0` 是对原始本地环境计算，**不表示**这些 CIF 已上传 GitHub。

完整分路线结构、绘图输入表与脚本、历史 LLM 工具调用轨迹尚未开放，因此无法单靠本仓库重现论文全部图。返修提交前应将缺失结构与绘图输入存入持久数据仓库，在此加入有版本的 URL／DOI，并与论文 Data Availability Statement 一致。本页不能代替已公开的数据集。
