"""
Risk Optimization — Módulo de optimización de portafolios.

Proporciona herramientas para:
- Optimización de pesos (HRP, Markowitz)
- Cálculo de métricas de rendimiento
- Gestión dinámica de portafolios con rebalanceo

Interfaz principal: PortfolioEngine
"""

from .portfolio_engine import PortfolioEngine
from .optimizers import RiskOptimizer, HRPOptimizer, MarkowitzOptimizer
from . import metrics

__all__ = [
    "PortfolioEngine",
    "RiskOptimizer",
    "HRPOptimizer",
    "MarkowitzOptimizer",
    "metrics",
]
