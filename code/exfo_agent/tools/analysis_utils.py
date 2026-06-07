"""
二维材料高通量筛选结果分析工具

提供真2D维度鉴定和数据可视化功能
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Tuple
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pymatgen.core import Structure
from collections import Counter


def _calculate_vacuum_and_thickness(structure: Structure) -> Dict[str, float]:
    """
    计算结构在三个方向上的真空层和厚度（完美兼容六方/倾斜晶系）
    """
    lattice = structure.lattice
    frac_coords = structure.frac_coords
    results = {}

    # 遍历 a, b, c 三个方向
    for axis_idx, axis_name in enumerate(['a', 'b', 'c']):
        # 提取该方向的分数坐标并排序
        coords_1d = sorted(frac_coords[:, axis_idx])

        # 计算相邻原子间的间距（分数坐标）
        gaps = []
        for i in range(len(coords_1d)):
            next_i = (i + 1) % len(coords_1d)
            if next_i == 0:
                # 考虑周期性边界条件：最后一个原子到第一个原子的跨越距离
                gap = 1.0 - coords_1d[i] + coords_1d[0]
            else:
                gap = coords_1d[next_i] - coords_1d[i]
            gaps.append(gap)

        max_gap_frac = max(gaps) if gaps else 0.0

        # 🌟 核心修复：使用晶面间距 (d_hkl) 替代晶格矢量长度，防止斜晶胞厚度高估
        hkl = [0, 0, 0]
        hkl[axis_idx] = 1
        dir_length = lattice.d_hkl(hkl)

        max_gap_angstrom = max_gap_frac * dir_length
        thickness_angstrom = (1.0 - max_gap_frac) * dir_length

        results[f'{axis_name}_vacuum'] = max_gap_angstrom
        results[f'{axis_name}_thickness'] = thickness_angstrom

    return results


def filter_true_2d_impl(
    input_csv: str,
    output_csv: str,
    output_dir: str = "true_2d_cifs"
) -> str:
    """【几何维度提纯工具】鉴定并过滤真正的二维材料"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv, on_bad_lines='skip', engine='python')
    df_valid = df[df['optimized_cif'].notna() & (df['optimized_cif'] != '')].copy()

    stats = {
        'total': len(df),
        'has_cif': len(df_valid),
        'no_cif': len(df) - len(df_valid),
        'in_plane_fracture': 0,  
        'thick_or_curled': 0,     
        'parse_error': 0,         
        'true_2d': 0              
    }

    true_2d_rows = []

    for idx, row in df_valid.iterrows():
        cif_string = str(row['optimized_cif'])
        try:
            structure = Structure.from_str(cif_string, fmt='cif')
            metrics = _calculate_vacuum_and_thickness(structure)

            # 判据1: 检查 a, b 方向的真空层 (排除一维纳米带和零维团簇)
            if metrics['a_vacuum'] > 4.0 or metrics['b_vacuum'] > 4.0:
                stats['in_plane_fracture'] += 1
                continue

            # 判据2: 检查 c 方向的厚度 (排除严重起皱或卷曲)
            if metrics['c_thickness'] > 8.5:
                stats['thick_or_curled'] += 1
                continue

            stats['true_2d'] += 1

            row_dict = row.to_dict()
            row_dict['z_thickness_A'] = round(metrics['c_thickness'], 3)
            true_2d_rows.append(row_dict)

            # 🌟 修复列名映射
            original_file = str(row.get('original_file', f'struct_{idx}')).replace("/", "_").replace("\\", "_")
            formation_energy = row.get('formation_energy_eV', 0.0)
            z_thickness = metrics['c_thickness']

            cif_filename = f"{original_file}_E{formation_energy:.3f}_T{z_thickness:.2f}.cif"
            cif_path = output_path / cif_filename

            with open(cif_path, 'w') as f:
                f.write(cif_string)

        except Exception as e:
            stats['parse_error'] += 1
            continue

    if true_2d_rows:
        pd.DataFrame(true_2d_rows).to_csv(output_csv, index=False)
    else:
        pd.DataFrame().to_csv(output_csv, index=False)

    report = f"""
🔬 二维材料几何维度鉴定报告
{'='*60}
📊 数据统计:
  总结构数:           {stats['total']:>6}
  有效CIF结构:        {stats['has_cif']:>6}
  缺失CIF:            {stats['no_cif']:>6}

🚫 淘汰原因统计:
  面内断裂 (a/b真空层>4.0Å):  {stats['in_plane_fracture']:>6}
  厚度过大/卷曲 (c厚度>8.5Å): {stats['thick_or_curled']:>6}
  CIF解析失败:                {stats['parse_error']:>6}

✅ 最终结果:
  真正的2D材料:       {stats['true_2d']:>6}
  通过率:             {stats['true_2d']/stats['has_cif']*100 if stats['has_cif'] > 0 else 0:.1f}%

💾 输出文件:
  真2D名单: {output_csv}
  CIF实体:  {output_dir}/ ({stats['true_2d']} 个文件)
{'='*60}
"""
    return report


