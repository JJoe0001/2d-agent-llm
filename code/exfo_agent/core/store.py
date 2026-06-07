from __future__ import annotations

import os
import uuid
import threading
from dataclasses import dataclass
from typing import Dict, Any, Optional

from pymatgen.core import Structure
from core.config import config

# Thread-safe lock for store operations
_store_lock = threading.Lock()


@dataclass
class StoredStructure:
    structure: Structure
    meta: Dict[str, Any]


# In-process memory store (protected by _store_lock)
STRUCT_STORE: Dict[str, StoredStructure] = {}


def new_structure_id() -> str:
    return str(uuid.uuid4())


def is_path_allowed(file_path: str) -> bool:
    """Prevent path traversal by resolving realpath and checking whitelist dir."""
    real = os.path.realpath(file_path)
    base = os.path.realpath(config.WHITELIST_DIR) + os.sep
    return real.startswith(base)


def store_structure(structure_id: str, structure: Structure, meta: Dict[str, Any]) -> None:
    with _store_lock:
        STRUCT_STORE[structure_id] = StoredStructure(structure=structure, meta=meta)


def delete_structure(structure_id: str) -> None:
    with _store_lock:
        STRUCT_STORE.pop(structure_id, None)


def get_structure(structure_id: str) -> Structure:
    with _store_lock:
        if structure_id not in STRUCT_STORE:
            raise ValueError(f"Structure not found: {structure_id}. Please call parse_structure first.")
        return STRUCT_STORE[structure_id].structure


def get_meta(structure_id: str) -> Dict[str, Any]:
    with _store_lock:
        if structure_id not in STRUCT_STORE:
            raise ValueError(f"Structure not found: {structure_id}. Please call parse_structure first.")
        return STRUCT_STORE[structure_id].meta
