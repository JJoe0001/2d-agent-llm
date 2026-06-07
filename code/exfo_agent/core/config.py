# core/config.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

class ExfoConfig:
    """Centralized configuration for exfoliation agent."""

    # Path Configuration
    WHITELIST_DIR: str = os.getenv(
        "EXFO_WHITELIST_DIR",
        "."
    )

    # Performance Configuration
    BATCH_MAX_WORKERS: int = int(os.getenv("EXFO_MAX_WORKERS", "8"))

    # Physics Constants (BONDDEL)
    ENERGY_CLUSTER_TOLERANCE_EV: float = 0.03  # 30 meV
    ENERGY_CUTOFF_THRESHOLD_EV: float = -2.0   # Only cut weak bonds

    # Default Atomic Radii (Angstroms)
    DEFAULT_ATOMIC_RADIUS: float = 2.0
    DEFAULT_SAFE_RADIUS: float = 1.2

    @classmethod
    def validate(cls) -> None:
        """Validate configuration on startup."""
        if not os.path.exists(cls.WHITELIST_DIR):
            raise ValueError(
                f"WHITELIST_DIR does not exist: {cls.WHITELIST_DIR}. "
                f"Set EXFO_WHITELIST_DIR environment variable."
            )

# Singleton instance
config = ExfoConfig()
