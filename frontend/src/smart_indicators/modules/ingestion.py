"""
ingestion.py -- M1: Data ingestion stage.

Loads OHLCV data from local CSV files or yfinance.
Supports only time bars (no dollar bars).

Output keys in PipelineData:
    - close, open, high, low, volume (pd.Series)
    - ohlcv (pd.DataFrame with all columns)
"""

import os
import pandas as pd
import numpy as np

from ..core.base_module import StageBase
from ..core.pipeline_data import PipelineData


class IngestionModule(StageBase):
    """
    M1 Ingestion: Load raw price data from CSV or yfinance.

    Config keys (from 'ingestion' section):
        source: "csv" | "yfinance"
        csv_path: path to CSV file (if source == "csv")
        asset: ticker symbol (used for yfinance)
        period: [start_date, end_date]
        frequency: pandas frequency string, e.g., "15min", "1h", "1d"
        columns_map: optional dict to rename CSV columns to standard names
    """

    name = "ingestion"

    requires = {
        "data": {},
        "params": {
            "source": {
                "type": "str",
                "default": "csv",
                "desc": "Data source: 'csv' or 'yfinance'",
            },
        },
    }

    produces = {
        "close": "Close Serie de precios (pd.Series)",
        "open": "Open Serie de precios (pd.Series)",
        "high": "High Serie de precios (pd.Series)",
        "low": "Low Serie de precios (pd.Series)",
        "volume": "Volume series (pd.Series)",
        "ohlcv": "Full OHLCV DataFrame",
    }

    def run(self, data: PipelineData) -> PipelineData:
        """Load data according to the configured source."""
        source = self.config.get("source", "csv")

        if source == "csv":
            df = self._load_csv()
        elif source == "yfinance":
            df = self._load_yfinance()
        else:
            raise ValueError(f"Unknown data source: '{source}'. Use 'csv' or 'yfinance'.")

        # Filter by period if specified
        period = self.config.get("period")
        if period and len(period) == 2:
            start, end = period
            df = df.loc[start:end]

        # Resample to target frequency if needed
        frequency = self.config.get("frequency")
        if frequency and source == "yfinance":
            # yfinance data might already be at the right frequency
            pass

        if df.empty:
            raise ValueError(
                f"No data loaded for source='{source}'. "
                f"Check csv_path or asset/period configuration."
            )

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError(
                "Loaded data does not have a DatetimeIndex. "
                "Check the CSV format or column mapping."
            )

        # Store individual series and the full dataframe
        data.set("close", df["close"], source_module=self.name, desc="Close Serie de precios")
        data.set("open", df["open"], source_module=self.name, desc="Open Serie de precios")
        data.set("high", df["high"], source_module=self.name, desc="High Serie de precios")
        data.set("low", df["low"], source_module=self.name, desc="Low Serie de precios")
        data.set("volume", df["volume"], source_module=self.name, desc="Volume series")
        data.set("ohlcv", df, source_module=self.name, desc="Full OHLCV DataFrame")

        self.trace["rows_loaded"] = len(df)
        self.trace["date_range"] = [str(df.index.min()), str(df.index.max())]
        self.trace["columns"] = list(df.columns)

        return data

    def _load_csv(self) -> pd.DataFrame:
        """Load OHLCV data from a local CSV file."""
        csv_path = self.config.get("csv_path")
        if not csv_path:
            raise ValueError("'csv_path' must be specified when source='csv'.")

        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: '{csv_path}'")

        # Read CSV
        df = pd.read_csv(csv_path)

        # Apply column mapping if provided
        columns_map = self.config.get("columns_map", {})
        if columns_map:
            df = df.rename(columns=columns_map)

        # Normalize column names to lowercase
        df.columns = [c.lower().strip() for c in df.columns]

        # Detect and set datetime index
        date_col = self.config.get("date_column")
        if date_col and date_col.lower() in df.columns:
            df[date_col.lower()] = pd.to_datetime(df[date_col.lower()])
            df = df.set_index(date_col.lower())
        elif "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        elif "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.set_index("datetime")
        elif "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")
        else:
            # Try parsing the first column as datetime
            first_col = df.columns[0]
            try:
                df[first_col] = pd.to_datetime(df[first_col])
                df = df.set_index(first_col)
            except (ValueError, TypeError):
                raise ValueError(
                    "Could not identify a datetime column. "
                    "Specify 'date_column' in the ingestion config."
                )

        df = df.sort_index()

        # Validate required columns
        required = ["open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(
                f"Missing required columns: {missing}. "
                f"Available columns: {list(df.columns)}. "
                f"Use 'columns_map' to rename columns."
            )

        # Select and clean
        df = df[required].copy()
        df = df.apply(pd.to_numeric, errors="coerce")
        df = df.dropna(subset=["close"])

        return df

    def _load_yfinance(self) -> pd.DataFrame:
        """Load OHLCV data from yfinance."""
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError(
                "yfinance is required for source='yfinance'. "
                "Install with: pip install yfinance"
            )

        asset = self.config.get("asset")
        if not asset:
            raise ValueError("'asset' must be specified when source='yfinance'.")

        period_cfg = self.config.get("period", [])
        if len(period_cfg) != 2:
            raise ValueError("'period' must be [start_date, end_date].")

        start, end = period_cfg
        frequency = self.config.get("frequency", "1d")

        # Map common frequency strings to yfinance intervals
        freq_map = {
            "1min": "1m",
            "5min": "5m",
            "15min": "15m",
            "30min": "30m",
            "1h": "1h",
            "1d": "1d",
            "1wk": "1wk",
            "1mo": "1mo",
        }
        interval = freq_map.get(frequency, frequency)

        ticker = yf.Ticker(asset)
        df = ticker.history(start=start, end=end, interval=interval)

        if df.empty:
            raise ValueError(
                f"No data returned from yfinance for {asset} "
                f"from {start} to {end} at interval {interval}."
            )

        # Normalize column names
        df.columns = [c.lower().strip() for c in df.columns]

        # Keep only OHLCV
        keep = ["open", "high", "low", "close", "volume"]
        available = [c for c in keep if c in df.columns]
        df = df[available].copy()

        return df
