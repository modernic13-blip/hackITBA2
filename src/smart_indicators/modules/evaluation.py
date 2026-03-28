"""
evaluation.py -- M8: Model evaluation stage.

Computes comprehensive evaluation metrics WITHOUT MLFlow dependency:
    - AUC-ROC per fold and overall
    - Accuracy, Precision, Recall, F1
    - Sharpe Ratio (annualized)
    - Maximum Drawdown
    - Deflated Sharpe Ratio (DSR)
    - Probability of Backtest Overfitting (PBO)

Output keys in PipelineData:
    - metrics: dict with all evaluation metrics
    - fold_predictions: DataFrame with per-fold predictions
    - equity_curve: Series with cumulative strategy returns
"""

import numpy as np
import pandas as pd
from typing import Optional
from itertools import combinations
from scipy import stats as scipy_stats
from sklearn.metrics import (
    roc_auc_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    log_loss,
)
from sklearn.base import clone

from ..core.base_module import StageBase
from ..core.pipeline_data import PipelineData


# ---------------------------------------------------------------------------
# Financial Metrics
# ---------------------------------------------------------------------------

def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """
    Annualized Sharpe Ratio.

    Args:
        returns: Series of strategy returns.
        risk_free_rate: Annual risk-free rate (default 0).
        periods_per_year: Number of trading periods per year.

    Returns:
        Annualized Sharpe Ratio.
    """
    if len(returns) == 0 or returns.std() == 0:
        return 0.0

    excess = returns - risk_free_rate / periods_per_year
    return float(np.sqrt(periods_per_year) * excess.mean() / excess.std())


def max_drawdown(equity_curve: pd.Series) -> float:
    """
    Maximum drawdown from peak.

    Args:
        equity_curve: Cumulative return series (starts at 1.0).

    Returns:
        Maximum drawdown as a negative fraction (e.g., -0.15 for 15% drawdown).
    """
    if len(equity_curve) == 0:
        return 0.0

    peak = equity_curve.cummax()
    dd = (equity_curve - peak) / peak
    return float(dd.min())


