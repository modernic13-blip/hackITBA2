"""
predictor.py -- SignalPredictor: generate trading signals from a trained pipeline.

Takes a trained model and feature configuration from a completed pipeline run
and produces buy/sell signals on new data.

Usage:
    # After pipeline training:
    predictor = SignalPredictor.from_pipeline_data(data)

    # On new data:
    signals = predictor.predict(new_ohlcv_df)
"""

import numpy as np
import pandas as pd
import joblib
from typing import Optional
from pathlib import Path

from .pipeline_data import PipelineData
from ..modules.features import (
    _generate_all_features,
    _detect_freq_minutes,
    _function_info,
)


class SignalPredictor:
    """
    Generate trading signals using a trained model.

    Encapsulates:
        - The trained sklearn model
        - Feature configuration (which indicators, timeframes, normalization)
        - Selected feature names
        - Label mapping

    Attributes:
        model: Trained sklearn classifier.
        feature_config: Dict with feature generation parameters.
        selected_features: List of feature names the model expects.
        label_map: Dict mapping original labels to model labels.
        label_map_inverse: Inverse mapping (model labels -> original).
    """

    def __init__(
        self,
        model,
        feature_config: dict,
        selected_features: list[str],
        label_map: Optional[dict] = None,
    ):
        self.model = model
        self.feature_config = feature_config
        self.selected_features = selected_features
        self.label_map = label_map

        # Build inverse label map
        if label_map:
            self.label_map_inverse = {v: k for k, v in label_map.items()}
        else:
            self.label_map_inverse = None

    @classmethod
    def from_pipeline_data(cls, data: PipelineData) -> "SignalPredictor":
        """
        Create a predictor from completed pipeline data.

        Extracts model, feature config, and selected features from PipelineData.

        Args:
            data: PipelineData from a completed pipeline run.

        Returns:
            SignalPredictor instance.
        """
        model = data.get("model")
        selected_features = data.get("selected_features", required=False)
        label_map = data.get("label_map", required=False)

        # Reconstruct feature config from what the pipeline stored
        feature_config = {
            "timeframes": data.get("feature_config_timeframes", required=False) or ["15min", "1h", "4h", "1d"],
            "indicators": data.get("feature_config_indicators", required=False) or list(_function_info().keys()),
            "indicator_params": data.get("feature_config_params", required=False) or {},
            "smooth": data.get("feature_config_smooth", required=False),
            "normalize": data.get("feature_config_normalize", required=False),
        }

        if selected_features is None:
            # Fallback: use all features from X
            X = data.get("X", required=False)
            if X is not None:
                selected_features = list(X.columns)
            else:
                selected_features = []

        return cls(
            model=model,
            feature_config=feature_config,
            selected_features=selected_features,
            label_map=label_map,
        )

    def predict(
        self,
        ohlcv: pd.DataFrame,
        return_proba: bool = False,
    ) -> pd.DataFrame:
        """
        Generate signals for new OHLCV data.

        Args:
            ohlcv: DataFrame with columns: open, high, low, close, volume.
                Must have a DatetimeIndex.
            return_proba: If True, include probability columns.

        Returns:
            DataFrame with columns:
                - signal: +1 (buy) or -1 (sell)
                - probability: model confidence (if return_proba=True)
        """
        # Normalize column names
        ohlcv = ohlcv.copy()
        ohlcv.columns = [c.lower().strip() for c in ohlcv.columns]

        required = ["open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in ohlcv.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Detect base frequency
        base_freq_minutes = _detect_freq_minutes(ohlcv.index)

        # Generate features
        features_df = _generate_all_features(
            ohlcv=ohlcv,
            base_freq_minutes=base_freq_minutes,
            timeframes_str=self.feature_config.get("timeframes", ["15min", "1h", "4h", "1d"]),
            indicators=self.feature_config.get("indicators", []),
            indicator_params=self.feature_config.get("indicator_params", {}),
            smooth_config=self.feature_config.get("smooth"),
            norm_config=self.feature_config.get("normalize"),
        )

        # Select features
        available = [f for f in self.selected_features if f in features_df.columns]
        missing_features = [f for f in self.selected_features if f not in features_df.columns]

        if not available:
            raise ValueError(
                f"None of the {len(self.selected_features)} selected features "
                f"are present in the generated features. "
                f"Missing: {missing_features[:10]}..."
            )

        if missing_features:
            print(
                f"Warning: {len(missing_features)} features missing, "
                f"using {len(available)}/{len(self.selected_features)} features."
            )

        X = features_df[available].copy()

        # Drop rows with NaN
        valid_mask = X.notna().all(axis=1)
        X_valid = X.loc[valid_mask]

        if len(X_valid) == 0:
            return pd.DataFrame(
                {"signal": [], "probability": []},
                index=pd.DatetimeIndex([]),
            )

        # Predict
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(X_valid.values)
            if proba.shape[1] == 2:
                prob_pos = proba[:, 1]
            else:
                prob_pos = proba[:, 1]
        else:
            prob_pos = self.model.decision_function(X_valid.values)

        y_pred = (prob_pos > 0.5).astype(int)

        # Map back to original labels
        if self.label_map_inverse:
            signals = pd.Series(y_pred, index=X_valid.index).map(self.label_map_inverse)
        else:
            signals = pd.Series(np.where(y_pred == 1, 1, -1), index=X_valid.index)

        result = pd.DataFrame({"signal": signals}, index=X_valid.index)
        if return_proba:
            result["probability"] = prob_pos

        return result

    def predict_latest(
        self,
        ohlcv: pd.DataFrame,
    ) -> dict:
        """
        Get the signal for the most recent bar.

        Args:
            ohlcv: OHLCV DataFrame.

        Returns:
            Dict with: signal, probability, timestamp.
        """
        predictions = self.predict(ohlcv, return_proba=True)

        if predictions.empty:
            return {
                "signal": 0,
                "probability": 0.5,
                "timestamp": None,
            }

        latest = predictions.iloc[-1]
        return {
            "signal": int(latest["signal"]),
            "probability": float(latest["probability"]),
            "timestamp": str(predictions.index[-1]),
        }

    def save(self, filepath: str) -> None:
        """Save predictor to disk."""
        payload = {
            "model": self.model,
            "feature_config": self.feature_config,
            "selected_features": self.selected_features,
            "label_map": self.label_map,
        }
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(payload, filepath)

    @classmethod
    def load(cls, filepath: str) -> "SignalPredictor":
        """Load predictor from disk."""
        payload = joblib.load(filepath)
        return cls(
            model=payload["model"],
            feature_config=payload["feature_config"],
            selected_features=payload["selected_features"],
            label_map=payload.get("label_map"),
        )

    def __repr__(self):
        n_features = len(self.selected_features)
        model_type = type(self.model).__name__
        return f"SignalPredictor(model={model_type}, n_features={n_features})"
