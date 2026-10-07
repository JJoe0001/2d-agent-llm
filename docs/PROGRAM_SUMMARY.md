# 程序概要

**名称：**面向二维材料发现的多路线高通量剥离工作流（Route-aware high-throughput exfoliation workflow for two-dimensional materials discovery）。

**作者：**Author A、Musen Li、Tianhao Su、Zihang Li、Shunbo Hu、Tongyi Zhang；正式发表前核对名单。

**许可：**MIT 风格学术开源许可，见 `../LICENSE`；数据来源许可另行核查。

**语言与依赖：**Python 3.10 或更新版本，原始 MCP 服务环境用 Python 3.11。主要依赖：`pymatgen`、`numpy`、`pandas`、`scipy`、`networkx`、`mcp`、`fastmcp`、`torch`、`chgnet`、`ase`、`matplotlib`、`seaborn`、`tqdm`、`joblib`、`pebble`。

**科学问题：**单一路线寻找三维母体中的 2D 候选会产生取样偏倚。程序把拓扑连接、层状超胞和混合几何／弱键剥离路线置于同一可经 MCP 调用的流程，再做去重、维度检查与 CHGNet 能量预评估。

**方法：**拓扑路线在周期图中找二维连接分量；层状路线用超胞簇尺度变化识别层状母体；混合路线结合面平均密度扫描、几何层提取与 XCP 加权弱键删除。结构生成后可合并、用 StructureMatcher 去重、经 CHGNet 松弛，再汇总母体／候选标签。LLM 仅作粗粒度工具调用，科学判据由 Python 实现。

**限制与时间：**全量运行需完整母体库、足够 CPU／GPU，以及 `chgnet`／`torch`。完整生成 CIF 不在精简包中。五母体示例主要检查输入和数据模式；超过 10⁵ 母体的运行时间由路线设置、候选数、CPU 并行度和 CHGNet 决定，不能由小样本外推。

**包含数据：**母体与候选标签、路线来源、能量汇总和最小母体样本；完整 CIF 按外部大文件处理。
