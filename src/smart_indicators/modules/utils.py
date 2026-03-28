"""
utils.py -- Shared utility functions for the smart_indicators pipeline.

Provides helper functions for data manipulation, logging, and common
operations used across multiple modules.
"""

import os
import json
import hashlib
import pandas as pd
import numpy as np
from typing import Optional, Any
from pathlib import Path


def compute_hash(config: dict) -> str:
    """Compute a deterministic hash for a configuration dict."""
    config_str = json.dumps(config, sort_keys=True, default=str)
    return hashlib.md5(config_str.encode()).hexdigest()[:12]


def safe_div(a, b, fill: float = 0.0):
    """Element-wise division with fill value for division by zero."""
    if isinstance(a, (pd.Series, pd.DataFrame)):
        return a.div(b).replace([np.inf, -np.inf], fill).fillna(fill)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(b != 0, a / b, fill)
    return result


def rolling_apply(series: pd.Series, window: int, func, min_periods: int = 1):
    """Apply a function over a rolling window of a series."""
    return series.rolling(window=window, min_periods=min_periods).apply(func, raw=True)


def ewm_apply(series: pd.Series, span: int):
    """Exponential weighted moving average."""
    return series.ewm(span=span, min_periods=span).mean()


def clip_outliers(series: pd.Series, n_std: float = 5.0) -> pd.Series:
    """Clip values beyond n_std standard deviations from the mean."""
    mean = series.mean()
    std = series.std()
    lower = mean - n_std * std
    upper = mean + n_std * std
    return series.clip(lower=lower, upper=upper)


def ensure_dir(path: str) -> str:
    """Create directory if it doesn't exist, return the path."""
    os.makedirs(path, exist_ok=True)
    return path


def save_json(data: Any, filepath: str) -> None:
    """Save data to a JSON file."""
    ensure_dir(os.path.dirname(filepath) or ".")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def load_json(filepath: str) -> Any:
    """Load data from a JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def date_range_overlap(start1, end1, start2, end2) -> bool:
    """Check if two date ranges overlap."""
    return start1 <= end2 and start2 <= end1


def purge_overlap(
    train_end: pd.Timestamp,
    test_start: pd.Timestamp,
    barrier_length: pd.Timedelta,
) -> pd.Timestamp:
    """
    Compute the adjusted train end date after purging.

    Removes training samples whose labels overlap with the test period.
    """
    purge_start = test_start - barrier_length
    if train_end > purge_start:
        return purge_start
    return train_end


def embargo_start(
    test_end: pd.Timestamp,
    embargo_pct: float,
    total_length: pd.Timedelta,
) -> pd.Timestamp:
    """
    Compute the embargo start date after the test period.

    Returns the earliest date that can be used for training after the test fold.
    """
    embargo_td = total_length * embargo_pct
    return test_end + embargo_td


def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}min"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def log_stage(stage_name: str, message: str, level: str = "INFO") -> None:
    """Simple stage-level logging."""
    print(f"[{level}] [{stage_name}] {message}")
