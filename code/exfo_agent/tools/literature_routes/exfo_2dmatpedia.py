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

# 忽略常规警告
warnings.filterwarnings("ignore")

# ==========================================
# 1. 日志系统配置
# ==========================================
def setup_logger(log_filename="2dmatpedia_screening.log"):
    logger = logging.getLogger("2DMatPedia")
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
# 2. 剥离辅助函数 (沿 c 轴加真空层)
# ==========================================
def extract_monolayer_2dmatpedia(structure: Structure, cluster_indices: list, vacuum_angstroms=20.0) -> Structure:
    """
    根据论文要求，从常规单胞中提取一个团簇，并在垂直于 2D 层的方向 (c 轴) 加上 20 Å 真空层。
    """
    sites = [structure[i] for i in cluster_indices]
    
    lattice = structure.lattice
    a, b, c = lattice.matrix[0], lattice.matrix[1], lattice.matrix[2]
    
    # 沿着 c 轴方向增加 20 Å 的真空层
    c_dir = c / np.linalg.norm(c)
    new_c = c + c_dir * vacuum_angstroms
    
    new_lattice = Lattice(np.vstack([a, b, new_c]))
    
    species = [s.specie for s in sites]
    cart_coords = [s.coords for s in sites]
    
    monolayer = Structure(new_lattice, species, cart_coords, coords_are_cartesian=True)
    
    # 将二维层在 z 轴上居中
    z_coords = [s.frac_coords[2] for s in monolayer]
    center_z = (max(z_coords) + min(z_coords)) / 2.0
    shift_z = 0.5 - center_z
    monolayer.translate_sites(range(len(monolayer)), [0, 0, shift_z])
    
    return monolayer

# ==========================================
# 3. 2DMatPedia 核心算法：超胞倍增判定
# ==========================================
class TwoDMatPediaExfoliator:
    def __init__(self):
        # 论文使用的 9 个容差值
        self.tolerances = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4]

    def _get_covalent_radius(self, element) -> float:
        """获取原子成键半径（多级回退保护）"""
        try:
            # 1. 尝试首选：共价半径 (部分 pymatgen 版本支持)
            if hasattr(element, "covalent_radius") and element.covalent_radius is not None:
                return float(element.covalent_radius)
                
            # 2. 尝试备选：标准原子半径 (pymatgen 通用属性)
            if hasattr(element, "atomic_radius") and element.atomic_radius is not None:
                return float(element.atomic_radius)
                
            # 3. 尝试底线：范德华半径 (按比例缩小以近似共价半径)
            if hasattr(element, "van_der_waals_radius") and element.van_der_waals_radius is not None:
                return float(element.van_der_waals_radius) * 0.8
                
        except Exception:
            pass
            
        # 4. 终极默认值：如果数据库里完全没有这个元素的半径数据
        return 1.5

    def _get_clusters(self, structure: Structure, tolerance: float) -> list:
        """返回结构中所有连通的原子簇的索引列表"""
        G = nx.Graph()
        G.add_nodes_from(range(len(structure)))
        
        # 搜索半径：最大共价半径(~2.0) * 2 + 最大容差(0.4) ≈ 4.4，取 6.0 足够安全
        all_neighbors = structure.get_all_neighbors(r=6.0)
        
        for i, neighbors in enumerate(all_neighbors):
            r_i = self._get_covalent_radius(structure[i].specie)
            for neighbor in neighbors:
                j = neighbor.index
                r_j = self._get_covalent_radius(neighbor.specie)
                dist = neighbor.nn_distance
                
                # 论文成键判定：距离 < 共价半径之和 + 容差
                if dist < (r_i + r_j + tolerance):
                    G.add_edge(i, j)
                    
        return list(nx.connected_components(G))

    def evaluate_and_extract(self, structure: Structure):
        """
        执行完整的筛选逻辑。
        返回 (is_layered, target_cluster_indices)
        """
        layered_matches = 0
        target_cluster = None
        
        # 论文要求：生成 3x3x3 的超胞
        supercell = structure.copy()
        supercell.make_supercell([3, 3, 3])
        
        for tol in self.tolerances:
            cell_clusters = self._get_clusters(structure, tol)
            n_cell = len(cell_clusters)
            
            if n_cell == 0:
                continue
                
            super_clusters = self._get_clusters(supercell, tol)
            n_super = len(super_clusters)
            
            # 核心判定：超胞的簇数量是单胞的 3 倍
            if n_super == 3 * n_cell:
                layered_matches += 1
                # 保存满足条件的常规单胞中的第一个团簇，以备提取
                if target_cluster is None:
                    target_cluster = list(cell_clusters[0])
                    
            # 只要有两个及以上的容差值满足条件，即判定为 2D 层状
            if layered_matches >= 2:
                return True, target_cluster
                
        return False, None

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
        "extracted_file": "",
        "error_message": ""
    }
    
    if not isinstance(cif_str, str) or len(cif_str.strip()) == 0:
        result["error_message"] = "Empty CIF"
        return result
        
    try:
        struct = Structure.from_str(cif_str, fmt="cif")
        
        # 1. 论文前置过滤：排除元素种类 > 4 的化合物
        if len(struct.composition.elements) > 4:
            result["error_message"] = "Skipped: > 4 elements"
            return result
            
        # 2. 提取常规单胞 (Conventional unit cell)
        sga = SpacegroupAnalyzer(struct, symprec=0.05)
        conv_struct = sga.get_conventional_standard_structure()
        if conv_struct is None:
             conv_struct = struct
             
        # 3. 论文前置过滤：忽略原胞（或这里转换后的单胞）原子数 > 40 的结构
        # 限制原子数这一步极大提升了后续构建 3x3x3 超胞的计算速度
        if len(conv_struct) > 40:
            result["error_message"] = "Skipped: > 40 atoms in cell"
            return result
            
        # 4. 执行 2DMatPedia 的超胞倍增判定算法
        exfoliator = TwoDMatPediaExfoliator()
        is_layered, cluster_indices = exfoliator.evaluate_and_extract(conv_struct)
        
        result["status"] = "Success"
        result["has_2d_layer"] = is_layered
        
        # 5. 剥离并落盘
        if is_layered and cluster_indices:
            monolayer = extract_monolayer_2dmatpedia(conv_struct, cluster_indices, vacuum_angstroms=20.0)
            
            safe_filename = str(mat_id).replace("/", "_").replace("\\", "_")
            cif_path = os.path.join(output_dir, f"{safe_filename}_2DMatPedia.cif")
            monolayer.to(filename=cif_path, fmt="cif")
            
            result["extracted_file"] = cif_path
            
    except Exception as e:
        result["error_message"] = f"Error: {str(e)}"
        
    return result

