#!/usr/bin/env python3
"""
main_executor.py — Orquestador Central del Sistema de Trading Algorítmico HackITBA
====================================================================================
Integra el pipeline ML (M1-M8) con optimización Black-Litterman para construir
portafolios multi-activo con predicciones de retorno generadas por XGBoost/LightGBM.

Flujo de Ejecución:
  1. Carga el dataset_completo.csv (historia 2020-2025, 11 activos, 1h)
  2. Ejecuta M2+M3 en el dataset COMPLETO (evita Cold Start en indicadores)
  3. Corte temporal estricto en 2025-01-01: train (2020-2024) / test (2025)
  4. Por cada perfil YAML: entrena M4-M8, genera predicciones 2025, corre BL diario
  5. Exporta results_<perfil>.json para el frontend React

Uso:
  python main_executor.py                          # Corre los 3 perfiles
  python main_executor.py --profiles low_risk      # Solo un perfil
  python main_executor.py --data /ruta/data.csv    # CSV personalizado
"""

import os
import sys
import json
import copy
import logging
import warnings
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from smart_indicators import SignalPipeline
from smart_indicators.core.pipeline_data import PipelineData

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Constantes globales ───────────────────────────────────────────────────────
TRAIN_CUTOFF = pd.Timestamp("2025-01-01")
DATA_PATH    = ROOT / "data" / "dataset_completo.csv"
PROFILES_DIR = ROOT / "configs"
OUTPUT_DIR   = ROOT / "results"
INITIAL_CAPITAL = 1_000.0

PROFILE_FILES = {
    "low_risk":  "low_risk.yaml",
    "med_risk":  "med_risk.yaml",
    "high_risk": "high_risk.yaml",
}

# ── Configuración base del pipeline para datos de 1 hora ─────────────────────
BASE_PIPELINE_CONFIG: dict = {
    "frequency": "1h",
    "ingestion": {
        "source": "csv",
    },
    "features": {
        "timeframes": ["1h", "4h", "12h", "1d"],
        "indicators": "all",
        "indicator_params": {
            "rsi":          {"period": [14, 21]},
            "macd":         {"fast": [12], "slow": [26], "signal": [9]},
            "cci":          {"period": [20]},
            "willr":        {"period": [14]},
            "bbands":       {"period": [20], "num_std": [2.0]},
            "adx":          {"period": [14]},
            "atr":          {"period": [14]},
            "supertrend":   {"period": [10], "multiplier": [3.0]},
            "cmf":          {"period": [20]},
            "mfi":          {"period": [14]},
            "ofi":          {"period": [20]},
            "trans_rate":   {"period": [20]},
            "tick_autocorr":{"period": [20]},
            "ems_pct":      {"span": [20, 50]},
        },
        "normalize": {
            "methods": ["zscore"],
            "window": 504,      # ~21 días a 1h — suficiente historia para normalizar
        },
        "drop_na_threshold": 0.5,
    },
    "filtering": {
        "method":     "adaptive_cusum",
        "cusum_mode": "symmetric",
        "k_Px":       0.5,
        "lookback":   168,      # 7 días en horas
        "min_events": 50,
    },
    "labeling": {
        "pt_sl":              [1.5, 1.0],
        "min_ret":            0.0,
        "vertical_bars":      72,   # 3 días a 1h
        "vol_span":           168,
        "use_sample_weights": True,
    },
    "splitting": {
        "n_splits":       5,
        "test_size":      0.2,
        "purge_hours":    72,
        "embargo_pct":    0.01,
        "expanding":      True,
        "min_train_size": 500,
    },
    "feature_selection": {
        "max_features":       25,
        "min_improvement":    0.002,
        "n_estimators":       100,
        "max_depth":          5,
        "use_sample_weights": True,
        "verbose":            False,
    },
    "modeling": {
        "model":                 "xgboost",
        "max_combinations":      12,
        "use_sample_weights":    True,
        "use_selected_features": True,
        "verbose":               False,
    },
    "evaluation": {
        "risk_free_rate":   0.045,
        "periods_per_year": 6048,   # 252 días × 24 horas
        "n_trials_dsr":     10,
        "pbo_partitions":   6,
        "commission_bps":   5.0,
        "use_selected_features": True,
    },
}


# =============================================================================
# Black-Litterman Optimizer
# =============================================================================

