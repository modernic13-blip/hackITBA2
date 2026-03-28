"""
Métricas de rendimiento del portafolio.

Funciones simples para calcular métricas financieras sin dependencias
externas más allá de numpy/pandas.
"""

import numpy as np
import pandas as pd
from typing import Union


def sharpe_ratio(
    returns: Union[pd.Series, np.ndarray],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """
    Calcula el Sharpe Ratio anualizado.

    Args:
        returns: Serie de retornos (diarios, semanales, etc.)
        risk_free_rate: Tasa libre de riesgo anualizada (default 0%)
        periods_per_year: Número de períodos por año (252 para diarios)

    Returns:
        Sharpe Ratio anualizado
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    if len(returns) < 2:
        return 0.0

    excess_returns = returns - (risk_free_rate / periods_per_year)
    mean_excess = np.mean(excess_returns)
    std_excess = np.std(excess_returns, ddof=1)

    if std_excess == 0:
        return 0.0

    return (mean_excess / std_excess) * np.sqrt(periods_per_year)


def max_drawdown(prices_or_returns: Union[pd.Series, np.ndarray]) -> float:
    """
    Calcula el máximo drawdown (máxima caída acumulada).

    Args:
        prices_or_returns: Serie de precios o retornos acumulados

    Returns:
        Máximo drawdown (negativo, p.ej. -0.15 = -15%)
    """
    if isinstance(prices_or_returns, pd.Series):
        values = prices_or_returns.values
    else:
        values = prices_or_returns

    # Si los valores parecen retornos simples (< 10), convertir a valores acumulados
    if np.all(np.abs(values) < 10) and np.all(values > -1):
        # Son retornos, calcular valor acumulado
        equity_curve = np.cumprod(1 + values)
    else:
        # Son precios o valores acumulados
        equity_curve = values

    running_max = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - running_max) / running_max

    return np.min(drawdown)


def cagr(
    initial_value: float,
    final_value: float,
    periods: int,
    periods_per_year: int = 252
) -> float:
    """
    Calcula el CAGR (Compound Annual Growth Rate).

    Args:
        initial_value: Valor inicial del portafolio
        final_value: Valor final del portafolio
        periods: Número de períodos en los datos
        periods_per_year: Número de períodos por año (252 para diarios)

    Returns:
        CAGR anualizado (0.1 = 10%)
    """
    if initial_value <= 0 or final_value <= 0:
        return 0.0

    years = periods / periods_per_year
    if years <= 0:
        return 0.0

    cagr_value = (final_value / initial_value) ** (1 / years) - 1
    return cagr_value


def calmar_ratio(
    returns: Union[pd.Series, np.ndarray],
    periods_per_year: int = 252
) -> float:
    """
    Calcula el Calmar Ratio (CAGR / |Max Drawdown|).

    Args:
        returns: Serie de retornos
        periods_per_year: Número de períodos por año

    Returns:
        Calmar Ratio
    """
    if isinstance(returns, pd.Series):
        equity_curve = (1 + returns).cumprod().values
    else:
        equity_curve = np.cumprod(1 + returns)

    # CAGR
    cagr_val = cagr(equity_curve[0], equity_curve[-1], len(equity_curve), periods_per_year)

    # Max Drawdown
    mdd = max_drawdown(equity_curve)

    if mdd == 0 or abs(mdd) < 1e-10:
        return 0.0

    return cagr_val / abs(mdd)


def sortino_ratio(
    returns: Union[pd.Series, np.ndarray],
    target_return: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """
    Calcula el Sortino Ratio (solo penaliza volatilidad a la baja).

    Args:
        returns: Serie de retornos
        target_return: Retorno objetivo (default 0%)
        periods_per_year: Número de períodos por año

    Returns:
        Sortino Ratio anualizado
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    if len(returns) < 2:
        return 0.0

    excess_returns = returns - (target_return / periods_per_year)
    downside_returns = excess_returns[excess_returns < 0]

    if len(downside_returns) == 0:
        return 0.0

    downside_std = np.std(downside_returns, ddof=1)

    if downside_std == 0:
        return 0.0

    mean_excess = np.mean(excess_returns)
    return (mean_excess / downside_std) * np.sqrt(periods_per_year)


def information_ratio(
    returns: Union[pd.Series, np.ndarray],
    benchmark_returns: Union[pd.Series, np.ndarray],
    periods_per_year: int = 252
) -> float:
    """
    Calcula el Information Ratio (retorno vs benchmark / tracking error).

    Args:
        returns: Serie de retornos de la estrategia
        benchmark_returns: Serie de retornos del benchmark
        periods_per_year: Número de períodos por año

    Returns:
        Information Ratio anualizado
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    if isinstance(benchmark_returns, pd.Series):
        benchmark_returns = benchmark_returns.values

    active_returns = returns - benchmark_returns
    mean_active = np.mean(active_returns)
    tracking_error = np.std(active_returns, ddof=1)

    if tracking_error == 0:
        return 0.0

    return (mean_active / tracking_error) * np.sqrt(periods_per_year)
