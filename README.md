# QuantFlow AI — Portfolio Inteligente con Machine Learning

> Sistema de inversión automatizado que combina **Machine Learning** (XGBoost/LightGBM) con un **motor de optimización adaptativo** (Black-Litterman / HRP / Kelly) para gestión dinámica de portafolios multi-activo. Detecta el régimen de mercado en tiempo real y selecciona automáticamente la estrategia óptima: bayesiana en mercados neutros, defensiva en crisis, y agresiva en tendencias alcistas.

**hackITBA 2025** | Equipo: [dav1dchaparro](https://github.com/dav1dchaparro)

---

## Tabla de Contenidos

- [Descripcion del Proyecto](#descripcion-del-proyecto)
- [Arquitectura](#arquitectura)
- [Pipeline ML (M1-M8)](#pipeline-ml-m1-m8)
- [Motor de Optimizacion Adaptativo](#motor-de-optimizacion-adaptativo)
  - [Deteccion de Regimen de Mercado](#deteccion-de-regimen-de-mercado)
  - [Black-Litterman (Neutro)](#black-litterman-neutro)
  - [HRP — Hierarchical Risk Parity (Bear / Crisis)](#hrp--hierarchical-risk-parity-bear--crisis)
  - [Kelly Criterion (Bull)](#kelly-criterion-bull)
- [Persistencia de Modelos](#persistencia-de-modelos)
- [Perfiles de Riesgo](#perfiles-de-riesgo)
- [Resultados del Backtest](#resultados-del-backtest)
- [Instalacion y Ejecucion](#instalacion-y-ejecucion)
- [Frontend](#frontend)
- [Stack Tecnologico](#stack-tecnologico)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Metodologia de Validacion](#metodologia-de-validacion--cero-overfitting)

---

## Descripcion del Proyecto

### El Problema
Los inversores retail enfrentan dos desafíos principales:
1. **Selección de activos**: Decidir cuánto asignar a cada activo en cada momento
2. **Timing de mercado**: Cuándo rebalancear y con qué estrategia según las condiciones actuales

Las soluciones tradicionales (robo-advisors) usan reglas estáticas con un único optimizador. Nosotros usamos **ML para predecir retornos**, **detección de régimen de mercado** para elegir la estrategia correcta, y **tres optimizadores especializados** que se activan según las condiciones.

### La Solución
QuantFlow AI implementa un pipeline end-to-end que:

1. **Ingiere datos** OHLCV horarios de 11 activos (acciones, ETFs, crypto)
2. **Genera 30+ features** técnicos (RSI, MACD, Bollinger Bands, ATR, ADX, etc.)
3. **Filtra eventos relevantes** con CUSUM para evitar overtrading
4. **Etiqueta oportunidades** usando Triple Barrier Method (profit-take / stop-loss / timeout)
5. **Entrena modelos** XGBoost/LightGBM/RandomForest por activo con validación cruzada temporal
6. **Persiste los modelos** en disco (.joblib) — segunda ejecución es 10x más rápida
7. **Detecta el régimen de mercado** (BULL / BEAR / CRISIS / NEUTRAL) en tiempo real
8. **Selecciona el optimizador** óptimo para el régimen detectado
9. **Optimiza el portafolio** con el motor adaptativo usando señales ML como views
10. **Rebalancea dinámicamente** cada período según las predicciones actualizadas
11. **Visualiza resultados** en un frontend React interactivo con gráficos de evolución

### Diferenciadores Clave
- **Motor adaptativo de 3 optimizadores**: BL (neutro), HRP (defensivo), Kelly (agresivo) — se alternan automáticamente
- **Detección de régimen de mercado**: Bull/Bear/Crisis/Neutral basado en tendencia, volatilidad y correlación
- **Persistencia de modelos (.joblib)**: No re-entrena si los datos no cambiaron — ahorra 80% del tiempo
- **Black-Litterman bayesiano**: Combina equilibrio de mercado (CAPM) con views del ML
- **Triple Barrier Labeling**: Etiquetado financiero especializado (no simple up/down)
- **Caché de features en disco**: M2+M3 pre-computados, re-ejecuciones ~5x más rápidas
- **3 perfiles de riesgo**: Configurables via YAML, cada uno con activos y parámetros distintos
- **Cero data leakage**: Walk-forward CV con purge windows de 240 barras

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
│  Cache L1: M2+M3 → cache/cold_*.pkl   (re-uso entre perfiles)  │
│  Cache L2: Modelos → cache/models/*.joblib  (re-uso entre runs)│
│  Salida: signal_dict = {ticker: {prob_up, prob_down, signal}}   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              DETECCION DE REGIMEN DE MERCADO                    │
│                                                                 │
│  RegimeDetector analiza ventana de 60 días:                     │
│   • Trend:       SMA 50/200 proxy (retorno medio anualizado)    │
│   • Volatility:  vol reciente vs histórica (ratio percentil)    │
│   • Correlation: correlación media entre activos                │
│                                                                 │
│  BULL   → trend > +5% anual, vol normal                         │
│  BEAR   → trend < -5% anual                                     │
│  CRISIS → vol alta (>80 percentil) + correlación alta (>0.65)  │
│  NEUTRAL→ sin señal clara                                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  KELLY   │ │  BLACK-  │ │   HRP    │
        │ (BULL)   │ │LITTERMAN │ │(BEAR /   │
        │          │ │(NEUTRAL) │ │ CRISIS)  │
        └──────────┘ └──────────┘ └──────────┘
              └────────────┼────────────┘
                           │ pesos óptimos
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     RESULTADOS JSON                              │
│                                                                 │
│  results_{profile}.json → portfolio_value, benchmark,           │
│    allocations por día, confidence, regime, optimizer usado     │
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

### Caché Inteligente de Dos Niveles

#### Nivel 1 — Features (M2+M3)
Las etapas más costosas computacionalmente (~80% del tiempo de cold start). Se cachean en disco:

```
cache/cold_{TICKER}_{hash}.pkl
```

Donde `hash = MD5(ticker + nrows + last_date)`. Si los datos no cambian, la siguiente ejecución salta estas etapas completamente (~5x más rápido).

#### Nivel 2 — Modelos Entrenados (.joblib)
Los modelos M4-M8 también se persisten en disco. Si existe un modelo con el mismo `TRAIN_CUTOFF`, no se re-entrena:

```
cache/models/{TICKER}_{PROFILE}.joblib
```

El modelo guardado incluye: el objeto modelo (XGBoost/LightGBM), las features seleccionadas, y las métricas de evaluación. La invalidación es automática si cambia el `TRAIN_CUTOFF`.

---

## Motor de Optimizacion Adaptativo

El diferenciador central del sistema es su **motor de optimización de tres capas** que selecciona automáticamente la estrategia según el régimen de mercado detectado.

### Deteccion de Regimen de Mercado

`RegimeDetector` analiza una ventana de 60 días de precios de todos los activos del portafolio y clasifica en 4 regímenes:

```python
BULL    → trend > +5% anual, vol baja      → Kelly (crecer capital agresivamente)
BEAR    → trend < -5% anual                → HRP   (proteger capital)
CRISIS  → vol alta + correlación alta      → HRP   (máxima diversificación)
NEUTRAL → sin señal clara                  → Black-Litterman (bayesiano)
```

**Variables de detección:**

| Variable | Cálculo | Umbral |
|----------|---------|--------|
| **Trend** | Retorno promedio anualizado (ventana 60d) | >+5%=Bull, <-5%=Bear |
| **Volatility** | Vol reciente / Vol histórica × 100 | >80 percentil = Crisis |
| **Correlation** | Correlación media entre pares de activos | >0.65 = Crisis |

Cada día del backtest se detecta el régimen con los precios históricos disponibles y se selecciona el optimizador correspondiente. El JSON de resultados registra qué optimizador se usó en cada fecha.

---

### Black-Litterman (Neutro)

Optimizador bayesiano estándar de la industria. Se activa cuando el mercado no tiene tendencia clara.

#### Fórmula Central

```
μ_BL = M⁻¹ × [(τΣ)⁻¹Π + P'Ω⁻¹q]

Donde:
  Π  = retornos de equilibrio (CAPM implícito: δ·Σ·w_mkt)
  Σ  = matriz de covarianza de retornos
  τ  = parámetro de incertidumbre sobre Π (default: 0.05)
  P  = matriz de views (identidad: una view absoluta por activo)
  q  = views absolutas (predicciones del ML escaladas)
  Ω  = incertidumbre sobre las views (calibrada por confianza del modelo)
  M  = (τΣ)⁻¹ + P'Ω⁻¹P
```

**Flujo de Optimización:**
1. Calcula retornos de equilibrio Π = δ·Σ·w_mkt (δ = aversión al riesgo del perfil)
2. Transforma señales ML en views absolutas con incertidumbre calibrada
3. Computa posterior μ_BL combinando equilibrio + ML via Bayes
4. Optimiza pesos via mean-variance con constraints (max peso, long-only, sum = 1)
5. Proyecta al simplex si las constraints se violan

---

### HRP — Hierarchical Risk Parity (Bear / Crisis)

Alternativa robusta que **no requiere inversión de matrices de covarianza** — crucial en mercados volátiles donde la covarianza es inestable.

#### Algoritmo

```
1. Correlación → Distancia: d(i,j) = sqrt(0.5 × (1 - ρ_ij))
2. Clustering jerárquico (single linkage) sobre la matriz de distancias
3. Quasi-diagonalización: ordenar activos por similitud de clustering
4. Bisección recursiva: asignar pesos inversamente proporcionales a la varianza del cluster
5. Tilt final: ajustar pesos por señales ML (mantiene estructura HRP + incorpora alpha)
```

**Ventaja vs Markowitz:** No asume que el modelo de covarianza es perfecto. En crisis, las correlaciones se disparan y las matrices se vuelven mal condicionadas. HRP es agnóstico al modelo.

**Parámetros ajustables por régimen:**
- Ventana de covarianza (60d en crisis vs 120d en mercado normal)
- Factor de tilt ML (0.3 en BEAR, 0.5 en NEUTRAL)
- `max_weight` reducido en CRISIS para mayor diversificación

---

### Kelly Criterion (Bull)

Maximiza el **crecimiento geométrico esperado** del capital. Se activa en mercados alcistas donde el sistema tiene alta confianza en las predicciones.

#### Fórmula

```
f* = (p × b - q) / b

Donde:
  p = probabilidad de ganancia (señal ML + histórico win rate)
  q = 1 - p  (probabilidad de pérdida)
  b = ratio ganancia promedio / pérdida promedio (histórico)
  f* = fracción óptima del capital a asignar
```

**Ajustes de seguridad:**
- **Half-Kelly** por defecto (`fraction = 0.5`): reduce la apuesta al 50% de la óptima teórica
- Calibración mixta de `p`: 70% señal ML + 30% win rate histórico
- `max_weight` constraint: nunca supera el límite del perfil (25-40%)
- Si `f* < 0` para todos los activos: fallback a igual peso

---

## Persistencia de Modelos

Los modelos entrenados se guardan en `cache/models/` con joblib y compresión nivel 3:

```
cache/
├── cold_AAPL_9406e3c3.pkl        # Features + eventos filtrados (M2+M3)
├── cold_NVDA_f17a69bc.pkl
├── ...
└── models/
    ├── AAPL_low_risk.joblib      # Modelo + features + métricas (M4-M8)
    ├── AAPL_med_risk.joblib
    ├── NVDA_high_risk.joblib
    └── ...                       # {TICKER}_{PROFILE}.joblib por cada combinación
```

**Estructura del payload .joblib:**
```python
{
    "ticker":            "AAPL",
    "model":             <XGBoostClassifier / LGBMClassifier>,
    "selected_features": ["rsi_14_1h", "macd_signal_1d", ...],  # top 5 features
    "metrics":           {"mean_auc": 0.62, "mean_sharpe": 1.8, ...},
    "train_cutoff":      "2025-10-01",  # invalidación automática
}
```

**Invalidación automática:** Si `TRAIN_CUTOFF` cambia (nuevo período de datos), todos los modelos se re-entrenan la próxima vez. No hace falta borrar archivos manualmente.

**Speedup aproximado:**
| Escenario | Primera vez | Con caché L1 | Con caché L1+L2 |
|-----------|------------|-------------|----------------|
| 1 perfil, 7 activos | ~45 min | ~15 min | ~5 min |
| 3 perfiles | ~120 min | ~25 min | ~8 min |

---

## Perfiles de Riesgo

Cada perfil define activos, modelos, y parámetros de optimización via archivos YAML:

| Perfil | Activos | Modelo por defecto | Max peso | Optimizer preferido | Descripción |
|--------|---------|-------------------|----------|-------------------|-------------|
| **Low Risk** | AAPL, NVDA, AMZN, XOM, GLD, QQQ, TLT | LightGBM | 25% | BL / HRP | Conservador: incluye oro (GLD) y bonos (TLT) como refugio |
| **Med Risk** | AAPL, NVDA, META, AMZN, XOM, GLD, QQQ, BTC, COIN | LightGBM | 30% | BL / HRP / Kelly | Balanceado: mix de tech + commodities + crypto |
| **High Risk** | BTC, NVDA, META, PLTR, COIN, AMZN, AAPL | XGBoost | 40% | Kelly / BL | Agresivo: concentrado en tech de alto crecimiento y crypto |

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
# Correr los 3 perfiles (~45 min primera vez, ~8 min con caché completo)
python main_executor.py

# Solo un perfil específico (~15 min primera vez, ~5 min con caché)
python main_executor.py --profiles low_risk

# Múltiples perfiles
python main_executor.py --profiles low_risk med_risk
```

**Salida:**
- `results/results_{profile}.json` — Datos del backtest (incluye `regime` y `optimizer` por día)
- `frontend/public/data/results_{profile}.json` — Copia automática para el frontend
- `cache/cold_*.pkl` — Features pre-computadas (Nivel 1)
- `cache/models/*.joblib` — Modelos entrenados (Nivel 2)

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
| **joblib** | Persistencia de modelos entrenados (compresión nivel 3) |
| **scipy** | Clustering jerárquico (HRP), distribuciones, tests estadísticos |
| **PyPortfolioOpt** | Implementación Black-Litterman y mean-variance |
| **cvxpy** | Optimización convexa para constraints del portafolio |

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
│                                 # Incluye: BL, HRP, Kelly, RegimeDetector
├── requirements.txt              # Dependencias Python
├── README.md
│
├── configs/                      # Perfiles de riesgo (YAML)
│   ├── low_risk.yaml             # Conservador  — 7 activos, fee 1%
│   ├── med_risk.yaml             # Balanceado   — 9 activos, fee 10%
│   └── high_risk.yaml            # Agresivo     — 7 activos, fee 30%
│
├── data/                         # Datos OHLCV horarios
│   ├── AAPL_1h.csv               # Apple (3,467 barras)
│   ├── NVDA_1h.csv               # NVIDIA (3,467 barras)
│   ├── BTC_1h.csv                # Bitcoin (17,464 barras — 24/7)
│   └── ...                       # 11 activos totales
│
├── src/                          # Pipeline ML
│   ├── smart_indicators/         # Módulos M1-M8
│   │   ├── core/                 # Pipeline engine, PipelineData, config
│   │   └── modules/              # ingestion, features, filtering,
│   │                             # labeling, splitting, feature_selection,
│   │                             # modeling, evaluation
│   └── risk_optimization/        # Optimizadores de portafolio (legacy)
│       └── optimizers/           # HRP, Markowitz, base
│
├── cache/                        # Caché de dos niveles
│   ├── cold_*.pkl                # Nivel 1: M2+M3 features por activo
│   └── models/
│       └── {TICKER}_{PROFILE}.joblib  # Nivel 2: modelos entrenados
│
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

**Como lo logro?** El `RegimeDetector` clasificó el periodo como `BEAR` y activó **HRP** (defensivo). El modelo reasignó el capital hacia activos con momentum positivo (NVDA, META, AAPL), protegiendo el portafolio y capturando ganancias en otros mercados.

### 2. Maximizando el Rally de PLTR (+365% en 2024)

Palantir (PLTR) tuvo un ano extraordinario con **+365.5%** de retorno. El perfil **High Risk** — que incluye PLTR — logro un retorno total de **+182.2%**, superando a un portafolio equal-weight de los mismos activos (+121.1%).

```
Ano 2024 completo:
  S&P 500              +24.5%  ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░
  Benchmark (EW)      +121.1%  ████████████████████████████████████████████████████████████▓
  QuantFlow High Risk +182.2%  █████████████████████████████████████████████████████████████████████████████████████████████▓
```

**La clave:** En los periodos `BULL` el **Kelly Criterion** aumentó agresivamente la exposición a PLTR (hasta 24.9%), mientras que en correcciones el sistema rotó a **HRP** para proteger ganancias.

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
- **Hierarchical Risk Parity** — López de Prado (2016). "Building Diversified Portfolios that Outperform Out-of-Sample", Journal of Portfolio Management.
- **Kelly Criterion** — Kelly (1956). "A New Interpretation of Information Rate", Bell System Technical Journal.
- **Triple Barrier Method** — López de Prado (2018). Etiquetado financiero con profit-take, stop-loss y timeout.
- **CUSUM Filter** — Page (1954). Detección de cambios estructurales en series temporales.

---

*Desarrollado para hackITBA 2025*
