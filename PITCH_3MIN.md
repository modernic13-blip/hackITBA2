# QuantFlow AI — Pitch 3 Minutos

---

## MINUTO 1 — EL PROBLEMA (30s) + LA SOLUCIÓN (30s)

### El Problema
- **85% de los inversores retail pierden plata** tratando de hacer market timing
- Los robo-advisors tradicionales (Betterment, Balanz, Banza) usan **un solo algoritmo estático** — no se adaptan cuando el mercado cambia de tendencia
- Cuando viene un crash, siguen con la misma estrategia. Cuando viene un rally, no lo aprovechan

### La Solución: QuantFlow AI
- Un **sistema de inversión automatizado** que detecta si el mercado está en modo Bull, Bear o Crisis
- Y **cambia de estrategia automáticamente** según las condiciones:
  - **Mercado neutro** → Black-Litterman (bayesiano, equilibrado)
  - **Mercado en caída** → HRP (defensivo, protege capital)
  - **Mercado alcista** → Kelly Criterion (agresivo, maximiza ganancias)
- **Machine Learning** (XGBoost + LightGBM) predice qué activos van a subir
- **3 perfiles de riesgo**: Conservador, Dinámico, Agresivo

---

## MINUTO 2 — RESULTADOS (el momento WOW)

### Backtest 2024 (out-of-sample, datos que el modelo NUNCA vio)

| Perfil | Retorno | vs S&P 500 (+26%) | Sharpe Ratio |
|--------|---------|-------------------|--------------|
| **Conservador** | **+71.2%** | casi 3x el S&P | 2.80 |
| **Dinámico** | **+148.0%** | 5.7x el S&P | **2.97** |
| **Agresivo** | **+182.2%** | 7x el S&P | 2.44 |

### El momento clave
- Entre marzo y septiembre 2024, el mercado estuvo volátil
- El Equal-Weight (no hacer nada) subió +13.8%
- **QuantFlow Dinámico subió +46.6%** — el triple, porque reasignó capital inteligentemente

### Transparencia
- El benchmark justo es el Equal-Weight de los mismos 11 activos
- Alpha real del modelo: **+15% a +77%** sobre no hacer nada con los mismos activos
- Validación Walk-Forward: entrena con 2020-2023, testea en 2024. **Cero data leakage.**

---

## MINUTO 3 — MODELO DE NEGOCIO + DEMO

### Monetización: Performance Fee (solo cobramos si ganás)
- **Agresivo**: 1% de las ganancias
- **Dinámico**: 3% de las ganancias
- **Conservador**: 6% de las ganancias
- Si el modelo no genera ganancia, **no cobramos nada**

### Mercado
- Robo-advisors en LATAM: **USD 1.2B**, creciendo 25% anual
- En Argentina **no existe** un robo-advisor con ML predictivo + optimización adaptativa
- Competidores (Balanz, Banza, IOL) usan reglas estáticas

### Diferenciadores técnicos (si preguntan)
- **3 optimizadores** que se activan según régimen de mercado (único en retail)
- **Detección de régimen en tiempo real** (Bull/Bear/Crisis/Neutral)
- Basado en paper académico: "Advances in Financial ML" de López de Prado
- Pipeline de 8 módulos (M1-M8) con validación anti-overfitting

### Demo en vivo
→ Abrir **localhost:8080** → Simulacion → Play → Mostrar:
1. El gráfico corriendo en tiempo real
2. El **régimen detectado** cambiando en el sidebar
3. El **optimizador** alternando entre BL/HRP/Kelly
4. Los **top 5 activos** actualizándose día a día
5. Scrollear al home → sección de **3 líneas** (Portfolio vs Equal-Weight vs S&P 500)

---

## FRASE DE CIERRE

> "Lo que Two Sigma hace para millonarios con mínimos de 10 millones de dólares, nosotros lo hacemos accesible desde $6,000. Con datos reales, resultados verificables y cero overfitting."

---

## SI TE PREGUNTAN...

**"¿Cómo sé que no es overfitting?"**
→ Walk-Forward: entrenamos con 2020-2023, testeamos en 2024. El modelo nunca vio esos datos. Purge windows de 240 barras entre train y test.

**"¿Por qué no comparan contra el S&P 500 directamente?"**
→ Sí lo mostramos (línea roja en el gráfico). Pero la comparación más honesta es contra el Equal-Weight de los mismos activos, porque nuestro universo incluye BTC y NVDA que tuvieron un año atípico.

**"¿Qué pasa en un mercado realmente malo?"**
→ El RegimeDetector activa HRP (defensivo). Max Drawdown del perfil Dinámico fue solo -11.3% — controlado.

**"¿Cómo ganan plata ustedes?"**
→ Performance fee: solo cobramos un % de las ganancias. Si el usuario no gana, nosotros tampoco. Incentivos 100% alineados.

**"¿Qué tecnología usan?"**
→ Python (XGBoost, LightGBM, scikit-learn), React + TypeScript para el frontend, Supabase para auth y persistencia.
