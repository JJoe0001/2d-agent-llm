import pandas as pd
from pymatgen.core import Structure
from pymatgen.analysis.structure_matcher import StructureMatcher
from loguru import logger
import time
import sys
import csv

def deduplicate_candidates_csv(input_csv: str, output_csv: str):
    """
    对高通量提取出的候选 2D 结构进行严格的拓扑与几何查重
    """
    logger.info(f"开始读取候选结构进行查重: {input_csv}")
    
    try:
        # 解除 CSV 单元格长度限制
        maxInt = sys.maxsize
        while True:
            try:
                csv.field_size_limit(maxInt)
                break
            except OverflowError:
                maxInt = int(maxInt/10)

        # 读取超大 CIF 数据的终极配置
        df = pd.read_csv(
            input_csv, 
            on_bad_lines='skip',  # 跳过损坏的行
            engine='python',      # 使用 Python 引擎处理复杂引号
            quoting=csv.QUOTE_MINIMAL
        )
    except Exception as e:
        logger.error(f"读取 CSV 失败: {e}")
        return

    if df.empty or 'cif_content' not in df.columns:
        logger.warning("CSV 为空或缺少 cif_content 列！")
        return

    initial_count = len(df)
    
    # 初始化 pymatgen 的 StructureMatcher
    matcher = StructureMatcher(
        ltol=0.2,          
        stol=0.3,          
        angle_tol=5,       
        primitive_cell=True, 
        attempt_supercell=False 
    )

    unique_rows = []

    start_time = time.time()
    
    # 按照化学式对数据进行分组查重
    grouped = df.groupby('extracted_formula')
    total_groups = len(grouped)
    
    logger.info(f"共发现 {total_groups} 种不同的化学式分组，开始进行组内查重...")
    
    for i, (formula, group) in enumerate(grouped, 1):
        group_size = len(group)
        logger.info(f"进度 [{i}/{total_groups}]: 正在查重 {formula} (含 {group_size} 个初始结构)...")
        
        group_unique_structs = [] 
        
        for idx, row in group.iterrows():
            try:
                struct = Structure.from_str(row['cif_content'], fmt='cif')
                
                is_duplicate = False
                # 只需要和本组（同化学式）内已经确认为 unique 的结构进行比较
                for existing_struct in group_unique_structs:
                    if matcher.fit(struct, existing_struct):
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    group_unique_structs.append(struct)
                    unique_rows.append(row.to_dict())
                    
            except Exception as e:
                logger.debug(f"解析 CIF 失败，跳过该行: {e}")
        
        logger.info(f"   {formula} 清洗完毕: 存留 {len(group_unique_structs)} 个独立相")

    # 将去重后的结果保存
    df_unique = pd.DataFrame(unique_rows)
    df_unique.to_csv(output_csv, index=False)
    
    elapsed = time.time() - start_time
    duplicate_count = initial_count - len(df_unique)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"查重清洗完成。耗时: {elapsed:.2f} 秒")
    logger.info(f"原始候选结构数: {initial_count}")
    logger.info(f"成功拦截并剔除重复结构: {duplicate_count}")
    logger.info(f"最终保留的独立结构: {len(df_unique)}")
    logger.info(f"去重后的数据已保存至: {output_csv}")
    logger.info(f"{'='*60}")


import pandas as pd
from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.analysis.structure_matcher import StructureMatcher
import sys
import csv
import time

