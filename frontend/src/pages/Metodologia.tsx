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

        {/* Casos de Éxito */}
        <motion.section initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} className="space-y-10">
          <div className="text-center space-y-3">
            <h2 className="text-3xl font-bold tracking-tight">Casos de Éxito y Rendimiento</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto text-sm">
              Resultados reales de nuestro backtest out-of-sample (2024). El modelo nunca vio estos datos durante el entrenamiento.
            </p>
          </div>

          {/* Caso 1: Protección en caídas */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="bg-card border border-border rounded-2xl overflow-hidden"
          >
            <div className="bg-red-500/5 border-b border-red-500/20 px-6 py-3 flex items-center gap-2">
              <span className="text-lg">🛡️</span>
              <span className="text-xs font-bold uppercase tracking-wider text-red-400">Caso de Éxito 1 — Protección en Caídas</span>
            </div>
            <div className="p-6 space-y-4">
              <h3 className="text-xl font-semibold">Período difícil del mercado (Mar-Sep). Nuestro modelo ganó <span className="text-success">+46.6%</span>.</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Entre marzo y septiembre de 2024, el mercado crypto enfrentó correcciones significativas. El <strong className="text-foreground">RegimeDetector</strong> identificó los períodos de estrés y alternó entre <strong className="text-foreground">HRP (defensivo)</strong> y <strong className="text-foreground">Kelly (agresivo)</strong> según las condiciones.
              </p>
              <p className="text-sm text-muted-foreground leading-relaxed">
                El sistema reasignó capital dinámicamente hacia activos con momentum positivo: rotó de BTC hacia <strong className="text-foreground">META y NVDA</strong> cuando detectó debilidad. Resultado: el perfil Dinámico generó <strong className="text-foreground">+46.6%</strong> mientras el equal-weight solo subió +13.8%.
              </p>
              <div className="grid grid-cols-3 gap-3 pt-2">
                <div className="bg-background rounded-xl p-4 text-center border border-border">
                  <p className="text-2xl font-bold text-muted-foreground">+13.8%</p>
                  <p className="text-xs text-muted-foreground mt-1">Equal-Weight</p>
                </div>
                <div className="bg-background rounded-xl p-4 text-center border border-border">
                  <p className="text-2xl font-bold text-success">+39.6%</p>
                  <p className="text-xs text-muted-foreground mt-1">QuantFlow Agresivo</p>
                </div>
                <div className="bg-background rounded-xl p-4 text-center border border-primary/30">
                  <p className="text-2xl font-bold text-success">+46.6%</p>
                  <p className="text-xs text-muted-foreground mt-1">QuantFlow Dinámico</p>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Caso 2: Maximizando rally */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="bg-card border border-border rounded-2xl overflow-hidden"
          >
            <div className="bg-success/5 border-b border-success/20 px-6 py-3 flex items-center gap-2">
              <span className="text-lg">🚀</span>
              <span className="text-xs font-bold uppercase tracking-wider text-success">Caso de Éxito 2 — Maximizando Ganancias</span>
            </div>
            <div className="p-6 space-y-4">
              <h3 className="text-xl font-semibold">El portafolio Agresivo logró <span className="text-success">+182.2%</span> en 2024.</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                El perfil High Risk capturó los mejores rallies del año. Cuando el <strong className="text-foreground">RegimeDetector</strong> identificó régimen <strong className="text-foreground">BULL</strong>, activó el <strong className="text-foreground">Kelly Criterion</strong> — el optimizador agresivo que maximiza crecimiento geométrico.
              </p>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Kelly concentró exposición en activos ganadores: <strong className="text-foreground">NVDA (40%), BTC (34-40%), PLTR (10-15%)</strong> en los momentos de mayor confianza. En correcciones, rotó a <strong className="text-foreground">HRP</strong> para proteger ganancias. El resultado: <strong className="text-foreground">+61.1% de alpha</strong> sobre el equal-weight de los mismos activos.
              </p>
              <div className="grid grid-cols-3 gap-3 pt-2">
                <div className="bg-background rounded-xl p-4 text-center border border-border">
                  <p className="text-2xl font-bold text-muted-foreground">+26%</p>
                  <p className="text-xs text-muted-foreground mt-1">S&P 500 (SPY)</p>
                </div>
                <div className="bg-background rounded-xl p-4 text-center border border-border">
                  <p className="text-2xl font-bold text-success">+121.1%</p>
                  <p className="text-xs text-muted-foreground mt-1">Equal-Weight</p>
                </div>
                <div className="bg-background rounded-xl p-4 text-center border border-primary/30">
                  <p className="text-2xl font-bold text-success">+182.2%</p>
                  <p className="text-xs text-muted-foreground mt-1">QuantFlow Agresivo</p>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Caso 3: vs S&P 500 */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="bg-card border border-border rounded-2xl overflow-hidden"
          >
            <div className="bg-primary/5 border-b border-primary/20 px-6 py-3 flex items-center gap-2">
              <span className="text-lg">📊</span>
              <span className="text-xs font-bold uppercase tracking-wider text-primary">Superando al S&P 500 — Consistentemente</span>
            </div>
            <div className="p-6 space-y-4">
              <h3 className="text-xl font-semibold">Los <span className="text-primary">3 perfiles</span> superaron al S&P 500 en 2024.</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                El objetivo principal del sistema era <strong className="text-foreground">generar retornos superiores al índice de referencia más importante del mundo</strong>. Lo logramos de forma contundente: incluso nuestro perfil más conservador casi <strong className="text-foreground">triplicó</strong> el rendimiento del S&P 500.
              </p>
              <div className="space-y-3 pt-2">
                {[
                  { name: "S&P 500 (SPY)", ret: "+26%", color: "text-muted-foreground", bg: "bg-muted", width: "14%" },
                  { name: "Conservador", ret: "+71.2%", color: "text-primary", bg: "bg-primary/20", width: "39%" },
                  { name: "Dinámico", ret: "+148%", color: "text-primary", bg: "bg-primary/30", width: "81%" },
                  { name: "Agresivo", ret: "+182.2%", color: "text-primary", bg: "bg-primary/40", width: "100%" },
                ].map((item) => (
                  <div key={item.name} className="space-y-1.5">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium text-foreground">{item.name}</span>
                      <span className={`font-bold ${item.color}`}>{item.ret}</span>
                    </div>
                    <div className="h-3 bg-muted rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        whileInView={{ width: item.width }}
                        viewport={{ once: true }}
                        transition={{ duration: 1, ease: "easeOut" }}
                        className={`h-full rounded-full ${item.bg}`}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <div className="bg-primary/5 border border-primary/20 rounded-xl p-4 mt-4">
                <p className="text-xs text-muted-foreground leading-relaxed">
                  <strong className="text-foreground">Nota de transparencia:</strong> El universo de activos de QuantFlow incluye activos de alto crecimiento (NVDA, BTC, PLTR) que tuvieron rendimientos atípicos en 2024. La comparación más justa es contra el Equal-Weight de los mismos 11 activos, donde el modelo genera <strong className="text-foreground">+15% a +77% de alpha</strong> gracias a la optimización adaptativa.
                </p>
              </div>
            </div>
          </motion.div>

          {/* Tabla resumen */}
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="bg-card border border-border rounded-2xl p-6"
          >
            <h3 className="text-sm font-semibold text-foreground mb-4">Resumen de Rendimiento (Backtest 2024, out-of-sample)</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-muted-foreground uppercase">
                    <th className="text-left py-3 pr-4">Perfil</th>
                    <th className="text-right py-3 px-3">Retorno</th>
                    <th className="text-right py-3 px-3">vs EW</th>
                    <th className="text-right py-3 px-3">vs SPY</th>
                    <th className="text-right py-3 px-3">Sharpe</th>
                    <th className="text-right py-3 pl-3">Max DD</th>
                  </tr>
                </thead>
                <tbody className="text-foreground">
                  <tr className="border-b border-border/50">
                    <td className="py-3 pr-4 font-medium">Conservador</td>
                    <td className="py-3 px-3 text-right text-success font-bold">+71.2%</td>
                    <td className="py-3 px-3 text-right">+15.6%</td>
                    <td className="py-3 px-3 text-right">+45.2%</td>
                    <td className="py-3 px-3 text-right">2.80</td>
                    <td className="py-3 pl-3 text-right text-red-400">-12.7%</td>
                  </tr>
                  <tr className="border-b border-border/50">
                    <td className="py-3 pr-4 font-medium">Dinámico</td>
                    <td className="py-3 px-3 text-right text-success font-bold">+148.0%</td>
                    <td className="py-3 px-3 text-right">+76.7%</td>
                    <td className="py-3 px-3 text-right">+122%</td>
                    <td className="py-3 px-3 text-right font-bold">2.97</td>
                    <td className="py-3 pl-3 text-right text-red-400">-11.3%</td>
                  </tr>
                  <tr>
                    <td className="py-3 pr-4 font-medium">Agresivo</td>
                    <td className="py-3 px-3 text-right text-success font-bold">+182.2%</td>
                    <td className="py-3 px-3 text-right">+61.1%</td>
                    <td className="py-3 px-3 text-right">+156.2%</td>
                    <td className="py-3 px-3 text-right">2.44</td>
                    <td className="py-3 pl-3 text-right text-red-400">-18.9%</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-xs text-muted-foreground mt-4">
              El perfil <strong className="text-foreground">Dinámico</strong> ofrece el mejor ratio riesgo-retorno con un Sharpe de <strong className="text-foreground">2.97</strong> y un Max Drawdown de solo <strong className="text-foreground">-11.3%</strong> — retornos de triple dígito con riesgo controlado.
            </p>
          </motion.div>
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
