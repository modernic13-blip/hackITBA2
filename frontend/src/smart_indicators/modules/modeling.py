"""
modeling.py -- M7: Model training stage.

Trains sklearn-compatible classifiers with optional grid search:
    - XGBoost
    - LightGBM
    - CatBoost
    - RandomForest

Uses cross-validated AUC as the scoring metric.

Output keys in PipelineData:
    - model: trained best estimator
    - model_name: string name of the model type
    - cv_results: cross-validation scores per fold
    - best_params: best hyperparameters from grid search
"""

import numpy as np
import pandas as pd
from typing import Optional, Any
from sklearn.metrics import roc_auc_score, accuracy_score, make_scorer
from sklearn.model_selection import ParameterGrid
from sklearn.base import clone

from ..core.base_module import StageBase
from ..core.pipeline_data import PipelineData


# ---------------------------------------------------------------------------
# Default hyperparameter grids
# ---------------------------------------------------------------------------

def _default_param_grids() -> dict:
    """Return default hyperparameter grids for each model type."""
    return {
        "xgboost": {
            "n_estimators": [100, 200, 300],
            "max_depth": [3, 5, 7],
            "learning_rate": [0.01, 0.05, 0.1],
            "subsample": [0.8, 1.0],
            "colsample_bytree": [0.8, 1.0],
            "min_child_weight": [1, 3, 5],
        },
        "lightgbm": {
            "n_estimators": [100, 200, 300],
            "max_depth": [3, 5, 7, -1],
            "learning_rate": [0.01, 0.05, 0.1],
            "subsample": [0.8, 1.0],
            "colsample_bytree": [0.8, 1.0],
            "num_leaves": [31, 63, 127],
        },
        "catboost": {
            "iterations": [100, 200, 300],
            "depth": [3, 5, 7],
            "learning_rate": [0.01, 0.05, 0.1],
            "l2_leaf_reg": [1, 3, 5],
        },
        "random_forest": {
            "n_estimators": [100, 200, 300],
            "max_depth": [3, 5, 7, None],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [1, 2, 4],
            "max_features": ["sqrt", "log2"],
        },
    }


def _build_estimator(model_name: str, params: dict):
    """
    Build a sklearn-compatible estimator by name and parameters.

    Args:
        model_name: One of 'xgboost', 'lightgbm', 'catboost', 'random_forest'.
        params: Hyperparameters to pass to the constructor.

    Returns:
        Instantiated estimator.
    """
    if model_name == "xgboost":
        try:
            from xgboost import XGBClassifier
        except ImportError:
            raise ImportError("xgboost is required. Install with: pip install xgboost")
        return XGBClassifier(
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42,
            verbosity=0,
            **params,
        )

    elif model_name == "lightgbm":
        try:
            from lightgbm import LGBMClassifier
        except ImportError:
            raise ImportError("lightgbm is required. Install with: pip install lightgbm")
        return LGBMClassifier(
            random_state=42,
            verbose=-1,
            **params,
        )

    elif model_name == "catboost":
        try:
            from catboost import CatBoostClassifier
        except ImportError:
            raise ImportError("catboost is required. Install with: pip install catboost")
        return CatBoostClassifier(
            random_state=42,
            verbose=0,
            **params,
        )

    elif model_name == "random_forest":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(
            random_state=42,
            n_jobs=-1,
            **params,
        )

    else:
        raise ValueError(
            f"Unknown model: '{model_name}'. "
            f"Options: xgboost, lightgbm, catboost, random_forest"
        )


