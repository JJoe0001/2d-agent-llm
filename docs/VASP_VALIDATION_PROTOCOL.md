# 返修用 VASP 验证方案

本文是待执行的计算方案，**不代表已经得到 DFT 结果**。`examples/dft_validation/` 提供 8 个体系的初始结构和 CHGNet 松弛结构，共 16 个 CIF；`structure_manifest.csv` 记录文件标识与 SHA-256。8 个体系在打包的未钝化筛选表中均标记为“已松弛且几何判为 2D”。优先从 CHGNet 松弛结构起算；若发生可疑重构，再从初始结构独立起算作对照。

## 计算对象与优先级

| 优先级 | 候选文件 | 用途 | 筛选表原子数 |
| --- | --- | --- | ---: |
| 1 | `mp-2507_2D_ortho.cif` | GaS 经典对照 | 4 |
| 1 | `mp-224_2DMatPedia.cif` | WS₂ 经典对照 | 3 |
| 1 | `mp-2222863_4607.cif` | BaYMgCuAgO₅，重点氧化物 | 10 |
| 1 | `mp-1211355_20554.cif` | KLiAl₂Si₄(O₅F)₂，重点混阴离子候选 | 20 |
| 2 | `mp-1223590_21201.cif` | KMgMn₂AlGe₃(O₅F)₂ | 20 |
| 2 | `mp-1194882_5319.cif` | BaMnPClO₄F | 36 |
| 3 | `mp-1221200_44751.cif` | Na₄Li₄MnFe₃P₄(O₄F)₄ | 72 |
| 3 | `mp-1200090_46069.cif` | Na₇TiNb₂Si₄P₂O₂₅F | 84 |

8 个体系均做固定晶胞 slab 松弛。至少对 4 个优先级 1 体系和 2 个优先级 2 体系做面内变胞松弛。GaS、WS₂和 2 个重点非经典候选需要声子计算；算力允许时再扩展。未收敛、坍塌或出现真实虚频的结果也须保留并报告。

## 输入准备

1. 记录 VASP 版本、PAW 势名称与版本或哈希、泛函、色散方案、机器与并行设置，以及全部输入输出文件。slab 与母体能量比较必须使用一致的泛函和 POTCAR 家族。不要将受许可限制的 POTCAR 上传 GitHub。
2. 以 `examples/dft_validation/prepared_vasp/<candidate>/POSCAR` 和 `KPOINTS` 作为**起始输入**。`scripts/prepare_vasp_structures.py` 从已核对哈希的松弛 CIF 出发，用 ASE 将 slab 法向调整至 c 轴，并把原先过大或倾斜的真空矢量改为垂直方向。运行前人工检查原子数、化学式、层法向、厚度与局部配位。现成 KPOINTS 只是初猜，仍须收敛测试。INCAR 和 POTCAR 要按具体体系与机器补齐。
3. 预备 POSCAR 的周期镜像之间约有 20 Å 空真空。对 4 个优先级 1 体系比较 20 Å 与 25 Å；总能差（每原子）应低于预设收敛阈值。固定晶胞与面内变胞比较时使用相同真空厚度。
4. 检查最短原子间距及形式电荷合理性。若切割导致非中性或离散的 slab，定义剥离能前必须先说明表面终止及化学势模型。

**已发现的化学计量问题：**`mp-1200090_46069.cif` 的 84 原子 slab 含 50 个 O，而与其对应的 2 个 `mp-1200090` 母体晶胞含 58 个 O。该体系不能直接用“slab 能量减母体能量”计算普通剥离能。其他 7 对在元素数目上成比例，但这只是建立剥离路径的必要条件，不足以证明路径在物理上可行。对应母体 CIF/POSCAR 在本地 `2d_agent_llm_revision_2026_10/vasp_parent_reference/`。

## 统一收敛与松弛设置

