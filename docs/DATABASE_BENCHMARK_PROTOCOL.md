# 三库结构恢复率的定版比对方案

2DMatPedia v3 和 MC2D 2022.84 的逐结构结果、定版来源、分母和哈希见[数据库结构比对中文报告](数据库结构比对_中文.md)。基线比较使用 73,105 份去重后的**初始候选 CIF**，对照外部库的优化结构；不把化学式重合等同结构恢复，也不把未匹配称作新材料。C2DB 尚无定版全量结构文件，故第三库恢复率暂不能计算。

## 参考集与当前结果

| 参考集 | 定版文件 | 可解析记录 | 结构匹配 |
|---|---|---:|---:|
| 2DMatPedia | Figshare v3 JSON Lines，DOI 10.6084/m9.figshare.7699910.v3 | 6,351 | 526（8.28%） |
| MC2D | Materials Cloud 2022.84 优化结构 CIF ZIP，DOI 10.24435/materialscloud:36-nd | 2,742 | 271（9.88%） |
| C2DB | 官方完整 ASE c2db.db 定版导出，待取得 | 待定 | 待定 |

[2DHub 官方页面](https://www.2dhub.org/c2db/c2db.html)注明完整 C2DB 数据需申请，并列出各次版本扩充。网页实时检索的条目数不能代替一次可核验的全量结构导出。取得 ASE 数据库后记录下载日期、提供方版本、文件 SHA-256、数据库总行数、可解析结构数和解析失败明细；外部文件不未经许可重新分发。

## 统一匹配规则

1. 以约化化学式分组，最长晶格矢量视为真空轴，将切片居中且真空长度设为 25 Å。
2. 面内面积按化学式单元归一化，相对差不超过 5%；层厚相对差不超过 20%。
3. 对每条参考结构最多测试 25 个几何接近候选，用 `StructureMatcher(primitive_cell=True, scale=True, attempt_supercell=False, allow_subset=False, ltol=0.2, stol=0.3, angle_tol=5°)`。
4. 每条参考记录只赋予最高匹配等级：`structure_match`、`formula_and_geometry_match`、`formula_only_match` 或 `no_formula_match`。结构恢复率分母为可解析参考结构数，逐条 CSV 和汇总 JSON 均保留。
5. 联合放宽面积、层厚和候选测试上限的已完成结果另报，不与基线混用。下一步再分别测试单个参数和 CHGNet 松弛后结构。

C2DB 文件取得后运行：

```bash
python scripts/revision_external_match.py --dataset C2DB --reference /path/to/pinned/c2db.db --candidate-archive data/external_large_files/unique_candidate_cifs.tar.gz --candidate-table data/final_2d_candidates/final_2d_candidates.csv.gz --output-prefix data/computed_results/C2DB_VERSION_match
```

正式结果需要填写真实版本替换 `VERSION`，并核对结构恢复率、解析失败数及各级匹配加总。不同库之间若要求统计去重后的并集，须先按跨库结构匹配建立等价类；各库的恢复率不能直接相加。
