"""
feature_selection.py -- M6: Forward feature selection stage.

Implements a greedy forward selection algorithm that:
    1. Starts with no features
    2. At each step, adds the feature that maximizes cross-validated AUC
    3. Stops when AUC stops improving or max features is reached

This reduces overfitting and improves model interpretability by selecting
only the 15-30 most predictive features from 200+.

Output keys in PipelineData:
    - selected_features: list of selected feature names
    - X_selected: feature matrix with only selected features
    - selection_trace: detailed log of the selection process
"""

import numpy as np
import pandas as pd
from typing import Optional
from sklearn.metrics import roc_auc_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.base import clone

from ..core.base_module import StageBase
from ..core.pipeline_data import PipelineData


# ---------------------------------------------------------------------------
# Forward Feature Selection
# ---------------------------------------------------------------------------

def forward_feature_selection(
    X: pd.DataFrame,
    y: pd.Series,
    cv_splits: list[tuple[np.ndarray, np.ndarray]],
    estimator=None,
    max_features: int = 30,
    min_improvement: float = 0.001,
    sample_weights: Optional[pd.Series] = None,
    verbose: bool = False,
) -> dict:
    """
    Greedy forward feature selection using cross-validated AUC.

    At each step, every remaining candidate feature is tested. The feature
    that yields the highest mean CV AUC when added to the current set is
    selected. The process stops when:
        - max_features is reached
        - Adding any feature does not improve AUC by min_improvement
        - All features have been added

    Args:
        X: Full feature matrix.
        y: Labels.
        cv_splits: List of (train_idx, test_idx) from walk-forward CV.
        estimator: Sklearn classifier (default: RandomForestClassifier).
        max_features: Maximum number of features to select.
        min_improvement: Minimum AUC improvement to continue adding features.
        sample_weights: Optional sample weights for training.
        verbose: Print progress.

    Returns:
        Dict with:
            - selected: list of selected feature names in order of addition
            - scores: list of AUC scores after each feature addition
            - trace: list of dicts with per-step details
    """
    if estimator is None:
        estimator = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            random_state=42,
            n_jobs=-1,
        )

    candidates = list(X.columns)
    selected = []
    scores = []
    trace = []
    best_auc = 0.0

    for step in range(min(max_features, len(candidates))):
        best_candidate = None
        best_candidate_auc = -np.inf
        step_results = []

        remaining = [f for f in candidates if f not in selected]
        if not remaining:
            break

        for candidate in remaining:
            test_features = selected + [candidate]
            X_sub = X[test_features]

            # Cross-validated AUC
            fold_aucs = []
            for train_idx, test_idx in cv_splits:
                X_train = X_sub.iloc[train_idx]
                X_test = X_sub.iloc[test_idx]
                y_train = y.iloc[train_idx]
                y_test = y.iloc[test_idx]

                # Skip folds with single class
                if len(y_train.unique()) < 2 or len(y_test.unique()) < 2:
                    continue

                model = clone(estimator)

                fit_params = {}
                if sample_weights is not None:
                    w_train = sample_weights.iloc[train_idx]
                    fit_params["sample_weight"] = w_train.values

                try:
                    model.fit(X_train.values, y_train.values, **fit_params)
                    if hasattr(model, "predict_proba"):
                        y_prob = model.predict_proba(X_test.values)[:, 1]
                    else:
                        y_prob = model.decision_function(X_test.values)
                    auc = roc_auc_score(y_test.values, y_prob)
                    fold_aucs.append(auc)
                except Exception:
                    continue

            if fold_aucs:
                mean_auc = np.mean(fold_aucs)
            else:
                mean_auc = 0.0

            step_results.append({
                "feature": candidate,
                "mean_auc": mean_auc,
                "n_folds": len(fold_aucs),
            })

            if mean_auc > best_candidate_auc:
                best_candidate_auc = mean_auc
                best_candidate = candidate

        if best_candidate is None:
            break

        improvement = best_candidate_auc - best_auc

        if step > 0 and improvement < min_improvement:
            if verbose:
                print(
                    f"  Step {step + 1}: best candidate '{best_candidate}' "
                    f"AUC={best_candidate_auc:.4f}, improvement={improvement:.4f} "
                    f"< {min_improvement}. Stopping."
                )
            break

        selected.append(best_candidate)
        best_auc = best_candidate_auc
        scores.append(best_auc)

        trace.append({
            "step": step + 1,
            "feature_added": best_candidate,
            "auc": round(best_auc, 4),
            "improvement": round(improvement, 4),
            "n_candidates_tested": len(step_results),
        })

        if verbose:
            print(
                f"  Step {step + 1}: +'{best_candidate}' "
                f"AUC={best_auc:.4f} (+{improvement:.4f})"
            )

    return {
        "selected": selected,
        "scores": scores,
        "trace": trace,
    }


