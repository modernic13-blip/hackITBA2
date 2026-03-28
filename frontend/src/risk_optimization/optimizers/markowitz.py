"""
Optimizador Markowitz Penalizado.

Implementa la optimización cuadrática clásica de Markowitz con:
- Minimización de varianza ponderada por aversión al riesgo (lambda_risk)
- Penalización de turnover para evitar rebalanceos excesivos
- Constraint de fully invested (long-only)
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np
from .base import RiskOptimizer

try:
    import cvxpy as cp
except ImportError:
    raise ImportError("Se requiere la librería 'cvxpy'. Instala con: pip install cvxpy")


class MarkowitzOptimizer(RiskOptimizer):
    """
    Optimizador Markowitz con penalización por turnover.

    Minimiza: lambda_risk * varianza - retorno + penalty * |w - w_anterior|

    Parámetros:
        lambda_risk (float): Aversión al riesgo (default 2.0)
            Riesgo bajo: 5-8
            Riesgo alto: 2-4
        penalty (float): Penalización por cambios de pesos (default 0.001)
        previous_weights (dict): Pesos previos para penalizar turnover
    """

    def __init__(self, config: dict = None):
        """
        Inicializa el optimizador Markowitz.

        Args:
            config: Dict con parámetros. Ejemplo:
                {
                    "lambda_risk": 6.0,
                    "penalty": 0.001
                }
        """
        super().__init__(config)
        self.lambda_risk = self.config.get("lambda_risk", 2.0)
        self.penalty = self.config.get("penalty", 0.001)
        self.previous_weights = None

    def set_previous_weights(self, weights: Dict[str, float]) -> None:
        """
        Establece los pesos previos para penalizar turnover.

        Args:
            weights: Dict con pesos previos {ticker: peso}
        """
        self.previous_weights = weights

    def optimize(self, prices: pd.DataFrame) -> Dict[str, float]:
        """
        Calcula los pesos óptimos de Markowitz con penalización.

        Args:
            prices: DataFrame con precios históricos

        Returns:
            Dict con pesos óptimos por activo
        """
        # Validar entrada
        self._validate_prices(prices)

        # Calcular retornos simples
        returns = prices.pct_change().dropna()

        if returns.shape[0] < 10:
            raise ValueError(
                f"Se necesitan al menos 10 observaciones de retornos, "
                f"se obtuvieron {returns.shape[0]}"
            )

        try:
            # Calcular estadísticas
            mu = returns.mean().values  # vector de retornos esperados
            sigma = returns.cov().values  # matriz de covarianza
            n = len(prices.columns)

            # Vector de pesos previos (para penalizar turnover)
            if self.previous_weights is not None:
                w_prev = np.array([
                    self.previous_weights.get(ticker, 0)
                    for ticker in prices.columns
                ])
            else:
                w_prev = np.zeros(n)

            # Variable de decisión: pesos
            w = cp.Variable(n)

            # Función objetivo
            # Minimizar: (lambda/2) * w^T * Sigma * w - mu^T * w + penalty * ||w - w_prev||_1
            variance_term = (self.lambda_risk / 2.0) * cp.quad_form(w, sigma)
            return_term = mu @ w
            turnover_penalty = self.penalty * cp.norm(w - w_prev, 1)

            objective = cp.Minimize(variance_term - return_term + turnover_penalty)

            # Constraints:
            # 1. Fully invested: sum(w) = 1.0
            # 2. Long-only: w >= 0
            constraints = [
                cp.sum(w) == 1.0,
                w >= 0
            ]

            # Resolver problema
            problem = cp.Problem(objective, constraints)

            # Intenta resolver con diferentes solvers en cadena
            for solver in [cp.OSQP, cp.SCS, cp.ECOS]:
                try:
                    problem.solve(solver=solver, verbose=False)
                    if problem.status == cp.OPTIMAL:
                        break
                except Exception:
                    continue

            if problem.status != cp.OPTIMAL:
                raise ValueError(f"Optimización no convergió. Status: {problem.status}")

            # Extraer pesos
            weights_array = np.array(w.value).flatten()
            weights_dict = dict(zip(prices.columns, weights_array))

            # Limpiar pesos muy pequeños
            weights_dict = {
                ticker: max(0, w) for ticker, w in weights_dict.items()
            }

            # Renormalizar
            total = sum(weights_dict.values())
            if total > 1e-10:
                weights_dict = {
                    ticker: w / total for ticker, w in weights_dict.items()
                }
            else:
                # Fallback: distribución equitativa
                n = len(weights_dict)
                weights_dict = {ticker: 1.0 / n for ticker in weights_dict.keys()}

            # Validar pesos
            self._validate_weights(weights_dict)

            return weights_dict

        except Exception as e:
            raise ValueError(f"Error en optimización Markowitz: {str(e)}")
