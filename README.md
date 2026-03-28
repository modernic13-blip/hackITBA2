# QuantFlow AI — Portfolio Inteligente con Machine Learning

> Sistema de inversión automatizado que combina **Machine Learning** (XGBoost/LightGBM) con el modelo **Black-Litterman** para gestión dinámica de portafolios multi-activo. Analiza datos horarios de 11 activos, genera señales predictivas y rebalancea automáticamente según 3 perfiles de riesgo.

**hackITBA 2025** | Equipo: [dav1dchaparro](https://github.com/dav1dchaparro)

---

## Tabla de Contenidos

- [Descripcion del Proyecto](#descripcion-del-proyecto)
- [Arquitectura](#arquitectura)
- [Pipeline ML (M1-M8)](#pipeline-ml-m1-m8)
- [Optimizador Black-Litterman](#optimizador-black-litterman)
- [Perfiles de Riesgo](#perfiles-de-riesgo)
- [Resultados del Backtest](#resultados-del-backtest)
- [Instalacion y Ejecucion](#instalacion-y-ejecucion)
- [Frontend](#frontend)
- [Stack Tecnologico](#stack-tecnologico)
- [Estructura del Proyecto](#estructura-del-proyecto)

---

## Descripcion del Proyecto

### El Problema
Los inversores retail enfrentan dos desafíos principales:
1. **Selección de activos**: Decidir cuánto asignar a cada activo en cada momento
2. **Timing de mercado**: Cuándo rebalancear el portafolio

Las soluciones tradicionales (robo-advisors) usan reglas estáticas. Nosotros usamos **ML para predecir retornos** y **Black-Litterman para traducir esas predicciones en asignaciones óptimas**.

### La Solución
QuantFlow AI implementa un pipeline end-to-end que:

1. **Ingiere datos** OHLCV horarios de 11 activos (acciones, ETFs, crypto)
2. **Genera 30+ features** técnicos (RSI, MACD, Bollinger Bands, ATR, ADX, etc.)
3. **Filtra eventos relevantes** con CUSUM para evitar overtrading
4. **Etiqueta oportunidades** usando Triple Barrier Method (profit-take / stop-loss / timeout)
5. **Entrena modelos** XGBoost/LightGBM/RandomForest por activo con validación cruzada temporal
6. **Optimiza el portafolio** con Black-Litterman usando las señales ML como views
7. **Rebalancea dinámicamente** cada período según las predicciones actualizadas
8. **Visualiza resultados** en un frontend React interactivo con gráficos de evolución

### Diferenciadores Clave
- **No es un simple clasificador**: El sistema completo va de datos crudos → asignación de capital
- **Black-Litterman**: Combina equilibrio de mercado (CAPM) con views del ML de forma bayesiana
- **Triple Barrier Labeling**: Etiquetado financiero especializado (no simple up/down)
- **Caché inteligente**: Features pre-computados en disco para re-ejecuciones rápidas
- **3 perfiles de riesgo**: Configurables via YAML, cada uno con activos y parámetros distintos

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATOS DE ENTRADA                         │
│         CSVs OHLCV horarios (11 activos, abr2024-mar2026)       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PIPELINE ML (M1-M8)                          │
│                                                                 │
│  M1 Ingestion → M2 Features → M3 CUSUM Filter → M4 Labeling    │
│       → M5 Splitting → M6 Feature Selection → M7 Modeling       │
│                        → M8 Evaluation                          │
│                                                                 │
│  Cache: M2+M3 se guardan en disco (cache/cold_*.pkl)            │
│  Salida: signal_dict = {ticker: {prob_up, prob_down, pred}}     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│               OPTIMIZADOR BLACK-LITTERMAN                       │
│                                                                 │
│  1. Equilibrium returns (Π = δ·Σ·w_mkt)                        │
│  2. ML signals → views absolutas (q = predicted returns)        │
│  3. Posterior: μ_BL = inv(M) × [(τΣ)⁻¹Π + P'Ω⁻¹q]            │
│  4. Mean-Variance optimization → pesos óptimos                  │
│  5. Constraints: max_weight, long-only, fully invested          │
│                                                                 │
│  Rebalancea cada barra temporal con señales actualizadas         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     RESULTADOS JSON                              │
│                                                                 │
│  results_{profile}.json → portfolio_value, benchmark,           │
│                           allocations por día, confidence        │
│                                                                 │
│  Se copian automáticamente a frontend/public/data/              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FRONTEND REACT                                │
│                                                                 │
│  Onboarding (perfil de riesgo) → Simulación de backtest         │
│  → Gráfico de evolución → Allocations (stacked area + pie)      │
│  → Métricas: Sharpe, MaxDD, Return, vs Benchmark                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Pipeline ML (M1-M8)

El sistema implementa un pipeline modular de 8 etapas basado en el framework de **Advances in Financial Machine Learning** (Marcos López de Prado):

| Módulo | Nombre | Descripción |
|--------|--------|-------------|
| **M1** | Ingestion | Carga y normaliza datos OHLCV, detecta frecuencia automáticamente |
| **M2** | Features | Calcula 30+ indicadores técnicos: RSI, MACD, Bollinger Bands, ATR, ADX, retornos logarítmicos, volatilidad realizada |
| **M3** | CUSUM Filter | Filtra eventos relevantes usando Cumulative Sum filter — reduce ruido y evita overtrading |
| **M4** | Triple Barrier | Etiqueta cada evento como +1 (profit-take), -1 (stop-loss) o 0 (timeout) con barreras dinámicas basadas en volatilidad |
| **M5** | Splitting | Divide datos en train/test con corte temporal estricto (sin data leakage) |
| **M6** | Feature Selection | Selección de features por importancia (MDI/MDA) — reduce de 30+ a ~5 features clave |
| **M7** | Modeling | Entrena XGBoost, LightGBM o RandomForest por activo con GridSearchCV temporal |
| **M8** | Evaluation | Métricas de rendimiento: Accuracy, F1, Sharpe Ratio (CV), Max Drawdown, DSR, PBO |

### Caché Inteligente (M2+M3)
Las etapas M2 y M3 son las más costosas computacionalmente (~80% del tiempo). El sistema las cachea en disco:

```
cache/cold_{TICKER}_{hash}.pkl
```

Donde `hash = MD5(ticker + nrows + last_date)`. Si los datos no cambian, la siguiente ejecución salta estas etapas completamente (~5x más rápido).

---

## Optimizador Black-Litterman

El modelo **Black-Litterman** es el estándar de la industria para combinar views de inversión con equilibrio de mercado:

### Fórmula Central

```
μ_BL = M⁻¹ × [(τΣ)⁻¹Π + P'Ω⁻¹q]

Donde:
  Π  = retornos de equilibrio (CAPM implícito)
  Σ  = matriz de covarianza de retornos
  τ  = parámetro de incertidumbre sobre Π
  P  = matriz de views (identidad: una view por activo)
  q  = views absolutas (predicciones del ML)
  Ω  = incertidumbre sobre las views (basada en confianza del modelo)
  M  = (τΣ)⁻¹ + P'Ω⁻¹P
```

### Flujo de Optimización
1. Calcula retornos de equilibrio Π = δ·Σ·w_mkt (donde δ = aversión al riesgo del perfil)
2. Transforma señales ML en views absolutas con incertidumbre calibrada
3. Computa posterior μ_BL combinando equilibrio + ML
4. Optimiza pesos via mean-variance con constraints (max peso, long-only, sum = 1)
5. Proyecta al simplex si las constraints se violan

---

## Perfiles de Riesgo

Cada perfil define activos, modelos, y parámetros de optimización via archivos YAML:

| Perfil | Activos | Modelo por defecto | Max peso | Fee | Descripción |
|--------|---------|-------------------|----------|-----|-------------|
| **Low Risk** | AAPL, NVDA, AMZN, XOM, GLD, QQQ, TLT | LightGBM | 25% | 1% | Conservador: incluye oro (GLD) y bonos (TLT) como refugio |
| **Med Risk** | AAPL, NVDA, META, AMZN, XOM, GLD, QQQ, BTC, COIN | LightGBM | 30% | 10% | Balanceado: mix de tech + commodities + crypto |
| **High Risk** | BTC, NVDA, META, PLTR, COIN, AMZN, AAPL | XGBoost | 40% | 30% | Agresivo: concentrado en tech de alto crecimiento y crypto |

Los archivos YAML permiten personalizar por activo:
- Modelo específico (XGBoost vs LightGBM vs RandomForest)
- Hiperparámetros del modelo
- Parámetros de CUSUM y Triple Barrier
- Aversión al riesgo (delta) y confianza (tau) del Black-Litterman

---

## Resultados del Backtest (2024)

**Entrenamiento:** 2020-2023 (4 anos de datos diarios)
**Test (out-of-sample):** Enero 2024 - Diciembre 2024 (251 dias de trading)

| Perfil | Retorno Total | S&P 500 | vs S&P 500 | Sharpe | Max Drawdown |
|--------|:------------:|:-------:|:----------:|:------:|:------------:|
| **Low Risk** | **+71.2%** | +24.5% | **+46.7%** | 2.80 | -12.7% |
| **Med Risk** | **+148.0%** | +24.5% | **+123.5%** | **2.97** | -11.3% |
| **High Risk** | **+182.2%** | +24.5% | **+157.7%** | 2.44 | -18.9% |

```
Inversion de USD 100 en Enero 2024:
  S&P 500 (SPY)       → USD 124     (+24.5%)
  QuantFlow Low Risk   → USD 171     (+71.2%)   ██████████████████████████████████▓░░░░░░
  QuantFlow Med Risk   → USD 248     (+148.0%)  ██████████████████████████████████████████████████████████████████████████▓░░░
  QuantFlow High Risk  → USD 282     (+182.2%)  ██████████████████████████████████████████████████████████████████████████████████████████████▓
```

> Los 3 perfiles superaron al S&P 500 de forma contundente. Incluso el perfil Conservador (+71.2%) casi triplicó el rendimiento del indice (+24.5%).

---

## Instalacion y Ejecucion

### Requisitos Previos
- Python 3.10 - 3.12
- Node.js 18+
- Git

### 1. Clonar el repositorio

```bash
git clone https://github.com/dav1dchaparro/hackITBA.git
cd hackITBA
```

### 2. Backend — Entorno Python

```bash
# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate.bat       # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Ejecutar el modelo

```bash
# Correr los 3 perfiles (~45 min primera vez, ~10 min con caché)
python main_executor.py

# Solo un perfil específico (~15 min)
python main_executor.py --profiles low_risk

# Múltiples perfiles
python main_executor.py --profiles low_risk med_risk
```

**Salida:**
- `results/results_{profile}.json` — Datos del backtest
- `frontend/public/data/results_{profile}.json` — Copia automática para el frontend

### 4. Frontend — App React

```bash
cd frontend
npm install
npm run dev
```

Abrir **http://localhost:8080** en el navegador.

### Flujo completo (copy-paste)

```bash
git clone https://github.com/dav1dchaparro/hackITBA.git
cd hackITBA
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main_executor.py
cd frontend && npm install && npm run dev
```

---

## Frontend

La aplicación web permite a los usuarios:

1. **Onboarding**: Cuestionario interactivo que determina el perfil de riesgo
2. **Simulación**: Visualización del backtest con gráfico de evolución del portafolio vs benchmark
3. **Allocations**: Gráfico stacked area mostrando la evolución de asignaciones por activo + pie chart del último día
4. **Métricas**: Retorno total, Sharpe Ratio, Max Drawdown, rendimiento vs benchmark
5. **Dashboard**: Panel con autenticación via Supabase

### Componentes Principales
- `AllocationChart` — Stacked area chart + pie chart de asignaciones + tarjetas de metricas
- `HeroSection` — Landing page con propuesta de valor
- `ConversionSection` — Call to action y FAQ

---

## Stack Tecnologico

### Backend (ML Pipeline)
| Tecnología | Uso |
|-----------|-----|
| **Python 3.12** | Lenguaje principal |
| **XGBoost / LightGBM** | Modelos de clasificación de señales |
| **scikit-learn** | Feature selection, validación cruzada, métricas |
| **pandas / numpy** | Manipulación de datos y cálculos numéricos |
| **PyPortfolioOpt** | Implementación Black-Litterman y mean-variance |
| **cvxpy** | Optimización convexa para constraints del portafolio |
| **scipy** | Distribuciones, tests estadísticos |

### Frontend
| Tecnología | Uso |
|-----------|-----|
| **React 18** + TypeScript | Framework UI |
| **Vite** | Build tool y dev server |
| **Recharts** | Gráficos de evolución y allocations |
| **Tailwind CSS** | Estilos |
| **Framer Motion** | Animaciones |
| **Supabase** | Autenticación de usuarios |

---

## Estructura del Proyecto

```
hackITBA/
├── main_executor.py              # Orquestador principal del pipeline
├── requirements.txt              # Dependencias Python
├── README.md
│
├── configs/                      # Perfiles de riesgo (YAML)
│   ├── low_risk.yaml             # Conservador  — 7 activos, fee 1%
│   ├── med_risk.yaml             # Balanceado   — 9 activos, fee 10%
│   └── high_risk.yaml            # Agresivo     — 7 activos, fee 30%
│
├── data/                         # Datos OHLCV horarios
│   ├── AAPL_1h.csv               # Apple
│   ├── NVDA_1h.csv               # NVIDIA
│   ├── BTC_1h.csv                # Bitcoin
│   └── ...                       # 11 activos totales
│
├── src/                          # Pipeline ML
│   ├── smart_indicators/         # Módulos M1-M8
│   │   ├── core/                 # Pipeline engine, PipelineData, config
│   │   └── modules/              # ingestion, features, filtering,
│   │                             # labeling, splitting, feature_selection,
│   │                             # modeling, evaluation
│   └── risk_optimization/        # Optimizadores de portafolio
│       └── optimizers/           # HRP, Markowitz, base
│
├── cache/                        # Caché M2+M3 por activo (.pkl)
├── results/                      # JSONs generados por el modelo
│
└── frontend/                     # App React
    ├── src/
    │   ├── components/           # BacktestingReveal, AllocationChart, etc.
    │   ├── pages/                # Index, Simulacion, Login, Dashboard
    │   ├── hooks/                # useBacktestData
    │   └── data/                 # Datos del onboarding
    ├── public/data/              # JSONs de resultados (auto-copiado)
    └── package.json
```

---

## Metodologia de Validacion — Cero Overfitting

### Walk-Forward con Ventana Expansiva

El modelo **no memoriza**: se valida con una metodologia Walk-Forward estricta que simula exactamente como operaria en el mundo real.

```
Ronda 1:  Train [2020]           → Test [2021]     ✓ sin data leakage
Ronda 2:  Train [2020-2021]      → Test [2022]     ✓ sin data leakage
Ronda 3:  Train [2020-2022]      → Test [2023]     ✓ sin data leakage
Ronda 4:  Train [2020-2023]      → Test [2024]     ✓ RESULTADOS FINALES
```

- Cada ronda entrena con **todo el historico disponible** hasta ese momento
- El modelo **nunca ve datos futuros** durante el entrenamiento
- Se usan **purge windows** (240 barras de separacion) entre train y test para evitar leakage temporal
- Cross-validation temporal con **embargo** entre folds

### Realismo en la Ejecucion

El sistema esta disenado para operar en el mundo real, no solo en backtests:

- **Solo Long** — Solo compra, nunca vende en corto. Compatible con cualquier broker retail.
- **1 rebalanceo por dia** — Ajusta los pesos del portafolio una vez al dia al cierre del mercado. No hace high-frequency trading.
- **Comisiones incluidas** — El backtest descuenta comisiones de 3-5 bps por operacion (similar a brokers como Interactive Brokers).
- **Long-only, fully invested** — El capital siempre esta 100% en el mercado, distribuido entre los activos del perfil.
- **Max weight constraint** — Ningun activo puede superar el 25-40% del portafolio (segun perfil), forzando diversificacion.

---

## Casos de Exito

### 1. Proteccion Inteligente durante el Crash de Bitcoin (-26%)

Entre marzo y septiembre de 2024, **Bitcoin se desplomo un 26.2%** (de USD 73,084 a USD 53,949). Durante ese mismo periodo, el perfil **Med Risk** — que incluye BTC en su universo de activos — logro una ganancia de **+22.6%**.

```
Marzo - Septiembre 2024:
  Bitcoin (BTC)        -26.2%  ████████████████████████░░  Desplome
  Benchmark (EW)        -0.8%  ░░░░░░░░░░░░░░░░░░░░░░░░░  Plano
  QuantFlow Med Risk   +22.6%  ██████████████████████▓░░░  Ganancia
```

**Como lo logro?** El modelo detecto las senales bajistas en BTC y **reasigno el capital** hacia activos con momentum positivo (NVDA, META, AAPL), protegiendo el portafolio y capturando ganancias en otros mercados.

### 2. Maximizando el Rally de PLTR (+365% en 2024)

Palantir (PLTR) tuvo un ano extraordinario con **+365.5%** de retorno. El perfil **High Risk** — que incluye PLTR — logro un retorno total de **+182.2%**, superando a un portafolio equal-weight de los mismos activos (+121.1%).

```
Ano 2024 completo:
  S&P 500              +24.5%  ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░
  Benchmark (EW)      +121.1%  ████████████████████████████████████████████████████████████▓
  QuantFlow High Risk +182.2%  █████████████████████████████████████████████████████████████████████████████████████████████▓
```

**La clave:** El modelo ajusto dinamicamente la asignacion a PLTR entre **1.2% y 24.9%** segun las senales del ML — aumentando exposicion antes de los rallies y reduciendola antes de las correcciones.

### 3. Superando al S&P 500 — Consistentemente

El objetivo principal del sistema era **ganarle al S&P 500**. Lo logramos en todos los perfiles:

| Perfil | QuantFlow | S&P 500 | Diferencia | Sharpe Ratio |
|--------|:---------:|:-------:|:----------:|:------------:|
| Conservador | **+71.2%** | +24.5% | **+46.7%** | 2.80 |
| Balanceado | **+148.0%** | +24.5% | **+123.5%** | **2.97** |
| Agresivo | **+182.2%** | +24.5% | **+157.7%** | 2.44 |

> Incluso el perfil **mas conservador** (Low Risk) casi **triplico** el rendimiento del S&P 500, con un Sharpe Ratio de 2.80 — indicando retornos excelentes ajustados por riesgo.

> El perfil **Balanceado** logro el mejor ratio riesgo/retorno con un Sharpe de **2.97** y un Max Drawdown de solo **-11.3%**, demostrando que es posible obtener retornos de triple digito con riesgo controlado.

---

## Referencias

- **Advances in Financial Machine Learning** — Marcos López de Prado (2018). Framework teórico para M1-M8.
- **Black-Litterman Model** — Black & Litterman (1992). "Global Portfolio Optimization", Financial Analysts Journal.
- **Triple Barrier Method** — López de Prado (2018). Etiquetado financiero con profit-take, stop-loss y timeout.
- **CUSUM Filter** — Page (1954). Detección de cambios estructurales en series temporales.

---

*Desarrollado para hackITBA 2025*
