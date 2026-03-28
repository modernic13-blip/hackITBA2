"""
Optimizador HRP (Hierarchical Risk Parity).

Implementa la estrategia HRP de López de Prado, que no requiere
estimación explícita de retornos esperados.
"""

from typing import Dict
import pandas as pd
import numpy as np
from .base import RiskOptimizer

try:
    from pypfopt import HRPOpt
except ImportError:
    raise ImportError("Se requiere la librería 'pypfopt'. Instala con: pip install pypfopt")


class HRPOptimizer(RiskOptimizer):
    """
    Optimizador Hierarchical Risk Parity.

    Utiliza la librería PyPortfolioOpt para calcular pesos HRP basados en
    clustering jerárquico de la matriz de correlación.

    Ventajas:
    - No requiere estimar retornos esperados (más robusto)
    - Maneja bien correlaciones dinámicas
    - Evita extremos de pesos

    Parámetros:
        linkage_method (str): Método de clustering. Opciones:
            "single" (default), "complete", "average", "ward"
    """

    def __init__(self, config: dict = None):
        """
        Inicializa el optimizador HRP.

        Args:
            config: Dict con parámetros. Ejemplo:
                {
                    "linkage_method": "single"
                }
        """
        super().__init__(config)
        self.linkage_method = self.config.get("linkage_method", "single")

    def optimize(self, prices: pd.DataFrame) -> Dict[str, float]:
        """
        Calcula los pesos HRP.

        Args:
            prices: DataFrame con precios históricos

        Returns:
            Dict con pesos óptimos por activo
        """
        # Validar entrada
        self._validate_prices(prices)

        # Calcular retornos logarítmicos (más estables que simples)
        returns = np.log(prices / prices.shift(1)).dropna()

        if returns.shape[0] < 10:
            raise ValueError(f"Se necesitan al menos 10 observaciones de retornos, se obtuvieron {returns.shape[0]}")

        try:
            # Instanciar HRP con matriz de correlación de retornos
            hrp = HRPOpt(returns)

            # Optimizar con el método de clustering especificado
            hrp.optimize(linkage_method=self.linkage_method)

            # Limpiar pesos: eliminar muy pequeños y normalizar
            raw_weights = hrp.weights
            weights_dict = dict(zip(prices.columns, raw_weights))

            # Limpiar pesos muy pequeños (< 1e-5)
            weights_dict = {
                ticker: max(0, w) for ticker, w in weights_dict.items()
            }

            # Renormalizar para que sumen exactamente 1.0
            total = sum(weights_dict.values())
            if total > 0:
                weights_dict = {ticker: w / total for ticker, w in weights_dict.items()}
            else:
                # Si todos los pesos son cero, distribuir equitativamente
                n = len(weights_dict)
                weights_dict = {ticker: 1.0 / n for ticker in weights_dict.keys()}

            # Validar pesos antes de retornar
            self._validate_weights(weights_dict)

            return weights_dict

        except Exception as e:
            raise ValueError(f"Error en optimización HRP: {str(e)}")
