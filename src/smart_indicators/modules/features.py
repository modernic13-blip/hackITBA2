"""
features.py -- M2: Feature engineering stage.

Generates 200+ technical indicators across multiple timeframes.
All features are computed from OHLCV data and include:
    - Momentum: RSI, MACD, CCI, Williams %R
    - Volatility: Bollinger Bands, SuperTrend (ATR)
    - Volume: VWAP, CMF, MFI, OBV
    - Trend: ADX
    - Microstructure: OFI, TRANS_RATE, TICK_AUTOCORR
    - Smoothed and normalized variants

Output key in PipelineData:
    - features_df: pd.DataFrame with all computed features
"""

import re
import warnings
import numpy as np
import pandas as pd
from typing import Optional, Union

from ..core.base_module import StageBase
from ..core.pipeline_data import PipelineData

warnings.filterwarnings("ignore", category=RuntimeWarning)


# ---------------------------------------------------------------------------
# Helper functions: timeframe parsing and detection
# ---------------------------------------------------------------------------

def _parse_timeframe_str(tf_str: str) -> pd.Timedelta:
    """
    Parse a timeframe string like '15min', '1h', '4h', '1d' into a Timedelta.

    Supported formats:
        '15min', '30min', '1h', '4h', '12h', '1d', '1w'
    """
    tf_str = tf_str.strip().lower()
    match = re.match(r"^(\d+)\s*(min|h|d|w)$", tf_str)
    if not match:
        raise ValueError(f"Cannot parse timeframe string: '{tf_str}'")

    value = int(match.group(1))
    unit = match.group(2)

    unit_map = {
        "min": "min",
        "h": "h",
        "d": "D",
        "w": "W",
    }
    return pd.Timedelta(value, unit=unit_map[unit])


def _timeframe(tf_str: str) -> dict:
    """
    Return a dict with timeframe info.

    Returns:
        {"str": "1h", "td": Timedelta('0 days 01:00:00'), "minutes": 60}
    """
    td = _parse_timeframe_str(tf_str)
    total_minutes = int(td.total_seconds() / 60)
    return {"str": tf_str, "td": td, "minutes": total_minutes}


def _detect_freq_minutes(index: pd.DatetimeIndex) -> int:
    """
    Detect the most common bar frequency in minutes from a DatetimeIndex.

    Returns the mode of time differences in minutes.
    """
    if len(index) < 2:
        return 1
    diffs = pd.Series(index).diff().dropna()
    minutes = diffs.dt.total_seconds() / 60
    mode_val = minutes.mode()
    if len(mode_val) == 0:
        return int(minutes.median())
    return int(mode_val.iloc[0])


def _transform_timeframe(
    series: pd.Series,
    base_freq_minutes: int,
    target_tf_minutes: int,
    agg: str = "last",
) -> pd.Series:
    """
    Resample a series from base frequency to a target timeframe.

    Args:
        series: Input series at base frequency.
        base_freq_minutes: Base bar frequency in minutes.
        target_tf_minutes: Target timeframe in minutes.
        agg: Aggregation method ('last', 'first', 'max', 'min', 'sum', 'mean').

    Returns:
        Resampled series, forward-filled to original index.
    """
    if target_tf_minutes <= base_freq_minutes:
        return series.copy()

    rule = f"{target_tf_minutes}min"
    resampled = series.resample(rule).agg(agg)
    # Forward-fill and reindex to original
    return resampled.reindex(series.index, method="ffill")


def _nan_length(series: pd.Series) -> int:
    """Count leading NaN values in a series."""
    if len(series) == 0:
        return 0
    first_valid = series.first_valid_index()
    if first_valid is None:
        return len(series)
    return series.index.get_loc(first_valid)


def _preprocess_series(series: pd.Series, fill_method: str = "ffill") -> pd.Series:
    """Preprocess a series: forward-fill, then backward-fill remaining NaNs at the start."""
    s = series.copy()
    if fill_method == "ffill":
        s = s.ffill().bfill()
    return s


# ---------------------------------------------------------------------------
# Indicator functions
# ---------------------------------------------------------------------------

