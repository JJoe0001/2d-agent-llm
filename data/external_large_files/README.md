# 衍生结构归档与母体重新获取

此目录提供论文筛选产生的三组 CIF 归档。它们是候选结构数据，**不是 DFT 稳定结构或新的数据库相鉴定**。归档与逐文件清单的 SHA-256、大小和记录数见 [`archive_summary.json`](archive_summary.json)。

| 归档 | CIF 数 | 含义 |
|---|---:|---|
| `unique_candidate_cifs.tar.gz` | 73,105 | 跨路线去重后的初始候选 |
| `relaxed_unpassivated_cifs.tar.gz` | 69,624 | 成功输出未钝化 CHGNet 松弛结构的记录 |
| `relaxed_passivated_cifs.tar.gz` | 64,297 | 成功输出钝化 CHGNet 松弛结构的记录 |

每个归档都有同名前缀的 `*_manifest.tsv`，逐条给出成员路径、大小和 SHA-256。归档成员已逐个核验；从 GitHub 下载后可先运行 `shasum -a 256 *.tar.gz *_manifest.tsv`，与摘要核对，再用 `tar -tzf unique_candidate_cifs.tar.gz | head` 查看成员。候选元数据、来源路线与形貌标签分别在 `../final_2d_candidates/`、`../route_outputs/` 和 `../dimensionality/`。69,624 是松弛成功数；其中同时保持未钝化二维形貌的记录数为 68,089，不能把两个口径混同。

完整母体 CIF **不在本归档**。可从 `../parents/parent_level_metadata.csv.gz` 读取 143,259 个 MP ID，用仓库根目录的 `scripts/download_parent_cifs.py` 和自己的 Materials Project API 密钥重新下载当前 API 可用的结构；运行方法见 [`docs/DATA_AVAILABILITY.md`](../../docs/DATA_AVAILABILITY.md)。MP 数据库会更新，下载的结构不保证与历史生产快照完全相同。对于旧 ID，可能需要按 MP 文档通过 tasks API 追溯。原始 LLM 客户端调用轨迹也未保存。

## 来源与使用范围

父体结构源于 Materials Project；衍生 CIF 经本项目切片、钝化或 CHGNet 松弛产生。请引用 Materials Project 和本文，并标明这些文件是变换后的结构。MP 官方文档说明部分 GNoME 来源记录采用 BY-NC 许可；本归档尚未完成逐母体来源归类，因此不可把根目录的软件 `LICENSE` 自动套用于这些数据，也不应假定整包可商业再利用。XCP 参数表的另一个上游来源单独见 [`docs/PARAMETER_AUDIT.md`](../../docs/PARAMETER_AUDIT.md)。

GitHub 提供文件访问与校验，不提供论文编辑部要求的**持久数据 DOI**。正式提交时仍须建立有版本的长期数据存档，给出 DOI，并使论文及单独的 Data Availability Statement 完全一致。