def calmar_ratio(
    returns: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """
    Calmar Ratio: annualized return / max drawdown.

    Args:
        returns: Series of strategy returns.
        periods_per_year: Number of trading periods per year.

    Returns:
        Calmar Ratio.
    """
    eq = (1 + returns).cumprod()
    mdd = abs(max_drawdown(eq))
    if mdd == 0:
        return 0.0
    ann_ret = (eq.iloc[-1]) ** (periods_per_year / len(returns)) - 1
    return float(ann_ret / mdd)


# ---------------------------------------------------------------------------
# Deflated Sharpe Ratio (DSR)
# ---------------------------------------------------------------------------

def deflated_sharpe_ratio(
    sharpe_observed: float,
    n_trials: int,
    n_returns: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    sharpe_benchmark: float = 0.0,
) -> float:
    """
    Deflated Sharpe Ratio (DSR) per Bailey & Lopez de Prado (2014).

    Adjusts the Sharpe Ratio for multiple testing (selection bias).
    Returns the probability that the observed Sharpe is significant
    after accounting for the number of trials.

    Args:
        sharpe_observed: Observed (best) Sharpe Ratio.
        n_trials: Number of independent backtests / strategies tried.
        n_returns: Number of return observations.
        skewness: Skewness of returns.
        kurtosis: Kurtosis of returns (excess kurtosis + 3).
        sharpe_benchmark: Expected Sharpe under null hypothesis.

    Returns:
        DSR probability in [0, 1]. Higher = more likely genuine.
    """
    if n_trials <= 0 or n_returns <= 0:
        return 0.0

    # Expected maximum Sharpe from n_trials under null
    # E[max(SR)] ~ SR_benchmark + sqrt(2 * log(n_trials)) * adjustment
    e_max = sharpe_benchmark
    if n_trials > 1:
        gamma = 0.5772156649  # Euler-Mascheroni constant
        e_max += np.sqrt(2 * np.log(n_trials)) * (
            1 - gamma / np.sqrt(2 * np.log(n_trials))
        )

    # Standard error of Sharpe estimate
    se_sr = np.sqrt(
        (1 - skewness * sharpe_observed + (kurtosis - 1) / 4 * sharpe_observed ** 2)
        / (n_returns - 1)
    )

    if se_sr <= 0:
        return 0.0

    # DSR = Prob(SR > E[max(SR)])
    z = (sharpe_observed - e_max) / se_sr
    dsr = float(scipy_stats.norm.cdf(z))

    return dsr


# ---------------------------------------------------------------------------
# Probability of Backtest Overfitting (PBO)
# ---------------------------------------------------------------------------

def probability_of_backtest_overfitting(
    fold_returns: list[pd.Series],
    n_partitions: int = 8,
) -> dict:
    """
    Probability of Backtest Overfitting (PBO) via combinatorial purged CV.

    The idea: split OOS fold returns into 2S groups, form all (S choose S)
    combinations of in-sample / out-of-sample, and check how often the
    best IS strategy underperforms the median OOS.

    A high PBO (close to 1) means the strategy is likely overfit.

    Args:
        fold_returns: List of return Series, one per CV fold.
        n_partitions: Number of partitions for the CSCV matrix.

    Returns:
        Dict with:
            - pbo: float, probability of overfitting
            - logits: list of logit values per combination
            - n_combinations: number of combinations tested
    """
    n_folds = len(fold_returns)
    if n_folds < 2:
        return {"pbo": 0.0, "logits": [], "n_combinations": 0}

    # Concatenate all fold returns into a matrix
    # Each row = time step, each column = fold strategy returns
    all_returns = pd.concat(fold_returns, axis=1).dropna()
    if all_returns.empty:
        return {"pbo": 0.0, "logits": [], "n_combinations": 0}

    n_obs = len(all_returns)
    n_strategies = all_returns.shape[1]

    if n_strategies < 2:
        return {"pbo": 0.0, "logits": [], "n_combinations": 0}

    # Partition the time series into n_partitions blocks
    block_size = max(1, n_obs // n_partitions)
    actual_partitions = min(n_partitions, n_obs)

    partition_sharpes = []
    for i in range(actual_partitions):
        start = i * block_size
        end = min((i + 1) * block_size, n_obs)
        block = all_returns.iloc[start:end]
        # Sharpe per strategy for this block
        sharpes = block.mean() / block.std().replace(0, np.nan)
        partition_sharpes.append(sharpes.fillna(0))

    if len(partition_sharpes) < 2:
        return {"pbo": 0.0, "logits": [], "n_combinations": 0}

    partition_sharpes_df = pd.DataFrame(partition_sharpes)

    # Generate IS/OOS combinations
    half = actual_partitions // 2
    if half < 1:
        return {"pbo": 0.0, "logits": [], "n_combinations": 0}

    all_indices = list(range(actual_partitions))

    # Limit combinations for performance
    max_combos = 100
    combo_list = list(combinations(all_indices, half))
    if len(combo_list) > max_combos:
        rng = np.random.RandomState(42)
        indices = rng.choice(len(combo_list), size=max_combos, replace=False)
        combo_list = [combo_list[i] for i in indices]

    logits = []
    n_overfit = 0

    for is_indices in combo_list:
        oos_indices = [i for i in all_indices if i not in is_indices]
        if not oos_indices:
            continue

        # IS performance: average Sharpe across IS partitions per strategy
        is_sharpes = partition_sharpes_df.iloc[list(is_indices)].mean()
        oos_sharpes = partition_sharpes_df.iloc[oos_indices].mean()

        # Best IS strategy
        best_is_strategy = is_sharpes.idxmax()

        # Rank of this strategy in OOS
        oos_rank = oos_sharpes.rank(ascending=False)
        best_oos_rank = oos_rank[best_is_strategy]

        # Logit: is the best IS strategy below median OOS?
        median_rank = n_strategies / 2.0
        if best_oos_rank > median_rank:
            n_overfit += 1
            logits.append(1)
        else:
            logits.append(0)

    n_combinations = len(combo_list)
    pbo = n_overfit / n_combinations if n_combinations > 0 else 0.0

    return {
        "pbo": round(pbo, 4),
        "logits": logits,
        "n_combinations": n_combinations,
    }


# ---------------------------------------------------------------------------
# Fold Evaluation Helper
# ---------------------------------------------------------------------------

def evaluate_fold(
    model,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    close_test: pd.Series,
    sample_weights_train: Optional[pd.Series] = None,
    label_map: Optional[dict] = None,
) -> dict:
    """
    Evaluate a model on a single fold.

    Returns dict with metrics and predictions.
    """
    model_clone = clone(model)

    # Prepare labels
    y_train_mapped = y_train.copy()
    y_test_mapped = y_test.copy()
    if label_map:
        y_train_mapped = y_train_mapped.map(label_map)
        y_test_mapped = y_test_mapped.map(label_map)

    # Fit
    fit_kwargs = {}
    if sample_weights_train is not None:
        fit_kwargs["sample_weight"] = sample_weights_train.values

    model_clone.fit(X_train.values, y_train_mapped.values, **fit_kwargs)

    # Predict
    if hasattr(model_clone, "predict_proba"):
        y_prob = model_clone.predict_proba(X_test.values)
        if y_prob.shape[1] == 2:
            y_prob_pos = y_prob[:, 1]
        else:
            y_prob_pos = y_prob[:, 1]
    else:
        y_prob_pos = model_clone.decision_function(X_test.values)

    y_pred = (y_prob_pos > 0.5).astype(int)

    # Classification metrics
    try:
        auc = roc_auc_score(y_test_mapped.values, y_prob_pos)
    except ValueError:
        auc = 0.5

    acc = accuracy_score(y_test_mapped.values, y_pred)

    try:
        prec = precision_score(y_test_mapped.values, y_pred, zero_division=0)
        rec = recall_score(y_test_mapped.values, y_pred, zero_division=0)
        f1 = f1_score(y_test_mapped.values, y_pred, zero_division=0)
    except Exception:
        prec = rec = f1 = 0.0

    # Strategy returns
    # Predictions in original label space: 1 = long, 0 (or -1) = short/flat
    positions = pd.Series(
        np.where(y_pred == 1, 1, -1),
        index=y_test.index,
    )

    if close_test is not None and len(close_test) > 0:
        aligned_close = close_test.reindex(y_test.index).ffill()
        price_returns = aligned_close.pct_change().fillna(0)
        strategy_returns = positions.shift(1).fillna(0) * price_returns
    else:
        strategy_returns = pd.Series(0, index=y_test.index)

    return {
        "auc": auc,
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "y_prob": y_prob_pos,
        "y_pred": y_pred,
        "positions": positions,
        "strategy_returns": strategy_returns,
    }


# ---------------------------------------------------------------------------
# EvaluationModule class
# ---------------------------------------------------------------------------

class EvaluationModule(StageBase):
    """
    M8 Evaluation stage: comprehensive model evaluation.

    Computes per-fold and aggregate metrics including DSR and PBO.
    No MLFlow dependency.

    Config keys (from 'evaluation' section):
        risk_free_rate: float, annual risk-free rate (default: 0.0)
        periods_per_year: int, trading periods per year (default: 252)
        n_trials_dsr: int, number of trials for DSR (default: 10)
        pbo_partitions: int, partitions for PBO (default: 8)
        commission_bps: float, commission in basis points (default: 1.0)
    """

    name = "evaluation"

    requires = {
        "data": {
            "model": {"required": True, "desc": "Trained model"},
            "X": {"required": True, "desc": "Feature matrix"},
            "y": {"required": True, "desc": "Labels"},
            "cv_splits": {"required": True, "desc": "CV splits"},
            "close": {"required": True, "desc": "Close Serie de precios"},
            "X_selected": {"required": False, "desc": "Selected features"},
            "selected_features": {"required": False, "desc": "Selected feature names"},
            "sample_weights": {"required": False, "desc": "Sample weights"},
            "label_map": {"required": False, "desc": "Label encoding map"},
        },
        "params": {},
    }

    produces = {
        "metrics": "Dict with all evaluation metrics",
        "fold_predictions": "DataFrame with per-fold predictions",
        "equity_curve": "Cumulative strategy returns",
    }

    def run(self, data: PipelineData) -> PipelineData:
        """Evaluate model on all CV folds and compute aggregate metrics."""
        model = data.get("model")
        X_full = data.get("X")
        y = data.get("y")
        cv_splits = data.get("cv_splits")
        close = data.get("close")

        # Use selected features if available
        X_selected = data.get("X_selected", required=False)
        selected_features = data.get("selected_features", required=False)
        use_selected = self.config.get("use_selected_features", True)

        if use_selected and X_selected is not None:
            X = X_selected
        else:
            X = X_full

        sample_weights = data.get("sample_weights", required=False)
        label_map = data.get("label_map", required=False)

        # Config
        risk_free_rate = self.config.get("risk_free_rate", 0.0)
        periods_per_year = self.config.get("periods_per_year", 252)
        n_trials_dsr = self.config.get("n_trials_dsr", 10)
        pbo_partitions = self.config.get("pbo_partitions", 8)
        commission_bps = self.config.get("commission_bps", 1.0)

        # Evaluate per fold
        fold_metrics = []
        all_predictions = []
        fold_returns_list = []

        for fold_i, (train_idx, test_idx) in enumerate(cv_splits):
            X_train = X.iloc[train_idx]
            X_test = X.iloc[test_idx]
            y_train = y.iloc[train_idx]
            y_test = y.iloc[test_idx]

            w_train = None
            if sample_weights is not None:
                w_train = sample_weights.iloc[train_idx]

            close_test = close.reindex(y_test.index)

            fold_result = evaluate_fold(
                model=model,
                X_train=X_train,
                y_train=y_train,
                X_test=X_test,
                y_test=y_test,
                close_test=close_test,
                sample_weights_train=w_train,
                label_map=label_map,
            )

            # Apply commission
            strategy_ret = fold_result["strategy_returns"]
            positions = fold_result["positions"]
            trades = positions.diff().abs().fillna(0)
            commission_cost = trades * (commission_bps / 10000.0)
            strategy_ret_net = strategy_ret - commission_cost

            fold_metrics.append({
                "fold": fold_i,
                "auc": fold_result["auc"],
                "accuracy": fold_result["accuracy"],
                "precision": fold_result["precision"],
                "recall": fold_result["recall"],
                "f1": fold_result["f1"],
                "sharpe": sharpe_ratio(strategy_ret_net, risk_free_rate, periods_per_year),
                "sharpe_gross": sharpe_ratio(strategy_ret, risk_free_rate, periods_per_year),
            })

            # Collect predictions
            pred_df = pd.DataFrame({
                "fold": fold_i,
                "y_true": y_test.values,
                "y_prob": fold_result["y_prob"],
                "y_pred": fold_result["y_pred"],
                "position": fold_result["positions"].values,
                "strategy_return": strategy_ret_net.values,
            }, index=y_test.index)
            all_predictions.append(pred_df)
            fold_returns_list.append(strategy_ret_net)

        # Aggregate metrics
        metrics_df = pd.DataFrame(fold_metrics)

        agg_metrics = {
            "mean_auc": round(float(metrics_df["auc"].mean()), 4),
            "std_auc": round(float(metrics_df["auc"].std()), 4),
            "mean_accuracy": round(float(metrics_df["accuracy"].mean()), 4),
            "mean_precision": round(float(metrics_df["precision"].mean()), 4),
            "mean_recall": round(float(metrics_df["recall"].mean()), 4),
            "mean_f1": round(float(metrics_df["f1"].mean()), 4),
            "mean_sharpe": round(float(metrics_df["sharpe"].mean()), 4),
            "std_sharpe": round(float(metrics_df["sharpe"].std()), 4),
            "per_fold": fold_metrics,
        }

        # Equity curve from concatenated fold returns
        if all_predictions:
            predictions_df = pd.concat(all_predictions).sort_index()
            all_strat_returns = predictions_df["strategy_return"]
            equity = (1 + all_strat_returns).cumprod()

            agg_metrics["total_return"] = round(float(equity.iloc[-1] - 1), 4)
            agg_metrics["max_drawdown"] = round(max_drawdown(equity), 4)
            agg_metrics["calmar_ratio"] = round(
                calmar_ratio(all_strat_returns, periods_per_year), 4
            )
        else:
            predictions_df = pd.DataFrame()
            equity = pd.Series(dtype=float)

        # Deflated Sharpe Ratio
        observed_sharpe = agg_metrics["mean_sharpe"]
        n_returns = sum(len(fr) for fr in fold_returns_list)
        all_rets = pd.concat(fold_returns_list) if fold_returns_list else pd.Series(dtype=float)

        if len(all_rets) > 2:
            skew = float(all_rets.skew())
            kurt = float(all_rets.kurtosis() + 3)  # excess -> raw
        else:
            skew = 0.0
            kurt = 3.0

        dsr = deflated_sharpe_ratio(
            sharpe_observed=observed_sharpe,
            n_trials=n_trials_dsr,
            n_returns=n_returns,
            skewness=skew,
            kurtosis=kurt,
        )
        agg_metrics["dsr"] = round(dsr, 4)
        agg_metrics["dsr_n_trials"] = n_trials_dsr

        # Probability of Backtest Overfitting
        pbo_result = probability_of_backtest_overfitting(
            fold_returns=fold_returns_list,
            n_partitions=pbo_partitions,
        )
        agg_metrics["pbo"] = pbo_result["pbo"]
        agg_metrics["pbo_n_combinations"] = pbo_result["n_combinations"]

        # Store results
        data.set("metrics", agg_metrics, source_module=self.name, desc="Evaluation metrics")
        data.set(
            "fold_predictions",
            predictions_df,
            source_module=self.name,
            desc="Per-fold predictions",
        )
        data.set("equity_curve", equity, source_module=self.name, desc="Strategy equity curve")

        # Trace
        self.trace["metrics"] = agg_metrics

        return data
