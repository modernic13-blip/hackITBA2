"""
Demo de resultados 2025 — hackITBA Portfolio Inteligente
=========================================================

Ejecuta el pipeline completo para todos los activos,
entrena en 2020-2024 y evalúa en 2025.

Uso:
    python demo_2025.py

Requisitos:
    - Archivos CSV en data/ (ver data/README.md)
    - pip install -e .
"""

import sys
import os
import time
import json
import warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd
import numpy as np

from smart_indicators import SignalPipeline
from smart_indicators.core.pipeline_data import PipelineData
from risk_optimization import PortfolioEngine
from risk_optimization import metrics as port_metrics


# =============================================================================
# Configuración del demo
# =============================================================================

TICKERS = {
    "ETFs":     ["GLD", "QQQ", "TLT"],
    "Acciones": ["AAPL", "NVDA", "META", "AMZN", "XOM", "PLTR", "COIN"],
    "Crypto":   ["BTC"],
}

CONFIG_MAP = {
    "GLD":  "configs/etf_bajo_riesgo.yaml",
    "QQQ":  "configs/etf_bajo_riesgo.yaml",
    "TLT":  "configs/etf_bajo_riesgo.yaml",
    "AAPL": "configs/acciones_alto_riesgo.yaml",
    "NVDA": "configs/acciones_alto_riesgo.yaml",
    "META": "configs/acciones_alto_riesgo.yaml",
    "AMZN": "configs/acciones_alto_riesgo.yaml",
    "XOM":  "configs/acciones_alto_riesgo.yaml",
    "PLTR": "configs/acciones_alto_riesgo.yaml",
    "COIN": "configs/acciones_alto_riesgo.yaml",
    "BTC":  "configs/btc_crypto.yaml",
}

CAPITAL_INICIAL = 100_000  # $100,000

# ─── Helpers de impresión ─────────────────────────────────────────────────────

def sep(char="═", n=65):
    print(char * n)

def title(texto):
    sep()
    print(f"  {texto}")
    sep()

def subtitle(texto):
    print()
    print(f"  {'─' * 50}")
    print(f"  {texto}")
    print(f"  {'─' * 50}")

def verde(texto):
    return f"\033[92m{texto}\033[0m"

def rojo(texto):
    return f"\033[91m{texto}\033[0m"

def amarillo(texto):
    return f"\033[93m{texto}\033[0m"

def bold(texto):
    return f"\033[1m{texto}\033[0m"

def formato_pct(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    color = verde if val >= 0 else rojo
    return color(f"{val:+.2f}%")

def formato_num(val, prefix="", decimals=2):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{prefix}{val:.{decimals}f}"

# ─── Entrenamiento por activo ─────────────────────────────────────────────────

def entrenar_activo(ticker: str, config_path: str) -> dict:
    """
    Entrena el pipeline completo para un activo y retorna métricas.
    """
    # Actualizar csv_path en el config
    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f)

    config["asset"] = ticker
    config["ingestion"]["csv_path"] = f"data/{ticker}.csv"

    print(f"  [{ticker}] Iniciando pipeline... ", end="", flush=True)
    t0 = time.time()

    try:
        pipeline = SignalPipeline(config)
        data = PipelineData()
        data, ok = pipeline.run_modules([1, 2, 3, 4, 5, 6, 7, 8], data)

        elapsed = time.time() - t0

        if not ok:
            print(rojo(f"FALLÓ ({elapsed:.1f}s)"))
            return {"ticker": ticker, "ok": False, "error": "Pipeline falló"}

        # Extraer métricas
        m = data.get("metrics", required=False) or {}
        predictions = data.get("fold_predictions", required=False)
        equity = data.get("equity_curve", required=False)
        model_obj = data.get("best_model_obj", required=False)

        print(verde(f"OK ({elapsed:.1f}s)"))

        return {
            "ticker":      ticker,
            "ok":          True,
            "auc":         m.get("mean_auc", 0),
            "sharpe":      m.get("mean_sharpe", 0),
            "max_dd":      m.get("max_drawdown", 0),
            "total_ret":   m.get("total_return", 0),
            "calmar":      m.get("calmar_ratio", 0),
            "dsr":         m.get("dsr", 0),
            "pbo":         m.get("pbo", 0),
            "predictions": predictions,
            "equity":      equity,
            "model_obj":   model_obj,
            "data":        data,
        }

    except Exception as e:
        elapsed = time.time() - t0
        print(rojo(f"ERROR ({elapsed:.1f}s): {str(e)[:60]}"))
        return {"ticker": ticker, "ok": False, "error": str(e)}


