"""
filtering.py -- M3: Event filtering stage.

Detects structurally significant events in the Serie de precios using:
    - CUSUM filter: symmetric or one-sided cumulative sum filter
    - Kalman filter: state-space model for trend detection

These events determine WHEN the model should make predictions,
rather than predicting at every bar.

Output keys in PipelineData:
    - tEvents: pd.DatetimeIndex of detected events
"""

import numpy as np
import pandas as pd
from typing import Optional

from ..core.base_module import StageBase
from ..core.pipeline_data import PipelineData


# ---------------------------------------------------------------------------
# CUSUM Filter
# ---------------------------------------------------------------------------

def cusum_filter(
    close: pd.Series,
    threshold: float,
    mode: str = "symmetric",
) -> pd.DatetimeIndex:
    """
    CUSUM filter for structural break detection.

    The filter fires an event whenever the cumulative sum of signed returns
    exceeds a threshold. After each event, the cumulative sum resets.

    Args:
        close: Close Serie de precios.
        threshold: Threshold for event detection. Typical values: 0.5-2.0
            times the daily standard deviation of returns.
        mode: 'symmetric' (fires on both positive and negative breaks) or
              'positive' or 'negative' (one-sided).

    Returns:
        DatetimeIndex of event timestamps.
    """
    if threshold <= 0:
        raise ValueError(f"CUSUM threshold must be positive, got {threshold}")

    log_returns = np.log(close / close.shift(1)).dropna()

    events = []
    s_pos = 0.0
    s_neg = 0.0

    for i in range(len(log_returns)):
        t = log_returns.index[i]
        r = log_returns.iloc[i]

        s_pos = max(0, s_pos + r)
        s_neg = min(0, s_neg + r)

        if mode == "symmetric":
            if s_pos > threshold:
                events.append(t)
                s_pos = 0.0
                s_neg = 0.0
            elif s_neg < -threshold:
                events.append(t)
                s_pos = 0.0
                s_neg = 0.0
        elif mode == "positive":
            if s_pos > threshold:
                events.append(t)
                s_pos = 0.0
        elif mode == "negative":
            if s_neg < -threshold:
                events.append(t)
                s_neg = 0.0
        else:
            raise ValueError(f"Unknown CUSUM mode: '{mode}'. Use 'symmetric', 'positive', or 'negative'.")

    return pd.DatetimeIndex(events)


