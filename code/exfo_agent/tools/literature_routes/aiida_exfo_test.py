import pandas as pd
import numpy as np
import networkx as nx
import logging
import os
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
from pymatgen.core import Structure, Lattice
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

# 忽略 pymatgen 解析带来的海量底层警告
warnings.filterwarnings("ignore")

# ==========================================
# 1. 日志系统配置
# ==========================================
def setup_logger(log_filename="screening_process.log"):
    logger = logging.getLogger("2D_Screening")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(log_filename, mode='w', encoding='utf-8')
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

# ==========================================
# 2. 剥离辅助函数：提取二维原胞并加真空层
# ==========================================
def extract_monolayer(structure: Structure, layer_indices: list, vacuum_angstroms=20.0) -> Structure:
    """
    根据给定的二维层原子索引，剥离出单层，并加上 20 Å 的真空层以备 DFT 计算。
    """
    # 提取属于该 2D 层的原子
    sites = [structure[i] for i in layer_indices]
    
    # 获取原始晶格
    lattice = structure.lattice
    a, b, c = lattice.matrix[0], lattice.matrix[1], lattice.matrix[2]
    
    # 增加真空层：由于使用了标准化，层通常垂直于 c 轴。我们将 c 轴方向拉长。
    c_dir = c / np.linalg.norm(c)
    new_c = c + c_dir * vacuum_angstroms
    
    # 构建新的包含了真空层的晶格
    new_lattice = Lattice(np.vstack([a, b, new_c]))
    
    # 必须使用笛卡尔坐标 (Cartesian)，因为晶格变大后，原有的分数坐标会失效
    species = [s.specie for s in sites]
    cart_coords = [s.coords for s in sites]
    
    monolayer = Structure(new_lattice, species, cart_coords, coords_are_cartesian=True)
    
    # 将二维层在 z 轴上居中放置 (这对 VASP/QE 计算非常友好)
    z_coords = [s.frac_coords[2] for s in monolayer]
    center_z = (max(z_coords) + min(z_coords)) / 2.0
    shift_z = 0.5 - center_z
    monolayer.translate_sites(range(len(monolayer)), [0, 0, shift_z])
    
    return monolayer

# ==========================================
# 3. 论文核心算法：维度拓扑分析器 (升级版)
# ==========================================
class DimensionalityAnalyzer:
    def __init__(self, delta=1.3):
        self.delta = delta

    def _get_vdw_radius(self, element) -> float:
        if element.van_der_waals_radius is not None:
            return element.van_der_waals_radius
        return 2.0 

    def get_dimensionalities(self, structure: Structure) -> list:
        """
        修改后：返回一个包含字典的列表，不仅包含维度(rank)，还包含原子的索引(indices)。
        """
        G = nx.MultiDiGraph()
        G.add_nodes_from(range(len(structure)))
        max_cutoff = 6.0 
        all_neighbors = structure.get_all_neighbors(r=max_cutoff)
        
        for i, neighbors in enumerate(all_neighbors):
            r_i = self._get_vdw_radius(structure[i].specie)
            for neighbor in neighbors:
                j = neighbor.index
                r_j = self._get_vdw_radius(neighbor.specie)
                dist = neighbor.nn_distance
                
                if dist < (r_i + r_j - self.delta):
                    image = np.array(neighbor.image, dtype=int)
                    G.add_edge(i, j, image=image)
                    
        undirected_G = nx.Graph()
        for u, v in G.edges():
            undirected_G.add_edge(u, v)
            
        components_info = []
        
        for component in nx.connected_components(undirected_G):
            pos_dict = {}
            start_node = list(component)[0]
            pos_dict[start_node] = np.zeros(3, dtype=int)
            
            queue = [start_node]
            while queue:
                curr = queue.pop(0)
                for neighbor in undirected_G.neighbors(curr):
                    if neighbor not in pos_dict:
                        if G.has_edge(curr, neighbor):
                            edge_data = list(G[curr][neighbor].values())[0]
                            pos_dict[neighbor] = pos_dict[curr] + edge_data['image']
                        else:
                            edge_data = list(G[neighbor][curr].values())[0]
                            pos_dict[neighbor] = pos_dict[curr] - edge_data['image']
                        queue.append(neighbor)
                        
            translations = []
            for u in component:
                for v in G.successors(u):
                    for key, edge_data in G[u][v].items():
                        image = edge_data['image']
                        diff = pos_dict[u] + image - pos_dict[v]
                        if np.any(diff != 0):
                            translations.append(diff)
                            
            if len(translations) > 0:
                rank = np.linalg.matrix_rank(np.array(translations))
            else:
                rank = 0
                
            components_info.append({
                'rank': rank,
                'indices': list(component)
            })
            
        return components_info

