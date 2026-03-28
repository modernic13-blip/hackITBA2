# Smart Indicators Pipeline — Architecture

## 🎯 Overview

Sistema de ML end-to-end para generación de señales de trading en portafolios multi-activo. Entrena modelos con datos históricos 2021-2024, testea en 2025, y listo para operar en vivo en 2026.

```
Raw Data (CSV/yfinance)
    ↓
[M1] Ingestion → Clean, normalize, time bars
    ↓
[M2] Features → 200+ technical indicators (multi-timeframe)
    ↓
[M3] Filtering → CUSUM event detection
    ↓
[M4] Labeling → Triple Barrier Method (PT/SL/vertical)
    ↓
[M5] Splitting → Walk-forward temporal CV (no leakage)
    ↓
[M6] Feature Selection → Greedy forward selection
    ↓
[M7] Modeling → XGBoost, LightGBM, CatBoost, RandomForest
    ↓
[M8] Evaluation → AUC, Sharpe, MaxDD, DSR, PBO
    ↓
Trading Signals & Portfolio Weights
```

---

## 📦 Module Structure

```
src/smart_indicators/
├── __init__.py                      # Exports: SignalPipeline, SignalPredictor
├── core/                            # Infrastructure
│   ├── base_module.py               # StageBase — abstract pipeline stage
│   ├── pipeline_data.py             # PipelineData — data container (replaces DataContainer)
│   ├── config_loader.py             # load_config() — YAML validation
│   ├── pipeline.py                  # SignalPipeline — orchestrator
│   └── predictor.py                 # SignalPredictor — inference wrapper
│
├── modules/                         # 8 Processing Stages
│   ├── ingestion.py        [M1]     # Load CSV, normalize OHLCV
│   ├── features.py         [M2]     # Generate 200+ features
│   ├── filtering.py        [M3]     # CUSUM/Kalman event detection
│   ├── labeling.py         [M4]     # Triple barrier labeling
│   ├── splitting.py        [M5]     # Walk-forward temporal split
│   ├── feature_selection.py [M6]    # Forward selection
│   ├── modeling.py         [M7]     # Train classifiers
│   ├── evaluation.py       [M8]     # Metrics + overfitting analysis
│   └── utils.py                     # Shared utilities
│
└── config/
    └── base_config.yaml             # Master config template
```

---

## 🔄 Pipeline Execution Flow

### 1️⃣ **Ingestion (M1)**
```
CSV → Normalize columns → Remove gaps (ffill) → raw_data
```
- **Input**: CSV file path or yfinance ticker
- **Output**: `raw_data` (DataFrame con OHLCV estandarizado)
- **Config keys**: `filepath`, `frequency`, `column_map`
- ✅ **Solo time bars** (sin dollar bars)

### 2️⃣ **Features (M2)**
```
raw_data → [15min, 1h, 4h, 12h, 1d] → 200+ indicadores → features
```
**Indicadores técnicos** (por timeframe):
- Momentum: RSI, MACD, CCI, Williams %R
- Volatilidad: Bollinger Bands, SuperTrend, ATR
- Volumen: VWAP, CMF, MFI, OBV
- Tendencia: ADX
- Microestructura: OFI, TRANS_RATE, TICK_AUTOCORR

**Features de mercado** (si existen):
- Premium, Funding rate, Long/Short ratio, CVD, Taker volume

- **Output**: `features` (1224 líneas, todas las funciones)
- **Normalizaciones**: Z-score, quantiles, EMA, detrending
- **Multi-timeframe**: Interleaved slicing (sin data loss)

### 3️⃣ **Filtering (M3)**
```
features → Detect significant price/OI moves → tEvents
```
**Métodos**:
- **CUSUM** (Cumulative Sum Control Chart): Acumula desviaciones, dispara cuando excede threshold
- **Kalman Filter**: Detecta desvíos de tendencia suavizada

- **Output**: `tEvents` (DatetimeIndex de eventos)
- **Config**: `method`, `filter_timeframe`, `k_Px`, `k_OI`
- **Densidad típica**: 5-20% de barras son eventos

### 4️⃣ **Labeling (M4)**
```
tEvents + close → Triple Barrier → labels {-1, 1}
```
**Triple Barrier Method**:
1. **PT (Profit Target)**: `volatility × ptSl[0]`
2. **SL (Stop Loss)**: `volatility × ptSl[1]`
3. **Vertical (Time)**: `timeframe × vertical_mult` barras