def _ema_emstd(
    close: pd.Series,
    span: int,
) -> tuple[pd.Series, pd.Series]:
    """
    Compute exponential moving average and exponential moving standard deviation.

    Args:
        close: Close Serie de precios.
        span: EMA span parameter.

    Returns:
        (ema, emstd) tuple of pd.Series.
    """
    ema = close.ewm(span=span, min_periods=span).mean()
    emstd = close.ewm(span=span, min_periods=span).std()
    return ema, emstd


def _willr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Williams %R oscillator.

    Measures overbought/oversold conditions.
    Range: [-100, 0] where -100 = oversold, 0 = overbought.
    """
    highest_high = high.rolling(window=period, min_periods=period).max()
    lowest_low = low.rolling(window=period, min_periods=period).min()
    denom = highest_high - lowest_low
    willr = -100 * (highest_high - close) / denom.replace(0, np.nan)
    return willr


def _vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    """
    Volume Weighted Average Price (VWAP).

    Cumulative VWAP = cumsum(typical_price * volume) / cumsum(volume).
    """
    typical_price = (high + low + close) / 3.0
    cum_tp_vol = (typical_price * volume).cumsum()
    cum_vol = volume.cumsum()
    vwap = cum_tp_vol / cum_vol.replace(0, np.nan)
    return vwap


def _cmf(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 20,
) -> pd.Series:
    """
    Chaikin Money Flow (CMF).

    Measures buying/selling pressure over a period.
    Range: [-1, +1].
    """
    hl_range = high - low
    mfm = ((close - low) - (high - close)) / hl_range.replace(0, np.nan)
    mfv = mfm * volume
    cmf = mfv.rolling(window=period, min_periods=period).sum() / \
          volume.rolling(window=period, min_periods=period).sum().replace(0, np.nan)
    return cmf


def _cci(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 20,
) -> pd.Series:
    """
    Commodity Channel Index (CCI).

    Measures deviation of price from its statistical mean.
    """
    typical_price = (high + low + close) / 3.0
    sma = typical_price.rolling(window=period, min_periods=period).mean()
    mad = typical_price.rolling(window=period, min_periods=period).apply(
        lambda x: np.abs(x - x.mean()).mean(), raw=True
    )
    cci = (typical_price - sma) / (0.015 * mad.replace(0, np.nan))
    return cci


def _bbands(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands.

    Returns:
        (upper_band, middle_band, lower_band)
    """
    middle = close.rolling(window=period, min_periods=period).mean()
    std = close.rolling(window=period, min_periods=period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return upper, lower, middle


def _ems(
    close: pd.Series,
    span: int,
) -> pd.Series:
    """
    Exponential Moving Smoothing (EMS).

    Simply the EMA of the close price.
    """
    return close.ewm(span=span, min_periods=span).mean()


def _ems_pct(
    close: pd.Series,
    span: int,
) -> pd.Series:
    """
    Percentage distance from EMS.

    (close - ems) / ems * 100
    """
    ems = _ems(close, span)
    return ((close - ems) / ems.replace(0, np.nan)) * 100.0


def _ofi(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 20,
) -> pd.Series:
    """
    Order Flow Imbalance (OFI).

    Microstructure indicator measuring buying vs selling pressure.
    Uses the Lee-Ready tick rule approximation.
    """
    # Tick direction: +1 if close > previous close, -1 otherwise
    tick_dir = np.sign(close.diff()).fillna(0)
    # Where diff == 0, use previous direction
    tick_dir = tick_dir.replace(0, np.nan).ffill().fillna(0)

    buy_vol = volume * (tick_dir == 1).astype(float)
    sell_vol = volume * (tick_dir == -1).astype(float)

    buy_sum = buy_vol.rolling(window=period, min_periods=1).sum()
    sell_sum = sell_vol.rolling(window=period, min_periods=1).sum()
    total = buy_sum + sell_sum

    ofi = (buy_sum - sell_sum) / total.replace(0, np.nan)
    return ofi


def _trans_rate(
    close: pd.Series,
    volume: pd.Series,
    period: int = 20,
) -> pd.Series:
    """
    Transaction Rate indicator.

    Measures the rate of price change relative to volume.
    """
    price_change = close.diff().abs()
    avg_price_change = price_change.rolling(window=period, min_periods=1).mean()
    avg_volume = volume.rolling(window=period, min_periods=1).mean()
    rate = avg_price_change / avg_volume.replace(0, np.nan)
    return rate


def _tick_autocorr(
    close: pd.Series,
    period: int = 20,
) -> pd.Series:
    """
    Tick autocorrelation.

    Measures the autocorrelation of price changes over a rolling window.
    High positive autocorrelation = trending, negative = mean-reverting.
    """
    returns = close.pct_change()
    autocorr = returns.rolling(window=period, min_periods=period).apply(
        lambda x: pd.Series(x).autocorr(lag=1) if len(x) > 1 else 0.0,
        raw=True,
    )
    return autocorr


# ---------------------------------------------------------------------------
# RSI implementation
# ---------------------------------------------------------------------------

def _rsi(
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Relative Strength Index (RSI).

    Uses Wilder's smoothing method (exponential).
    Range: [0, 100].
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


# ---------------------------------------------------------------------------
# MACD implementation
# ---------------------------------------------------------------------------

def _macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    MACD (Moving Average Convergence Divergence).

    Returns:
        (macd_line, signal_line, histogram)
    """
    ema_fast = close.ewm(span=fast, min_periods=fast).mean()
    ema_slow = close.ewm(span=slow, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


# ---------------------------------------------------------------------------
# ADX implementation
# ---------------------------------------------------------------------------

def _adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Average Directional Index (ADX).

    Measures trend strength regardless of direction.
    Range: [0, 100]. Values > 25 indicate a strong trend.
    """
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    # True Range
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Directional Movement
    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=close.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=close.index,
    )

    # Wilder's smoothing
    atr = tr.ewm(alpha=1.0 / period, min_periods=period).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / period, min_periods=period).mean() / atr.replace(0, np.nan)
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / period, min_periods=period).mean() / atr.replace(0, np.nan)

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1.0 / period, min_periods=period).mean()

    return adx


