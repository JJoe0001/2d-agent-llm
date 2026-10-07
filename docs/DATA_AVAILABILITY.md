# 数据可用性与来源

## 母体和候选结构

母体来自 Materials Project，筛选条件为能量高于凸包不超过 0.5 eV/atom。`data/parents/parent_level_metadata.csv.gz` 含 143,259 个母体的 ID、MP 物理量、路线标志、候选数量和能量汇总；没有逐个打包全部母体 CIF。`examples/minimal_run/sample_parent_input.csv` 自带 5 个母体的 CIF 文本。当前结构可用个人 MP API 密钥重新获取：`pip install mp-api`，设置 `MP_API_KEY` 后执行 `python scripts/download_parent_cifs.py --output-dir data/raw_parent_cifs`。脚本按 ID 分批下载，并写出逐文件 SHA-256 和失败清单；MP 当前结构可能不同于历史生产快照，旧 ID 可能需要 tasks API。

流程生成 76,852 个去重前候选 CIF、73,105 个去重后候选。`data/final_2d_candidates/final_2d_candidates.csv.gz` 含候选文件名、母体 ID、路线来源、CHGNet 形成能、松弛与验证状态、化学式及去重状态。

## 包中已有结果

- `data/computed_results/parent_exfoliability_labels.csv.gz` 与 `dataset_summary.json`：母体可剥离二元标签、路线标签、候选数和总计。
- `data/route_outputs/merged_candidate_manifest.csv.gz`：76,852 个去重前文件名与路线来源。
- `data/dimensionality/no_pass_dimensionality_post_ml.csv.gz`、`passivated_dimensionality_post_ml.csv.gz`：73,105 个唯一候选的 CHGNet 后形貌判定。
- `data/computed_results/revision_screening_summary.json`：由 `scripts/revision_audit.py` 重算，定义见 `docs/REVISION_FINDINGS.md`。
- `examples/dft_validation/`：8 对初始／松弛结构，共 16 个衍生 CIF；不是全库，不含 DFT 输出。
- `data/computed_results/`：200 父体的初始判维与几何切片敏感性、48 父体高斯宽度复算、9 父体断键阳性富集检查、500 候选去重容差压力测试、500 原子上限审计及两个混合路线实例。母体 CIF 仅以 MP ID 和 SHA-256 引用，未在此再分发。
- `data/external_large_files/`：73,105 个去重初始候选 CIF、69,624 个未钝化 CHGNet 松弛 CIF、64,297 个钝化 CHGNet 松弛 CIF 的三个压缩归档，分别附逐成员 SHA-256 清单和归档摘要。下载、核验和来源限制见同目录 `README.md`。

## 尚缺数据与归档

完整母体 CIF、去重前全部 76,852 个候选的分路线原始 CIF 仍未随仓库发布。去重后候选和成功输出的两组 CHGNet 松弛 CIF 现在可通过 GitHub 分支下载；但尚无独立的长期数据仓库 DOI。`dataset_summary.json` 中 `candidate_cif_missing: 0` 和 `parent_cif_missing: 0` 是对原始本地环境计算，不能据此推断所有历史输入及中间结果均已公开。

完整分路线结构、部分绘图输入表与脚本、历史 LLM 工具调用轨迹尚未开放，因此无法单靠本仓库重现论文全部图。返修提交前应将这些缺失数据和已发布的 CIF 归档存入持久数据仓库，在此加入有版本的 URL／DOI，并与论文 Data Availability Statement 一致。父体来自 MP，且部分 GNoME 来源记录有单独的非商业许可；请勿把软件 MIT 许可解释为结构数据的统一许可。