# ==========================================
# 5. 主控函数
# ==========================================
def run_2dmatpedia_screening(input_csv, output_csv, id_col, cif_col, workers=6):
    logger = setup_logger()
    logger.info("--- 启动 2DMatPedia 算法高通量筛选与剥离任务 ---")
    
    extracted_dir = "extracted_2dmatpedia_cifs"
    os.makedirs(extracted_dir, exist_ok=True)
    logger.info(f"单层结构将保存在: ./{extracted_dir}/")
    
    try:
        df = pd.read_csv(input_csv)
    except Exception as e:
        logger.error(f"读取 CSV 失败: {e}")
        return
        
    total = len(df)
    tasks = [{'id': row[id_col], 'cif_string': row[cif_col], 'output_dir': extracted_dir} for _, row in df.iterrows()]
    results_list = []
    
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_material, task): task for task in tasks}
        
        for future in tqdm(as_completed(futures), total=total, desc="2DMatPedia Exfoliating"):
            res = future.result()
            results_list.append(res)
            
            if res['status'] == 'Success':
                if res['has_2d_layer']:
                    logger.info(f"[EXFOLIATED] {res['material_id']} 成功提取单层！")
            else:
                # 只将真正的解析错误记为 warning，过滤条件导致的跳过记为 info 以保持日志整洁
                if "Skipped" in res['error_message']:
                    logger.info(f"[SKIP] {res['material_id']} 不满足论文前置条件 ({res['error_message']})")
                else:
                    logger.warning(f"[FAIL] {res['material_id']} 处理异常: {res['error_message']}")

    results_df = pd.DataFrame(results_list)
    results_df.to_csv(output_csv, index=False)
    
    layered_df = results_df[results_df['has_2d_layer'] == True]
    
    logger.info("--- 任务完成 ---")
    logger.info(f"总计找到符合 2DMatPedia 标准的层状结构: {len(layered_df)} 个。")

# ==========================================
# 6. 执行入口
# ==========================================
if __name__ == '__main__':
    INPUT_FILE = "../3.13_new_exfo_test/mp_data_14000.csv"   
    OUTPUT_FILE = "2dmatpedia_report.csv"
    
    ID_COLUMN_NAME = "original_file" 
    CIF_COLUMN_NAME = "cif_content"        
    
    run_2dmatpedia_screening(INPUT_FILE, OUTPUT_FILE, ID_COLUMN_NAME, CIF_COLUMN_NAME)
