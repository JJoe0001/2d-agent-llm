# 尚未嵌入的大型文件

以下生成物目前不在 GitHub 包中，也尚无公开下载地址：完整 Materials Project 母体 CIF、分路线生成 CIF、合并后的去重前 CIF、去重后唯一 2D CIF，以及单独归档时的 CHGNet 松弛结构。

建议的外部归档目录：

```text
external_archive/
  parent_cifs/
  route_outputs/
    topological/
    layered/
    hybrid/
  merged_candidates/
  unique_2d_candidates/
  relaxed_candidates/
  checksums/
```

`../parents/`、`../final_2d_candidates/`、`../computed_results/` 中的精简表保留 ID 与标签，但无法恢复每个结构。正式归档应提供清单，把候选映射到母体、路线、松弛状态和校验和；存档后再补充核验过的 URL 与 DOI。
