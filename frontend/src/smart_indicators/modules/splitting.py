"""
splitting.py -- M5: Walk-forward splitting with purging and embargo.

Implements time-series cross-validation that:
    - Splits data into expanding or rolling train/test folds
    - Purges training samples whose labels overlap with the test period
    - Applies an embargo gap after each test period

This prevents data leakage that is common in financial ML.

Output keys in PipelineData:
    - cv_splits: list of (train_idx, test_idx) tuples
    - split_info: list of dicts with split metadata
"""

import numpy as np
import pandas as pd
from typing import Optional

from ..core.base_module import StageBase
from ..core.pipeline_data import PipelineData


# ---------------------------------------------------------------------------
# Walk-Forward Splitter with Purging and Embargo
# ---------------------------------------------------------------------------

class WalkForwardCV:
    """
    Walk-forward cross-validator with purging and embargo.

    Produces K folds where each fold has:
        - Training set: all data before the test period (minus purged overlap)
        - Test set: a contiguous block of data
        - Embargo: a gap after the test set that is excluded from future training

    Args:
        n_splits: Number of test folds (default: 5).
        test_size: Fraction of data for each test fold (default: 0.2).
            If None, computed as 1/n_splits.
        purge_length: Timedelta of the label look-ahead window.
            Training samples within this distance before test start are removed.
        embargo_pct: Fraction of test size to use as embargo after test end.
        expanding: If True, training window expands; if False, rolling window.
        min_train_size: Minimum number of training samples required.
    """

    def __init__(
        self,
        n_splits: int = 5,
        test_size: Optional[float] = None,
        purge_length: Optional[pd.Timedelta] = None,
        embargo_pct: float = 0.01,
        expanding: bool = True,
        min_train_size: int = 100,
    ):
        self.n_splits = n_splits
        self.test_size = test_size or (1.0 / (n_splits + 1))
        self.purge_length = purge_length or pd.Timedelta(0)
        self.embargo_pct = embargo_pct
        self.expanding = expanding
        self.min_train_size = min_train_size

    def split(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None,
        barriers_info: Optional[pd.DataFrame] = None,
    ) -> list[tuple[np.ndarray, np.ndarray]]:
        """
        Generate train/test index splits.

        Args:
            X: Feature DataFrame with DatetimeIndex.
            y: Labels (optional, used for validation).
            barriers_info: DataFrame with 't1' column (barrier touch times)
                for accurate purging.

        Returns:
            List of (train_indices, test_indices) tuples.
        """
        n = len(X)
        index = X.index

        # Determine test fold size
        test_n = max(1, int(n * self.test_size))
        embargo_n = max(1, int(test_n * self.embargo_pct))

        # Generate fold boundaries
        splits = []

        for fold in range(self.n_splits):
            # Test start position: evenly spaced, last fold ends at data end
            test_end_pos = n - (self.n_splits - fold - 1) * test_n
            test_start_pos = test_end_pos - test_n

            if test_start_pos < self.min_train_size:
                continue

            test_start = index[test_start_pos]
            test_end = index[min(test_end_pos - 1, n - 1)]

            # Training: everything before test_start, with purging
            if barriers_info is not None and "t1" in barriers_info.columns:
                # Purge based on actual label expiration times
                purge_mask = self._get_purge_mask(
                    index, test_start, test_end, barriers_info
                )
            else:
                # Purge based on fixed purge_length
                purge_start = test_start - self.purge_length
                purge_mask = index < purge_start

            if self.expanding:
                train_mask = purge_mask
            else:
                # Rolling window: limit training to same size as expanding would give at last fold
                max_train = test_start_pos
                train_start_pos = max(0, test_start_pos - max_train)
                train_mask = purge_mask & (index >= index[train_start_pos])

            # Apply embargo: exclude data right after test end
            embargo_end_pos = min(test_end_pos + embargo_n, n)
            if embargo_end_pos < n:
                embargo_end_time = index[embargo_end_pos]
                train_mask = train_mask & ~((index > test_end) & (index < embargo_end_time))

            train_indices = np.where(train_mask)[0]
            test_indices = np.arange(test_start_pos, min(test_end_pos, n))

            if len(train_indices) < self.min_train_size:
                continue

            splits.append((train_indices, test_indices))

        return splits

    def _get_purge_mask(
        self,
        index: pd.DatetimeIndex,
        test_start: pd.Timestamp,
        test_end: pd.Timestamp,
        barriers_info: pd.DataFrame,
    ) -> pd.Series:
        """
        Create a boolean mask that excludes training samples whose labels
        overlap with the test period.

        A training sample at time t is purged if its label expiration (t1)
        falls within or after the test start.
        """
        mask = pd.Series(True, index=index)

        for t in index:
            if t >= test_start:
                mask.loc[t] = False
                continue

            if t in barriers_info.index and "t1" in barriers_info.columns:
                t1 = barriers_info.loc[t, "t1"]
                if isinstance(t1, pd.Series):
                    t1 = t1.iloc[0]
                if pd.notna(t1) and t1 >= test_start:
                    mask.loc[t] = False

        return mask

    def get_split_info(
        self,
        X: pd.DataFrame,
        splits: list[tuple[np.ndarray, np.ndarray]],
    ) -> list[dict]:
        """Return metadata about each split for tracing."""
        info = []
        for i, (train_idx, test_idx) in enumerate(splits):
            info.append({
                "fold": i,
                "train_size": len(train_idx),
                "test_size": len(test_idx),
                "train_start": str(X.index[train_idx[0]]),
                "train_end": str(X.index[train_idx[-1]]),
                "test_start": str(X.index[test_idx[0]]),
                "test_end": str(X.index[test_idx[-1]]),
            })
        return info