def grid_search_cv(
    X: pd.DataFrame,
    y: pd.Series,
    cv_splits: list[tuple[np.ndarray, np.ndarray]],
    model_name: str,
    param_grid: dict,
    sample_weights: Optional[pd.Series] = None,
    max_combinations: int = 50,
    verbose: bool = False,
) -> dict:
    """
    Manual grid search with walk-forward CV.

    We don't use sklearn GridSearchCV because we need custom CV splits
    (walk-forward with purging and embargo).

    Args:
        X: Feature matrix.
        y: Labels.
        cv_splits: Walk-forward CV splits.
        model_name: Model type name.
        param_grid: Hyperparameter grid.
        sample_weights: Optional sample weights.
        max_combinations: Maximum parameter combinations to try.
        verbose: Print progress.

    Returns:
        Dict with:
            - best_params: best hyperparameters
            - best_score: best mean CV AUC
            - all_results: list of (params, score) for all tried combinations
            - cv_scores: per-fold scores for the best model
    """
    # Generate parameter combinations
    all_params = list(ParameterGrid(param_grid))

    # Subsample if too many combinations
    if len(all_params) > max_combinations:
        rng = np.random.RandomState(42)
        indices = rng.choice(len(all_params), size=max_combinations, replace=False)
        all_params = [all_params[i] for i in indices]

    best_params = None
    best_score = -np.inf
    all_results = []

    for i, params in enumerate(all_params):
        fold_aucs = []

        for train_idx, test_idx in cv_splits:
            X_train = X.iloc[train_idx]
            X_test = X.iloc[test_idx]
            y_train = y.iloc[train_idx]
            y_test = y.iloc[test_idx]

            if len(y_train.unique()) < 2 or len(y_test.unique()) < 2:
                continue

            try:
                model = _build_estimator(model_name, params)

                fit_kwargs = {}
                if sample_weights is not None:
                    w = sample_weights.iloc[train_idx].values
                    fit_kwargs["sample_weight"] = w

                model.fit(X_train.values, y_train.values, **fit_kwargs)

                if hasattr(model, "predict_proba"):
                    y_prob = model.predict_proba(X_test.values)
                    # Handle binary classification
                    if y_prob.shape[1] == 2:
                        y_prob = y_prob[:, 1]
                    else:
                        y_prob = y_prob[:, 1]  # second class
                else:
                    y_prob = model.decision_function(X_test.values)

                auc = roc_auc_score(y_test.values, y_prob)
                fold_aucs.append(auc)
            except Exception:
                continue

        mean_auc = np.mean(fold_aucs) if fold_aucs else 0.0
        all_results.append({"params": params, "score": mean_auc, "n_folds": len(fold_aucs)})

        if mean_auc > best_score:
            best_score = mean_auc
            best_params = params

        if verbose and (i + 1) % 10 == 0:
            print(f"  Grid search: {i + 1}/{len(all_params)}, best AUC={best_score:.4f}")

    # Get per-fold scores for best model
    cv_scores = []
    if best_params is not None:
        for train_idx, test_idx in cv_splits:
            X_train = X.iloc[train_idx]
            X_test = X.iloc[test_idx]
            y_train = y.iloc[train_idx]
            y_test = y.iloc[test_idx]

            if len(y_train.unique()) < 2 or len(y_test.unique()) < 2:
                continue

            try:
                model = _build_estimator(model_name, best_params)
                fit_kwargs = {}
                if sample_weights is not None:
                    fit_kwargs["sample_weight"] = sample_weights.iloc[train_idx].values
                model.fit(X_train.values, y_train.values, **fit_kwargs)

                if hasattr(model, "predict_proba"):
                    y_prob = model.predict_proba(X_test.values)[:, 1]
                else:
                    y_prob = model.decision_function(X_test.values)

                auc = roc_auc_score(y_test.values, y_prob)
                acc = accuracy_score(y_test.values, (y_prob > 0.5).astype(int))
                cv_scores.append({"fold": len(cv_scores), "auc": auc, "accuracy": acc})
            except Exception:
                continue

    return {
        "best_params": best_params or {},
        "best_score": best_score,
        "all_results": all_results,
        "cv_scores": cv_scores,
    }


# ---------------------------------------------------------------------------
# ModelingModule class
# ---------------------------------------------------------------------------