def visualize_2d_results_impl(
    input_csv: str,
    output_dir: str = "analysis_plots"
) -> str:
    """【数据可视化工具】生成二维材料筛选结果的统计图表"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv, on_bad_lines='skip', engine='python')

    # 🌟 核心修复：跨平台中文字体支持
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Microsoft YaHei', 'SimHei', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False
    sns.set_theme(style="whitegrid", font=plt.rcParams['font.sans-serif'])
    plt.rcParams['figure.dpi'] = 300

    # ========== 图表1: 形成能分布直方图 ==========
    energy_col = 'formation_energy_eV'
    if energy_col in df.columns:
        energies = pd.to_numeric(df[energy_col], errors='coerce').dropna()
        energies = energies[(energies != 999.0) & (energies < 5.0)]

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.histplot(energies, bins=50, kde=True, color='steelblue', ax=ax)
        ax.axvline(x=0.05, color='red', linestyle='--', linewidth=2, label='热力学稳定阈值 (0.05 eV/atom)')
        
        ax.set_xlabel('形成能 (eV/atom)', fontsize=12)
        ax.set_ylabel('结构数量', fontsize=12)
        ax.set_title('二维材料形成能分布', fontsize=14, fontweight='bold')
        ax.legend()
        
        energy_plot_path = output_path / 'energy_distribution.png'
        plt.tight_layout()
        plt.savefig(energy_plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        energy_stats = f"形成能统计: 均值={energies.mean():.4f}, 中位数={energies.median():.4f}"
    else:
        energy_stats = f"未找到 {energy_col} 列"
        energy_plot_path = None

    # ========== 图表2: 元素频率排行榜 ==========
    if 'optimized_cif' in df.columns:
        element_counter = Counter()
        for cif_string in df['optimized_cif'].dropna():
            try:
                structure = Structure.from_str(str(cif_string), fmt='cif')
                for element in structure.composition.elements:
                    element_counter[str(element)] += 1
            except:
                continue

        top_elements = element_counter.most_common(25)
        if top_elements:
            elements, counts = zip(*top_elements)
            fig, ax = plt.subplots(figsize=(12, 8))
            sns.barplot(x=list(counts), y=list(elements), palette='viridis', ax=ax)
            
            ax.set_xlabel('出现次数', fontsize=12)
            ax.set_ylabel('元素', fontsize=12)
            ax.set_title('元素出现频率排行榜 (Top 25)', fontsize=14, fontweight='bold')
            
            for i, (elem, count) in enumerate(top_elements):
                ax.text(count, i, f' {count}', va='center', fontsize=9)
                
            element_plot_path = output_path / 'element_frequency.png'
            plt.tight_layout()
            plt.savefig(element_plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            element_stats = f"元素统计: 共发现 {len(element_counter)} 种元素，最常见: {top_elements[0][0]}"
        else:
            element_stats = "未能提取元素信息"
            element_plot_path = None
    else:
        element_stats = "未找到 optimized_cif 列"
        element_plot_path = None

    report = f"""
📊 数据可视化报告
{'='*60}
✅ 生成的图表:
"""
    if energy_plot_path:
        report += f"  1. 形成能分布图: {energy_plot_path}\n     {energy_stats}\n\n"
    if element_plot_path:
        report += f"  2. 元素频率图:   {element_plot_path}\n     {element_stats}\n\n"
        
    report += f"💾 所有图表已保存到: {output_dir}/\n{'='*60}"
    return report