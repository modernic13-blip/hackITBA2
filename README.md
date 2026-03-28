# hackITBA — Portfolio Inteligente con ML

Sistema de inversión automatizado basado en Machine Learning para la gestión de portafolios multi-activo. El usuario elige su nivel de inversión y riesgo; el modelo entrenado con datos históricos genera señales de compra/venta y optimiza la asignación del portafolio.

---

## Concepto

1. **El usuario** entra a la app, elige capital a invertir y perfil de riesgo (bajo / alto)
2. **El modelo** fue entrenado con datos 2021–2024 sobre 11 activos
3. **Backtesting 2025**: el usuario ve cuánto hubiera ganado con ese portafolio antes de comprometerse
4. **Suscripción 2026**: el modelo opera en vivo comprando y vendiendo automáticamente

---

## Activos

| Tipo | Activos |
|------|---------|
| ETFs | GLD, QQQ, TLT |
| Acciones | AAPL, NVDA, META, AMZN, XOM, PLTR, COIN |
| Crypto | BTC |

---

## Arquitectura del Sistema

```
Datos históricos (2021–2024)
        │
        ▼
┌─────────────────────────────┐
│     Smart Indicators        │  ← Pipeline de 8 módulos ML
│  M1 Ingestion               │
│  M2 Feature Engineering     │  200+ indicadores técnicos
│  M3 Filtering (CUSUM)       │  multi-timeframe (15min→1d)
│  M4 Labeling (Triple Barrier│
│  M5 Walk-Forward Split      │
│  M6 Feature Selection       │
│  M7 Model Training          │  XGBoost / LightGBM / RF
│  M8 Evaluation              │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│    Risk Optimization        │
│  HRP / Markowitz penalizado │  → Pesos por activo
│  Constraints: long-only,    │
│  leverage ≤ 1, threshold    │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│    Live Trading Engine      │  Backtesting 2025 / Live 2026
│  Señales → Órdenes          │
│  Rebalanceo dinámico        │
│  Log de operaciones (JSON)  │
└─────────────────────────────┘
```

---

## Smart Indicators: Pipeline ML

El núcleo del sistema. Genera señales de trading a partir de datos OHLCV.

### Módulos

| Módulo | Descripción |
|--------|-------------|
| M1 Ingestion | Carga datos CSV / AWS S3, soporta time-bars y dollar-bars |
| M2 Features | 200+ features técnicos en múltiples timeframes |
| M3 Filtering | Filtro CUSUM para detectar eventos significativos |
| M4 Labeling | Triple-Barrier Method — etiqueta {-1, +1} por barrera tocada |
| M5 Splitting | Walk-forward con purging y embargo (sin data leakage) |
| M6 Feature Selection | Forward selection greedy (~15-30 features finales) |
| M7 Modeling | XGBoost, LightGBM, CatBoost, RandomForest con grid search |
| M8 Evaluation | AUC, Sharpe, MaxDrawdown, DSR, PBO |

### Indicadores técnicos (multi-timeframe: 15min, 1h, 4h, 12h, 1d)

- **Momentum**: RSI, MACD, CCI, Williams %R
- **Volatilidad**: Bollinger Bands, SuperTrend (ATR)
- **Volumen**: VWAP, CMF, MFI, OBV
- **Tendencia**: ADX
- **Microestructura**: OFI, TRANS_RATE, TICK_AUTOCORR

---

## Optimización de Riesgo

Dos estrategias según perfil del usuario:

| Parámetro | Bajo Riesgo | Alto Riesgo |
|-----------|-------------|-------------|
| Optimizador | Markowitz λ=5-8 / HRP | Markowitz λ=2-4 / HRP |
| Lookback | 200–250 días | 100–160 días |
| Umbral rebalanceo | 5% | 1% |
| Comportamiento | Estable, baja rotación | Dinámico, sigue momentum |

**Constraints**: long-only, leverage ≤ 1.0, umbral mínimo de cambio para rebalancear.

---

## Backtesting

- **Train**: 2021-01-01 → 2024-12-31
- **Test**: 2025-01-01 → 2025-12-31
- **Método**: Walk-forward (5 folds), sin data leakage
- **Comisión simulada**: 0.01% por operación
- **Métricas**: Sharpe Ratio, Max Drawdown, AUC-ROC, DSR, PBO

---

## Estructura del Proyecto

```
hackITBA/
├── notebooks/
│   ├── smart_indicators/       # Experimentos por activo (META, BTC, etc.)
│   └── risk_optimization/      # HRP, Markowitz, HRP vs Equal Weight
├── src/
│   └── Pipelines/
│       ├── smart_indicators/   # Pipeline ML (core del sistema)
│       ├── risk_optimization/  # Optimizadores de portafolio
│       └── live_trading/       # Motor de ejecución
├── tests/                      # Suite de tests unitarios
├── docs/                       # Documentación técnica
└── main.ipynb                  # Notebook principal de ejecución
```

---

## Instalación

**Requisitos**: Python >= 3.10

```bash
git clone https://github.com/dav1dchaparro/hackITBA.git
cd hackITBA
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .\.venv\Scripts\Activate.ps1  # Windows
pip install -e .
```

---

## Uso rápido

```python
from src.Pipelines.risk_optimization.data.s3DataExtractor import S3DataExtractor
from src.Pipelines.risk_optimization.simulation.walk_forward import walk_forward_grid_search
from src.Pipelines.live_trading.engine.portfolio_holding_engine import PortfolioHoldingEngine

TICKERS = ["GLD", "QQQ", "TLT", "AAPL", "NVDA", "META", "AMZN", "XOM", "PLTR", "COIN", "BTC"]

# 1. Extraer datos
extractor = S3DataExtractor(...)
df_train = extractor.extract_data(assets=TICKERS, start="2021-01-01", end="2024-12-31")

# 2. Optimizar estrategia (walk-forward grid search)
best_optimizer = walk_forward_grid_search(data=df_train, ...)

# 3. Simular en 2025
engine = PortfolioHoldingEngine(assets=TICKERS, risk_optimizer=best_optimizer)
engine.run(df_test)
engine.export_trading_log("resultado_2025.json")
```

Ver [main.ipynb](main.ipynb) para el flujo completo.

---

## Tests

```bash
pytest
```

---

## Stack tecnológico

- **ML**: scikit-learn, XGBoost, LightGBM, CatBoost
- **Optimización**: PyPortfolioOpt, CVXPY
- **Datos**: yfinance, AWS S3
- **Tracking**: MLFlow
- **Data**: pandas, numpy, ta-lib
