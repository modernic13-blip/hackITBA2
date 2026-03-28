"""
Motor de Portafolio (Portfolio Engine).

Orquestador principal que:
1. Recibe señales de trading de Smart Indicators
2. Filtra activos con señal long (+1)
3. Calcula pesos óptimos usando HRP o Markowitz
4. Aplica constraint de rebalanceo con threshold
5. Convierte pesos a asignación en dinero ($)
"""

from typing import Dict, Optional, List
import pandas as pd
import numpy as np
from .optimizers.base import RiskOptimizer
from .optimizers.hrp import HRPOptimizer
from .optimizers.markowitz import MarkowitzOptimizer
from . import metrics


class PortfolioEngine:
    """
    Motor de gestión de portafolio.

    Flujo:
    1. Recibe precios históricos y señales de trading
    2. Filtra activos largos (signal = +1)
    3. Optimiza pesos con HRP o Markowitz
    4. Aplica threshold de rebalanceo
    5. Retorna pesos y asignación en $

    Atributos:
        prices: DataFrame de precios históricos
        signals: Dict con señales por activo {ticker: signal}
        config: Dict con configuración (optimizer, risk_profile, capital, etc.)
        optimizer: Instancia del optimizador (HRP o Markowitz)
        previous_weights: Pesos de la ejecución anterior (para turnover)
    """

    def __init__(
        self,
        prices: pd.DataFrame,
        signals: Dict[str, int],
        config: dict
    ):
        """
        Inicializa el motor de portafolio.

        Args:
            prices: DataFrame con precios históricos
                   (índice = fechas, columnas = tickers)
            signals: Dict con señales por activo {ticker: +1/-1/0}
            config: Dict con configuración. Ejemplo:
                {
                    "risk_profile": "low",       # "low" o "high"
                    "optimizer": "markowitz",    # "markowitz" o "hrp"
                    "lambda_risk": 6.0,
                    "lookback_days": 225,
                    "rebalance_threshold": 0.05,
                    "penalty": 0.001,
                    "capital": 100000
                }

        Raises:
            ValueError: Si la configuración es inválida
        """
        self.prices = prices.copy()
        self.signals = signals
        self.config = config
        self.previous_weights = None
        self.last_weights = None

        # Procesar configuración según perfil de riesgo
        self._process_risk_profile()

        # Instanciar optimizador
        self.optimizer = self._create_optimizer()

    def _process_risk_profile(self) -> None:
        """
        Ajusta parámetros según el perfil de riesgo.
        """
        risk_profile = self.config.get("risk_profile", "low").lower()

        if risk_profile == "low":
            self.config.setdefault("lambda_risk", 6.0)
            self.config.setdefault("lookback_days", 225)
            self.config.setdefault("rebalance_threshold", 0.05)
        elif risk_profile == "high":
            self.config.setdefault("lambda_risk", 3.0)
            self.config.setdefault("lookback_days", 130)
            self.config.setdefault("rebalance_threshold", 0.01)
        else:
            # Valores por defecto si no es reconocido
            self.config.setdefault("lambda_risk", 2.0)
            self.config.setdefault("lookback_days", 160)
            self.config.setdefault("rebalance_threshold", 0.02)

        self.config.setdefault("penalty", 0.001)
        self.config.setdefault("capital", 100000)
        self.config.setdefault("optimizer", "markowitz")

    def _create_optimizer(self) -> RiskOptimizer:
        """
        Crea la instancia del optimizador según la configuración.

        Returns:
            Instancia de RiskOptimizer (HRP o Markowitz)

        Raises:
            ValueError: Si el optimizador no es reconocido
        """
        optimizer_name = self.config.get("optimizer", "markowitz").lower()

        if optimizer_name == "hrp":
            return HRPOptimizer({
                "linkage_method": self.config.get("linkage_method", "single")
            })
        elif optimizer_name == "markowitz":
            return MarkowitzOptimizer({
                "lambda_risk": self.config.get("lambda_risk", 2.0),
                "penalty": self.config.get("penalty", 0.001)
            })
        else:
            raise ValueError(f"Optimizador no reconocido: {optimizer_name}")

    def _filter_assets_by_signal(self) -> List[str]:
        """
        Filtra activos que tienen señal de compra (signal = +1).

        Returns:
            Lista de tickers con señal long
        """
        long_assets = [
            ticker for ticker, signal in self.signals.items()
            if signal == 1 and ticker in self.prices.columns
        ]
        return long_assets if long_assets else list(self.prices.columns)

    def _get_lookback_window(self) -> pd.DataFrame:
        """
        Extrae la ventana de datos históricos para la optimización.

        Returns:
            DataFrame con precios en la ventana lookback
        """
        lookback_days = self.config.get("lookback_days", 225)
        if len(self.prices) <= lookback_days:
            return self.prices
        return self.prices.iloc[-lookback_days:]

    def _apply_threshold_rebalance(
        self,
        new_weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Aplica constraint de rebalanceo con threshold.

        Si el cambio en pesos es menor que el threshold,
        retorna los pesos anteriores (sin cambios).

        Args:
            new_weights: Pesos calculados por el optimizador

        Returns:
            Pesos finales (puede ser new_weights o previous_weights)
        """
        if self.previous_weights is None:
            return new_weights

        threshold = self.config.get("rebalance_threshold", 0.05)

        # Calcular cambios de peso
        all_tickers = set(new_weights.keys()) | set(self.previous_weights.keys())
        max_change = 0

        for ticker in all_tickers:
            old_w = self.previous_weights.get(ticker, 0)
            new_w = new_weights.get(ticker, 0)
            change = abs(new_w - old_w)
            max_change = max(max_change, change)

        # Si el cambio es menor que threshold, mantener pesos previos
        if max_change < threshold:
            return self.previous_weights

        return new_weights

    def compute_weights(self) -> Dict[str, float]:
        """
        Calcula los pesos óptimos del portafolio.

        Proceso:
        1. Filtrar activos con señal long
        2. Obtener ventana de precios (lookback)
        3. Llamar al optimizador
        4. Aplicar threshold de rebalanceo
        5. Rellenar con ceros activos sin señal

        Returns:
            Dict con pesos por activo {ticker: peso}

        Raises:
            ValueError: Si la optimización falla
        """
        # Filtrar activos largos
        long_assets = self._filter_assets_by_signal()

        if not long_assets:
            # Si no hay señal long, distribuir equitativamente
            n = len(self.prices.columns)
            return {ticker: 1.0 / n for ticker in self.prices.columns}

        # Obtener precios en ventana lookback
        window_prices = self._get_lookback_window()
        long_prices = window_prices[long_assets]

        # Optimizar
        if isinstance(self.optimizer, MarkowitzOptimizer) and self.previous_weights:
            # Para Markowitz, pasar pesos previos
            prev_dict = {
                t: self.previous_weights.get(t, 0)
                for t in long_assets
            }
            self.optimizer.set_previous_weights(prev_dict)

        weights_long = self.optimizer.optimize(long_prices)

        # Crear dict con todos los activos (ceros para sin señal)
        weights_full = {
            ticker: weights_long.get(ticker, 0)
            for ticker in self.prices.columns
        }

        # Normalizar para asegurar suma = 1.0
        total = sum(weights_full.values())
        if total > 0:
            weights_full = {t: w / total for t, w in weights_full.items()}

        # Aplicar threshold de rebalanceo
        final_weights = self._apply_threshold_rebalance(weights_full)

        # Guardar para próxima iteración
        self.last_weights = final_weights.copy()

        return final_weights

    def compute_allocation(self, capital: Optional[float] = None) -> Dict[str, float]:
        """
        Convierte pesos a asignación en dinero.

        Args:
            capital: Monto en $ a invertir. Si no se proporciona,
                    usa el del config (default 100,000)

        Returns:
            Dict con asignación en $ por activo {ticker: monto}

        Raises:
            ValueError: Si el capital es inválido
        """
        if capital is None:
            capital = self.config.get("capital", 100000)

        if capital <= 0:
            raise ValueError(f"Capital debe ser positivo, se recibió {capital}")

        weights = self.compute_weights()
        allocation = {
            ticker: capital * weight
            for ticker, weight in weights.items()
        }

        return allocation

    def update_previous_weights(self, weights: Dict[str, float]) -> None:
        """
        Actualiza los pesos previos (para usar en próxima iteración).

        Esto es necesario para calcular turnover y aplicar
        el threshold de rebalanceo en la próxima llamada.

        Args:
            weights: Dict con pesos actuales {ticker: peso}
        """
        self.previous_weights = weights.copy()

    def get_summary(self) -> Dict:
        """
        Retorna un resumen del portafolio actual.

        Returns:
            Dict con información del portafolio
        """
        weights = self.compute_weights()
        capital = self.config.get("capital", 100000)
        allocation = self.compute_allocation(capital)

        return {
            "optimizer": self.config.get("optimizer"),
            "risk_profile": self.config.get("risk_profile"),
            "capital": capital,
            "weights": weights,
            "allocation": allocation,
            "total_allocated": sum(allocation.values()),
            "num_long_positions": sum(1 for w in weights.values() if w > 1e-5),
        }
