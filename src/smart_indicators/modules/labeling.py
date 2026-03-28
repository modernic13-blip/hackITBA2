"""
labeling.py -- M4: Triple barrier labeling stage.

Implements the Triple Barrier Method for labeling financial events:
    - Upper barrier: take-profit (price rises by a factor of volatility)
    - Lower barrier: stop-loss (price falls by a factor of volatility)
    - Vertical barrier: maximum holding period (time expiration)

The label is determined by which barrier is touched first:
    +1 = upper barrier (profitable)
    -1 = lower barrier (loss)

If the vertical barrier is hit first, the label is determined by the
sign of the return at expiration.

Output keys in PipelineData:
    - labels: pd.Series with {-1, +1} labels at event timestamps
    - barriers_info: pd.DataFrame with barrier details per event
"""

import numpy as np
import pandas as pd
from typing import Optional

from ..core.base_module import StageBase
from ..core.pipeline_data import PipelineData


# ---------------------------------------------------------------------------
# Triple Barrier Implementation
# ---------------------------------------------------------------------------

def get_daily_volatility(
    close: pd.Series,
    span: int = 100,
) -> pd.Series:
    """
    Estimate daily (or per-bar) volatility using exponentially weighted std of returns.

    Args:
        close: Close Serie de precios.
        span: EMA span for volatility estimation.

    Returns:
        Series of volatility estimates at each timestamp.
    """
    log_returns = np.log(close / close.shift(1))
    return log_returns.ewm(span=span, min_periods=max(1, span // 2)).std()


def apply_triple_barrier(
    close: pd.Series,
    events: pd.DatetimeIndex,
    pt_sl: list[float],
    min_ret: float = 0.0,
    num_threads: int = 1,
    vertical_barrier_times: Optional[pd.Series] = None,
    volatility: Optional[pd.Series] = None,
    side: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """
    Apply the triple barrier method to a set of events.

    Args:
        close: Close Serie de precios.
        events: DatetimeIndex of event timestamps.
        pt_sl: [profit_taking_multiplier, stop_loss_multiplier].
            Each is a multiplier of volatility. Use 0 to disable a barrier.
        min_ret: Minimum return threshold (added to barriers).
        num_threads: Not used (kept for API compatibility).
        vertical_barrier_times: Series mapping event -> vertical barrier timestamp.
            If None, no vertical barrier is applied.
        volatility: Volatility series. If None, computed from close.
        side: Optional Series of {+1, -1} indicating predicted direction.
            If provided, barriers are asymmetric.

    Returns:
        DataFrame with columns:
            - t1: timestamp when a barrier was first touched
            - ret: return at barrier touch
            - label: +1 or -1
            - barrier: 'upper', 'lower', or 'vertical'
            - pt_level: upper barrier price
            - sl_level: lower barrier price
    """
    if volatility is None:
        volatility = get_daily_volatility(close)

    # Filter events to those in close index
    events = events[events.isin(close.index)]
    if len(events) == 0:
        return pd.DataFrame(columns=["t1", "ret", "label", "barrier", "pt_level", "sl_level"])

    results = []

    for event_time in events:
        if event_time not in close.index:
            continue

        # Get volatility at event time
        vol = volatility.loc[event_time] if event_time in volatility.index else np.nan
        if np.isnan(vol) or vol <= 0:
            vol = 0.01  # fallback

        # Entry price
        entry_price = close.loc[event_time]

        # Determine barrier levels
        pt_mult = pt_sl[0] if len(pt_sl) > 0 else 0
        sl_mult = pt_sl[1] if len(pt_sl) > 1 else 0

        # If side is provided, adjust barriers
        if side is not None and event_time in side.index:
            event_side = side.loc[event_time]
        else:
            event_side = 1  # default: long

        if event_side >= 0:
            pt_level = entry_price * (1 + pt_mult * vol + min_ret) if pt_mult > 0 else np.inf
            sl_level = entry_price * (1 - sl_mult * vol - min_ret) if sl_mult > 0 else -np.inf
        else:
            # Short side: barriers are flipped
            pt_level = entry_price * (1 - pt_mult * vol - min_ret) if pt_mult > 0 else -np.inf
            sl_level = entry_price * (1 + sl_mult * vol + min_ret) if sl_mult > 0 else np.inf

        # Vertical barrier
        if vertical_barrier_times is not None and event_time in vertical_barrier_times.index:
            vb_time = vertical_barrier_times.loc[event_time]
        else:
            vb_time = close.index[-1]

        # Get price path from event to vertical barrier
        loc_start = close.index.get_loc(event_time)
        if isinstance(loc_start, slice):
            loc_start = loc_start.start

        mask = (close.index > event_time) & (close.index <= vb_time)
        path = close.loc[mask]

        if len(path) == 0:
            # No future data available
            continue

        # Check barriers
        touch_time = None
        touch_barrier = None

        if event_side >= 0:
            # Long position
            upper_touches = path[path >= pt_level]
            lower_touches = path[path <= sl_level]
        else:
            # Short position
            upper_touches = path[path <= pt_level]
            lower_touches = path[path >= sl_level]

        first_upper = upper_touches.index[0] if len(upper_touches) > 0 else None
        first_lower = lower_touches.index[0] if len(lower_touches) > 0 else None

        if first_upper is not None and first_lower is not None:
            if first_upper <= first_lower:
                touch_time = first_upper
                touch_barrier = "upper"
            else:
                touch_time = first_lower
                touch_barrier = "lower"
        elif first_upper is not None:
            touch_time = first_upper
            touch_barrier = "upper"
        elif first_lower is not None:
            touch_time = first_lower
            touch_barrier = "lower"
        else:
            # Vertical barrier hit
            touch_time = path.index[-1]
            touch_barrier = "vertical"

        # Compute return
        exit_price = close.loc[touch_time]
        if event_side >= 0:
            ret = (exit_price - entry_price) / entry_price
        else:
            ret = (entry_price - exit_price) / entry_price

        # Label
        if touch_barrier == "upper":
            label = 1
        elif touch_barrier == "lower":
            label = -1
        else:
            # Vertical barrier: label by sign of return
            label = 1 if ret > 0 else -1

        results.append({
            "event_time": event_time,
            "t1": touch_time,
            "ret": ret,
            "label": label,
            "barrier": touch_barrier,
            "pt_level": pt_level if pt_mult > 0 else np.nan,
            "sl_level": sl_level if sl_mult > 0 else np.nan,
        })

    if not results:
        return pd.DataFrame(columns=["t1", "ret", "label", "barrier", "pt_level", "sl_level"])

    df = pd.DataFrame(results).set_index("event_time")
    return df


def get_vertical_barriers(
    events: pd.DatetimeIndex,
    close: pd.Series,
    num_bars: int,
) -> pd.Series:
    """
    Compute vertical barrier timestamps (expiration) for each event.

    Args:
        events: Event timestamps.
        close: Close Serie de precios (used for its index).
        num_bars: Number of bars after event for vertical barrier.

    Returns:
        Series mapping event_time -> vertical_barrier_time.
    """
    vb = pd.Series(dtype="datetime64[ns]", index=events)

    for event_time in events:
        if event_time not in close.index:
            continue
        loc = close.index.get_loc(event_time)
        if isinstance(loc, slice):
            loc = loc.start
        target_loc = min(loc + num_bars, len(close.index) - 1)
        vb.loc[event_time] = close.index[target_loc]

    return vb


def get_event_weights(
    barriers_df: pd.DataFrame,
    close: pd.Series,
    num_threads: int = 1,
) -> pd.Series:
    """
    Compute sample weights based on return magnitude.

    Larger absolute returns get higher weights.

    Args:
        barriers_df: Output of apply_triple_barrier.
        close: Close Serie de precios.

    Returns:
        Series of sample weights indexed by event time.
    """
    if "ret" not in barriers_df.columns:
        return pd.Series(1.0, index=barriers_df.index)

    abs_ret = barriers_df["ret"].abs()
    # Normalize to mean = 1
    if abs_ret.sum() > 0:
        weights = abs_ret / abs_ret.mean()
    else:
        weights = pd.Series(1.0, index=barriers_df.index)

    return weights.clip(lower=0.1, upper=10.0)


# ---------------------------------------------------------------------------
# LabelingModule class
# ---------------------------------------------------------------------------

class LabelingModule(StageBase):
    """
    M4 Labeling stage: apply triple barrier method to events.

    Config keys (from 'labeling' section):
        pt_sl: [profit_taking_mult, stop_loss_mult] (default: [1.0, 1.0])
        min_ret: minimum return threshold (default: 0.0)
        vertical_bars: number of bars for vertical barrier (default: 50)
        vol_span: span for volatility estimation (default: 100)
        use_sample_weights: bool, compute sample weights (default: True)
    """

    name = "labeling"

    requires = {
        "data": {
            "close": {"required": True, "desc": "Close Serie de precios"},
            "tEvents": {"required": True, "desc": "Event timestamps from filtering"},
        },
        "params": {
            "pt_sl": {
                "type": "list",
                "default": [1.0, 1.0],
                "desc": "Profit-taking and stop-loss multipliers",
            },
            "vertical_bars": {
                "type": "int",
                "default": 50,
                "desc": "Number of bars for vertical barrier",
            },
        },
    }

    produces = {
        "labels": "Series of {-1, +1} labels at event timestamps",
        "barriers_info": "DataFrame with barrier details per event",
        "sample_weights": "Series of sample weights (if configured)",
    }

    def run(self, data: PipelineData) -> PipelineData:
        """Apply triple barrier labeling to filtered events."""
        close = data.get("close")
        tEvents = data.get("tEvents")

        # Config
        pt_sl = self.config.get("pt_sl", [1.0, 1.0])
        min_ret = self.config.get("min_ret", 0.0)
        vertical_bars = self.config.get("vertical_bars", 50)
        vol_span = self.config.get("vol_span", 100)
        use_weights = self.config.get("use_sample_weights", True)

        # Compute volatility
        volatility = get_daily_volatility(close, span=vol_span)

        # Compute vertical barriers
        vb_times = get_vertical_barriers(tEvents, close, num_bars=vertical_bars)

        # Apply triple barrier
        barriers_df = apply_triple_barrier(
            close=close,
            events=tEvents,
            pt_sl=pt_sl,
            min_ret=min_ret,
            vertical_barrier_times=vb_times,
            volatility=volatility,
        )

        if barriers_df.empty:
            raise ValueError(
                "No labels generated. Check that events have enough future data "
                "for barrier evaluation."
            )

        labels = barriers_df["label"]

        # Store results
        data.set("labels", labels, source_module=self.name, desc="Triple barrier labels")
        data.set("barriers_info", barriers_df, source_module=self.name, desc="Barrier details")

        # Sample weights
        if use_weights:
            weights = get_event_weights(barriers_df, close)
            data.set("sample_weights", weights, source_module=self.name, desc="Sample weights")

        # Trace
        label_counts = labels.value_counts().to_dict()
        self.trace["n_labels"] = len(labels)
        self.trace["label_distribution"] = {str(k): int(v) for k, v in label_counts.items()}
        self.trace["pt_sl"] = pt_sl
        self.trace["vertical_bars"] = vertical_bars

        barrier_counts = barriers_df["barrier"].value_counts().to_dict()
        self.trace["barrier_distribution"] = barrier_counts
        self.trace["avg_return"] = round(float(barriers_df["ret"].mean()), 6)
        self.trace["avg_abs_return"] = round(float(barriers_df["ret"].abs().mean()), 6)

        return data
