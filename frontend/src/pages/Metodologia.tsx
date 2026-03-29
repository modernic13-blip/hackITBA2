import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";

const steps = [
  { round: "Ronda 1", train: "2020", test: "2021" },
  { round: "Ronda 2", train: "2020 – 2021", test: "2022" },
  { round: "Ronda 3", train: "2020 – 2022", test: "2023" },
  { round: "Ronda 4", train: "2020 – 2023", test: "2024  (resultados finales)" },
];

const realism = [
  { title: "Solo Long", desc: "Solo compra, nunca vende en corto. Compatible con cualquier broker retail." },
  { title: "1 rebalanceo por día", desc: "Ajusta pesos una vez al día al cierre. No hace high-frequency trading." },
  { title: "Comisiones incluidas", desc: "El backtest descuenta 3-5 bps por operación (similar a Interactive Brokers)." },
  { title: "Fully invested", desc: "Capital siempre 100% en el mercado, distribuido entre los activos del perfil." },
  { title: "Max weight constraint", desc: "Ningún activo supera el 25-40% del portafolio, forzando diversificación." },
];

const pipeline = [
  { step: "M1", name: "Ingesta", desc: "OHLCV diarios de 11 activos (acciones, ETFs, crypto) via yfinance" },
  { step: "M2", name: "Features", desc: "30+ indicadores técnicos: RSI, MACD, Bollinger, ATR, ADX, OBV, momentum" },
  { step: "M3", name: "Filtrado CUSUM", desc: "Detecta cambios estructurales para evitar overtrading con ruido" },
  { step: "M4", name: "Etiquetado", desc: "Triple Barrier Method: profit-take, stop-loss, timeout por evento" },
  { step: "M5", name: "Splitting", desc: "Walk-Forward con purge windows de 240 barras — cero data leakage" },
  { step: "M6", name: "Feature Selection", desc: "MDI + importancia por permutación para descartar features ruidosos" },
  { step: "M7", name: "Modelado", desc: "Ensemble XGBoost + LightGBM + RandomForest con meta-learner por activo" },
  { step: "M8", name: "Evaluación", desc: "Sharpe, Max Drawdown, retorno acumulado vs equal-weight y S&P 500" },
];