# ==========================================
# 4. 独立工作进程
# ==========================================
def process_material(task_dict):
    mat_id = task_dict['id']
    cif_str = task_dict['cif_string']
    output_dir = task_dict['output_dir']
    
    result = {
        "material_id": mat_id,
        "status": "Failed",
        "has_2d_layer": False,
        "dimensionalities": [],
        "extracted_file": "",
        "error_message": ""
    }
    
    if not isinstance(cif_str, str) or len(cif_str.strip()) == 0:
        result["error_message"] = "Empty CIF data"
        return result
        
    try:
        struct = Structure.from_str(cif_str, fmt="cif")
        
        if not struct.is_ordered:
            result["error_message"] = "Disordered structure (partial occupancies)"
            return result
            
        sga = SpacegroupAnalyzer(struct, symprec=0.05)
        refined_struct = sga.get_primitive_standard_structure()
        if refined_struct is None:
             refined_struct = struct
             
        delta_values = [1.1, 1.2, 1.3, 1.4, 1.5]
        found_2d = False
        final_comp_info = []
        
        for d in delta_values:
            analyzer = DimensionalityAnalyzer(delta=d)
            comp_info = analyzer.get_dimensionalities(refined_struct)
            
            ranks = [comp['rank'] for comp in comp_info]
            
            # 只要发现存在二维层 (rank == 2)
            if 2 in ranks:
                found_2d = True
                final_comp_info = comp_info
                break 
        
        if not found_2d:
            final_comp_info = comp_info 
            
        result["status"] = "Success"
        result["dimensionalities"] = [c['rank'] for c in final_comp_info]
        result["has_2d_layer"] = found_2d
        
        # ================== 核心剥离逻辑 ==================
        if found_2d:
            # 找到第一个维度为 2 的原子簇
            layer_cluster = next(c for c in final_comp_info if c['rank'] == 2)
            layer_indices = layer_cluster['indices']
            
            # 剥离并加真空层
            monolayer = extract_monolayer(refined_struct, layer_indices, vacuum_angstroms=20.0)
            
            # 保存 CIF 文件
            safe_filename = str(mat_id).replace("/", "_").replace("\\", "_")
            cif_path = os.path.join(output_dir, f"{safe_filename}_2D.cif")
            monolayer.to(filename=cif_path, fmt="cif")
            
            result["extracted_file"] = cif_path
            
    except Exception as e:
        result["error_message"] = f"Parse/Alg Error: {str(e)}"
        
    return result

# ==========================================
# 5. 主控函数
# ==========================================
def run_high_throughput_screening(input_csv, output_csv, id_col, cif_col, workers=6):
    logger = setup_logger()
    logger.info(f"--- 启动高通量 2D 材料筛选与自动剥离任务 ---")
    
    # 创建存放提取出的 2D CIF 的文件夹
    extracted_dir = "extracted_2d_cifs"
    os.makedirs(extracted_dir, exist_ok=True)
    logger.info(f"剥离出的 2D 结构将被保存在: ./{extracted_dir}/")
    
    try:
        df = pd.read_csv(input_csv)
    except Exception as e:
        logger.error(f"无法读取 CSV 文件: {e}")
        return
        
    total_materials = len(df)
    
    # 把输出路径打包进任务参数中
    tasks = [{'id': row[id_col], 'cif_string': row[cif_col], 'output_dir': extracted_dir} 
             for _, row in df.iterrows()]
             
    results_list = []
    
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_material, task): task for task in tasks}
        
        for future in tqdm(as_completed(futures), total=total_materials, desc="Exfoliating"):
            res = future.result()
            results_list.append(res)
            
            if res['status'] == 'Success':
                if res['has_2d_layer']:
                    logger.info(f"[EXFOLIATED] {res['material_id']} 成功剥离! 结构已保存。")
                else:
                    logger.info(f"[SKIP] {res['material_id']} 无 2D 层。")
            else:
                logger.warning(f"[FAIL] {res['material_id']} 处理失败: {res['error_message']}")

    results_df = pd.DataFrame(results_list)
    results_df.to_csv(output_csv, index=False)
    
    success_df = results_df[results_df['status'] == 'Success']
    layered_df = results_df[results_df['has_2d_layer'] == True]
    
    logger.info("--- 剥离任务完成 ---")
    logger.info(f"成功解析并剥离出 {len(layered_df)} 个 2D 结构。")
    logger.info(f"所有单层 CIF 文件均已存放至 ./{extracted_dir} 文件夹。")

# ==========================================
# 6. 执行入口
# ==========================================
if __name__ == '__main__':
    INPUT_FILE = "../3.13_new_exfo_test/mp_data_14000.csv"   
    OUTPUT_FILE = "2d_candidates_report.csv"
    
    ID_COLUMN_NAME = "original_file" 
    CIF_COLUMN_NAME = "cif_content"        
    
    run_high_throughput_screening(INPUT_FILE, OUTPUT_FILE, ID_COLUMN_NAME, CIF_COLUMN_NAME)