def shrink_to_primitive_impl(input_csv: str, output_csv: str) -> str:
    """【内部实现】原胞化瘦身 (带进度显示)"""
    maxInt = sys.maxsize
    while True:
        try:
            csv.field_size_limit(maxInt)
            break
        except OverflowError:
            maxInt = int(maxInt/10)

    try:
        df = pd.read_csv(input_csv)
    except Exception as e:
        return f"读取文件失败: {e}"

    shrunk_rows = []
    total_atoms_saved = 0
    total_items = len(df) # 获取总数

    logger.info(f"开始对 {total_items} 个结构进行原胞化瘦身，这可能需要一些时间...")

    for i, (idx, row) in enumerate(df.iterrows(), 1):
        if i % 50 == 0 or i == total_items:
            logger.info(f"瘦身进度: [{i}/{total_items}] 正在处理...")

        try:
            supercell_struct = Structure.from_str(row['cif_content'], fmt='cif')
            original_atoms = len(supercell_struct)
            
            sga = SpacegroupAnalyzer(supercell_struct, symprec=0.1, angle_tolerance=5.0)
            primitive_struct = sga.get_primitive_standard_structure()
            
            if primitive_struct is None:
                primitive_struct = supercell_struct.get_primitive_structure(tolerance=0.1)
                
            shrunk_atoms = len(primitive_struct)
            atoms_saved = original_atoms - shrunk_atoms
            
            if atoms_saved > 0:
                total_atoms_saved += atoms_saved
                
            row['cif_content'] = primitive_struct.to(fmt="cif")
            row['extracted_formula'] = primitive_struct.composition.reduced_formula
            shrunk_rows.append(row.to_dict())
            
        except Exception:
            shrunk_rows.append(row.to_dict())

    df_shrunk = pd.DataFrame(shrunk_rows)
    df_shrunk.to_csv(output_csv, index=False)

    msg = f"瘦身完成。共处理 {total_items} 个结构，减少 {total_atoms_saved} 个冗余原子。已保存至: {output_csv}"
    logger.info(msg)
    return msg


def cross_batch_deduplicate_impl(old_csv: str, new_csv: str, output_csv: str, max_atoms: int = 200) -> str:
    """【内部实现】增量查重与过滤 (带进度显示)"""
    maxInt = sys.maxsize
    while True:
        try:
            csv.field_size_limit(maxInt)
            break
        except OverflowError:
            maxInt = int(maxInt/10)

    try:
        df_old = pd.read_csv(old_csv)
        df_new = pd.read_csv(new_csv)
    except Exception as e:
        return f"读取 CSV 失败: {e}"

    matcher = StructureMatcher(
        ltol=0.2, stol=0.3, angle_tol=5, 
        primitive_cell=True, attempt_supercell=False
    )

    logger.info(f"正在解析历史数据 {old_csv}，建立已知参照池...")
    known_pool = {}
    for formula, group in df_old.groupby('extracted_formula'):
        structs = []
        for idx, row in group.iterrows():
            try:
                structs.append(Structure.from_str(row['cif_content'], fmt='cif'))
            except:
                pass
        known_pool[formula] = structs
    logger.info(f"历史参照池建立完毕 (共 {len(known_pool)} 种化学式)")

    unique_new_rows = []
    dropped_by_atoms = 0
    dropped_by_dup = 0

    grouped_new = df_new.groupby('extracted_formula')
    total_groups = len(grouped_new)
    
    logger.info(f"开始对新批次的 {total_groups} 种化学式进行物理查重...")

    for i, (formula, group) in enumerate(grouped_new, 1):
        logger.info(f"查重进度 [{i}/{total_groups}]: 正在比对 {formula} (含 {len(group)} 个结构)...")
        
        ref_structs = known_pool.get(formula, [])
        for idx, row in group.iterrows():
            try:
                struct = Structure.from_str(row['cif_content'], fmt='cif')
                
                if len(struct) > max_atoms:
                    dropped_by_atoms += 1
                    continue
                
                is_duplicate = False
                for ref in ref_structs:
                    if matcher.fit(struct, ref):
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    ref_structs.append(struct)
                    known_pool[formula] = ref_structs
                    unique_new_rows.append(row.to_dict())
                else:
                    dropped_by_dup += 1
            except:
                pass

    df_unique_new = pd.DataFrame(unique_new_rows)
    if not df_unique_new.empty:
        df_unique_new.to_csv(output_csv, index=False)
        
    msg = (f"增量查重与过滤完成。\n"
           f"输入新结构: {len(df_new)} 个\n"
           f"拦截超大结构 (>{max_atoms}原子): {dropped_by_atoms} 个\n"
           f"剔除历史/内部重复: {dropped_by_dup} 个\n"
           f"获得全新有效二维结构: {len(unique_new_rows)} 个\n"
           f"已保存至: {output_csv}")
    
    logger.info("\n" + msg)
    return msg

if __name__ == "__main__":
    INPUT = "/root/local-disk/2D_materials/exfo_agent/mp_stable_candidates_extracted_副本.csv"
    OUTPUT = "/root/local-disk/2D_materials/exfo_agent/candidates_unique.csv"
    deduplicate_candidates_csv(INPUT, OUTPUT)
