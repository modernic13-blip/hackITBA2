"""
Clase abstracta para optimizadores de riesgo de portafolio.

Define la interfaz común que todos los optimizadores deben implementar.
"""

from abc import ABC, abstractmethod
from typing import Dict
import pandas as pd


class RiskOptimizer(ABC):
    """
    Clase base abstracta para optimizadores de riesgo.

    Todos los optimizadores deben heredar de esta clase e implementar
    el método optimize() que recibe precios y retorna pesos.
    """

    def __init__(self, config: dict = None):
        """
        Inicializa el optimizador.

        Args:
            config: Diccionario con parámetros específicos del optimizador
        """
        self.config = config or {}

    @abstractmethod
    def optimize(self, prices: pd.DataFrame) -> Dict[str, float]:
        """
        Calcula los pesos óptimos del portafolio.

        Args:
            prices: DataFrame con precios históricos
                   (índice = fechas, columnas = tickers)

        Returns:
            Dict con pesos por activo: {ticker: peso}
            Los pesos suman 1.0 (fully invested)
            Todos los pesos son >= 0 (long-only)

        Raises:
            ValueError: Si los precios no son válidos o la optimización falla
        """
        pass

    def _validate_prices(self, prices: pd.DataFrame) -> None:
        """
        Valida que el DataFrame de precios sea válido.

        Args:
            prices: DataFrame a validar

        Raises:
            ValueError: Si hay problemas en los precios
        """
        if prices.empty:
            raise ValueError("El DataFrame de precios está vacío")

        if prices.shape[0] < 10:
            raise ValueError(f"Se necesitan al menos 10 observaciones, se proporcionaron {prices.shape[0]}")

        if prices.shape[1] == 0:
            raise ValueError("No hay activos en el DataFrame de precios")

        if prices.isnull().any().any():
            raise ValueError("El DataFrame contiene NaN. Por favor, rellenar o remover datos faltantes.")

    def _validate_weights(self, weights: Dict[str, float]) -> None:
        """
        Valida que los pesos sean válidos.

        Args:
            weights: Dict de pesos a validar

        Raises:
            ValueError: Si los pesos no son válidos
        """
        if not weights:
            raise ValueError("Los pesos resultantes están vacíos")

        total = sum(weights.values())
        if abs(total - 1.0) > 1e-5:
            raise ValueError(f"Los pesos no suman 1.0, suman {total:.6f}")

        for ticker, weight in weights.items():
            if weight < -1e-5:
                raise ValueError(f"Peso negativo para {ticker}: {weight}")