以 PBE+D3(BJ) 为基线，`IVDW=12`。至少选 1 个对照和 1 个非经典 slab 测试色散方案敏感性。起始松弛建议：`PREC=Accurate`、`LASPH=.TRUE.`、`EDIFF=1E-6` eV、`EDIFFG=-0.02` eV/Å、`IBRION=2`、`NSW=200`、`ISMEAR=0`、`SIGMA=0.05` eV。`ENCUT` 由所用 POTCAR 的最大 ENMAX 决定，可从 `1.3×max(ENMAX)` 起步并做收敛测试。若体系呈金属性，最终静态能计算改用合适的展宽并报告选择。Mn、Fe 等可能有磁性的体系用 `ISPIN=2`，为 `MAGMOM` 指定至少两组合理初态并比较。这些起始值不能替代收敛验证。

面内 k 网格从相当于 VASP `KSPACING≈0.25 Å⁻¹` 的密度开始，再测 `0.20 Å⁻¹` 或更密；孤立 slab 取 `k_z=1`。至少比较两组网格，目标总能差约低于 1–2 meV/atom，力差应足以支持松弛结论。[VASP KSPACING 文档](https://vasp.at/wiki/KSPACING)说明倒格矢约定。极性 slab 测试 `LDIPOL=.TRUE.; IDIPOL=3`，并将 `DIPOL` 中心置于层内；参见 [VASP 偶极修正文档](https://vasp.at/wiki/LDIPOL)。

**固定晶胞：**`ISIF=2`，只松弛原子位置。**面内变胞：**若 VASP 为 6.5.1 或更新版本，可在 slab 位于 a–b 平面时使用 `ISIF=3` 与 `LATTICE_CONSTRAINTS=.TRUE. .TRUE. .FALSE.`；务必从 OUTCAR 确认 c 矢量固定。[VASP 晶格约束文档](https://vasp.at/wiki/LATTICE_CONSTRAINTS)列出版本和非正交晶胞限制。若所装版本无法可靠锁定真空方向，就对面内晶格做二维应变网格扫描，例如各轴 −4%、−2%、0、+2%、+4%（必要时连角度一起扫描）；每个点用 `ISIF=2` 松弛原子，再拟合最低能量。不要把不加约束的 `ISIF=3` slab 计算称为“仅面内变胞”。

比较两种松弛的面内面积、最大键长变化、层厚变化、每原子能量差、2D 连通性及最大残余力。两组终态都要重新判定结构，不能假定 CHGNet 的 2D 标签在 DFT 后依然成立。

## 能量与声子

只有 slab 与母体**化学计量相符**时，才用一致的 VASP 设置计算母体参考能，并定义

\[
E_{\mathrm{exfol}}/A=(E_{\mathrm{slab}}-nE_{\mathrm{bulk,formula}})/A ,
\]

其中 `n` 是 slab 所含母体化学式单元数，`A` 为面内面积。说明 `E_slab` 是否对应单层以及表面数；对称双表面解理能应以 `2A` 为分母。化学计量不符时，需要给出质量守恒反应，或在明确化学势条件下定义巨势差，只能在这些假设下称为解理／形成能估计。MP 母体的 `E_hull` 不是 2D 凸包能；如果没有同一泛函下的竞争 2D 相集合，不报告数值“2D hull 稳定性”。

声子计算前更严格地松弛 DFT 结构，建议 `EDIFF≤1E-7`、`EDIFFG≤-0.01` eV/Å。使用力常数能在边界前衰减的面内超胞，并比较至少两种超胞大小。VASP `IBRION=6` 可求有限差分力常数；原胞计算只给出 Γ 点振动，色散需要超胞，见 [VASP 有限差分声子指南](https://vasp.at/wiki/Phonons_from_finite_differences)。对虚频检查 k 网格、真空、位移量、超胞大小和声学求和规则；若为真实不稳定模态，必须报告。

## 返还给论文整合的文件

每个候选、每种松弛方式在 `examples/dft_validation/results_template.csv` 填一行，并提供 `INCAR`、`KPOINTS`、`POSCAR`、`CONTCAR`、`OUTCAR`、`vasprun.xml`、声子力常数／图，以及母体参考计算的输入输出。只有核对这些文件后才能在论文和审稿回复中填写数值。失败或未收敛作业也要写入同一结果表，附原因。