class BlackLittermanOptimizer:
    """
    Optimizador Black-Litterman con vistas absolutas generadas por ML.

    Fórmula del posterior:
        Π  = δ × Σ × w_mkt              (retornos de equilibrio)
        μ_BL = M⁻¹ × [(τΣ)⁻¹ × Π + P'Ω⁻¹q]
        donde M = (τΣ)⁻¹ + P'Ω⁻¹P

    Referencia: Black & Litterman (1992), He & Litterman (1999)
    """

    def __init__(
        self,
        delta:      float = 2.5,
        tau:        float = 0.05,
        max_weight: float = 0.40,
        min_weight: float = 0.0,
    ):
        self.delta      = delta       # Aversión al riesgo del mercado
        self.tau        = tau         # Incertidumbre en el prior
        self.max_weight = max_weight  # Límite máx. por activo
        self.min_weight = min_weight

    # ------------------------------------------------------------------
    def optimize(
        self,
        prices:           pd.DataFrame,        # Precios históricos (T × n)
        ml_signals:       Dict[str, float],    # {ticker: señal ∈ [-1, +1]}
        confidence_level: float = 0.70,
    ) -> Tuple[Dict[str, float], float]:
        """
        Calcula pesos óptimos Black-Litterman.

        Args:
            prices:           DataFrame de precios históricos (días × activos).
            ml_signals:       Señales del modelo ML por activo.
            confidence_level: Confianza en las vistas ML (0-1).

        Returns:
            (weights_dict, avg_confidence)
        """
        tickers = list(prices.columns)
        n       = len(tickers)

        if n < 2:
            return {t: 1.0 / n for t in tickers}, 0.5

        returns = prices.pct_change().dropna()
        if len(returns) < 20:
            return {t: 1.0 / n for t in tickers}, 0.5

        # Covarianza anualizada
        cov = returns.cov().values * 252
        cov += np.eye(n) * 1e-6      # Regularización numérica

        # Prior: pesos de mercado iguales (sin datos de capitalización)
        w_mkt = np.ones(n) / n
        pi    = self.delta * cov @ w_mkt   # Retornos de equilibrio

        # Construir vistas ML (absolutas: P = identidad para los activos con vista)
        view_tickers = [t for t in tickers if t in ml_signals]
        if len(view_tickers) < 2:
            return {t: 1.0 / n for t in tickers}, 0.5

        k     = len(view_tickers)
        P     = np.zeros((k, n))
        q     = np.zeros(k)
        vols  = np.sqrt(np.diag(cov))

        for i, ticker in enumerate(view_tickers):
            j     = tickers.index(ticker)
            P[i, j] = 1.0
            # Vista escalada por volatilidad diaria del activo
            daily_vol = vols[j] / np.sqrt(252)
            q[i]      = float(ml_signals[ticker]) * daily_vol

        # Incertidumbre en vistas: inversamente proporcional a la confianza
        omega_diag = np.array([
            ((1.0 - confidence_level) / max(confidence_level, 1e-6))
            * self.tau
            * cov[tickers.index(t), tickers.index(t)]
            for t in view_tickers
        ])
        Omega = np.diag(omega_diag + 1e-8)

        # Posterior Black-Litterman
        try:
            tau_sigma_inv = np.linalg.inv(self.tau * cov)
            omega_inv     = np.linalg.inv(Omega)
            M             = tau_sigma_inv + P.T @ omega_inv @ P
            M_inv         = np.linalg.inv(M)
            mu_bl         = M_inv @ (tau_sigma_inv @ pi + P.T @ omega_inv @ q)
            sigma_bl      = cov + M_inv
        except np.linalg.LinAlgError:
            logger.warning("BL: fallo en inversión de matriz, usando pesos iguales")
            return {t: 1.0 / n for t in tickers}, 0.5

        # Pesos analíticos sin restricciones: w* = (δΣ_BL)⁻¹ μ_BL
        try:
            raw_w = np.linalg.inv(self.delta * sigma_bl) @ mu_bl
        except np.linalg.LinAlgError:
            raw_w = mu_bl.copy()

        # Proyectar al símplex con box constraints [0, max_weight]
        weights = self._project_simplex(raw_w, self.max_weight)

        # Confianza media: escala de [0.5, 1.0] basada en fuerza de señales
        avg_conf = 0.5 + 0.5 * float(np.mean([abs(ml_signals.get(t, 0)) for t in tickers]))

        return {t: float(w) for t, w in zip(tickers, weights)}, avg_conf

    @staticmethod
    def _project_simplex(raw: np.ndarray, max_w: float) -> np.ndarray:
        """
        Proyecta sobre el símplex de probabilidad con restricción max_w por activo.
        Garantiza: Σwᵢ = 1, wᵢ ≥ 0, wᵢ ≤ max_w.
        """
        w = np.clip(raw, 0.0, None)
        s = w.sum()
        if s <= 0:
            n = len(raw)
            return np.ones(n) / n
        w /= s

        # Iteración para imponer max_weight
        for _ in range(200):
            excess_mask = w > max_w
            if not excess_mask.any():
                break
            excess       = w[excess_mask].sum() - max_w * excess_mask.sum()
            w[excess_mask] = max_w
            below         = ~excess_mask
            if below.any():
                w[below] += excess / below.sum()

        total = w.sum()
        return w / total if total > 0 else np.ones(len(w)) / len(w)