export default function Metodologia() {
  return (
    <div className="min-h-screen bg-background text-foreground font-sans">
      <header className="p-6 border-b border-border sticky top-0 bg-background/80 backdrop-blur-md z-10">
        <Link to="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft size={16} />
          Volver al inicio
        </Link>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-16 space-y-20">

        {/* Hero */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center space-y-4">
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight">Metodología de Validación</h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Cero overfitting. Nuestro modelo se valida con Walk-Forward estricto — nunca ve datos futuros durante el entrenamiento.
          </p>
        </motion.div>

        {/* Pipeline ML */}
        <motion.section initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} className="space-y-8">
          <h2 className="text-2xl font-semibold">Pipeline ML (M1 — M8)</h2>
          <p className="text-muted-foreground text-sm">Basado en "Advances in Financial Machine Learning" de Marcos López de Prado.</p>
          <div className="grid gap-3">
            {pipeline.map((p, i) => (
              <motion.div
                key={p.step}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="flex items-start gap-4 bg-card border border-border rounded-xl p-4"
              >
                <span className="shrink-0 w-10 h-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center text-sm font-bold">
                  {p.step}
                </span>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">{p.name}</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">{p.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.section>

        {/* Walk-Forward */}
        <motion.section initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} className="space-y-8">
          <h2 className="text-2xl font-semibold">Walk-Forward con Ventana Expansiva</h2>
          <p className="text-muted-foreground text-sm">El modelo se entrena incrementalmente, simulando exactamente cómo operaría en el mundo real.</p>
          <div className="space-y-3">
            {steps.map((s, i) => (
              <motion.div
                key={s.round}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="flex items-center gap-4 bg-card border border-border rounded-xl p-4"
              >
                <span className="shrink-0 text-xs font-bold text-primary bg-primary/10 px-3 py-1.5 rounded-lg">
                  {s.round}
                </span>
                <div className="flex-1 grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground text-xs uppercase">Train</span>
                    <p className="font-medium">{s.train}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs uppercase">Test</span>
                    <p className="font-medium">{s.test}</p>
                  </div>
                </div>
                <span className="text-success text-xs font-mono">sin data leakage</span>
              </motion.div>
            ))}
          </div>
          <div className="bg-primary/5 border border-primary/20 rounded-xl p-5 text-sm text-muted-foreground space-y-2">
            <p>Purge windows de <strong className="text-foreground">240 barras</strong> entre train y test para evitar leakage temporal.</p>
            <p>Cross-validation temporal con <strong className="text-foreground">embargo</strong> entre folds.</p>
          </div>
        </motion.section>

        {/* Realismo */}
        <motion.section initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} className="space-y-8">
          <h2 className="text-2xl font-semibold">Realismo en la Ejecución</h2>
          <p className="text-muted-foreground text-sm">Diseñado para operar en el mundo real, no solo en backtests.</p>
          <div className="grid sm:grid-cols-2 gap-4">
            {realism.map((r, i) => (
              <motion.div
                key={r.title}
                initial={{ opacity: 0, scale: 0.95 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="bg-card border border-border rounded-xl p-5 space-y-2"
              >
                <h3 className="text-sm font-semibold text-foreground">{r.title}</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">{r.desc}</p>
              </motion.div>
            ))}
          </div>
        </motion.section>

        {/* Optimización Adaptativa */}
        <motion.section initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} className="space-y-8">
          <h2 className="text-2xl font-semibold">Motor de Optimización Adaptativo</h2>
          <div className="grid sm:grid-cols-3 gap-4">
            <div className="bg-card border border-border rounded-xl p-5 space-y-3">
              <div className="text-2xl">⚖️</div>
              <h3 className="text-sm font-semibold">Black-Litterman</h3>
              <p className="text-xs text-muted-foreground">Régimen Neutro — combina equilibrio de mercado con views ML bayesianas.</p>
            </div>
            <div className="bg-card border border-border rounded-xl p-5 space-y-3">
              <div className="text-2xl">🛡️</div>
              <h3 className="text-sm font-semibold">HRP (Hierarchical Risk Parity)</h3>
              <p className="text-xs text-muted-foreground">Régimen Bear / Crisis — diversificación jerárquica sin invertir la covarianza.</p>
            </div>
            <div className="bg-card border border-border rounded-xl p-5 space-y-3">
              <div className="text-2xl">🎯</div>
              <h3 className="text-sm font-semibold">Kelly Criterion</h3>
              <p className="text-xs text-muted-foreground">Régimen Bull — maximiza crecimiento geométrico cuando la confianza es alta.</p>
            </div>
          </div>
        </motion.section>

        {/* Referencias */}
        <motion.section initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} className="space-y-6 pb-12">
          <h2 className="text-2xl font-semibold">Referencias Académicas</h2>
          <ul className="space-y-3 text-sm text-muted-foreground">
            <li className="border-l-2 border-primary/30 pl-4"><strong className="text-foreground">Advances in Financial Machine Learning</strong> — Marcos López de Prado (2018). Framework M1-M8.</li>
            <li className="border-l-2 border-primary/30 pl-4"><strong className="text-foreground">Black-Litterman Model</strong> — Black & Litterman (1992). Global Portfolio Optimization.</li>
            <li className="border-l-2 border-primary/30 pl-4"><strong className="text-foreground">Hierarchical Risk Parity</strong> — López de Prado (2016). Building Diversified Portfolios.</li>
            <li className="border-l-2 border-primary/30 pl-4"><strong className="text-foreground">Kelly Criterion</strong> — Kelly (1956). A New Interpretation of Information Rate.</li>
            <li className="border-l-2 border-primary/30 pl-4"><strong className="text-foreground">Triple Barrier Method</strong> — López de Prado (2018). Etiquetado financiero.</li>
          </ul>
        </motion.section>

      </main>
    </div>
  );
}
