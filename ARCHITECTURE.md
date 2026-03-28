# Pipeline de Indicadores Inteligentes — Arquitectura

## 🎯 Descripción General

Sistema de ML end-to-end para generación de señales de trading en portafolios multi-activo. Entrena modelos con datos históricos 2021-2024, testea en 2025, y listo para operar en vivo en 2026.

```
Datos en Bruto (CSV/yfinance)
    ↓
[M1] Ingesta → Limpiar, normalizar, barras temporales
    ↓
[M2] Características → 200+ indicadores técnicos (multi-timeframe)
    ↓
[M3] Filtrado → Detección de eventos CUSUM
    ↓
[M4] Etiquetado → Método de Triple Barrera (PT/SL/vertical)
    ↓
[M5] Partición → CV temporal walk-forward (sin fuga)
    ↓
[M6] Selección de Características → Selección greedy hacia adelante
    ↓
[M7] Modelado → XGBoost, LightGBM, CatBoost, RandomForest
    ↓
[M8] Evaluación → AUC, Sharpe, MaxDD, DSR, PBO
    ↓
Señales de Trading y Pesos del Portafolio
```

---

## 📦 Estructura de Módulos

```
src/smart_indicators/
├── __init__.py                      # Exporta: SignalPipeline, SignalPredictor
├── core/                            # Infraestructura
│   ├── base_module.py               # StageBase — etapa abstracta del pipeline
│   ├── pipeline_data.py             # PipelineData — contenedor de datos (reemplaza DataContainer)
│   ├── config_loader.py             # load_config() — validación YAML
│   ├── pipeline.py                  # SignalPipeline — orquestador
│   └── predictor.py                 # SignalPredictor — envoltorio de inferencia
│
├── modules/                         # 8 Etapas de Procesamiento
│   ├── ingestion.py        [M1]     # Cargar CSV, normalizar OHLCV
│   ├── features.py         [M2]     # Generar 200+ características
│   ├── filtering.py        [M3]     # Detección de eventos CUSUM/Kalman
│   ├── labeling.py         [M4]     # Etiquetado de triple barrera
│   ├── splitting.py        [M5]     # Partición temporal walk-forward
│   ├── feature_selection.py [M6]    # Selección hacia adelante
│   ├── modeling.py         [M7]     # Entrenar clasificadores
│   ├── evaluation.py       [M8]     # Métricas + análisis de sobreajuste
│   └── utils.py                     # Utilidades compartidas
│
└── config/
    └── base_config.yaml             # Plantilla de configuración maestra
```

---

## 🔄 Flujo de Ejecución del Pipeline

### 1️⃣ **Ingesta (M1)**
```
CSV → Normalizar columnas → Remover brechas (ffill) → raw_data
```
- **Entrada**: Ruta de archivo CSV o ticker de yfinance
- **Salida**: `raw_data` (DataFrame con OHLCV estandarizado)
- **Claves de configuración**: `filepath`, `frequency`, `column_map`
- ✅ **Solo barras temporales** (sin barras de dólar)

### 2️⃣ **Características (M2)**
```
raw_data → [15min, 1h, 4h, 12h, 1d] → 200+ indicadores → características
```
**Indicadores técnicos** (por timeframe):
- Momento: RSI, MACD, CCI, Williams %R
- Volatilidad: Bandas de Bollinger, SuperTrend, ATR
- Volumen: VWAP, CMF, MFI, OBV
- Tendencia: ADX
- Microestructura: OFI, TRANS_RATE, TICK_AUTOCORR

**Características de mercado** (si existen):
- Prima, Tasa de financiamiento, Ratio Long/Short, CVD, Volumen Taker

- **Salida**: `features` (1224 líneas, todas las funciones)
- **Normalizaciones**: Z-score, cuantiles, EMA, detrending
- **Multi-timeframe**: Slicing intercalado (sin pérdida de datos)

### 3️⃣ **Filtrado (M3)**
```
características → Detectar movimientos significativos de precio/OI → tEvents
```
**Métodos**:
- **CUSUM** (Gráfico de Control de Suma Acumulada): Acumula desviaciones, dispara cuando excede umbral
- **Filtro de Kalman**: Detecta desvíos de tendencia suavizada

