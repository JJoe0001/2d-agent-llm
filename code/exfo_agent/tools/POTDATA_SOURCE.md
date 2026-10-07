# XCP 元素对参数表来源

`POTDATA_morse_yukawa_2025` 与 Barnowsky、Friedrich 发布的 [FINDSLAB v1.1](https://doi.org/10.14278/rodare.4687) 压缩包内同名文件逐字节一致。两者的 SHA-256 均为：

`213e68e6dc87dad20c5b65053f25df6c63c423137e307b0914b5a7d86eb7dc91`

请引用 Barnowsky、Timm、Friedrich 的 [XCP 原方法论文](https://doi.org/10.1038/s41467-026-76806-8) 和上述 FINDSLAB v1.1 软件归档。原论文说明五个元素对参数根据 AFLOW-ICSD 中的 DFT 力和能量拟合，本项目没有重新拟合这些数值。原归档的许可文本保存在同目录 `POTDATA_LICENSE.txt`，不由仓库根目录的软件 MIT 许可替代。

本项目 `xcp_potential.py` 的 Python 实现对论文显示的 Morse 势减去常数 `D`，使远距离势能为零。跨元素对的绝对势能排序及固定阈值因此不能直接视为 FINDSLAB 原实现的结果；涉及这一点的科学结论应以本项目实际代码和输出为准。