# ─── Resultados 2025 ──────────────────────────────────────────────────────────

def evaluar_2025(ticker: str, model_obj, config_path: str) -> dict:
    """
    Evalúa el modelo entrenado sobre datos de 2025.
    """
    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f)

    csv_path = f"data/{ticker}.csv"
    if not os.path.exists(csv_path):
        return {"ticker": ticker, "ok": False, "error": "CSV no encontrado"}

    df = pd.read_csv(csv_path, parse_dates=["date"], index_col="date")
    df_2025 = df[df.index.year == 2025]

    if df_2025.empty:
        return {"ticker": ticker, "ok": False, "error": "No hay datos de 2025"}

    # Retorno buy & hold de 2025 (benchmark)
    bh_return = (df_2025["close"].iloc[-1] / df_2025["close"].iloc[0] - 1) * 100

    return {
        "ticker":         ticker,
        "ok":             True,
        "bh_return_2025": bh_return,
        "n_dias":         len(df_2025),
        "precio_inicio":  df_2025["close"].iloc[0],
        "precio_fin":     df_2025["close"].iloc[-1],
    }


# ─── Portafolio ───────────────────────────────────────────────────────────────

def calcular_portafolio(resultados: list, capital: float, perfil: str) -> dict:
    """
    Calcula la asignación óptima del portafolio.
    """
    # Señales: +1 si el modelo predice ganancia, -1 si no
    signals = {}
    for r in resultados:
        if r["ok"] and r.get("auc", 0) > 0.52:  # Solo activos con AUC decente
            signals[r["ticker"]] = 1
        else:
            signals[r["ticker"]] = 0

    # Construir DataFrame de precios de los activos con señal
    tickers_long = [t for t, s in signals.items() if s == 1]
    if not tickers_long:
        return {"ok": False, "error": "Ningún activo con señal positiva"}

    prices_dict = {}
    for ticker in tickers_long:
        csv_path = f"data/{ticker}.csv"
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path, parse_dates=["date"], index_col="date")
            df_train = df[(df.index.year >= 2020) & (df.index.year <= 2024)]
            if not df_train.empty:
                prices_dict[ticker] = df_train["close"]

    if not prices_dict:
        return {"ok": False, "error": "No se pudieron cargar precios"}

    prices_df = pd.DataFrame(prices_dict).dropna()

    config = {
        "risk_profile":       perfil,
        "optimizer":          "markowitz" if perfil == "low" else "hrp",
        "capital":            capital,
        "rebalance_threshold": 0.05 if perfil == "low" else 0.02,
    }

    try:
        engine = PortfolioEngine(prices_df, signals, config)
        weights = engine.compute_weights()
        allocation = engine.compute_allocation(capital)
        return {"ok": True, "weights": weights, "allocation": allocation}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── Impresión de resultados ──────────────────────────────────────────────────