# ---------------------------------------------------------------------------
# FeatureSelectionModule class
# ---------------------------------------------------------------------------

class FeatureSelectionModule(StageBase):
    """
    M6 Feature Selection stage: greedy forward selection.

    Config keys (from 'feature_selection' section):
        max_features: int, maximum features to select (default: 30)
        min_improvement: float, minimum AUC gain to continue (default: 0.001)
        estimator: str, base estimator name (default: 'random_forest')
        n_estimators: int, trees in forest (default: 100)
        max_depth: int, tree depth (default: 5)
        verbose: bool, print progress (default: False)
        use_sample_weights: bool, use weights from labeling (default: True)
    """

    name = "feature_selection"

    requires = {
        "data": {
            "X": {"required": True, "desc": "Feature matrix"},
            "y": {"required": True, "desc": "Labels"},
            "cv_splits": {"required": True, "desc": "CV splits"},
            "sample_weights": {"required": False, "desc": "Sample weights"},
        },
        "params": {
            "max_features": {"type": "int", "default": 30, "desc": "Max features"},
            "min_improvement": {"type": "float", "default": 0.001, "desc": "Min AUC improvement"},
        },
    }

    produces = {
        "selected_features": "List of selected feature names",
        "X_selected": "Feature matrix with selected features only",
        "selection_trace": "Detailed selection process log",
    }

    def run(self, data: PipelineData) -> PipelineData:
        """Run forward feature selection."""
        X = data.get("X")
        y = data.get("y")
        cv_splits = data.get("cv_splits")
        sample_weights = data.get("sample_weights", required=False)

        # Config
        max_features = self.config.get("max_features", 30)
        min_improvement = self.config.get("min_improvement", 0.001)
        verbose = self.config.get("verbose", False)
        use_weights = self.config.get("use_sample_weights", True)
        n_estimators = self.config.get("n_estimators", 100)
        max_depth = self.config.get("max_depth", 5)

        # Build estimator
        estimator = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42,
            n_jobs=-1,
        )

        weights = sample_weights if use_weights else None

        # Run selection
        result = forward_feature_selection(
            X=X,
            y=y,
            cv_splits=cv_splits,
            estimator=estimator,
            max_features=max_features,
            min_improvement=min_improvement,
            sample_weights=weights,
            verbose=verbose,
        )

        selected = result["selected"]

        if not selected:
            raise ValueError(
                "Feature selection did not select any features. "
                "Check that the data has predictive signal."
            )

        X_selected = X[selected].copy()

        # Store results
        data.set(
            "selected_features",
            selected,
            source_module=self.name,
            desc=f"{len(selected)} features selected",
        )
        data.set(
            "X_selected",
            X_selected,
            source_module=self.name,
            desc=f"Feature matrix: {X_selected.shape}",
        )
        data.set(
            "selection_trace",
            result["trace"],
            source_module=self.name,
            desc="Feature selection process log",
        )

        # Trace
        self.trace["n_selected"] = len(selected)
        self.trace["n_original"] = X.shape[1]
        self.trace["selected_features"] = selected
        self.trace["final_auc"] = result["scores"][-1] if result["scores"] else 0.0
        self.trace["selection_steps"] = result["trace"]

        return data