- **Volatilidad**: EWM de retornos absolutos (span = `trgt_length`)
- **Filtrado**: Solo eventos con `volatility ≥ minRet`

- **Output**: `labels` {-1, 1}, `ret_at_cross`, `barrier_touched`

### 5️⃣ **Splitting (M5)**
```
labeled_data → Walk-forward CV (no leakage) → splits
```
**Walk-Forward** (no acumulativo):
- Divide datos en N segmentos iguales
- Genera N-1 rondas: train=[seg_i] test=[seg_i+1]

**Purging & Embargo** (prevenir leakage):
- **Purging**: Elimina del train eventos cuya barrera se resuelve en test
- **Embargo**: Descarta % inicial del test set

- **Output**: `splits` (lista de dicts con train_idx, test_idx)

### 6️⃣ **Feature Selection (M6)**
```
features → Forward selection → selected_features
```
**2 fases**:
1. **Ranking**: Evalúa AUC individual de cada feature
2. **Forward Selection**: Greedy → agrega features que mejoren AUC

- **Evaluador**: RandomForest ligero (n_estimators=50, max_depth=5)
- **Criterio parada**: Mejora mínima de AUC = `criterio_parada` (default 0.005)
- **Output**: `selected_features` (2 equipos por defecto)

### 7️⃣ **Modeling (M7)**
```
selected_features + labels → Grid search → trained models
```
**Clasificadores disponibles**:
- RandomForest, GradientBoosting, LogisticRegression
- XGBoost, LightGBM, CatBoost, AdaBoost, DecisionTree, KNN, NaiveBayes

**Grid Search**: Cada modelo × equipo × split
- Evaluación sobre los splits del walk-forward
- Sin data leakage temporal

- **Output**: `model_predictions`, `model_scores`, `best_model_obj`

### 8️⃣ **Evaluation (M8)**
```
model_predictions → Métricas financieras + overfitting analysis
```
**Métricas**:
- **AUC-ROC**: Capacidad de separar clases (0.5=random, 1=perfecto)
- **Precision/Recall**: Exactitud del modelo
- **Sharpe**: Retorno / Volatilidad (riesgo-retorno)
- **Max Drawdown**: Peor caída acumulada

**Overfitting Analysis**:
- **DSR** (Deflated Sharpe Ratio): Ajusta Sharpe por multiple testing
- **PBO** (Probability of Backtest Overfitting): López de Prado 2018

- **Sin MLFlow** (todos los cálculos locales)

---

## 🎛️ Configuration System

**Config keys** (inglés):
```yaml
asset: "BTC"                    # Ticker
period: ["2021-01-01", "2024-12-31"]
frequency: "1min"              # Frecuencia de datos
timeframes: ["15min", "1h", "4h", "12h", "1d"]  # Para features

ingestion:
  filepath: "data/BTC.csv"
  frequency: "1min"

features:
  use_subset: false
  norm_window: 1000

filtering:
  method: "cusum"
  filter_timeframe: "1h"
  k_Px: 0.5

labeling:
  method: "triple_barrier"
  ptSl: [1, 1]
  minRet: 0.001

splitting:
  n_splits: 5
  embargo_pct: 0.01

feature_selection:
  modelo_evaluador: "RandomForest"
  criterio_parada: 0.005
  n_equipos: 2

modeling:
  modelos:
    - name: RandomForest
      params: {class_weight: balanced}
      grid_search:
        n_estimators: [100, 300, 500]
        max_depth: [5, 10, 20, null]

evaluation:
  metricas: ["auc_roc", "precision", "recall", "sharpe", "max_drawdown"]
  threshold: 0.5
```

---

## 💾 Core Classes

### **PipelineData** (contenedor de datos)
```python
data = PipelineData()
data.set("close", serie_precios, source_module="ingestion")
close = data.get("close", required=True)
data.delete("close")  # Liberar memoria
data.keys()  # ['close', 'volume', ...]
data.summary()  # Info sobre cada entrada
data.save("checkpoint.pkl")
data = PipelineData.load("checkpoint.pkl")
```

### **StageBase** (clase abstracta para cada módulo)
```python
class MyStage(StageBase):
    name = "my_stage"
    requires = {
        "data": {"close": {"required": True}},
        "params": {"k": {"type": "float", "default": 0.5}}
    }
    produces = {"output": "..."}

    def run(self, data: PipelineData) -> PipelineData:
        # Tu lógica aquí
        data.set("output", result)
        return data
```

