"""
PipelineData -- Data object that flows between pipeline stages.

Each stage reads what it needs and adds its outputs.
Essentially a typed dictionary with validation and metadata tracking.

Usage:
    data = PipelineData()
    data.set("close", price_series)
    data.set("tEvents", cusum_events)

    # Later stage:
    close = data.get("close")            # required -- raises if missing
    oi = data.get("oi", required=False)   # optional -- returns None if missing
"""

import os
import joblib
import pandas as pd
from typing import Any, Optional


class PipelineData:
    """
    Data container that flows between pipeline stages.

    Internally a dictionary with:
    - Validation: request data as required, fails clearly if missing.
    - Registry: inspect contents at any point.
    - Metadata: each entry tracks who produced it and why.
    """

    def __init__(self):
        self._store = {}
        self._meta = {}

    def set(self, key: str, value: Any, source_module: str = "", desc: str = ""):
        """Add or overwrite a data entry."""
        self._store[key] = value
        self._meta[key] = {
            "source_module": source_module,
            "desc": desc,
        }

    def get(self, key: str, required: bool = True) -> Optional[Any]:
        """Retrieve a data entry."""
        if key in self._store:
            return self._store[key]

        if required:
            available = list(self._store.keys())
            raise KeyError(
                f"Data '{key}' not found in container. "
                f"Available keys: {available}"
            )
        return None

    def has(self, key: str) -> bool:
        """Check if a data entry exists."""
        return key in self._store

    def delete(self, key: str) -> bool:
        """Remove a data entry (useful for freeing memory)."""
        if key in self._store:
            del self._store[key]
            del self._meta[key]
            return True
        return False

    def keys(self) -> list:
        """List all available data entries."""
        return list(self._store.keys())

    def summary(self) -> dict:
        """Summary of contents for debugging and tracing."""
        result = {}
        for key, value in self._store.items():
            info = {
                "type": type(value).__name__,
                "source_module": self._meta[key]["source_module"],
            }

            if isinstance(value, pd.DataFrame):
                info["shape"] = list(value.shape)
                info["columns"] = len(value.columns)
            elif isinstance(value, pd.Series):
                info["length"] = len(value)
            elif isinstance(value, pd.DatetimeIndex):
                info["length"] = len(value)

            result[key] = info

        return result

    def save(self, filepath: str):
        """Persist full container state to local disk."""
        payload = {"data": self._store, "metadata": self._meta}
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        joblib.dump(payload, filepath)

    @classmethod
    def load(cls, filepath: str) -> "PipelineData":
        """Load a previously saved PipelineData."""
        state = joblib.load(filepath)
        container = cls()
        container._store = state["data"]
        container._meta = state["metadata"]
        return container

    def __repr__(self):
        items = []
        for key in self._store:
            val = self._store[key]
            if isinstance(val, (pd.DataFrame, pd.Series, pd.DatetimeIndex)):
                items.append(f"  {key}: {type(val).__name__} len={len(val)}")
            else:
                items.append(f"  {key}: {type(val).__name__}")
        content = "\n".join(items) if items else "  (empty)"
        return f"PipelineData:\n{content}"
