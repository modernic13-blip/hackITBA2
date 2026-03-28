# hackITBA — Portfolio Inteligente con ML

Sistema de inversión automatizado con Machine Learning + Black-Litterman para gestión de portafolios multi-activo. El usuario elige capital y perfil de riesgo; el modelo entrenado con datos históricos genera señales y optimiza la asignación del portafolio.

---

## Guía Rápida (nueva PC)

> Seguí estos pasos en orden. Nada más es necesario.

**Requisitos previos que necesitás tener instalados:**
- Python 3.10, 3.11 o 3.12 (NO usar 3.13)
- Node.js 18+ y npm
- Git

```bash
# ── 1. CLONAR ────────────────────────────────────────────────────────────────
git clone https://github.com/dav1dchaparro/hackITBA.git
cd hackITBA

# ── 2. ENTORNO PYTHON ────────────────────────────────────────────────────────
python3 -m venv venv
source venv/bin/activate          # Linux/macOS
# venv\Scripts\activate.bat       # Windows

# ── 3. DEPENDENCIAS PYTHON ───────────────────────────────────────────────────
pip install -r requirements.txt
# Paquetes: numpy, pandas, scikit-learn, xgboost, lightgbm,
#           PyPortfolioOpt, cvxpy, PyYAML, scipy, packaging

# ── 4. DATOS (CSVs ya deben estar en data/) ──────────────────────────────────
# Verificar que existan:
ls data/
# Debe mostrar: AAPL.csv NVDA.csv META.csv AMZN.csv XOM.csv
#               PLTR.csv COIN.csv GLD.csv QQQ.csv TLT.csv BTC-USD.csv

# ── 5. CORRER EL MODELO ──────────────────────────────────────────────────────
python main_executor.py                          # Los 3 perfiles (~30-45 min)
python main_executor.py --profiles low_risk      # Solo uno (~10-15 min)

# Los resultados quedan en results/
# results_low_risk.json | results_med_risk.json | results_high_risk.json

# ── 6. PASAR RESULTADOS AL FRONTEND ──────────────────────────────────────────
cp results/results_*.json public/data/

# ── 7. LEVANTAR EL FRONTEND ──────────────────────────────────────────────────
npm install          # solo la primera vez
npm run dev          # http://localhost:5173
```

---

## Arquitectura

```
Datos históricos (2020–2024, OHLCV diario)
        │
        ▼
┌─────────────────────────────────┐
│  Smart Indicators Pipeline      │
│  M2 Feature Engineering         │  RSI, MACD, BBands, ATR, ADX
│  M3 Filtering (CUSUM adaptativo)│
│  M4 Labeling (Triple Barrier)   │
│  M5 Walk-Forward Split          │
│  M6 Feature Selection           │
│  M7 Model Training              │  XGBoost / LightGBM / RandomForest
│  M8 Evaluation                  │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│  Black-Litterman Optimizer      │
│  Señales ML → vistas absolutas  │
│  Π = δ·Σ·w_mkt  →  μ_BL        │
│  Rebalanceo diario 2024         │
└─────────────────────────────────┘
        │
        ▼
results_low_risk.json / med_risk.json / high_risk.json
        │
        ▼
React Frontend (smart-capital branch)
```

---

## Activos por Perfil

| Perfil | Activos | Fee |
|--------|---------|-----|
| Low Risk | AAPL, NVDA, AMZN, XOM, GLD, QQQ, TLT | 1% sobre ganancias |
| Med Risk | AAPL, NVDA, META, AMZN, XOM, GLD, QQQ, BTC, COIN | 10% |
| High Risk | BTC, NVDA, META, PLTR, COIN, AMZN, AAPL | 30% |

---

## Requisitos del Sistema

- Python **3.10, 3.11 o 3.12** (el proyecto NO fue testeado en 3.13)
- pip >= 23.0
- ~2 GB RAM disponibles

---

## Instalación (primera vez)

```bash
# 1. Clonar el repositorio
git clone https://github.com/dav1dchaparro/hackITBA.git
cd hackITBA

# 2. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows

# 3. Instalar dependencias del backend
pip install -r requirements.txt

# 4. Instalar dependencias del frontend
cd smart-capital   # o el subdirectorio donde está el frontend
npm install
cd ..
```

---

## Datos Necesarios