def adaptive_cusum_filter(
    close: pd.Series,
    k_factor: float = 0.5,
    lookback: int = 100,
    mode: str = "symmetric",
) -> pd.DatetimeIndex:
    """
    Adaptive CUSUM filter with rolling volatility-scaled threshold.

    Instead of a fixed threshold, uses k_factor * rolling_std(returns, lookback).

    Args:
        close: Close Serie de precios.
        k_factor: Multiplier for rolling standard deviation (sensitivity).
            Lower = more events, higher = fewer events.
        lookback: Window for rolling standard deviation.
        mode: 'symmetric', 'positive', or 'negative'.

    Returns:
        DatetimeIndex of event timestamps.
    """
    log_returns = np.log(close / close.shift(1)).dropna()
    rolling_std = log_returns.rolling(window=lookback, min_periods=max(1, lookback // 2)).std()

    events = []
    s_pos = 0.0
    s_neg = 0.0

    for i in range(len(log_returns)):
        t = log_returns.index[i]
        r = log_returns.iloc[i]
        sigma = rolling_std.iloc[i] if not np.isnan(rolling_std.iloc[i]) else 0.01
        threshold = k_factor * sigma

        s_pos = max(0, s_pos + r)
        s_neg = min(0, s_neg + r)

        if mode == "symmetric":
            if s_pos > threshold:
                events.append(t)
                s_pos = 0.0
                s_neg = 0.0
            elif s_neg < -threshold:
                events.append(t)
                s_pos = 0.0
                s_neg = 0.0
        elif mode == "positive":
            if s_pos > threshold:
                events.append(t)
                s_pos = 0.0
        elif mode == "negative":
            if s_neg < -threshold:
                events.append(t)
                s_neg = 0.0

    return pd.DatetimeIndex(events)


# ---------------------------------------------------------------------------
# Kalman Filter
# ---------------------------------------------------------------------------

def kalman_filter_events(
    close: pd.Series,
    process_noise: float = 0.01,
    measurement_noise: float = 1.0,
    threshold_std: float = 2.0,
) -> pd.DatetimeIndex:
    """
    Kalman filter-based event detection.

    Uses a simple 1D Kalman filter to estimate the trend. Events fire when
    the innovation (prediction error) exceeds threshold_std * innovation_std.

    Args:
        close: Close Serie de precios.
        process_noise: Process noise variance (Q). Higher = more responsive.
        measurement_noise: Measurement noise variance (R). Higher = more smoothing.
        threshold_std: Number of innovation standard deviations for event detection.

    Returns:
        DatetimeIndex of event timestamps.
    """
    n = len(close)
    if n < 2:
        return pd.DatetimeIndex([])

    # State estimate and covariance
    x_hat = close.iloc[0]
    P = 1.0
    Q = process_noise
    R = measurement_noise

    innovations = []
    events = []

    for i in range(1, n):
        # Predict
        x_pred = x_hat
        P_pred = P + Q

        # Update
        z = close.iloc[i]
        innovation = z - x_pred
        S = P_pred + R  # Innovation covariance
        K = P_pred / S  # Kalman gain

        x_hat = x_pred + K * innovation
        P = (1 - K) * P_pred

        innovations.append(innovation)

    # Detect events from innovation magnitude
    innovations = pd.Series(innovations, index=close.index[1:])
    inn_std = innovations.rolling(window=50, min_periods=10).std()

    for i in range(len(innovations)):
        t = innovations.index[i]
        inn = abs(innovations.iloc[i])
        std_val = inn_std.iloc[i] if not np.isnan(inn_std.iloc[i]) else 1.0

        if inn > threshold_std * std_val:
            events.append(t)

    return pd.DatetimeIndex(events)


# ---------------------------------------------------------------------------
# FilteringModule class
# ---------------------------------------------------------------------------

class FilteringModule(StageBase):
    """
    M3 Filtering stage: detect structurally significant events.

    Config keys (from 'filtering' section):
        method: 'cusum' | 'adaptive_cusum' | 'kalman' (default: 'adaptive_cusum')
        cusum_mode: 'symmetric' | 'positive' | 'negative' (default: 'symmetric')
        k_Px: float, Sensibilidad CUSUM for price (default: 0.5)
        k_Vol: float, Sensibilidad CUSUM for volume (optional)
        threshold: float, fixed threshold for basic CUSUM
        lookback: int, rolling window for adaptive CUSUM (default: 100)
        kalman_process_noise: float (default: 0.01)
        kalman_measurement_noise: float (default: 1.0)
        kalman_threshold_std: float (default: 2.0)
        min_events: int, minimum number of events required (default: 50)
        combine: 'union' | 'intersection', how to combine price and volume events
    """

    name = "filtering"

    requires = {
        "data": {
            "close": {"required": True, "desc": "Close Serie de precios"},
            "volume": {"required": False, "desc": "Volume series (for volume CUSUM)"},
        },
        "params": {
            "method": {
                "type": "str",
                "default": "adaptive_cusum",
                "desc": "Filtering method",
            },
            "k_Px": {
                "type": "float",
                "default": 0.5,
                "desc": "Sensibilidad CUSUM for price",
            },
        },
    }

    produces = {
        "tEvents": "DatetimeIndex of significant events",
    }

    def run(self, data: PipelineData) -> PipelineData:
        """Detect significant events using the configured method."""
        close = data.get("close")
        volume = data.get("volume", required=False)
        method = self.config.get("method", "adaptive_cusum")
        cusum_mode = self.config.get("cusum_mode", "symmetric")

        # Price events
        if method == "cusum":
            threshold = self.config.get("threshold", 0.02)
            price_events = cusum_filter(close, threshold=threshold, mode=cusum_mode)

        elif method == "adaptive_cusum":
            k_Px = self.config.get("k_Px", 0.5)
            lookback = self.config.get("lookback", 100)
            price_events = adaptive_cusum_filter(
                close, k_factor=k_Px, lookback=lookback, mode=cusum_mode
            )

        elif method == "kalman":
            process_noise = self.config.get("kalman_process_noise", 0.01)
            measurement_noise = self.config.get("kalman_measurement_noise", 1.0)
            threshold_std = self.config.get("kalman_threshold_std", 2.0)
            price_events = kalman_filter_events(
                close,
                process_noise=process_noise,
                measurement_noise=measurement_noise,
                threshold_std=threshold_std,
            )
        else:
            raise ValueError(f"Unknown filtering method: '{method}'")

        # Optional volume events
        combine = self.config.get("combine", "union")
        k_Vol = self.config.get("k_Vol")

        if k_Vol is not None and volume is not None:
            lookback = self.config.get("lookback", 100)
            vol_events = adaptive_cusum_filter(
                volume, k_factor=k_Vol, lookback=lookback, mode=cusum_mode
            )

            if combine == "union":
                all_events = price_events.union(vol_events).sort_values()
            elif combine == "intersection":
                all_events = price_events.intersection(vol_events).sort_values()
            else:
                all_events = price_events
        else:
            all_events = price_events

        # Deduplicate and sort
        all_events = all_events.drop_duplicates().sort_values()

        # Check minimum events
        min_events = self.config.get("min_events", 50)
        if len(all_events) < min_events:
            self.trace["warning"] = (
                f"Only {len(all_events)} events detected (minimum: {min_events}). "
                f"Consider lowering k_Px or threshold."
            )

        # Store results
        data.set(
            "tEvents",
            all_events,
            source_module=self.name,
            desc=f"{len(all_events)} events via {method}",
        )

        # Trace
        self.trace["method"] = method
        self.trace["n_events"] = len(all_events)
        self.trace["n_bars"] = len(close)
        self.trace["event_ratio"] = round(len(all_events) / len(close), 4) if len(close) > 0 else 0
        if len(all_events) > 0:
            self.trace["first_event"] = str(all_events[0])
            self.trace["last_event"] = str(all_events[-1])

        return data