# ---------------------------------------------------------------------------
# ATR and SuperTrend
# ---------------------------------------------------------------------------

def _atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average True Range (ATR)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=period).mean()


def _supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 10,
    multiplier: float = 3.0,
) -> pd.Series:
    """
    SuperTrend indicator.

    Returns the SuperTrend line. Above close = bearish, below = bullish.
    """
    atr = _atr(high, low, close, period)
    hl2 = (high + low) / 2.0

    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    supertrend = pd.Series(np.nan, index=close.index)
    direction = pd.Series(1, index=close.index)

    for i in range(1, len(close)):
        if close.iloc[i] > upper_band.iloc[i - 1]:
            direction.iloc[i] = 1
        elif close.iloc[i] < lower_band.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]

            if direction.iloc[i] == 1 and lower_band.iloc[i] < lower_band.iloc[i - 1]:
                lower_band.iloc[i] = lower_band.iloc[i - 1]
            if direction.iloc[i] == -1 and upper_band.iloc[i] > upper_band.iloc[i - 1]:
                upper_band.iloc[i] = upper_band.iloc[i - 1]

        supertrend.iloc[i] = lower_band.iloc[i] if direction.iloc[i] == 1 else upper_band.iloc[i]

    return supertrend


# ---------------------------------------------------------------------------
# MFI and OBV
# ---------------------------------------------------------------------------