- **Salida**: `tEvents` (DatetimeIndex de eventos)
- **Configuración**: `method`, `filter_timeframe`, `k_Px`, `k_OI`
- **Densidad típica**: 5-20% de barras son eventos

### 4️⃣ **Etiquetado (M4)**
```
tEvents + cierre → Triple Barrera → etiquetas {-1, 1}
```
**Método de Triple Barrera**:
1. **PT (Objetivo de Ganancia)**: `volatilidad × ptSl[0]`
2. **SL (Parada de Pérdida)**: `volatilidad × ptSl[1]`
3. **Vertical (Tiempo)**: `timeframe × vertical_mult` barras

- **Volatilidad**: EWM de retornos absolutos (span = `trgt_length`)
- **Filtrado**: Solo eventos con `volatilidad ≥ minRet`

- **Salida**: `etiquetas` {-1, 1}, `ret_at_cross`, `barrier_touched`

### 5️⃣ **Partición (M5)**
```
datos_etiquetados → CV walk-forward (sin fuga) → particiones
```
**Walk-Forward** (no acumulativo):
- Divide datos en N segmentos iguales
- Genera N-1 rondas: entrenamiento=[seg_i] prueba=[seg_i+1]

**Purging & Embargo** (prevenir fuga):
- **Purging**: Elimina del entrenamiento eventos cuya barrera se resuelve en prueba
- **Embargo**: Descarta % inicial del conjunto de prueba

- **Salida**: `particiones` (lista de dicts con train_idx, test_idx)

### 6️⃣ **Selección de Características (M6)**
```
características → Selección hacia adelante → características_seleccionadas
```
**2 fases**:
1. **Ranking**: Evalúa AUC individual de cada característica
2. **Selección Hacia Adelante**: Greedy → agrega características que mejoren AUC

- **Evaluador**: RandomForest ligero (n_estimators=50, max_depth=5)
- **Criterio de parada**: Mejora mínima de AUC = `criterio_parada` (predeterminado 0.005)
- **Salida**: `características_seleccionadas` (2 equipos por defecto)

### 7️⃣ **Modelado (M7)**
```
características_seleccionadas + etiquetas → Búsqueda en malla → modelos entrenados
```
**Clasificadores disponibles**:
- RandomForest, GradientBoosting, LogisticRegression
- XGBoost, LightGBM, CatBoost, AdaBoost, DecisionTree, KNN, NaiveBayes

**Búsqueda en Malla**: Cada modelo × equipo × partición
- Evaluación sobre las particiones del walk-forward
- Sin fuga de datos temporal

- **Salida**: `predicciones_modelo`, `puntuaciones_modelo`, `mejor_modelo_obj`

### 8️⃣ **Evaluación (M8)**
```
predicciones_modelo → Métricas financieras + análisis de sobreajuste
```
**Métricas**:
- **AUC-ROC**: Capacidad de separar clases (0.5=aleatorio, 1=perfecto)
- **Precisión/Recall**: Exactitud del modelo
- **Sharpe**: Retorno / Volatilidad (riesgo-rendimiento)
- **Caída Máxima**: Peor caída acumulada

**Análisis de Sobreajuste**:
- **DSR** (Relación de Sharpe Deflacionada): Ajusta Sharpe por pruebas múltiples
- **PBO** (Probabilidad de Sobreajuste en Backtesting): López de Prado 2018

- **Sin MLFlow** (todos los cálculos locales)

---

## 🎛️ Sistema de Configuración

**Claves de configuración** (inglés):
```yaml
asset: "BTC"                    # Ticker
period: ["2021-01-01", "2024-12-31"]
frequency: "1min"              # Frecuencia de datos
timeframes: ["15min", "1h", "4h", "12h", "1d"]  # Para características

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

## 💾 Clases Principales

### **PipelineData** (contenedor de datos)
```python
data = PipelineData()
data.set("close", serie_precios, source_module="ingestion")
close = data.get("close", required=True)
data.delete("close")  # Liberar memoria
data.keys()  # ['close', 'volume', ...]
data.summary()  # Información sobre cada entrada
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
pipeline.save_run("runs/")  # Guarda JSON con configuración + trazas