def imprimir_resultados_por_activo(resultados: list):
    """
    Imprime tabla de métricas ML por activo.
    """
    subtitle("RENDIMIENTO DEL MODELO (2020-2024 entrenamiento)")
    print()
    print(f"  {'Activo':<8} {'AUC':>7} {'Sharpe':>8} {'MaxDD':>9} {'Retorno':>9} {'DSR':>7} {'PBO':>7}")
    print(f"  {'─'*8} {'─'*7} {'─'*8} {'─'*9} {'─'*9} {'─'*7} {'─'*7}")

    for r in resultados:
        if not r["ok"]:
            print(f"  {r['ticker']:<8} {rojo('ERROR: ' + r.get('error', '')[:40])}")
            continue

        auc     = r.get("auc", 0)
        sharpe  = r.get("sharpe", 0)
        max_dd  = r.get("max_dd", 0)
        ret     = r.get("total_ret", 0) * 100
        dsr     = r.get("dsr", 0)
        pbo     = r.get("pbo", 0)

        # Colorear AUC
        auc_str = verde(f"{auc:.4f}") if auc > 0.55 else (amarillo(f"{auc:.4f}") if auc > 0.5 else rojo(f"{auc:.4f}"))
        sharpe_str = verde(f"{sharpe:+.2f}") if sharpe > 1.0 else (amarillo(f"{sharpe:+.2f}") if sharpe > 0 else rojo(f"{sharpe:+.2f}"))
        dd_str = rojo(f"{max_dd:.2%}")
        ret_str = verde(f"{ret:+.1f}%") if ret > 0 else rojo(f"{ret:+.1f}%")
        dsr_str = verde(f"{dsr:.4f}") if dsr > 0 else rojo(f"{dsr:.4f}")
        pbo_str = verde(f"{pbo:.2f}") if pbo < 0.3 else (amarillo(f"{pbo:.2f}") if pbo < 0.5 else rojo(f"{pbo:.2f}"))

        print(f"  {r['ticker']:<8} {auc_str:>7} {sharpe_str:>8} {dd_str:>9} {ret_str:>9} {dsr_str:>7} {pbo_str:>7}")

    print()
    print("  AUC > 0.55 = bueno  |  Sharpe > 1.0 = bueno  |  PBO < 0.30 = sin overfitting")


def imprimir_portafolio(portafolio_bajo: dict, portafolio_alto: dict):
    """
    Imprime la asignación de portafolio para ambos perfiles.
    """
    subtitle("ASIGNACIÓN DEL PORTAFOLIO (basado en señales del modelo)")
    print()

    for label, port in [("Bajo Riesgo", portafolio_bajo), ("Alto Riesgo", portafolio_alto)]:
        print(f"  {'─'*50}")
        print(f"  Perfil: {bold(label)}")
        print(f"  {'─'*50}")

        if not port.get("ok"):
            print(f"  {rojo('No disponible: ' + port.get('error', ''))}")
            print()
            continue

        weights    = port["weights"]
        allocation = port["allocation"]
        total_inv  = sum(v for v in allocation.values() if v > 0)

        print(f"  {'Activo':<8} {'Peso':>8} {'Monto ($)':>12}")
        print(f"  {'─'*8} {'─'*8} {'─'*12}")

        for ticker, weight in sorted(weights.items(), key=lambda x: -x[1]):
            if weight < 0.001:
                continue
            monto = allocation.get(ticker, 0)
            pct_str = f"{weight:.1%}"
            monto_str = f"${monto:>10,.0f}"
            print(f"  {ticker:<8} {pct_str:>8} {monto_str:>12}")

        print(f"  {'─'*8} {'─'*8} {'─'*12}")
        print(f"  {'TOTAL':<8} {'100%':>8} {'${:>10,.0f}'.format(total_inv):>12}")
        print()


