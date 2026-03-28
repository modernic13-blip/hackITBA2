import { useState, useEffect, useRef } from "react";
import { motion, useInView } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, Legend,
} from "recharts";
import { useBacktestData, computeMetrics, getRiskProfile } from "@/hooks/useBacktestData";

// Submuestrear cada N puntos para no animar 260 puntos uno por uno
const SAMPLE_EVERY = 5;

const BacktestingReveal = ({ capital, risk }: { capital: number; risk: number }) => {
  const [visiblePoints, setVisiblePoints] = useState(0);
  const [showMetrics,   setShowMetrics]   = useState(false);
  const sectionRef  = useRef<HTMLDivElement>(null);
  const isInView    = useInView(sectionRef, { once: true, margin: "-200px" });
  const hasStarted  = useRef(false);

  const { data: rawData, loading, error } = useBacktestData(risk);
  const profile    = getRiskProfile(risk);
  const multiplier = capital > 0 ? capital / 1000 : 1;

  // Submuestrear y transformar al formato del gráfico
  const chartData = rawData
    .filter((_, i) => i % SAMPLE_EVERY === 0)
    .map((d) => ({
      month:     d.date.slice(0, 7),
      portfolio: Math.round(d.portfolio_value * multiplier),
      benchmark: Math.round(d.benchmark_value * multiplier),
    }));

  // Reiniciar animación si cambia el perfil
  useEffect(() => {
    setVisiblePoints(0);
    setShowMetrics(false);
    hasStarted.current = false;
  }, [profile]);

  // Arrancar animación cuando entra en viewport
  useEffect(() => {
    if (!isInView || hasStarted.current || chartData.length === 0) return;
    hasStarted.current = true;

    const interval = setInterval(() => {
      setVisiblePoints((prev) => {
        if (prev >= chartData.length) {
          clearInterval(interval);
          setTimeout(() => setShowMetrics(true), 400);
          return prev;
        }
        return prev + 1;
      });
    }, 120);
    return () => clearInterval(interval);
  }, [isInView, chartData.length]);

  const animatedData = chartData.slice(0, visiblePoints);
  const metrics      = computeMetrics(rawData);
  const finalValue   = animatedData[animatedData.length - 1]?.portfolio ?? Math.round(capital);

  if (loading) {
    return (
      <section className="min-h-screen flex items-center justify-center">
        <span className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </section>
    );
  }

  if (error) {
    return (
      <section className="min-h-screen flex items-center justify-center px-6">
        <p className="text-muted-foreground text-sm">
          No se pudo cargar el backtest. Corré el modelo primero.
        </p>
      </section>
    );
  }

  return (
    <section ref={sectionRef} className="min-h-screen flex items-center justify-center px-6 py-24">
      <div className="w-full max-w-4xl space-y-16">

        {/* Título */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          <h2 className="text-3xl sm:text-4xl font-semibold text-foreground">
            Backtesting 2025 —{" "}
            {risk < 34 ? "Perfil Conservador" : risk < 67 ? "Perfil Balanceado" : "Perfil Agresivo"}
          </h2>
          <p className="mt-3 text-muted-foreground text-sm">
            Retornos generados con Black-Litterman + predicciones ML hora a hora.
          </p>
        </motion.div>

        {/* Gráfico */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, delay: 0.3 }}
        >
          <div className="h-[360px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={animatedData} margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <XAxis
                  dataKey="month"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }}
                  tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
                  width={55}
                />
                <Tooltip
                  contentStyle={{
                    background: "hsl(0, 0%, 100%)",
                    border: "1px solid hsl(220, 13%, 91%)",
                    borderRadius: "8px",
                    fontSize: "12px",
                    boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                  }}
                  formatter={(value: number, name: string) => [
                    `$${value.toLocaleString()}`,
                    name === "portfolio" ? "Portafolio IA" : "Benchmark",
                  ]}
                />
                <Legend
                  formatter={(v) => (v === "portfolio" ? "Portafolio IA" : "Benchmark")}
                  wrapperStyle={{ fontSize: 12 }}
                />
                <Line
                  type="monotone"
                  dataKey="portfolio"
                  stroke="hsl(217, 91%, 60%)"
                  strokeWidth={2.5}
                  dot={false}
                  animationDuration={0}
                />
                <Line
                  type="monotone"
                  dataKey="benchmark"
                  stroke="hsl(220, 9%, 65%)"
                  strokeWidth={1.5}
                  strokeDasharray="4 4"
                  dot={false}
                  animationDuration={0}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Métricas reales */}
        {showMetrics && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="grid grid-cols-2 sm:grid-cols-4 gap-4"
          >
            {[
              {
                label: "Retorno Total",
                value: `${metrics.totalReturn >= 0 ? "+" : ""}${metrics.totalReturn}%`,
                colored: true,
                positive: metrics.totalReturn >= 0,
              },
              { label: "Max Drawdown", value: `${metrics.maxDrawdown}%`, colored: false },
              { label: "Sharpe Ratio", value: String(metrics.sharpeRatio), colored: false },
              {
                label: "vs Benchmark",
                value: `${metrics.vsbenchmark >= 0 ? "+" : ""}${metrics.vsbenchmark}%`,
                colored: true,
                positive: metrics.vsbenchmark >= 0,
              },
            ].map(({ label, value, colored, positive }) => (
              <div key={label} className="text-center p-5 rounded-xl border border-border bg-card">
                <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">{label}</p>
                <p
                  className={`text-2xl font-semibold ${
                    colored
                      ? positive
                        ? "text-green-500"
                        : "text-red-500"
                      : "text-foreground"
                  }`}
                >
                  {value}
                </p>
              </div>
            ))}
          </motion.div>
        )}

        {showMetrics && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="text-center space-y-1"
          >
            <p className="text-sm font-medium text-foreground">
              Capital final:{" "}
              <span className="text-primary">${finalValue.toLocaleString()}</span>
            </p>
            <p className="text-xs text-muted-foreground/70">
              Predicciones horarias XGBoost/LightGBM · Optimización Black-Litterman diaria
            </p>
          </motion.div>
        )}
      </div>
    </section>
  );
};

export default BacktestingReveal;