# ---------------------------------------------------------------------------
# SplittingModule class
# ---------------------------------------------------------------------------

class SplittingModule(StageBase):
    """
    M5 Splitting stage: walk-forward cross-validation with purging and embargo.

    Config keys (from 'splitting' section):
        n_splits: int, number of folds (default: 5)
        test_size: float, fraction of data per test fold (default: 0.2)
        purge_hours: float, hours of look-ahead to purge (default: 24)
        embargo_pct: float, embargo as fraction of test size (default: 0.01)
        expanding: bool, expanding vs rolling window (default: True)
        min_train_size: int, minimum training samples (default: 100)
    """

    name = "splitting"

    requires = {
        "data": {
            "features_df": {"required": True, "desc": "Feature matrix"},
            "labels": {"required": True, "desc": "Labels from triple barrier"},
            "barriers_info": {"required": False, "desc": "Barrier details for purging"},
        },
        "params": {
            "n_splits": {"type": "int", "default": 5, "desc": "Number of CV folds"},
            "purge_hours": {"type": "float", "default": 24, "desc": "Purge window in hours"},
            "embargo_pct": {"type": "float", "default": 0.01, "desc": "Embargo percentage"},
        },
    }

    produces = {
        "cv_splits": "List of (train_idx, test_idx) tuples",
        "split_info": "List of dicts with split metadata",
        "X": "Aligned feature matrix (events only)",
        "y": "Aligned labels",
    }

    def run(self, data: PipelineData) -> PipelineData:
        """Create walk-forward CV splits with purging and embargo."""
        features_df = data.get("features_df")
        labels = data.get("labels")
        barriers_info = data.get("barriers_info", required=False)

        # Align features and labels to common index
        common_idx = features_df.index.intersection(labels.index)
        if len(common_idx) == 0:
            raise ValueError(
                "No overlap between features and labels indices. "
                "Check that filtering events are within the feature time range."
            )

        X = features_df.loc[common_idx].copy()
        y = labels.loc[common_idx].copy()

        # Drop rows with NaN features
        valid_mask = X.notna().all(axis=1)
        X = X.loc[valid_mask]
        y = y.loc[X.index]

        if len(X) == 0:
            raise ValueError("No valid samples after dropping NaN features.")

        # Align barriers_info if available
        if barriers_info is not None:
            barriers_aligned = barriers_info.loc[
                barriers_info.index.isin(X.index)
            ]
        else:
            barriers_aligned = None

        # Config
        n_splits = self.config.get("n_splits", 5)
        test_size = self.config.get("test_size", 0.2)
        purge_hours = self.config.get("purge_hours", 24)
        embargo_pct = self.config.get("embargo_pct", 0.01)
        expanding = self.config.get("expanding", True)
        min_train_size = self.config.get("min_train_size", 100)

        purge_length = pd.Timedelta(hours=purge_hours)

        # Create splitter
        cv = WalkForwardCV(
            n_splits=n_splits,
            test_size=test_size,
            purge_length=purge_length,
            embargo_pct=embargo_pct,
            expanding=expanding,
            min_train_size=min_train_size,
        )

        splits = cv.split(X, y, barriers_info=barriers_aligned)
        split_info = cv.get_split_info(X, splits)

        if len(splits) == 0:
            raise ValueError(
                f"No valid CV splits generated with n_splits={n_splits}, "
                f"test_size={test_size}, min_train_size={min_train_size}. "
                f"Dataset has {len(X)} samples."
            )

        # Store results
        data.set("cv_splits", splits, source_module=self.name, desc="CV splits")
        data.set("split_info", split_info, source_module=self.name, desc="Split metadata")
        data.set("X", X, source_module=self.name, desc="Aligned feature matrix")
        data.set("y", y, source_module=self.name, desc="Aligned labels")

        # Trace
        self.trace["n_splits"] = len(splits)
        self.trace["n_samples"] = len(X)
        self.trace["n_features"] = X.shape[1]
        self.trace["label_distribution"] = {str(k): int(v) for k, v in y.value_counts().items()}
        self.trace["splits"] = split_info

        return data
