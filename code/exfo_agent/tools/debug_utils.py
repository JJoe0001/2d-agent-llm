# file: tools/debug_utils.py
from __future__ import annotations
import os
import sys
import time
import traceback
from typing import Any, Dict, Optional
from pathlib import Path
from loguru import logger
import threading

# =============================================================================
# DEBUG CONTEXT (Global Singleton)
# =============================================================================
DEBUG_CONTEXT = {
    "enabled": False,
    "output_dir": "debug_artifacts",
    "log_file": "logs/01_geometric_extraction_debug.log"
}

def setup_global_logger(log_file_path: Optional[str] = None):
    """
    配置 Loguru 全局日志系统
    """
    if not log_file_path:
        log_file_path = DEBUG_CONTEXT["log_file"]

    # [Fix] 设置默认 extra 字段，防止 KeyError: 'task'
    logger.configure(extra={"task": "System"}) 

    # 1. 重置 logger
    logger.remove()

    # 2. 控制台输出配置 (简洁模式)
    logger.add(
        sys.stderr,
        # 使用 extra.get 来安全获取 task，或者依赖上面的 configure 默认值
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[task]}</cyan> - <level>{message}</level>",
        level="INFO"
    )

    # 3. 文件输出配置 (详细调试模式)
    log_path = Path(log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        str(log_path),
        # 格式包含：时间 | 级别 | 线程名 | 源码位置 | 任务名 | 消息
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {thread.name} | {module}:{function}:{line} | {extra[task]} - {message}",
        level="DEBUG",
        rotation="100 MB",
        retention="7 days",
        encoding="utf-8",
        enqueue=True 
    )
    logger.info(f"🐛 Debug Logging Initialized. Full log -> {log_path}")

def set_debug_mode_impl(enabled: bool) -> str:
    """Implementation for the MCP tool"""
    DEBUG_CONTEXT["enabled"] = enabled
    status = "ON" if enabled else "OFF"
    
    if enabled:
        os.makedirs(DEBUG_CONTEXT["output_dir"], exist_ok=True)
        setup_global_logger()
        
    logger.info(f"Debug Mode set to {status}")
    return f"Debug Mode is now {status}. Logs: {DEBUG_CONTEXT['log_file']}"

def is_debug_enabled() -> bool:
    return DEBUG_CONTEXT["enabled"]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_debug_dir(source_name: str) -> str:
    safe_name = os.path.splitext(os.path.basename(source_name))[0]
    date_str = time.strftime("%Y%m%d")
    save_dir = os.path.join(DEBUG_CONTEXT["output_dir"], date_str, safe_name)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir, exist_ok=True)
    return save_dir

def log_debug_trace(source_name: str, message: str, level: str = "INFO"):
    """
    [核心日志函数] 向全局日志写入流水账。自动绑定 task 名称。
    """
    if not DEBUG_CONTEXT["enabled"] and level.upper() == "DEBUG":
        return

    # 绑定任务上下文
    task_logger = logger.bind(task=source_name)

    lvl = level.upper()
    if lvl in ["ERROR", "FATAL"]:
        task_logger.error(message)
    elif lvl == "WARNING":
        task_logger.warning(message)
    elif lvl == "DEBUG":
        task_logger.debug(message)
    else:
        task_logger.info(message)

def dump_error_artifact(source_name: str, exception: Exception):
    """
    记录错误工件。
    注意：已移除 try-except，如果写入失败（如权限问题），程序将崩溃。
    """
    if not DEBUG_CONTEXT["enabled"]:
        return

    log_debug_trace(source_name, f"💥 CRITICAL ERROR: {str(exception)}", "ERROR")
    log_debug_trace(source_name, traceback.format_exc(), "DEBUG")

    # 直接执行文件写入，不捕获异常
    save_dir = _get_debug_dir(source_name)
    error_path = os.path.join(save_dir, "CRITICAL_ERROR.txt")
    with open(error_path, "w", encoding="utf-8") as f:
        f.write(f"Error Type: {type(exception).__name__}\n")
        f.write(f"Error Message: {str(exception)}\n")
        f.write("-" * 50 + "\n")
        traceback.print_exc(file=f)

def save_debug_snapshot(struct: Any, stage_name: str, source_name: str, info: str = ""):
    """
    保存结构快照。
    注意：已移除 try-except，如果 struct 没有 .to 方法或写入失败，程序将崩溃。
    """
    if not DEBUG_CONTEXT["enabled"]:
        return

    # 直接执行快照保存逻辑，不捕获异常
    save_dir = _get_debug_dir(source_name)
    timestamp = time.strftime("%H%M%S")
    filename = f"{timestamp}_{stage_name}.cif"
    filepath = os.path.join(save_dir, filename)

    if hasattr(struct, "to"):
        struct.to(fmt="cif", filename=filepath)
        log_debug_trace(source_name, f"📸 Snapshot saved: {filename} ({info})", "DEBUG")
    else:
        log_debug_trace(source_name, f"Failed to save snapshot {stage_name} (No .to method)", "WARNING")