### **SignalPipeline** (orquestador)
```python
pipeline = SignalPipeline.from_yaml("config/base_config.yaml")
data, success = pipeline.run_modules([1, 2, 3, 4, 5, 6, 7, 8], data)
pipeline.save_run("runs/")  # Guarda JSON con config + traces

# Auto-search de hiperparámetros
data, results, ok = pipeline.auto_search_m3(data, checkpoint_path="...")
data, results, ok = pipeline.auto_search_m4(data)
```

### **SignalPredictor** (inferencia en vivo)
```python
data = PipelineData.load("checkpoint.pkl")
predictor = SignalPredictor(data, config)
predictions = predictor.predict_bar_by_bar(new_ohlcv)
predictor.update_context(new_ohlcv)  # Actualizar histórico
```

---

## 🔑 Key Features

### ✅ Sin Dollar Bars
- Solo time bars (CSV regular)
- Más simple, determinístico, reproducible

### ✅ Sin AWS/S3
- Solo datos locales (CSV)
- O yfinance para descargar históricos
- Checkpoints en disk local

### ✅ Sin MLFlow
- Todas las métricas calculadas localmente
- JSON de run record para reproducibilidad
- DSR y PBO integrados (sin dependencias externas)

### ✅ 8 Módulos Independientes
- Cada uno es un StageBase
- Pueden reordenarse o saltarse (checkpoint resume)
- Validación automática de inputs

### ✅ Walk-Forward Temporal
- Purging: evita entrenar en datos que "miraron al futuro"
- Embargo: separa train de test
- Sin data leakage

### ✅ Multi-Model Comparison
- Entrena 10+ clasificadores en paralelo
- Grid search en cada modelo
- Selecciona el mejor por AUC

---

## 📊 User Journey

1. **Preparar datos**: CSV con OHLCV (2021-2024)
2. **Configurar YAML**: Editar `base_config.yaml`
3. **Ejecutar pipeline**:
   ```python
   from smart_indicators import SignalPipeline
   pipeline = SignalPipeline.from_yaml("config.yaml")
   data = PipelineData()
   data, ok = pipeline.run_modules([1,2,3,4,5,6,7,8], data)
   ```
4. **Backtesting 2025**: Usar `best_model_obj` sobre 2025
5. **Live trading 2026**: `SignalPredictor` genera señales diarias

---

## 🛠️ What's Different from Original

| Aspecto | Original (Pluszero) | New (hackITBA) |
|---------|-------------------|-----------------|
| Dollar Bars | ✅ Soportadas | ❌ Removidas |
| AWS/S3 | ✅ Full support | ❌ Removido |
| MLFlow | ✅ Integrado | ❌ Removido |
| Config keys | Spanish (ingesta, frecuencia, activo) | English (ingestion, frequency, asset) |
| Class names | BaseModule, DataContainer, SmartIndicatorsPipeline | StageBase, PipelineData, SignalPipeline |
| Comments | Spanish | English |
| Líneas de código | ~5000 | ~3000 (sin S3, sin MLFlow, sin dollar bars) |

---

## 📈 8 Modules at a Glance

| Módulo | Entrada | Salida | Clave |
|--------|---------|--------|-------|
| **M1 Ingestion** | CSV | raw_data | Normalizar OHLCV |
| **M2 Features** | raw_data | features (200+) | Multi-timeframe indicators |
| **M3 Filtering** | features | tEvents | Detectar eventos significativos |
| **M4 Labeling** | tEvents + close | labels {-1,1} | Triple barrier (PT/SL/vertical) |
| **M5 Splitting** | labels | splits | Walk-forward CV sin leakage |
| **M6 Selection** | features + splits | selected_features | Forward selection greedy |
| **M7 Modeling** | features + splits | best_model_obj | Grid search multi-modelo |
| **M8 Evaluation** | predictions | metrics + overfitting | AUC, Sharpe, DSR, PBO |

---

## 🚀 Next Steps for Your Team

1. **Entienden el flujo**: Datos → Features → Eventos → Labels → Split → Select → Train → Eval
2. **Saben qué cambiar**: Cada módulo es independiente, pueden tunearse parámetros por separado
3. **Saben ejecutar**: `SignalPipeline.from_yaml()` + `run_modules()`
4. **Saben debuggear**: Checkpoints intermedios, traces con duración y errores

---

Hecho con ❤️ para el hackathon