class ModelingModule(StageBase):
    """
    M7 Modeling stage: train classifiers with grid search.

    Config keys (from 'modeling' section):
        model: str, model type (default: 'xgboost')
        param_grid: dict, hyperparameter grid (default: built-in grid)
        max_combinations: int, max grid search combos (default: 50)
        use_sample_weights: bool (default: True)
        use_selected_features: bool, use M6 output (default: True)
        verbose: bool (default: False)
    """

    name = "modeling"

    requires = {
        "data": {
            "X": {"required": True, "desc": "Feature matrix"},
            "y": {"required": True, "desc": "Labels"},
            "cv_splits": {"required": True, "desc": "CV splits"},
            "X_selected": {"required": False, "desc": "Selected feature matrix from M6"},
            "selected_features": {"required": False, "desc": "Selected feature names"},
            "sample_weights": {"required": False, "desc": "Sample weights"},
        },
        "params": {
            "model": {"type": "str", "default": "xgboost", "desc": "Model type"},
        },
    }

    produces = {
        "model": "Trained best estimator",
        "model_name": "Model type string",
        "cv_results": "Cross-validation results",
        "best_params": "Best hyperparameters",
    }

    def run(self, data: PipelineData) -> PipelineData:
        """Train model with grid search over walk-forward CV."""
        X_full = data.get("X")
        y = data.get("y")
        cv_splits = data.get("cv_splits")

        # Use selected features if available and configured
        use_selected = self.config.get("use_selected_features", True)
        X_selected = data.get("X_selected", required=False)
        selected_features = data.get("selected_features", required=False)

        if use_selected and X_selected is not None:
            X = X_selected
        else:
            X = X_full

        sample_weights = data.get("sample_weights", required=False)
        use_weights = self.config.get("use_sample_weights", True)
        weights = sample_weights if use_weights else None

        model_name = self.config.get("model", "xgboost")
        verbose = self.config.get("verbose", False)
        max_combinations = self.config.get("max_combinations", 50)

        # Get parameter grid
        param_grid = self.config.get("param_grid")
        if not param_grid:
            defaults = _default_param_grids()
            param_grid = defaults.get(model_name, {})

        # Run grid search
        gs_result = grid_search_cv(
            X=X,
            y=y,
            cv_splits=cv_splits,
            model_name=model_name,
            param_grid=param_grid,
            sample_weights=weights,
            max_combinations=max_combinations,
            verbose=verbose,
        )

        # Train final model on all data with best params
        best_params = gs_result["best_params"]
        final_model = _build_estimator(model_name, best_params)

        fit_kwargs = {}
        if weights is not None:
            fit_kwargs["sample_weight"] = weights.values

        # Remap labels: if labels are {-1, +1}, map to {0, 1}
        y_train = y.copy()
        label_map = None
        unique_labels = sorted(y_train.unique())
        if set(unique_labels) == {-1, 1}:
            label_map = {-1: 0, 1: 1}
            y_train = y_train.map(label_map)

        final_model.fit(X.values, y_train.values, **fit_kwargs)

        # Store results
        data.set("model", final_model, source_module=self.name, desc=f"Trained {model_name}")
        data.set("model_name", model_name, source_module=self.name, desc="Model type")
        data.set("cv_results", gs_result, source_module=self.name, desc="Grid search results")
        data.set("best_params", best_params, source_module=self.name, desc="Best hyperparameters")

        if label_map is not None:
            data.set("label_map", label_map, source_module=self.name, desc="Label encoding map")

        # Trace
        self.trace["model"] = model_name
        self.trace["best_params"] = best_params
        self.trace["best_cv_auc"] = round(gs_result["best_score"], 4)
        self.trace["n_combinations_tested"] = len(gs_result["all_results"])
        self.trace["cv_scores"] = gs_result["cv_scores"]
        self.trace["n_features_used"] = X.shape[1]

        return data
