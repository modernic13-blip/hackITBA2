# hackITBA — Portfolio Inteligente con ML

Sistema de inversión automatizado con Machine Learning + Black-Litterman para gestión de portafolios multi-activo. Datos horarios, 11 activos, 3 perfiles de riesgo.

---

## Guía Rápida (nueva PC)

**Requisitos previos:** Python 3.10-3.12, Node.js 18+, Git

```bash
# 1. CLONAR
git clone https://github.com/dav1dchaparro/hackITBA.git
cd hackITBA

# 2. BACKEND — entorno virtual
python3 -m venv venv
source venv/bin/activate          # Linux/macOS
# venv\Scripts\activate.bat       # Windows
pip install -r requirements.txt

# 3. CORRER EL MODELO (entrena y genera JSONs)
python main_executor.py                         # Los 3 perfiles (~45 min)
python main_executor.py --profiles low_risk     # Solo uno (~15 min)
# Resultados → results/ y frontend/public/data/ (auto-copiado)

# 4. FRONTEND
cd frontend
npm install
npm run dev        # http://localhost:8080
```

---

## Estructura del Proyecto

```
hackITBA/
├── main_executor.py          # Orquestador principal (corre el modelo)
├── requirements.txt          # Dependencias Python
│
├── configs/                  # Perfiles de riesgo
│   ├── low_risk.yaml         # Conservador  — fee 1%
│   ├── med_risk.yaml         # Balanceado   — fee 10%
│   └── high_risk.yaml        # Agresivo     — fee 30%
│
├── data/                     # Datos OHLCV horarios (1h)
│   ├── AAPL_1h.csv
│   ├── NVDA_1h.csv
│   └── ...                   # 11 activos
│
├── cache/                    # Caché M2+M3 por activo (.pkl)
│                             # Se reutiliza en ejecuciones siguientes
├── results/                  # JSONs generados por el modelo
│
├── frontend/                 # App React (Vite + Recharts + Supabase)
│   ├── src/
│   │   ├── components/       # BacktestingReveal, AllocationChart, etc.
│   │   ├── pages/            # Index, Simulacion, Login, Dashboard
│   │   ├── hooks/            # useBacktestData
│   │   └── data/             # mockData (allocations del onboarding)
│   ├── public/data/          # JSONs de resultados (se copian automáticamente)
│   ├── package.json
│   └── vite.config.ts
│
└── src/                      # Pipeline ML (no tocar)
    ├── smart_indicators/     # M1-M8
    └── risk_optimization/    # Optimizadores HRP/Markowitz
```

---

## Activos por Perfil

| Perfil | Activos | Fee sobre ganancias |
|--------|---------|---------------------|
| Low Risk | AAPL, NVDA, AMZN, XOM, GLD, QQQ, TLT | 1% |
| Med Risk | AAPL, NVDA, META, AMZN, XOM, GLD, QQQ, BTC, COIN | 10% |
| High Risk | BTC, NVDA, META, PLTR, COIN, AMZN, AAPL | 30% |

---

## Tiempos Estimados

| Ejecución | Tiempo |
|-----------|--------|
| Primera vez (sin caché) | ~45-60 min (3 perfiles) |
| Con caché M2+M3 | ~10-15 min (3 perfiles) |
| Si cambian los CSVs | Caché se invalida → primera vez |

> M2+M3 (features + CUSUM) se cachea por activo en `cache/cold_{TICKER}_{hash}.pkl`.
> Si los datos no cambian, la próxima ejecución salta esos módulos.

---

## Dependencias Python

| Paquete | Versión |
|---------|---------|
| pandas | 3.0.1 |
| numpy | 2.4.3 |
| scikit-learn | 1.8.0 |
| xgboost | 3.2.0 |
| lightgbm | 4.6.0 |
| PyPortfolioOpt | 1.6.0 |
| cvxpy | 1.8.2 |
| PyYAML | 6.0.3 |
| scipy | 1.17.1 |