# Búsqueda automática de hiperparámetros
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

## 🔑 Características Principales

### ✅ Sin Barras de Dólar
- Solo barras temporales (CSV regular)
- Más simple, determinístico, reproducible

### ✅ Sin AWS/S3
- Solo datos locales (CSV)
- O yfinance para descargar históricos
- Checkpoints en disco local

### ✅ Sin MLFlow
- Todas las métricas calculadas localmente
- JSON de registro de ejecución para reproducibilidad
- DSR y PBO integrados (sin dependencias externas)

### ✅ 8 Módulos Independientes
- Cada uno es un StageBase
- Pueden reordenarse o saltarse (reanudación desde checkpoint)
- Validación automática de entradas

### ✅ Walk-Forward Temporal
- Purging: evita entrenar en datos que "miraron al futuro"
- Embargo: separa entrenamiento de prueba
- Sin fuga de datos

### ✅ Comparación Multi-Modelo
- Entrena 10+ clasificadores en paralelo
- Búsqueda en malla en cada modelo
- Selecciona el mejor por AUC

---

## 📊 Viaje del Usuario

1. **Preparar datos**: CSV con OHLCV (2021-2024)
2. **Configurar YAML**: Editar `base_config.yaml`
3. **Ejecutar pipeline**:
   ```python
   from smart_indicators import SignalPipeline
   pipeline = SignalPipeline.from_yaml("config.yaml")
   data = PipelineData()
   data, ok = pipeline.run_modules([1,2,3,4,5,6,7,8], data)
   ```
4. **Backtesting 2025**: Usar `mejor_modelo_obj` sobre 2025
5. **Trading en vivo 2026**: `SignalPredictor` genera señales diarias

---

## 🛠️ Qué es Diferente del Original

| Aspecto | Original (Pluszero) | Nuevo (hackITBA) |
|---------|-------------------|-----------------|
| Barras de Dólar | ✅ Soportadas | ❌ Removidas |
| AWS/S3 | ✅ Soporte completo | ❌ Removido |
| MLFlow | ✅ Integrado | ❌ Removido |
| Claves de configuración | Español (ingesta, frecuencia, activo) | Inglés (ingestion, frequency, asset) |
| Nombres de clases | BaseModule, DataContainer, SmartIndicatorsPipeline | StageBase, PipelineData, SignalPipeline |
| Comentarios | Español | Inglés |
| Líneas de código | ~5000 | ~3000 (sin S3, sin MLFlow, sin barras de dólar) |

---

## 📈 8 Módulos de un Vistazo

| Módulo | Entrada | Salida | Clave |
|--------|---------|--------|-------|
| **M1 Ingesta** | CSV | raw_data | Normalizar OHLCV |
| **M2 Características** | raw_data | características (200+) | Indicadores multi-timeframe |
| **M3 Filtrado** | características | tEvents | Detectar eventos significativos |
| **M4 Etiquetado** | tEvents + cierre | etiquetas {-1,1} | Triple barrera (PT/SL/vertical) |
| **M5 Partición** | etiquetas | particiones | CV walk-forward sin fuga |
| **M6 Selección** | características + particiones | características_seleccionadas | Selección forward greedy |
| **M7 Modelado** | características + particiones | mejor_modelo_obj | Búsqueda malla multi-modelo |
| **M8 Evaluación** | predicciones | métricas + sobreajuste | AUC, Sharpe, DSR, PBO |

---

## 🚀 Próximos Pasos para tu Equipo

1. **Entienden el flujo**: Datos → Características → Eventos → Etiquetas → Partición → Selección → Entrenamiento → Evaluación
2. **Saben qué cambiar**: Cada módulo es independiente, pueden tunearse parámetros por separado
3. **Saben ejecutar**: `SignalPipeline.from_yaml()` + `run_modules()`
4. **Saben debuggear**: Checkpoints intermedios, trazas con duración y errores

---

Hecho con ❤️ para el hackathon