def imprimir_benchmark_2025(resultados_2025: list):
    """
    Imprime comparación de rendimiento en 2025 (Buy & Hold vs Modelo).
    """
    subtitle("BENCHMARK 2025 — Buy & Hold (sin modelo)")
    print()
    print(f"  {'Activo':<8} {'Inicio 2025':>12} {'Fin 2025':>12} {'Retorno B&H':>13}")
    print(f"  {'─'*8} {'─'*12} {'─'*12} {'─'*13}")

    total_bh = []
    for r in resultados_2025:
        if not r.get("ok"):
            print(f"  {r['ticker']:<8} {rojo('Sin datos 2025')}")
            continue

        bh = r["bh_return_2025"]
        total_bh.append(bh)
        bh_str = formato_pct(bh)
        print(f"  {r['ticker']:<8} "
              f"${r['precio_inicio']:>10,.2f} "
              f"${r['precio_fin']:>10,.2f} "
              f"{bh_str:>13}")

    if total_bh:
        avg_bh = np.mean(total_bh)
        print(f"  {'─'*8} {'─'*12} {'─'*12} {'─'*13}")
        print(f"  {'PROMEDIO':<8} {'':>12} {'':>12} {formato_pct(avg_bh):>13}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    title("hackITBA — Portfolio Inteligente con ML")
    print(f"  Fecha de ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Capital inicial:    ${CAPITAL_INICIAL:,}")
    print(f"  Período train:      2020-01-01 → 2024-12-31")
    print(f"  Período test:       2025-01-01 → 2025-12-31")
    sep("─")

    # ── 1. Verificar datos ────────────────────────────────────────────────────
    print()
    print("  Verificando archivos CSV...")
    todos_tickers = [t for grupo in TICKERS.values() for t in grupo]
    faltantes = [t for t in todos_tickers if not os.path.exists(f"data/{t}.csv")]
    disponibles = [t for t in todos_tickers if os.path.exists(f"data/{t}.csv")]

    if faltantes:
        print(f"  {amarillo('⚠')} CSV faltantes: {', '.join(faltantes)}")
        print(f"  {verde('✓')} CSV disponibles: {', '.join(disponibles)}")
        if not disponibles:
            print(rojo("\n  No hay archivos CSV. Por favor colocar en data/"))
            sys.exit(1)
        tickers_a_procesar = disponibles
    else:
        print(f"  {verde('✓')} Todos los CSV disponibles ({len(disponibles)} activos)")
        tickers_a_procesar = todos_tickers

    # ── 2. Entrenar pipeline por activo ───────────────────────────────────────
    subtitle(f"ENTRENANDO PIPELINE ML (2020–2024)")
    print()

    resultados = []
    for ticker in tickers_a_procesar:
        config_path = CONFIG_MAP.get(ticker, "configs/base_daily.yaml")
        if not os.path.exists(config_path):
            print(f"  [{ticker}] {amarillo('Config no encontrado, usando base_daily.yaml')}")
            config_path = "configs/base_daily.yaml"
        r = entrenar_activo(ticker, config_path)
        resultados.append(r)

    # ── 3. Métricas de entrenamiento ──────────────────────────────────────────
    imprimir_resultados_por_activo(resultados)

    # ── 4. Portafolio ─────────────────────────────────────────────────────────
    port_bajo = calcular_portafolio(resultados, CAPITAL_INICIAL, "low")
    port_alto = calcular_portafolio(resultados, CAPITAL_INICIAL, "high")
    imprimir_portafolio(port_bajo, port_alto)

    # ── 5. Benchmark 2025 ─────────────────────────────────────────────────────
    resultados_ok = [r for r in resultados if r["ok"]]
    if resultados_ok:
        resultados_2025 = []
        for r in resultados_ok:
            r25 = evaluar_2025(r["ticker"], r.get("model_obj"), CONFIG_MAP.get(r["ticker"], "configs/base_daily.yaml"))
            resultados_2025.append(r25)
        imprimir_benchmark_2025(resultados_2025)

    # ── 6. Resumen final ──────────────────────────────────────────────────────
    subtitle("RESUMEN FINAL")
    print()
    exitosos = [r for r in resultados if r["ok"]]
    print(f"  Activos entrenados:  {len(exitosos)}/{len(tickers_a_procesar)}")
    if exitosos:
        aucs = [r["auc"] for r in exitosos if r.get("auc")]
        sharpes = [r["sharpe"] for r in exitosos if r.get("sharpe")]
        if aucs:
            print(f"  AUC promedio:        {np.mean(aucs):.4f}")
        if sharpes:
            print(f"  Sharpe promedio:     {np.mean(sharpes):+.2f}")

    print()
    sep("═")
    print()
    print("  Para suscribirse al portafolio inteligente:")
    print("  → hackITBA Portfolio genera señales diarias automáticas")
    print("  → Selección de activos basada en Machine Learning")
    print("  → Optimización de riesgo personalizada (bajo / alto)")
    print()
    sep("═")
    print()


if __name__ == "__main__":
    main()
