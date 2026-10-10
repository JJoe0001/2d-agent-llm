# 图源数据归档说明

`historical_figure_source_tables_and_scripts.tar.gz` 收录此前论文作图目录中 8 份处理后 CSV 和 8 份 Python 绘图脚本。`historical_figure_source_manifest.json` 记录每个成员的大小与 SHA-256。该归档用于核对历史图的数据来源；部分旧脚本保留原工作站 `/Volumes/J/...` 绝对路径，不能直接视为当前返修图的可运行生成器。

8 cm × 4 cm 目录图由 `scripts/make_toc_graphic.py` 根据 `data/computed_results/revision_screening_summary.json` 生成，PDF 见 `docs/figures/toc_8x4cm.pdf`。原图 1 保持不变。返修图 2 的路线与筛选漏斗由 `scripts/make_revision_figure.py`、`data/computed_results/revision_screening_summary.json` 和 `data/computed_results/parent_exfoliability_labels.csv.gz` 生成。其余旧图与历史归档的对应关系仍需逐图核对；在完成前不宣称所有原图都可一键重绘。

核验历史归档：

```bash
python scripts/verify_figure_source_archive.py
```

这些文件是项目计算衍生表，不代表重新分发 Materials Project 或其他外部数据库的原始结构。完整父体 CIF、去重前分路线 CIF 和第三方参考库结构另按各自来源说明处理。