def _mfi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Money Flow Index (MFI).

    Volume-weighted RSI. Range: [0, 100].
    """
    typical_price = (high + low + close) / 3.0
    money_flow = typical_price * volume

    tp_diff = typical_price.diff()
    pos_flow = pd.Series(
        np.where(tp_diff > 0, money_flow, 0.0), index=close.index
    )
    neg_flow = pd.Series(
        np.where(tp_diff < 0, money_flow, 0.0), index=close.index
    )

    pos_sum = pos_flow.rolling(window=period, min_periods=period).sum()
    neg_sum = neg_flow.rolling(window=period, min_periods=period).sum()

    mfr = pos_sum / neg_sum.replace(0, np.nan)
    mfi = 100.0 - (100.0 / (1.0 + mfr))
    return mfi


def _obv(
    close: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    """
    On-Balance Volume (OBV).

    Cumulative volume with sign determined by price direction.
    """
    direction = np.sign(close.diff()).fillna(0)
    obv = (volume * direction).cumsum()
    return obv


# ---------------------------------------------------------------------------
# Normalization functions
# ---------------------------------------------------------------------------

def _quantiles(
    series: pd.Series,
    window: int = 100,
) -> pd.Series:
    """
    Rolling quantile normalization.

    Maps each value to its percentile rank within the rolling window.
    Range: [0, 1].
    """
    return series.rolling(window=window, min_periods=max(1, window // 2)).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else np.nan,
        raw=False,
    )


def _zscore(
    series: pd.Series,
    window: int = 100,
) -> pd.Series:
    """
    Rolling Z-score normalization.

    (x - rolling_mean) / rolling_std.
    """
    rolling_mean = series.rolling(window=window, min_periods=max(1, window // 2)).mean()
    rolling_std = series.rolling(window=window, min_periods=max(1, window // 2)).std()
    return (series - rolling_mean) / rolling_std.replace(0, np.nan)


def _ema_norm(
    series: pd.Series,
    span: int = 100,
) -> pd.Series:
    """
    EMA normalization.

    (x - ema) / ema, measures relative deviation from trend.
    """
    ema = series.ewm(span=span, min_periods=span).mean()
    return (series - ema) / ema.replace(0, np.nan)


def _mean_sustraction(
    series: pd.Series,
    window: int = 100,
) -> pd.Series:
    """
    Rolling mean subtraction (demeaning).

    x - rolling_mean.
    """
    rolling_mean = series.rolling(window=window, min_periods=max(1, window // 2)).mean()
    return series - rolling_mean


def _mean_division(
    series: pd.Series,
    window: int = 100,
) -> pd.Series:
    """
    Rolling mean division.

    x / rolling_mean.
    """
    rolling_mean = series.rolling(window=window, min_periods=max(1, window // 2)).mean()
    return series / rolling_mean.replace(0, np.nan)


# ---------------------------------------------------------------------------
# Higher-level feature composition helpers
# ---------------------------------------------------------------------------

def _function_info() -> dict:
    """
    Return a registry of all available indicator functions and their metadata.

    Each entry maps a function name to:
        - func: the callable
        - inputs: list of required OHLCV columns
        - outputs: list of output column names (templates)
        - params: dict of parameter names -> default values
    """
    return {
        "rsi": {
            "func": _rsi,
            "inputs": ["close"],
            "outputs": ["rsi_{period}"],
            "params": {"period": [14]},
        },
        "macd": {
            "func": _macd,
            "inputs": ["close"],
            "outputs": ["macd_line", "macd_signal", "macd_hist"],
            "params": {"fast": [12], "slow": [26], "signal": [9]},
        },
        "cci": {
            "func": _cci,
            "inputs": ["high", "low", "close"],
            "outputs": ["cci_{period}"],
            "params": {"period": [20]},
        },
        "willr": {
            "func": _willr,
            "inputs": ["high", "low", "close"],
            "outputs": ["willr_{period}"],
            "params": {"period": [14]},
        },
        "bbands": {
            "func": _bbands,
            "inputs": ["close"],
            "outputs": ["bb_upper_{period}", "bb_lower_{period}", "bb_middle_{period}"],
            "params": {"period": [20], "num_std": [2.0]},
        },
        "adx": {
            "func": _adx,
            "inputs": ["high", "low", "close"],
            "outputs": ["adx_{period}"],
            "params": {"period": [14]},
        },
        "atr": {
            "func": _atr,
            "inputs": ["high", "low", "close"],
            "outputs": ["atr_{period}"],
            "params": {"period": [14]},
        },
        "supertrend": {
            "func": _supertrend,
            "inputs": ["high", "low", "close"],
            "outputs": ["supertrend_{period}"],
            "params": {"period": [10], "multiplier": [3.0]},
        },
        "vwap": {
            "func": _vwap,
            "inputs": ["high", "low", "close", "volume"],
            "outputs": ["vwap"],
            "params": {},
        },
        "cmf": {
            "func": _cmf,
            "inputs": ["high", "low", "close", "volume"],
            "outputs": ["cmf_{period}"],
            "params": {"period": [20]},
        },
        "mfi": {
            "func": _mfi,
            "inputs": ["high", "low", "close", "volume"],
            "outputs": ["mfi_{period}"],
            "params": {"period": [14]},
        },
        "obv": {
            "func": _obv,
            "inputs": ["close", "volume"],
            "outputs": ["obv"],
            "params": {},
        },
        "ofi": {
            "func": _ofi,
            "inputs": ["open", "high", "low", "close", "volume"],
            "outputs": ["ofi_{period}"],
            "params": {"period": [20]},
        },
        "trans_rate": {
            "func": _trans_rate,
            "inputs": ["close", "volume"],
            "outputs": ["trans_rate_{period}"],
            "params": {"period": [20]},
        },
        "tick_autocorr": {
            "func": _tick_autocorr,
            "inputs": ["close"],
            "outputs": ["tick_autocorr_{period}"],
            "params": {"period": [20]},
        },
        "ems_pct": {
            "func": _ems_pct,
            "inputs": ["close"],
            "outputs": ["ems_pct_{span}"],
            "params": {"span": [20]},
        },
    }


def _function_per_timeframe(
    func_name: str,
    ohlcv: pd.DataFrame,
    base_freq_minutes: int,
    target_tf_minutes: int,
    tf_label: str,
    params: dict,
) -> pd.DataFrame:
    """
    Compute a single indicator at a specific timeframe.

    Args:
        func_name: Name of indicator function (key in _function_info).
        ohlcv: OHLCV DataFrame at base frequency.
        base_freq_minutes: Base bar frequency in minutes.
        target_tf_minutes: Target timeframe in minutes.
        tf_label: String label for the timeframe (e.g., "1h").
        params: Parameter overrides for the indicator.

    Returns:
        DataFrame with computed indicator columns, prefixed with timeframe.
    """
    info = _function_info()
    if func_name not in info:
        raise ValueError(f"Unknown indicator: '{func_name}'")

    spec = info[func_name]
    func = spec["func"]
    input_names = spec["inputs"]

    # Resample input series to target timeframe
    resampled = {}
    agg_map = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }

    for col_name in input_names:
        if col_name not in ohlcv.columns:
            return pd.DataFrame(index=ohlcv.index)
        agg = agg_map.get(col_name, "last")
        resampled[col_name] = _transform_timeframe(
            ohlcv[col_name], base_freq_minutes, target_tf_minutes, agg=agg
        )

    # Build function arguments
    merged_params = {}
    for pname, defaults in spec["params"].items():
        if pname in params:
            val = params[pname]
            merged_params[pname] = val if isinstance(val, list) else [val]
        else:
            merged_params[pname] = defaults

    result_frames = []

    # Generate all parameter combinations
    param_combos = [{}]
    for pname, values in merged_params.items():
        new_combos = []
        for combo in param_combos:
            for v in values:
                new_combo = combo.copy()
                new_combo[pname] = v
                new_combos.append(new_combo)
        param_combos = new_combos

    for combo in param_combos:
        # Build kwargs for function call
        kwargs = {}
        input_args = []

        # Positional: input series
        if func_name == "ofi":
            input_args = [
                resampled["open"],
                resampled["high"],
                resampled["low"],
                resampled["close"],
                resampled["volume"],
            ]
        elif func_name in ("vwap", "cmf", "mfi"):
            input_args = [
                resampled["high"],
                resampled["low"],
                resampled["close"],
                resampled["volume"],
            ]
        elif func_name in ("cci", "willr", "adx", "atr", "supertrend"):
            input_args = [
                resampled["high"],
                resampled["low"],
                resampled["close"],
            ]
        elif func_name == "obv":
            input_args = [resampled["close"], resampled["volume"]]
        elif func_name == "trans_rate":
            input_args = [resampled["close"], resampled["volume"]]
        else:
            input_args = [resampled["close"]]

        # Add named parameters
        kwargs.update(combo)

        try:
            result = func(*input_args, **kwargs)
        except Exception:
            continue

        # Handle single vs multiple output
        output_templates = spec["outputs"]

        if isinstance(result, tuple):
            for i, (template, series) in enumerate(zip(output_templates, result)):
                col_name = template.format(**combo)
                col_full = f"{tf_label}_{col_name}"
                result_frames.append(series.rename(col_full))
        else:
            if output_templates:
                col_name = output_templates[0].format(**combo)
            else:
                col_name = func_name
            col_full = f"{tf_label}_{col_name}"
            result_frames.append(result.rename(col_full))

    if not result_frames:
        return pd.DataFrame(index=ohlcv.index)

    return pd.concat(result_frames, axis=1)


def _function_per_timeframes(
    func_name: str,
    ohlcv: pd.DataFrame,
    base_freq_minutes: int,
    timeframes: list[dict],
    params: dict,
) -> pd.DataFrame:
    """
    Compute a single indicator across multiple timeframes.

    Args:
        func_name: Indicator name.
        ohlcv: Base OHLCV data.
        base_freq_minutes: Base frequency in minutes.
        timeframes: List of timeframe dicts from _timeframe().
        params: Parameter overrides.

    Returns:
        DataFrame with columns for each timeframe variant.
    """
    frames = []
    for tf in timeframes:
        tf_minutes = tf["minutes"]
        tf_label = tf["str"]
        if tf_minutes < base_freq_minutes:
            continue
        df = _function_per_timeframe(
            func_name, ohlcv, base_freq_minutes, tf_minutes, tf_label, params
        )
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame(index=ohlcv.index)

    return pd.concat(frames, axis=1)


def _smoothie(
    series: pd.Series,
    window: int,
    method: str = "ema",
) -> pd.Series:
    """
    Smooth a series using the specified method.

    Methods: 'ema', 'sma', 'wma'.
    """
    if method == "ema":
        return series.ewm(span=window, min_periods=window).mean()
    elif method == "sma":
        return series.rolling(window=window, min_periods=window).mean()
    elif method == "wma":
        weights = np.arange(1, window + 1, dtype=float)
        return series.rolling(window=window, min_periods=window).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )
    else:
        return series


def _normalize_per_timeframes(
    features_df: pd.DataFrame,
    norm_methods: list[str],
    norm_window: int = 100,
) -> pd.DataFrame:
    """
    Apply normalization methods to all feature columns.

    Args:
        features_df: DataFrame of raw features.
        norm_methods: List of normalization methods to apply.
            Options: 'quantiles', 'zscore', 'ema_norm', 'mean_sub', 'mean_div'
        norm_window: Rolling window for normalization.

    Returns:
        DataFrame with original + normalized columns.
    """
    norm_funcs = {
        "quantiles": lambda s: _quantiles(s, window=norm_window),
        "zscore": lambda s: _zscore(s, window=norm_window),
        "ema_norm": lambda s: _ema_norm(s, span=norm_window),
        "mean_sub": lambda s: _mean_sustraction(s, window=norm_window),
        "mean_div": lambda s: _mean_division(s, window=norm_window),
    }

    new_cols = {}
    for method in norm_methods:
        if method not in norm_funcs:
            continue
        func = norm_funcs[method]
        for col in features_df.columns:
            new_name = f"{col}__{method}"
            new_cols[new_name] = func(features_df[col])

    if new_cols:
        norm_df = pd.DataFrame(new_cols, index=features_df.index)
        return pd.concat([features_df, norm_df], axis=1)

    return features_df


def _get_subset(
    features_df: pd.DataFrame,
    subset_config: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Select a subset of features based on configuration.

    subset_config options:
        include: list of regex patterns to include
        exclude: list of regex patterns to exclude
        max_features: maximum number of features to keep
    """
    if subset_config is None:
        return features_df

    df = features_df.copy()

    # Include filter
    include_patterns = subset_config.get("include", [])
    if include_patterns:
        cols_to_keep = set()
        for pattern in include_patterns:
            matched = [c for c in df.columns if re.search(pattern, c)]
            cols_to_keep.update(matched)
        if cols_to_keep:
            df = df[[c for c in df.columns if c in cols_to_keep]]

    # Exclude filter
    exclude_patterns = subset_config.get("exclude", [])
    for pattern in exclude_patterns:
        cols_to_drop = [c for c in df.columns if re.search(pattern, c)]
        df = df.drop(columns=cols_to_drop, errors="ignore")

    # Max features
    max_features = subset_config.get("max_features")
    if max_features and len(df.columns) > max_features:
        # Keep columns with least NaN proportion
        nan_pct = df.isna().mean().sort_values()
        df = df[nan_pct.index[:max_features]]

    return df


