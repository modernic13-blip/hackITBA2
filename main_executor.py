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
import pickle
import hashlib
import logging
import warnings
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml
import joblib
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform

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
TRAIN_CUTOFF = pd.Timestamp("2025-10-01")   # Entrena abr2024-sep2025, testea oct2025+
DATA_PATH    = ROOT / "data" / "dataset_completo.csv"
PROFILES_DIR = ROOT / "configs"
OUTPUT_DIR   = ROOT / "results"
INITIAL_CAPITAL = 1_000.0

PROFILE_FILES = {
    "low_risk":  "low_risk.yaml",
    "med_risk":  "med_risk.yaml",
    "high_risk": "high_risk.yaml",
}

CACHE_DIR  = ROOT / "cache"
MODELS_DIR = ROOT / "cache" / "models"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── Configuración base del pipeline (auto-adapta a frecuencia detectada) ────────
BASE_PIPELINE_CONFIG: dict = {
    "frequency": "1h",  # Se detecta automáticamente, pero default es 1h para datos nuevos
    "ingestion": {
        "source": "csv",
    },
    "features": {
        "timeframes": ["1h", "4h", "1d"],     # 1h, 4h, 1d para datos horarios
        "indicators": ["rsi", "macd", "bbands", "atr", "adx"],  # 5 indicadores clave
        "indicator_params": {
            "rsi":    {"period": [14]},
            "macd":   {"fast": [12], "slow": [26], "signal": [9]},
            "bbands": {"period": [20], "num_std": [2.0]},
            "atr":    {"period": [14]},
            "adx":    {"period": [14]},
        },
        "normalize": {
            "methods": ["zscore"],
            "window": 240,      # 240 horas = 10 días para zscore rolling
        },
        "drop_na_threshold": 0.5,
    },
    "filtering": {
        "method":     "adaptive_cusum",
        "cusum_mode": "symmetric",
        "k_Px":       0.7,
        "lookback":   240,      # 240 horas = 10 días
        "min_events": 30,
    },
    "labeling": {
        "pt_sl":              [1.5, 1.0],
        "min_ret":            0.0,
        "vertical_bars":      240,  # 240 horas = 10 días de datos horarios
        "vol_span":           240,  # 240 horas
        "use_sample_weights": False,
    },
    "splitting": {
        "n_splits":       3,            # FAST: 3 folds en lugar de 5
        "test_size":      0.2,
        "purge_hours":    240,
        "embargo_pct":    0.01,
        "expanding":      True,
        "min_train_size": 200,
    },
    "feature_selection": {
        "max_features":       5,        # FAST: máx 5 features
        "min_improvement":    0.005,
        "n_estimators":       20,       # FAST: 20 árboles para selección
        "max_depth":          3,
        "use_sample_weights": False,    # Desactivado: evita mismatch de tamaños
        "verbose":            False,
    },
    "modeling": {
        "model":                 "xgboost",
        "max_combinations":      2,     # FAST: solo 2 combinaciones de hiper-params
        "use_sample_weights":    False, # Desactivado: evita mismatch de tamaños post-split
        "use_selected_features": True,
        "verbose":               False,
        "param_grid": {
            "n_estimators":  [100],
            "max_depth":     [3],
            "learning_rate": [0.1],
        },
    },
    "evaluation": {
        "risk_free_rate":   0.045,
        "periods_per_year": 8760,  # Horas por año (para datos horarios)
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
# HRP Optimizer (Hierarchical Risk Parity — López de Prado)
# =============================================================================

class HRPOptimizer:
    """
    Hierarchical Risk Parity: no requiere inversión de matrices.
    Robusto en mercados volátiles con matrices de covarianza inestables.

    Algoritmo:
      1. Correlación → distancia → clustering jerárquico
      2. Quasi-diagonalización de la covarianza
      3. Bisección recursiva asignando peso inverso a varianza
    """

    def __init__(self, max_weight: float = 0.40):
        self.max_weight = max_weight

    def optimize(
        self,
        prices:           pd.DataFrame,
        ml_signals:       Dict[str, float],
        confidence_level: float = 0.70,
    ) -> Tuple[Dict[str, float], float]:
        tickers = list(prices.columns)
        n = len(tickers)
        if n < 2:
            return {t: 1.0 / n for t in tickers}, 0.5

        returns = prices.pct_change().dropna()
        if len(returns) < 20:
            return {t: 1.0 / n for t in tickers}, 0.5

        cov  = returns.cov().values
        corr = returns.corr().values

        # 1. Distancia y clustering
        dist = np.sqrt(0.5 * (1 - corr))
        np.fill_diagonal(dist, 0)
        dist = np.nan_to_num(dist, nan=0.0)
        condensed = squareform(dist, checks=False)
        condensed = np.nan_to_num(condensed, nan=0.0)
        link = linkage(condensed, method="single")
        sort_ix = list(leaves_list(link))

        # 2. Bisección recursiva
        weights = np.ones(n)
        clusters = [sort_ix]

        while clusters:
            new_clusters = []
            for cluster in clusters:
                if len(cluster) <= 1:
                    continue
                mid = len(cluster) // 2
                left, right = cluster[:mid], cluster[mid:]

                var_left  = self._cluster_var(cov, left)
                var_right = self._cluster_var(cov, right)
                alpha = 1.0 - var_left / (var_left + var_right + 1e-10)

                for i in left:
                    weights[i] *= alpha
                for i in right:
                    weights[i] *= (1.0 - alpha)

                if len(left)  > 1: new_clusters.append(left)
                if len(right) > 1: new_clusters.append(right)
            clusters = new_clusters

        # 3. Ajustar por señales ML (tilt)
        for i, t in enumerate(tickers):
            if t in ml_signals:
                signal = ml_signals[t]
                tilt = 1.0 + signal * confidence_level * 0.5
                weights[i] *= max(tilt, 0.1)

        # Normalizar y aplicar max_weight
        weights = np.clip(weights, 0, None)
        total = weights.sum()
        if total > 0:
            weights /= total
        else:
            weights = np.ones(n) / n

        weights = BlackLittermanOptimizer._project_simplex(weights, self.max_weight)

        avg_conf = 0.5 + 0.5 * float(np.mean([abs(ml_signals.get(t, 0)) for t in tickers]))
        return {t: float(w) for t, w in zip(tickers, weights)}, avg_conf

    @staticmethod
    def _cluster_var(cov: np.ndarray, indices: List[int]) -> float:
        sub_cov = cov[np.ix_(indices, indices)]
        inv_diag = 1.0 / (np.diag(sub_cov) + 1e-10)
        w = inv_diag / inv_diag.sum()
        return float(w @ sub_cov @ w)


# =============================================================================
# Kelly Criterion Optimizer
# =============================================================================

class KellyOptimizer:
    """
    Kelly Criterion adaptado para portafolios multi-activo.
    Maximiza el crecimiento geométrico esperado del capital.

    Fórmula: f* = (p × b - q) / b
      p = probabilidad de ganar, b = ratio ganancia/pérdida, q = 1-p

    Se usa un fraction < 1.0 para reducir agresividad (Half-Kelly típico).
    """

    def __init__(self, max_weight: float = 0.40, fraction: float = 0.5):
        self.max_weight = max_weight
        self.fraction   = fraction  # Half-Kelly por defecto

    def optimize(
        self,
        prices:           pd.DataFrame,
        ml_signals:       Dict[str, float],
        confidence_level: float = 0.70,
    ) -> Tuple[Dict[str, float], float]:
        tickers = list(prices.columns)
        n = len(tickers)
        if n < 2:
            return {t: 1.0 / n for t in tickers}, 0.5

        returns = prices.pct_change().dropna()
        if len(returns) < 20:
            return {t: 1.0 / n for t in tickers}, 0.5

        weights = {}
        for t in tickers:
            if t not in returns.columns:
                weights[t] = 0.0
                continue

            r = returns[t].values
            signal = ml_signals.get(t, 0.0)

            # Probabilidad basada en señal ML + histórico
            hist_win_rate = float((r > 0).mean())
            p = np.clip(0.5 + signal * confidence_level * 0.3 + (hist_win_rate - 0.5) * 0.2, 0.01, 0.99)
            q = 1.0 - p

            # Ratio ganancia/pérdida
            gains  = r[r > 0]
            losses = r[r < 0]
            avg_gain = float(gains.mean()) if len(gains) > 0 else 0.01
            avg_loss = float(abs(losses.mean())) if len(losses) > 0 else 0.01
            b = avg_gain / (avg_loss + 1e-10)

            # Kelly fraction
            f = (p * b - q) / (b + 1e-10)
            f = max(f, 0.0) * self.fraction  # Aplicar fracción conservadora

            weights[t] = f

        # Normalizar
        total = sum(weights.values())
        if total > 0:
            weights = {t: v / total for t, v in weights.items()}
        else:
            weights = {t: 1.0 / n for t in tickers}

        w_array = np.array([weights[t] for t in tickers])
        w_array = BlackLittermanOptimizer._project_simplex(w_array, self.max_weight)
        weights = {t: float(w) for t, w in zip(tickers, w_array)}

        avg_conf = 0.5 + 0.5 * float(np.mean([abs(ml_signals.get(t, 0)) for t in tickers]))
        return weights, avg_conf


# =============================================================================
# Regime Detector — Detecta bull/bear/crisis para adaptar la estrategia
# =============================================================================

class RegimeDetector:
    """
    Detecta el régimen de mercado actual analizando:
      - Trend: retorno acumulado rolling (SMA 50 vs SMA 200 equivalente)
      - Volatility: percentil de volatilidad realizada vs histórica
      - Correlation: correlación media entre activos (risk-on/risk-off)

    Regímenes:
      BULL     → Trend positivo, vol baja     → usar Kelly (más agresivo)
      BEAR     → Trend negativo, vol normal   → usar HRP (defensivo)
      CRISIS   → Vol alta, correlación alta   → usar HRP (máxima diversificación)
      NEUTRAL  → Sin señal clara              → usar Black-Litterman (bayesiano)
    """

    BULL    = "bull"
    BEAR    = "bear"
    CRISIS  = "crisis"
    NEUTRAL = "neutral"

    def __init__(
        self,
        vol_lookback:     int   = 60,
        trend_lookback:   int   = 120,
        vol_crisis_pctile: float = 80.0,
        corr_crisis_thresh: float = 0.65,
    ):
        self.vol_lookback       = vol_lookback
        self.trend_lookback     = trend_lookback
        self.vol_crisis_pctile  = vol_crisis_pctile
        self.corr_crisis_thresh = corr_crisis_thresh

    def detect(self, prices: pd.DataFrame) -> str:
        """
        Analiza los últimos N días de precios y retorna el régimen.
        """
        if len(prices) < self.trend_lookback:
            return self.NEUTRAL

        returns = prices.pct_change().dropna()
        recent  = returns.tail(self.vol_lookback)

        # 1. Trend: retorno promedio de todos los activos en la ventana
        mean_return = float(recent.mean().mean()) * 252  # anualizado
        trend_positive = mean_return > 0.05   # >5% anualizado = bull
        trend_negative = mean_return < -0.05  # <-5% anualizado = bear

        # 2. Volatilidad: vol reciente vs histórica
        recent_vol = float(recent.std().mean()) * np.sqrt(252)
        full_vol   = float(returns.std().mean()) * np.sqrt(252)
        vol_ratio  = recent_vol / (full_vol + 1e-10) * 100  # percentil proxy
        high_vol   = vol_ratio > self.vol_crisis_pctile

        # 3. Correlación media entre activos
        if recent.shape[1] >= 2:
            corr_matrix = recent.corr().values
            n = corr_matrix.shape[0]
            upper = corr_matrix[np.triu_indices(n, k=1)]
            mean_corr = float(np.nanmean(upper))
        else:
            mean_corr = 0.0
        high_corr = mean_corr > self.corr_crisis_thresh

        # 4. Clasificar régimen
        if high_vol and high_corr:
            regime = self.CRISIS
        elif trend_negative:
            regime = self.BEAR
        elif trend_positive and not high_vol:
            regime = self.BULL
        else:
            regime = self.NEUTRAL

        return regime

    @staticmethod
    def select_optimizer(
        regime: str,
        bl:     BlackLittermanOptimizer,
        hrp:    HRPOptimizer,
        kelly:  KellyOptimizer,
    ):
        """Retorna el optimizador óptimo para el régimen detectado."""
        if regime == RegimeDetector.BULL:
            return kelly, "Kelly"
        elif regime in (RegimeDetector.BEAR, RegimeDetector.CRISIS):
            return hrp, "HRP"
        else:
            return bl, "Black-Litterman"


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
        Carga siempre los CSVs individuales (formato más limpio).
        dataset_completo.csv tiene formato wide con multi-header — usar individuales.
        """
        logger.info(f"Cargando CSVs individuales desde {self.data_path.parent}")
        self._load_individual_csvs()
        logger.info(f"Activos cargados: {sorted(self.raw_data.keys())}")
        return self.raw_data

    def _load_combined_csv(self):
        """No usado — dataset_completo.csv tiene formato wide no estándar."""
        self._load_individual_csvs()

    def _load_individual_csvs(self):
        """
        Carga CSVs individuales por activo.
        Prioriza archivos *_1h.csv (datos horarios) sobre los diarios si ambos existen.
        Maneja el formato con doble header (fila 0: columnas, fila 1: tickers repetidos).
        """
        data_dir = self.data_path.parent
        skip     = {"dataset_completo.csv", "README.md", "dd.csv"}

        # Construir mapa: ticker → archivo preferido (1h > diario)
        csv_map: dict = {}
        for csv_file in sorted(data_dir.glob("*.csv")):
            if csv_file.name in skip:
                continue
            stem   = csv_file.stem            # ej: "AAPL_1h" o "AAPL"
            is_1h  = stem.endswith("_1h")
            ticker = stem.replace("_1h", "").replace("-USD", "").replace("-", "")
            # Prefiere horario sobre diario
            if ticker not in csv_map or is_1h:
                csv_map[ticker] = csv_file

        for ticker, csv_file in sorted(csv_map.items()):
            try:
                raw      = pd.read_csv(csv_file, header=0)
                date_col = raw.columns[0]

                # Detectar y eliminar fila de tickers repetidos (ej: ",AAPL,AAPL,...")
                if str(raw.iloc[0, 0]) in ("", "nan") or str(raw.iloc[0, 0]).strip().upper() == ticker.upper():
                    raw = raw.iloc[1:].reset_index(drop=True)

                # Parsear fechas con timezone → normalizar a UTC naive
                raw[date_col] = pd.to_datetime(raw[date_col], errors="coerce", utc=True)
                raw[date_col] = raw[date_col].dt.tz_localize(None)   # quitar timezone
                raw = raw.dropna(subset=[date_col])
                raw = raw.set_index(date_col).sort_index()
                raw.columns = [c.lower() for c in raw.columns]

                # Convertir columnas a numérico
                for col in raw.columns:
                    raw[col] = pd.to_numeric(raw[col], errors="coerce")

                ohlcv = self._extract_ohlcv(raw)
                if len(ohlcv) >= 100:
                    self.raw_data[ticker] = ohlcv
                    freq_tag = "1h" if csv_file.stem.endswith("_1h") else "1d"
                    logger.info(f"  {ticker} [{freq_tag}]: {len(ohlcv)} barras ({ohlcv.index[0].date()} → {ohlcv.index[-1].date()})")
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

    @staticmethod
    def _cold_cache_path(ticker: str, ohlcv: pd.DataFrame) -> Path:
        """
        Devuelve la ruta del archivo de caché para el cold-start de un ticker.
        El nombre incluye un hash corto basado en el nº de filas y la última fecha,
        así si cambian los datos el caché se invalida automáticamente.
        """
        key   = f"{ticker}_{len(ohlcv)}_{ohlcv.index[-1].date()}"
        short = hashlib.md5(key.encode()).hexdigest()[:8]
        return CACHE_DIR / f"cold_{ticker}_{short}.pkl"

    def run_cold_start(
        self,
        ticker: str,
        ohlcv:  pd.DataFrame,
        config: dict,
    ) -> Optional[PipelineData]:
        """
        Ejecuta M2 (features) y M3 (filtering) sobre el historial COMPLETO.
        Guarda el resultado en disco (cache/) para no repetirlo entre perfiles
        ni entre ejecuciones del modelo.
        """
        # 1. Caché en memoria (mismo proceso)
        if ticker in self.cold_data:
            return self.cold_data[ticker]

        # 2. Caché en disco
        cache_path = self._cold_cache_path(ticker, ohlcv)
        if cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    cached = pickle.load(f)
                # Reconstruir PipelineData desde el dict guardado
                result = PipelineData()
                for k, v in cached.items():
                    result.set(k, v, "cache")
                t_ev    = result.get("tEvents",    required=False)
                n_feats = result.get("features_df", required=False)
                n_events = len(t_ev)    if t_ev    is not None else 0
                n_feats  = n_feats.shape[1] if n_feats is not None else 0
                logger.info(
                    f"[{ticker}] Cold-start CARGADO desde caché | "
                    f"features={n_feats} | eventos={n_events}"
                )
                self.cold_data[ticker] = result
                return result
            except Exception as exc:
                logger.warning(f"[{ticker}] Caché corrupto, recalculando: {exc}")
                cache_path.unlink(missing_ok=True)

        # 3. Calcular desde cero
        logger.info(f"[{ticker}] Cold-start M2+M3 sobre {len(ohlcv)} barras...")

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

            t_ev     = result.get("tEvents",    required=False)
            n_feats  = result.get("features_df", required=False)
            n_events = len(t_ev)    if t_ev    is not None else 0
            n_feats  = n_feats.shape[1] if n_feats is not None else 0
            logger.info(f"[{ticker}] Cold-start OK | features={n_feats} | eventos={n_events}")

            # Guardar en disco: extraer los objetos clave
            cache_dict = {}
            for key in ("features_df", "tEvents", "close", "open", "high", "low", "volume", "ohlcv"):
                val = result.get(key, required=False)
                if val is not None:
                    cache_dict[key] = val
            try:
                with open(cache_path, "wb") as f:
                    pickle.dump(cache_dict, f, protocol=pickle.HIGHEST_PROTOCOL)
                logger.info(f"[{ticker}] Caché guardado en {cache_path.name}")
            except Exception as exc:
                logger.warning(f"[{ticker}] No se pudo guardar caché: {exc}")

            self.cold_data[ticker] = result
            return result

        except Exception as exc:
            logger.error(f"[{ticker}] Cold-start error: {exc}", exc_info=True)
            return None

    # =========================================================================
    # 4. Entrenamiento: M4-M8 sobre datos pre-2025
    # =========================================================================

    # ─── Model Persistence (.joblib) ─────────────────────────────────────

    @staticmethod
    def _model_path(ticker: str, profile_name: str) -> Path:
        """Ruta del modelo entrenado guardado en disco."""
        return MODELS_DIR / f"{ticker}_{profile_name}.joblib"

    def _save_trained_model(self, ticker: str, profile_name: str, trained: dict):
        """Guarda modelo entrenado + features seleccionadas en disco."""
        path = self._model_path(ticker, profile_name)
        payload = {
            "ticker":            ticker,
            "model":             trained["model"],
            "selected_features": trained["selected_features"],
            "metrics":           trained["metrics"],
            "train_cutoff":      str(TRAIN_CUTOFF),
        }
        try:
            joblib.dump(payload, path, compress=3)
            logger.info(f"[{ticker}] Modelo guardado → {path.name}")
        except Exception as exc:
            logger.warning(f"[{ticker}] No se pudo guardar modelo: {exc}")

    def _load_trained_model(
        self, ticker: str, profile_name: str, features_df: pd.DataFrame, close: pd.Series
    ) -> Optional[dict]:
        """Carga modelo pre-entrenado si existe y coincide el TRAIN_CUTOFF."""
        path = self._model_path(ticker, profile_name)
        if not path.exists():
            return None
        try:
            payload = joblib.load(path)
            if payload.get("train_cutoff") != str(TRAIN_CUTOFF):
                logger.info(f"[{ticker}] Modelo expirado (cutoff distinto), re-entrenando")
                return None
            logger.info(f"[{ticker}] Modelo CARGADO desde {path.name}")
            return {
                "ticker":            ticker,
                "model":             payload["model"],
                "selected_features": payload["selected_features"],
                "features_df_full":  features_df,
                "close":             close,
                "metrics":           payload["metrics"],
            }
        except Exception as exc:
            logger.warning(f"[{ticker}] Modelo corrupto, re-entrenando: {exc}")
            return None

    def train_asset(
        self,
        ticker:    str,
        cold:      PipelineData,
        config:    dict,
        profile_name: str = "",
    ) -> Optional[dict]:
        """
        Ejecuta M4 (labeling) → M5 (splitting) → M6 (feature_selection)
        → M7 (modeling) → M8 (evaluation) sobre el período de entrenamiento.

        Usa features_df pre-computadas (cold start) para evitar NaN en
        indicadores al inicio del período.

        Si existe un modelo guardado (.joblib) con el mismo TRAIN_CUTOFF,
        lo carga en lugar de re-entrenar (ahorra ~80% del tiempo).
        """
        logger.info(f"[{ticker}] Entrenando con datos 2020-2024...")

        try:
            features_df: pd.DataFrame  = cold.get("features_df")
            close:       pd.Series     = cold.get("close")
            ohlcv:       pd.DataFrame  = cold.get("ohlcv")
            t_events:    pd.DatetimeIndex = cold.get("tEvents")

            # ── Intentar cargar modelo guardado (.joblib) ─────────────
            cached_model = self._load_trained_model(ticker, profile_name, features_df, close)
            if cached_model is not None:
                return cached_model

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
                verbose=True,
            )

            if not ok:
                # Mostrar el trace del stage que falló
                for tr in pipeline.traces:
                    if tr["trace"].get("status") not in ("OK",):
                        logger.error(f"[{ticker}] Stage '{tr['module']}' status={tr['trace'].get('status')} error={tr['trace'].get('error','')}")
                logger.error(f"[{ticker}] Pipeline de entrenamiento falló")
                return None

            model             = result.get("model",             required=False)
            selected_features = result.get("selected_features", required=False) or []
            metrics           = result.get("metrics",           required=False) or {}

            if model is None:
                logger.warning(f"[{ticker}] No se generó modelo")
                return None

            # Log completo de métricas de training (CV)
            logger.info(
                f"[{ticker}] TRAIN | "
                f"AUC={metrics.get('mean_auc', 0):.4f}±{metrics.get('std_auc', 0):.4f} | "
                f"Acc={metrics.get('mean_accuracy', 0):.4f} | "
                f"F1={metrics.get('mean_f1', 0):.4f} | "
                f"Sharpe(CV)={metrics.get('mean_sharpe', 0):.4f}±{metrics.get('std_sharpe', 0):.4f} | "
                f"MaxDD={metrics.get('max_drawdown', 0):.4f} | "
                f"TotalReturn(CV)={metrics.get('total_return', 0):.4f} | "
                f"DSR={metrics.get('dsr', 0):.4f} | "
                f"PBO={metrics.get('pbo', 0):.4f} | "
                f"features={len(selected_features)}"
            )

            result = {
                "ticker":            ticker,
                "model":             model,
                "selected_features": selected_features,
                "features_df_full":  features_df,
                "close":             close,
                "metrics":           metrics,
            }

            # ── Guardar modelo en disco (.joblib) ─────────────────────
            self._save_trained_model(ticker, profile_name, result)

            return result

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
        # ── Parámetros desde el perfil ────────────────────────────────────
        bl_cfg           = profile_config.get("black_litterman", {})
        delta            = float(bl_cfg.get("delta",              2.5))
        tau              = float(bl_cfg.get("tau",                0.05))
        confidence_level = float(profile_config.get("confidence_level", 0.70))
        max_weight       = float(profile_config.get("max_weight_per_asset", 0.40))

        # ── Tres optimizadores + detector de régimen ──────────────────
        bl    = BlackLittermanOptimizer(delta=delta, tau=tau, max_weight=max_weight)
        hrp   = HRPOptimizer(max_weight=max_weight)
        kelly = KellyOptimizer(max_weight=max_weight, fraction=0.5)
        regime_detector = RegimeDetector()

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
        regime   = "neutral"               # Inicializar para primer día sin ventana
        opt_name = "Black-Litterman"

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

            # 3. Optimización adaptativa por régimen de mercado
            if len(window_parts) >= 2 and len(daily_signals) >= 2:
                avail_tickers = sorted(window_parts.keys())
                hist_df       = pd.DataFrame(
                    {t: window_parts[t] for t in avail_tickers}
                ).ffill().dropna(how="all")

                if len(hist_df) >= 30:
                    avail_signals = {t: daily_signals.get(t, 0.0) for t in avail_tickers}

                    # Detectar régimen y seleccionar optimizador
                    regime = regime_detector.detect(hist_df)
                    optimizer, opt_name = RegimeDetector.select_optimizer(
                        regime, bl, hrp, kelly
                    )

                    opt_weights, _ = optimizer.optimize(
                        prices=hist_df,
                        ml_signals=avail_signals,
                        confidence_level=confidence_level,
                    )
                    # Extender a todos los tickers (0 para los no incluidos)
                    raw_w = {t: opt_weights.get(t, 0.0) for t in tickers}
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
                "regime":          regime if 'regime' in dir() else "neutral",
                "optimizer":       opt_name if 'opt_name' in dir() else "Black-Litterman",
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
            trained = self.train_asset(ticker, cold, config, profile_name=profile_name)
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
        self._print_train_vs_test(all_results)
        self._copy_to_frontend(all_results)
        return all_results

    @staticmethod
    def _copy_to_frontend(all_results: Dict[str, List[dict]]):
        """Copia los JSON generados a public/data/ para el frontend React."""
        frontend_dirs = [
            ROOT / "frontend" / "public" / "data",
        ]
        copied_to = []
        for dest_dir in frontend_dirs:
            if dest_dir.exists():
                for profile_name, results in all_results.items():
                    if not results:
                        continue
                    dest = dest_dir / f"results_{profile_name}.json"
                    with open(dest, "w") as f:
                        json.dump(results, f, indent=2, default=str)
                copied_to.append(str(dest_dir))

        if copied_to:
            logger.info(f"JSON copiados al frontend: {copied_to}")

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _print_summary(all_results: Dict[str, List[dict]]):
        """Imprime tabla resumen de resultados de backtest (TEST)."""
        print(f"\n{'='*75}")
        print("RESUMEN FINAL — BACKTEST (TEST)")
        print(f"{'='*75}")
        print(f"{'Perfil':<15} {'Días':>6} {'Portafolio':>12} {'Benchmark':>12} "
              f"{'Retorno':>9} {'vs Bench':>9}")
        print(f"{'-'*75}")
        for name, results in all_results.items():
            if not results:
                print(f"{name:<15} {'N/A':>6}")
                continue
            last        = results[-1]
            final_port  = last["portfolio_value"]
            final_bench = last["benchmark_value"]
            ret_pct     = (final_port  / INITIAL_CAPITAL - 1) * 100
            bench_pct   = (final_bench / INITIAL_CAPITAL - 1) * 100
            vs_bench    = ret_pct - bench_pct

            # Sharpe del test
            vals = [d["portfolio_value"] for d in results]
            rets = [(vals[i] - vals[i-1]) / vals[i-1] for i in range(1, len(vals))]
            if len(rets) > 1:
                mean_r = float(np.mean(rets))
                std_r  = float(np.std(rets))
                sharpe_test = (mean_r / std_r) * np.sqrt(8760) if std_r > 0 else 0
            else:
                sharpe_test = 0

            print(
                f"{name:<15} {len(results):>6} "
                f"${final_port:>10,.2f} "
                f"${final_bench:>10,.2f} "
                f"{ret_pct:>+8.1f}% "
                f"{vs_bench:>+8.1f}%  "
                f"Sharpe(test)={sharpe_test:.2f}"
            )
        print(f"{'='*75}\n")

    def _print_train_vs_test(self, all_results: Dict[str, List[dict]]):
        """Imprime comparativa de métricas TRAINING (CV) vs TEST (backtest)."""
        print(f"\n{'='*90}")
        print("COMPARATIVA TRAINING (Cross-Validation) vs TEST (Backtest)")
        print(f"{'='*90}")

        for profile_name, results in all_results.items():
            print(f"\n── {profile_name.upper()} ──")

            # Métricas de training por activo
            models = self.profile_models.get(profile_name, {})
            if models:
                print(f"  {'Activo':<8} {'AUC(CV)':>9} {'Acc(CV)':>9} "
                      f"{'F1(CV)':>8} {'Sharpe(CV)':>11} {'MaxDD(CV)':>10} "
                      f"{'Return(CV)':>11} {'DSR':>7} {'PBO':>7}")
                print(f"  {'-'*83}")
                for ticker, trained in sorted(models.items()):
                    m = trained.get("metrics", {})
                    print(
                        f"  {ticker:<8} "
                        f"{m.get('mean_auc', 0):>9.4f} "
                        f"{m.get('mean_accuracy', 0):>9.4f} "
                        f"{m.get('mean_f1', 0):>8.4f} "
                        f"{m.get('mean_sharpe', 0):>11.4f} "
                        f"{m.get('max_drawdown', 0):>10.4f} "
                        f"{m.get('total_return', 0):>+11.4f} "
                        f"{m.get('dsr', 0):>7.4f} "
                        f"{m.get('pbo', 0):>7.4f}"
                    )

            # Métricas del backtest (TEST)
            if results:
                vals   = [d["portfolio_value"] for d in results]
                rets   = [(vals[i] - vals[i-1]) / vals[i-1] for i in range(1, len(vals))]
                mean_r = float(np.mean(rets)) if rets else 0
                std_r  = float(np.std(rets))  if rets else 0
                sharpe_test = (mean_r / std_r) * np.sqrt(8760) if std_r > 0 else 0

                peak = vals[0]
                max_dd = 0.0
                for v in vals:
                    if v > peak: peak = v
                    dd = (v - peak) / peak
                    if dd < max_dd: max_dd = dd

                total_ret = (vals[-1] / vals[0] - 1)
                n_days    = len(results)
                avg_conf  = np.mean([d["confidence"] for d in results])

                print(f"\n  TEST (backtest):")
                print(f"    Días           : {n_days}")
                print(f"    Retorno total  : {total_ret:+.4f} ({total_ret*100:+.1f}%)")
                print(f"    Sharpe (test)  : {sharpe_test:.4f}")
                print(f"    Max Drawdown   : {max_dd:.4f} ({max_dd*100:.1f}%)")
                print(f"    Confianza media: {avg_conf:.4f}")
            else:
                print(f"\n  TEST: Sin resultados")

        print(f"\n{'='*90}\n")


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