Los CSVs de precios deben estar en `data/` con formato estándar yfinance:

```
data/
  AAPL.csv
  NVDA.csv
  META.csv
  AMZN.csv
  XOM.csv
  PLTR.csv
  COIN.csv
  GLD.csv
  QQQ.csv
  TLT.csv
  BTC-USD.csv
```

Cada CSV debe tener columnas: `Date, Open, High, Low, Close, Volume`
Rango mínimo recomendado: **2020-01-01 a 2024-12-31**

Para descargar los datos automáticamente:
```bash
python scripts/download_data.py   # si está disponible
# o manualmente desde Yahoo Finance / yfinance
```

---

## Correr el Modelo (Backend)

```bash
# Activar entorno
source venv/bin/activate

# Correr los 3 perfiles (modo RÁPIDO — ~10-15 min total)
python main_executor.py

# Correr solo un perfil
python main_executor.py --profiles low_risk
python main_executor.py --profiles med_risk
python main_executor.py --profiles high_risk

# Correr varios perfiles
python main_executor.py --profiles low_risk med_risk
```

### Estimación de Tiempos (modo RÁPIDO actual)

| Etapa | Tiempo estimado |
|-------|-----------------|
| Cold Start M2+M3 por ticker | ~20–40 seg/activo |
| Entrenamiento M4-M8 por activo | ~1–2 min/activo |
| Low Risk (7 activos) | ~10–15 min |
| Med Risk (9 activos) | ~12–18 min |
| High Risk (7 activos) | ~10–15 min |
| **Total 3 perfiles** | **~30–45 min** |

> Activos en común entre perfiles se calculan una sola vez (cache interno).

---

## Copiar Resultados al Frontend

Después de correr el modelo, copiar los JSON generados a la carpeta pública del frontend:

```bash
# Los resultados se guardan en results/
ls results/
# results_low_risk.json
# results_med_risk.json
# results_high_risk.json

# Copiar al frontend (ajustar ruta según tu estructura)
cp results/results_*.json smart-capital/public/data/
# o
cp results/results_*.json public/data/
```

---

## Correr el Frontend

```bash
cd smart-capital        # directorio del frontend React
npm run dev             # inicia servidor en http://localhost:5173
```

El frontend leerá automáticamente `/data/results_{profile}.json` al cambiar de perfil.

---

## Estructura del Proyecto

```
hackITBA/
├── main_executor.py          # Orquestador principal
├── requirements.txt          # Dependencias Python
├── configs/
│   ├── low_risk.yaml         # Perfil conservador
│   ├── med_risk.yaml         # Perfil balanceado
│   └── high_risk.yaml        # Perfil agresivo
├── data/
│   ├── AAPL.csv              # Datos históricos por activo
│   ├── NVDA.csv
│   └── ...
├── results/                  # JSON generados por main_executor.py
│   ├── results_low_risk.json
│   ├── results_med_risk.json
│   └── results_high_risk.json
└── src/
    └── smart_indicators/     # Pipeline ML (M1–M8)
```

---

## Parámetros Ajustables (configs/\*.yaml)

```yaml
risk_tolerance: 0.3          # Tolerancia al riesgo [0-1]
max_weight_per_asset: 0.25   # Máx peso por activo (0.25 = 25%)
confidence_level: 0.65       # Confianza en señales ML
initial_capital: 1000.0      # Capital inicial para backtest

black_litterman:
  delta: 3.5                 # Aversión al riesgo (más alto = más conservador)
  tau: 0.05                  # Incertidumbre en el prior del mercado

assets: [AAPL, NVDA, ...]    # Lista de activos del portafolio
```

---

## Dependencias Principales

| Paquete | Versión | Uso |
|---------|---------|-----|
| pandas | 3.0.1 | Manejo de datos |
| numpy | 2.4.3 | Cálculo numérico |
| scikit-learn | 1.8.0 | Pipeline ML |
| xgboost | 3.2.0 | Modelo principal |
| lightgbm | 4.6.0 | Modelo alternativo |
| PyPortfolioOpt | 1.6.0 | Optimización Black-Litterman |
| cvxpy | 1.8.2 | Optimización convexa |
| PyYAML | 6.0.3 | Lectura de configs |
| scipy | 1.17.1 | Álgebra lineal |