def _generate_all_features(
    ohlcv: pd.DataFrame,
    base_freq_minutes: int,
    timeframes_str: list[str],
    indicators: list[str],
    indicator_params: dict,
    smooth_config: Optional[dict] = None,
    norm_config: Optional[dict] = None,
    subset_config: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Master function to generate all features.

    This is the main entry point for feature generation. It:
    1. Parses timeframes.
    2. Computes each indicator across all valid timeframes.
    3. Optionally smooths the features.
    4. Optionally normalizes the features.
    5. Optionally subsets the features.

    Args:
        ohlcv: OHLCV DataFrame at base frequency.
        base_freq_minutes: Base bar frequency in minutes.
        timeframes_str: List of timeframe strings, e.g., ["15min", "1h", "4h", "1d"].
        indicators: List of indicator names to compute.
        indicator_params: Dict of indicator_name -> params overrides.
        smooth_config: Optional smoothing config {"method": "ema", "window": 5}.
        norm_config: Optional normalization config {"methods": ["zscore"], "window": 100}.
        subset_config: Optional subset config.

    Returns:
        DataFrame with all computed features aligned to the original index.
    """
    # Parse timeframes
    timeframes = [_timeframe(tf) for tf in timeframes_str]

    # Available indicators
    available = _function_info()
    if not indicators:
        indicators = list(available.keys())

    all_frames = []

    for indicator_name in indicators:
        if indicator_name not in available:
            continue

        params = indicator_params.get(indicator_name, {})
        df = _function_per_timeframes(
            indicator_name, ohlcv, base_freq_minutes, timeframes, params
        )
        if not df.empty:
            all_frames.append(df)

    if not all_frames:
        return pd.DataFrame(index=ohlcv.index)

    features_df = pd.concat(all_frames, axis=1)

    # Add basic return features
    close = ohlcv["close"]
    for tf in timeframes:
        tf_minutes = tf["minutes"]
        tf_label = tf["str"]
        if tf_minutes < base_freq_minutes:
            continue

        # Returns at this timeframe
        tf_close = _transform_timeframe(close, base_freq_minutes, tf_minutes, agg="last")
        bars = max(1, tf_minutes // base_freq_minutes)

        # Simple return
        ret = tf_close.pct_change(periods=bars)
        features_df[f"{tf_label}_return"] = ret

        # Log return
        log_ret = np.log(tf_close / tf_close.shift(bars))
        features_df[f"{tf_label}_log_return"] = log_ret

        # Realized volatility (rolling std of returns)
        vol_window = max(2, 20 * bars)
        features_df[f"{tf_label}_realized_vol"] = ret.rolling(
            window=vol_window, min_periods=max(1, vol_window // 2)
        ).std()

    # Apply smoothing if configured
    if smooth_config:
        method = smooth_config.get("method", "ema")
        window = smooth_config.get("window", 5)
        smooth_cols = {}
        for col in features_df.columns:
            smoothed = _smoothie(features_df[col], window=window, method=method)
            smooth_cols[f"{col}__smooth_{method}{window}"] = smoothed
        smooth_df = pd.DataFrame(smooth_cols, index=features_df.index)
        features_df = pd.concat([features_df, smooth_df], axis=1)

    # Apply normalization if configured
    if norm_config:
        methods = norm_config.get("methods", [])
        window = norm_config.get("window", 100)
        features_df = _normalize_per_timeframes(features_df, methods, window)

    # Apply subset filter if configured
    if subset_config:
        features_df = _get_subset(features_df, subset_config)

    # Clean up: replace infinities and clip extreme values
    features_df = features_df.replace([np.inf, -np.inf], np.nan)

    return features_df


# ---------------------------------------------------------------------------
# FeaturesModule class
# ---------------------------------------------------------------------------

class FeaturesModule(StageBase):
    """
    M2 Feature Engineering stage.

    Takes OHLCV data from PipelineData and generates 200+ technical indicators
    across multiple timeframes, with optional smoothing and normalization.

    Config keys (from 'features' section):
        timeframes: list of timeframe strings, e.g., ["15min", "1h", "4h", "12h", "1d"]
        indicators: list of indicator names to compute (or "all")
        indicator_params: dict of indicator-specific parameter overrides
        smooth: optional smoothing config {"method": "ema", "window": 5}
        normalize: optional normalization config {"methods": ["zscore", "quantiles"], "window": 100}
        subset: optional subset config {"include": [...], "exclude": [...], "max_features": N}
        drop_na_threshold: float, drop columns with NaN fraction above this (default 0.5)
    """

    name = "features"

    requires = {
        "data": {
            "close": {"required": True, "desc": "Close Serie de precios"},
            "open": {"required": True, "desc": "Open Serie de precios"},
            "high": {"required": True, "desc": "High Serie de precios"},
            "low": {"required": True, "desc": "Low Serie de precios"},
            "volume": {"required": True, "desc": "Volume series"},
            "ohlcv": {"required": True, "desc": "Full OHLCV DataFrame"},
        },
        "params": {},
    }

    produces = {
        "features_df": "DataFrame with all computed features",
        "feature_names": "List of feature column names",
    }

    def run(self, data: PipelineData) -> PipelineData:
        """Generate all features from OHLCV data."""
        ohlcv = data.get("ohlcv")

        # Detect base frequency
        base_freq_minutes = _detect_freq_minutes(ohlcv.index)

        # Read configuration
        timeframes_str = self.config.get("timeframes", ["15min", "1h", "4h", "1d"])
        indicators = self.config.get("indicators", [])
        if indicators == "all" or not indicators:
            indicators = list(_function_info().keys())

        indicator_params = self.config.get("indicator_params", {})
        smooth_config = self.config.get("smooth", None)
        norm_config = self.config.get("normalize", None)
        subset_config = self.config.get("subset", None)
        drop_na_threshold = self.config.get("drop_na_threshold", 0.5)

        # Generate features
        features_df = _generate_all_features(
            ohlcv=ohlcv,
            base_freq_minutes=base_freq_minutes,
            timeframes_str=timeframes_str,
            indicators=indicators,
            indicator_params=indicator_params,
            smooth_config=smooth_config,
            norm_config=norm_config,
            subset_config=subset_config,
        )

        # Drop columns with too many NaNs
        if drop_na_threshold > 0:
            nan_frac = features_df.isna().mean()
            cols_to_drop = nan_frac[nan_frac > drop_na_threshold].index.tolist()
            if cols_to_drop:
                features_df = features_df.drop(columns=cols_to_drop)

        # Store results
        data.set(
            "features_df",
            features_df,
            source_module=self.name,
            desc=f"Feature matrix: {features_df.shape[1]} features x {features_df.shape[0]} bars",
        )
        data.set(
            "feature_names",
            list(features_df.columns),
            source_module=self.name,
            desc="List of feature column names",
        )

        # Trace info
        self.trace["n_features"] = features_df.shape[1]
        self.trace["n_bars"] = features_df.shape[0]
        self.trace["base_freq_minutes"] = base_freq_minutes
        self.trace["timeframes"] = timeframes_str
        self.trace["indicators_used"] = indicators
        self.trace["nan_columns_dropped"] = len(cols_to_drop) if drop_na_threshold > 0 else 0

        return data