# =============================================================================
# Main Executor
# =============================================================================

class MainExecutor:
    """
    Orquestador central del sistema de trading algorítmico.

    Coordina la carga de datos, entrenamiento por activo, generación de
    predicciones y optimización de portafolio con Black-Litterman.
    """

    def __init__(
        self,
        data_path:    Optional[str] = None,
        profiles_dir: Optional[str] = None,
        output_dir:   Optional[str] = None,
    ):
        self.data_path    = Path(data_path    or DATA_PATH)
        self.profiles_dir = Path(profiles_dir or PROFILES_DIR)
        self.output_dir   = Path(output_dir   or OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Caché compartida entre perfiles
        self.raw_data:  Dict[str, pd.DataFrame] = {}   # {ticker: ohlcv_df}
        self.cold_data: Dict[str, PipelineData]  = {}   # {ticker: PipelineData M2+M3}

        # Modelos entrenados por perfil × activo
        self.profile_models: Dict[str, Dict[str, dict]] = {}

    # =========================================================================
    # 1. Carga de Datos
    # =========================================================================

    def load_data(self) -> Dict[str, pd.DataFrame]:
        """
        Carga dataset_completo.csv y separa por activo.
        Fallback a CSVs individuales si no existe el combinado.
        """
        logger.info(f"Cargando datos desde {self.data_path}")

        if self.data_path.exists():
            self._load_combined_csv()
        else:
            logger.warning("dataset_completo.csv no encontrado, usando CSVs individuales")
            self._load_individual_csvs()

        logger.info(f"Activos cargados: {sorted(self.raw_data.keys())}")
        return self.raw_data

    def _load_combined_csv(self):
        """Carga el CSV combinado y separa por columna 'Ticker'."""
        df = pd.read_csv(self.data_path)

        # Normalizar nombre de columna de fecha
        date_col = next(
            (c for c in df.columns if c.lower() in ("date", "datetime", "timestamp")),
            df.columns[0],
        )
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.set_index(date_col).sort_index()
        df.columns = [c.lower() for c in df.columns]

        if "ticker" not in df.columns:
            # Un solo activo, usar nombre del archivo
            ticker = self.data_path.stem.replace("-usd", "").upper()
            self.raw_data[ticker] = self._extract_ohlcv(df)
            return

        for ticker, group in df.groupby("ticker"):
            ticker_clean = str(ticker).replace("-USD", "").replace("-", "")
            asset_df     = group.drop(columns=["ticker"])
            ohlcv        = self._extract_ohlcv(asset_df)
            if len(ohlcv) >= 100:
                self.raw_data[ticker_clean] = ohlcv

    def _load_individual_csvs(self):
        """Carga CSVs individuales por activo desde el directorio de datos."""
        data_dir = self.data_path.parent
        skip     = {"dataset_completo.csv", "README.md"}

        for csv_file in sorted(data_dir.glob("*.csv")):
            if csv_file.name in skip:
                continue
            ticker = csv_file.stem.replace("-USD", "").replace("-", "")
            try:
                df = pd.read_csv(csv_file)
                date_col = next(
                    (c for c in df.columns if c.lower() in ("date", "datetime")),
                    df.columns[0],
                )
                df[date_col] = pd.to_datetime(df[date_col])
                df = df.set_index(date_col).sort_index()
                df.columns = [c.lower() for c in df.columns]
                ohlcv = self._extract_ohlcv(df)
                if len(ohlcv) >= 100:
                    self.raw_data[ticker] = ohlcv
            except Exception as exc:
                logger.warning(f"No se pudo cargar {csv_file.name}: {exc}")

    @staticmethod
    def _extract_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza columnas a [open, high, low, close, volume]."""
        rename = {
            "adj close": "close",
            "adj_close": "close",
        }
        df = df.rename(columns=rename)
        needed = ["open", "high", "low", "close", "volume"]
        present = [c for c in needed if c in df.columns]
        if "close" not in present:
            raise ValueError("Columna 'close' no encontrada")
        result = df[present].copy()
        # Rellenar columnas OHLCV faltantes con close si es necesario
        for col in needed:
            if col not in result.columns:
                result[col] = result["close"] if col != "volume" else 0.0
        return result[needed].dropna(how="all")

    # =========================================================================
    # 2. Construcción de Configuración del Pipeline
    # =========================================================================

    def load_profile(self, profile_name: str) -> dict:
        """Carga y retorna el YAML de perfil de riesgo."""
        path = self.profiles_dir / PROFILE_FILES[profile_name]
        if not path.exists():
            raise FileNotFoundError(f"Perfil no encontrado: {path}")
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def build_pipeline_config(
        self,
        ticker:           str,
        ohlcv:            pd.DataFrame,
        profile_config:   dict,
        asset_overrides:  dict,
    ) -> dict:
        """
        Construye el config completo para SignalPipeline fusionando:
          BASE_PIPELINE_CONFIG → overrides del perfil → overrides del activo.
        """
        config = copy.deepcopy(BASE_PIPELINE_CONFIG)
        config["asset"]  = ticker
        config["period"] = [
            ohlcv.index.min().strftime("%Y-%m-%d"),
            ohlcv.index.max().strftime("%Y-%m-%d"),
        ]
        config["frequency"] = self._detect_frequency(ohlcv)

        # Overrides a nivel de perfil (sección "pipeline" en el YAML)
        pipeline_overrides = profile_config.get("pipeline", {})
        config = _deep_merge(config, pipeline_overrides)

        # Overrides específicos del activo (sección "custom_assets" en el YAML)
        if asset_overrides:
            config = _deep_merge(config, asset_overrides)

        # Crypto: ajustar periods_per_year a 8760 (24/7)
        crypto_tickers = {"BTC", "ETH", "COIN", "DOGE", "SOL"}
        if ticker.upper() in crypto_tickers:
            config["evaluation"]["periods_per_year"] = 8760

        return config

    @staticmethod
    def _detect_frequency(ohlcv: pd.DataFrame) -> str:
        """Auto-detecta la frecuencia de barras a partir del índice."""
        if len(ohlcv) < 3:
            return "1d"
        diffs   = pd.Series(ohlcv.index).diff().dropna()
        median  = diffs.median().total_seconds() / 60  # minutos
        if   median <=  5:  return "5min"
        elif median <= 15:  return "15min"
        elif median <= 60:  return "1h"
        elif median <= 240: return "4h"
        else:               return "1d"

    # =========================================================================
    # 3. Cold Start: M2 + M3 sobre datos completos (2020-2025)
    # =========================================================================

    def run_cold_start(
        self,
        ticker: str,
        ohlcv:  pd.DataFrame,
        config: dict,
    ) -> Optional[PipelineData]:
        """
        Ejecuta M2 (features) y M3 (filtering) sobre el historial COMPLETO.
        Almacena el resultado en caché para no repetirlo entre perfiles.
        """
        if ticker in self.cold_data:
            return self.cold_data[ticker]

        logger.info(f"[{ticker}] Cold-start M2+M3 sobre {len(ohlcv)} barras (2020-2025)...")

        # Inyectar OHLCV directamente — se salta M1
        data = PipelineData()
        data.set("close",  ohlcv["close"],  "executor", "Precios de cierre completos")
        data.set("open",   ohlcv["open"],   "executor")
        data.set("high",   ohlcv["high"],   "executor")
        data.set("low",    ohlcv["low"],    "executor")
        data.set("volume", ohlcv["volume"], "executor")
        data.set("ohlcv",  ohlcv,           "executor", "OHLCV completo 2020-2025")

        try:
            pipeline     = SignalPipeline(config=config)
            result, ok   = pipeline.run(
                stages=["features", "filtering"],
                data=data,
                verbose=False,
            )
            if not ok:
                logger.error(f"[{ticker}] Cold-start falló")
                return None

            n_events = len(result.get("tEvents", required=False) or [])
            n_feats  = result.get("features_df", required=False)
            n_feats  = n_feats.shape[1] if n_feats is not None else 0
            logger.info(f"[{ticker}] Cold-start OK | features={n_feats} | eventos={n_events}")

            self.cold_data[ticker] = result
            return result

        except Exception as exc:
            logger.error(f"[{ticker}] Cold-start error: {exc}", exc_info=True)
            return None

    # =========================================================================
    # 4. Entrenamiento: M4-M8 sobre datos pre-2025
    # =========================================================================

    def train_asset(
        self,
        ticker:    str,
        cold:      PipelineData,
        config:    dict,
    ) -> Optional[dict]:
        """
        Ejecuta M4 (labeling) → M5 (splitting) → M6 (feature_selection)
        → M7 (modeling) → M8 (evaluation) sobre el período de entrenamiento.

        Usa features_df pre-computadas (cold start) para evitar NaN en
        indicadores al inicio del período.
        """
        logger.info(f"[{ticker}] Entrenando con datos 2020-2024...")

        try:
            features_df: pd.DataFrame  = cold.get("features_df")
            close:       pd.Series     = cold.get("close")
            ohlcv:       pd.DataFrame  = cold.get("ohlcv")
            t_events:    pd.DatetimeIndex = cold.get("tEvents")

            # ── Corte temporal: solo eventos pre-2025 ──────────────────────
            train_events = t_events[t_events < TRAIN_CUTOFF]
            logger.info(f"[{ticker}] Eventos de entrenamiento: {len(train_events)}")

            if len(train_events) < 50:
                logger.warning(f"[{ticker}] Muy pocos eventos ({len(train_events)}), saltando")
                return None

            # ── Nuevo PipelineData para M4-M8 ─────────────────────────────
            # features_df contiene TODA la historia (M5 alineará al índice de labels)
            train_data = PipelineData()
            train_data.set("close",       close,        "executor")
            train_data.set("open",        ohlcv["open"],  "executor")
            train_data.set("high",        ohlcv["high"],  "executor")
            train_data.set("low",         ohlcv["low"],   "executor")
            train_data.set("volume",      ohlcv["volume"],"executor")
            train_data.set("ohlcv",       ohlcv,          "executor")
            train_data.set("features_df", features_df,    "executor",
                           "Features pre-computadas cold-start")
            train_data.set("tEvents",     train_events,   "executor",
                           "Eventos filtrados pre-2025")

            pipeline   = SignalPipeline(config=config)
            result, ok = pipeline.run(
                stages=["labeling", "splitting",
                        "feature_selection", "modeling", "evaluation"],
                data=train_data,
                verbose=False,
            )

            if not ok:
                logger.error(f"[{ticker}] Pipeline de entrenamiento falló")
                return None

            model             = result.get("model",             required=False)
            selected_features = result.get("selected_features", required=False) or []
            metrics           = result.get("metrics",           required=False) or {}

            if model is None:
                logger.warning(f"[{ticker}] No se generó modelo")
                return None

            auc = metrics.get("auc_roc", 0.0)
            logger.info(
                f"[{ticker}] Entrenamiento OK | "
                f"AUC={auc:.4f} | features={len(selected_features)}"
            )

            return {
                "ticker":            ticker,
                "model":             model,
                "selected_features": selected_features,
                "features_df_full":  features_df,   # Para inferencia 2025
                "close":             close,
                "metrics":           metrics,
            }

        except Exception as exc:
            logger.error(f"[{ticker}] Error de entrenamiento: {exc}", exc_info=True)
            return None

    # =========================================================================
    # 5. Inferencia: Predicciones horarias 2025
    # =========================================================================

    def generate_predictions(
        self,
        ticker:  str,
        trained: dict,
    ) -> Optional[pd.DataFrame]:
        """
        Genera predicciones hora a hora para el período 2025 usando las
        features pre-computadas en el cold start (sin riesgo de data leakage).

        Retorna DataFrame con columnas:
            signal, prob_up, prob_down, signal_strength
        """
        logger.info(f"[{ticker}] Generando predicciones 2025...")

        model             = trained["model"]
        selected_features = trained["selected_features"]
        features_df:  pd.DataFrame = trained["features_df_full"]

        # Filtrar al período de test (2025+)
        features_2025 = features_df[features_df.index >= TRAIN_CUTOFF].copy()
        if len(features_2025) == 0:
            logger.warning(f"[{ticker}] Sin datos 2025 en features_df")
            return None

        # Verificar que las features seleccionadas existan
        if not selected_features:
            selected_features = [c for c in features_2025.columns]

        available = [f for f in selected_features if f in features_2025.columns]
        if len(available) < max(1, len(selected_features) // 2):
            logger.warning(
                f"[{ticker}] Solo {len(available)}/{len(selected_features)} "
                "features disponibles en 2025"
            )
        if not available:
            return None

        X = features_2025[available].ffill().fillna(0.0)

        try:
            if hasattr(model, "predict_proba"):
                proba   = model.predict_proba(X)
                classes = list(model.classes_)
                # Determinar columna UP: clase máxima en {-1, 0, 1}
                pos_idx = classes.index(max(classes))
                neg_idx = classes.index(min(classes))
                prob_up   = proba[:, pos_idx]
                prob_down = proba[:, neg_idx]
            else:
                preds     = model.predict(X).astype(float)
                prob_up   = np.clip(preds,  0, 1)
                prob_down = np.clip(-preds, 0, 1)

            signal_strength = prob_up - prob_down          # [-1, +1]
            signals         = np.sign(signal_strength).astype(int)
            signals[signals == 0] = 1   # Neutral → bullish por defecto

            pred_df = pd.DataFrame(
                {
                    "signal":          signals,
                    "prob_up":         prob_up,
                    "prob_down":       prob_down,
                    "signal_strength": signal_strength,
                },
                index=X.index,
            )

            buy_pct = 100.0 * (pred_df["signal"] == 1).mean()
            logger.info(
                f"[{ticker}] {len(pred_df)} predicciones | "
                f"Alcista={buy_pct:.1f}%"
            )
            return pred_df

        except Exception as exc:
            logger.error(f"[{ticker}] Error de predicción: {exc}", exc_info=True)
            return None

    # =========================================================================
    # 6. Backtest Diario con Black-Litterman
    # =========================================================================

    def run_daily_backtest(
        self,
        predictions:     Dict[str, pd.DataFrame],
        profile_config:  dict,
        initial_capital: float = INITIAL_CAPITAL,
    ) -> List[dict]:
        """
        Simula el portafolio diariamente re-balanceando con Black-Litterman.

        Por cada día de trading en 2025:
          1. Obtiene la última señal ML de cada activo
          2. Corre BL para calcular pesos óptimos
          3. Aplica retornos del día siguiente
          4. Registra {date, portfolio_value, benchmark_value, allocations, confidence}

        Args:
            predictions:     {ticker: DataFrame de predicciones horarias}
            profile_config:  YAML del perfil (parámetros BL y restricciones)
            initial_capital: Capital inicial (USD)

        Returns:
            Lista de registros diarios compatibles con el frontend React.
        """
        # ── Parámetros Black-Litterman desde el perfil ────────────────────
        bl_cfg           = profile_config.get("black_litterman", {})
        delta            = float(bl_cfg.get("delta",              2.5))
        tau              = float(bl_cfg.get("tau",                0.05))
        confidence_level = float(profile_config.get("confidence_level", 0.70))
        max_weight       = float(profile_config.get("max_weight_per_asset", 0.40))

        bl = BlackLittermanOptimizer(delta=delta, tau=tau, max_weight=max_weight)

        tickers = [t for t in predictions if len(predictions[t]) > 0]
        if not tickers:
            logger.error("Sin predicciones disponibles para backtest")
            return []

        # ── Precios de cierre 2025 (agregados de la caché cold_data) ──────
        close_2025_parts = {}
        for ticker in tickers:
            if ticker in self.cold_data:
                close_full = self.cold_data[ticker].get("close")
                part       = close_full[close_full.index >= TRAIN_CUTOFF]
                if len(part) > 0:
                    close_2025_parts[ticker] = part

        if not close_2025_parts:
            logger.error("Sin precios 2025 en caché")
            return []

        prices_2025  = pd.DataFrame(close_2025_parts).sort_index().ffill()
        daily_prices = prices_2025.resample("1D").last().dropna(how="all")
        trading_days = daily_prices.index
        daily_rets   = daily_prices.pct_change().fillna(0.0)

        if len(trading_days) < 2:
            logger.error("Datos 2025 insuficientes para backtest")
            return []

        # ── Precios históricos de entrenamiento (para covarianza BL) ──────
        hist_close: Dict[str, pd.Series] = {}
        for ticker in tickers:
            if ticker in self.cold_data:
                close_full = self.cold_data[ticker].get("close")
                hist_close[ticker] = close_full[close_full.index < TRAIN_CUTOFF]

        # ── Inicialización ─────────────────────────────────────────────────
        equal_w          = {t: 1.0 / len(tickers) for t in tickers}
        portfolio_value  = initial_capital
        benchmark_value  = initial_capital
        current_weights  = dict(equal_w)   # Pesos iniciales iguales
        results: List[dict] = []

        # ── Loop diario ────────────────────────────────────────────────────
        for i, date in enumerate(trading_days[:-1]):
            next_date = trading_days[i + 1]

            # 1. Obtener señales ML del día actual
            daily_signals:    Dict[str, float] = {}
            conf_scores: List[float]            = []

            for ticker in tickers:
                pred_df = predictions[ticker]
                day_mask = pred_df.index.date <= date.date()
                if day_mask.any():
                    latest = pred_df[day_mask].iloc[-1]
                    daily_signals[ticker] = float(latest["signal_strength"])
                    conf_scores.append(float(np.clip(latest["prob_up"], 0.5, 1.0)))

            avg_conf = float(np.mean(conf_scores)) if conf_scores else 0.5

            # 2. Construir ventana histórica de precios (252 días anteriores)
            window_start = date - pd.Timedelta(days=365)
            window_parts = {}
            for ticker in tickers:
                if ticker not in hist_close:
                    continue
                series = hist_close[ticker]
                mask   = (series.index >= window_start) & (series.index <= date)
                slice_ = series[mask]
                if len(slice_) >= 30:
                    window_parts[ticker] = slice_

            # 3. Black-Litterman si hay suficientes datos
            if len(window_parts) >= 2 and len(daily_signals) >= 2:
                avail_tickers = sorted(window_parts.keys())
                hist_df       = pd.DataFrame(
                    {t: window_parts[t] for t in avail_tickers}
                ).ffill().dropna(how="all")

                if len(hist_df) >= 30:
                    avail_signals = {t: daily_signals.get(t, 0.0) for t in avail_tickers}
                    bl_weights, _ = bl.optimize(
                        prices=hist_df,
                        ml_signals=avail_signals,
                        confidence_level=confidence_level,
                    )
                    # Extender a todos los tickers (0 para los no incluidos)
                    raw_w = {t: bl_weights.get(t, 0.0) for t in tickers}
                    total = sum(raw_w.values())
                    current_weights = (
                        {t: v / total for t, v in raw_w.items()}
                        if total > 0 else equal_w
                    )

            # 4. Aplicar retornos del siguiente día
            port_ret  = 0.0
            bench_ret = 0.0

            for ticker in tickers:
                if ticker not in daily_rets.columns:
                    continue
                if next_date not in daily_rets.index:
                    continue
                r           = float(daily_rets.loc[next_date, ticker])
                port_ret   += current_weights.get(ticker, 0.0) * r
                bench_ret  += equal_w[ticker] * r

            portfolio_value *= (1.0 + port_ret)
            benchmark_value *= (1.0 + bench_ret)

            # 5. Registrar resultado del día
            results.append({
                "date":            date.strftime("%Y-%m-%d"),
                "portfolio_value": round(portfolio_value, 4),
                "benchmark_value": round(benchmark_value, 4),
                "allocations":     {t: round(current_weights.get(t, 0.0), 4) for t in tickers},
                "confidence":      round(avg_conf, 4),
            })

        final_port  = results[-1]["portfolio_value"] if results else initial_capital
        final_bench = results[-1]["benchmark_value"] if results else initial_capital
        port_ret_pct  = (final_port  / initial_capital - 1) * 100
        bench_ret_pct = (final_bench / initial_capital - 1) * 100

        logger.info(
            f"Backtest completado: {len(results)} días | "
            f"Portafolio ${final_port:.2f} ({port_ret_pct:+.1f}%) | "
            f"Benchmark ${final_bench:.2f} ({bench_ret_pct:+.1f}%)"
        )
        return results

    # =========================================================================
    # 7. Runner por Perfil
    # =========================================================================

    def run_profile(self, profile_name: str) -> List[dict]:
        """
        Ejecuta el pipeline completo para un perfil de riesgo.

        Pasos:
          1. Cargar YAML del perfil
          2. Por activo: cold-start → entrenamiento → predicción
          3. Backtest diario con Black-Litterman
          4. Guardar results_<perfil>.json

        Returns:
            Lista de registros diarios en el formato requerido por el frontend.
        """
        logger.info(f"\n{'='*60}\nPerfil: {profile_name.upper()}\n{'='*60}")

        profile_config   = self.load_profile(profile_name)
        assets           = profile_config.get("assets", list(self.raw_data.keys()))
        custom_assets    = profile_config.get("custom_assets", {})
        initial_capital  = float(profile_config.get("initial_capital", INITIAL_CAPITAL))

        self.profile_models.setdefault(profile_name, {})
        predictions: Dict[str, pd.DataFrame] = {}

        for ticker in assets:
            if ticker not in self.raw_data:
                logger.warning(f"[{ticker}] No está en los datos cargados, saltando")
                continue

            ohlcv = self.raw_data[ticker]
            if len(ohlcv) < 500:
                logger.warning(f"[{ticker}] Datos insuficientes ({len(ohlcv)} filas), saltando")
                continue

            asset_overrides = custom_assets.get(ticker, {})
            config          = self.build_pipeline_config(ticker, ohlcv, profile_config, asset_overrides)

            # ── Cold Start (caché compartida entre perfiles) ───────────────
            cold = self.run_cold_start(ticker, ohlcv, config)
            if cold is None:
                continue

            # ── Entrenamiento (específico por perfil × activo) ─────────────
            trained = self.train_asset(ticker, cold, config)
            if trained is None:
                continue

            self.profile_models[profile_name][ticker] = trained

            # ── Predicciones 2025 ──────────────────────────────────────────
            pred_df = self.generate_predictions(ticker, trained)
            if pred_df is not None and len(pred_df) > 0:
                predictions[ticker] = pred_df

        if not predictions:
            logger.error(f"Sin predicciones para el perfil '{profile_name}'")
            return []

        # ── Backtest diario con Black-Litterman ────────────────────────────
        results = self.run_daily_backtest(
            predictions=predictions,
            profile_config=profile_config,
            initial_capital=initial_capital,
        )

        # ── Persistir JSON ─────────────────────────────────────────────────
        output_path = self.output_dir / f"results_{profile_name}.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Resultados guardados en {output_path}")

        return results

    # =========================================================================
    # 8. Punto de Entrada Principal
    # =========================================================================

    def run_all(self, profiles: Optional[List[str]] = None) -> Dict[str, List[dict]]:
        """
        Ejecuta el pipeline para todos (o los especificados) perfiles de riesgo.

        Args:
            profiles: Lista de perfiles a correr (default: los 3 perfiles).

        Returns:
            {profile_name: lista de resultados diarios}
        """
        profiles = profiles or list(PROFILE_FILES.keys())

        if not self.raw_data:
            self.load_data()

        if not self.raw_data:
            raise RuntimeError(
                "No se cargaron datos. Verificar ruta del CSV y formato."
            )

        all_results: Dict[str, List[dict]] = {}
        for profile_name in profiles:
            try:
                results = self.run_profile(profile_name)
                all_results[profile_name] = results
            except Exception as exc:
                logger.error(f"Perfil '{profile_name}' falló: {exc}", exc_info=True)
                all_results[profile_name] = []

        self._print_summary(all_results)
        return all_results

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _print_summary(all_results: Dict[str, List[dict]]):
        """Imprime tabla resumen de resultados por perfil."""
        print(f"\n{'='*70}")
        print("RESUMEN FINAL")
        print(f"{'='*70}")
        print(f"{'Perfil':<15} {'Días':>6} {'Portafolio Final':>18} "
              f"{'Benchmark':>12} {'Retorno':>9}")
        print(f"{'-'*70}")
        for name, results in all_results.items():
            if not results:
                print(f"{name:<15} {'N/A':>6}")
                continue
            last       = results[-1]
            final_port = last["portfolio_value"]
            final_bench= last["benchmark_value"]
            ret_pct    = (final_port / INITIAL_CAPITAL - 1) * 100
            print(
                f"{name:<15} {len(results):>6} "
                f"${final_port:>16,.2f} "
                f"${final_bench:>10,.2f} "
                f"{ret_pct:>+8.1f}%"
            )
        print(f"{'='*70}\n")


# =============================================================================
# Utilidades
# =============================================================================

def _deep_merge(base: dict, override: dict) -> dict:
    """Fusión recursiva: override sobreescribe keys en base."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="HackITBA — Orquestador de Trading Algorítmico",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main_executor.py                              # Corre los 3 perfiles
  python main_executor.py --profiles low_risk high_risk
  python main_executor.py --data data/mi_dataset.csv --output resultados/
""",
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        choices=list(PROFILE_FILES.keys()),
        default=list(PROFILE_FILES.keys()),
        help="Perfiles de riesgo a ejecutar (default: todos)",
    )
    parser.add_argument(
        "--data",
        type=str,
        default=None,
        help="Ruta al CSV combinado (default: data/dataset_completo.csv)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Directorio de salida para los JSON (default: results/)",
    )
    parser.add_argument(
        "--configs",
        type=str,
        default=None,
        help="Directorio de configs YAML (default: configs/)",
    )

    args = parser.parse_args()

    executor = MainExecutor(
        data_path=args.data,
        profiles_dir=args.configs,
        output_dir=args.output,
    )
    executor.run_all(profiles=args.profiles)


if __name__ == "__main__":
    main()
