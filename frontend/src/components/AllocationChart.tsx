import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  AreaChart, Area, PieChart, Pie, Cell, XAxis, YAxis, ResponsiveContainer,
  Tooltip, Legend, LineChart, Line,
} from "recharts";
import { computeMetrics, type BacktestDay } from "@/hooks/useBacktestData";

const COLORS = [
  "hsl(217, 91%, 60%)",   // Azul
  "hsl(142, 76%, 36%)",   // Verde
  "hsl(0, 84%, 60%)",     // Rojo
  "hsl(39, 100%, 50%)",   // Naranja
  "hsl(280, 85%, 65%)",   // Púrpura
  "hsl(197, 100%, 50%)",  // Cian
  "hsl(12, 100%, 50%)",   // Naranja rojo
  "hsl(60, 100%, 50%)",   // Amarillo
];

interface AllocationChartProps {
  data: BacktestDay[];
}

const AllocationChart = ({ data }: AllocationChartProps) => {
  const [chartData, setChartData] = useState<any[]>([]);
  const [lastDayAllocs, setLastDayAllocs] = useState<Array<{ name: string; value: number }>>([]);
  const [assets, setAssets] = useState<string[]>([]);
  const [regimeStats, setRegimeStats] = useState<Array<{ name: string; days: number; pct: number; color: string }>>([]);
  const [optimizerStats, setOptimizerStats] = useState<Array<{ name: string; days: number; pct: number }>>([]);
  const multiplier = 25; // Scale up 1000 to match the 25k static capital for visualizations

  useEffect(() => {
    if (data.length === 0) return;

    // Extraer todos los activos
    const allAssets = new Set<string>();
    data.forEach((d) => {
      Object.keys(d.allocations).forEach((a) => allAssets.add(a));
    });
    const assetList = Array.from(allAssets).sort();
    setAssets(assetList);

    // Preprocesar para stacked area chart y line chart (portfolio value)
    const processedData = data.map((d, idx) => {
      const row: any = {
        day: idx + 1,
        portfolio: Math.round(d.portfolio_value * multiplier),
        benchmark: Math.round(d.benchmark_value * multiplier),
        spy: d.spy_value ? Math.round(d.spy_value * multiplier) : null,
        month: d.date.slice(0, 7)
      };
      assetList.forEach((asset) => {
        row[asset] = (d.allocations[asset] || 0) * 100; // % format
      });
      return row;
    });

    // Submuestrear cada 10 días para no saturar los gráficos visualmente
    const sampled = processedData.filter((_, i) => i % 10 === 0 || i === processedData.length - 1);
    setChartData(sampled);

    // Último día para pie chart
    const lastDay = data[data.length - 1];
    const pieData = assetList
      .map((a) => ({ name: a, value: parseFloat(((lastDay.allocations[a] || 0) * 100).toFixed(1)) }))
      .filter((d) => d.value > 0.1)
      .sort((a, b) => b.value - a.value);
    setLastDayAllocs(pieData);

    // Estadísticas de régimen y optimizador
    const regimeColors: Record<string, string> = {
      bull:    "hsl(142, 76%, 36%)",
      bear:    "hsl(0, 84%, 60%)",
      crisis:  "hsl(39, 100%, 50%)",
      neutral: "hsl(220, 9%, 55%)",
    };
    const regimeCounts: Record<string, number> = {};
    const optimizerCounts: Record<string, number> = {};
    for (const d of data) {
      const r = (d.regime ?? "neutral").toLowerCase();
      regimeCounts[r] = (regimeCounts[r] ?? 0) + 1;
      const o = d.optimizer ?? "Black-Litterman";
      optimizerCounts[o] = (optimizerCounts[o] ?? 0) + 1;
    }
    const total = data.length;
    setRegimeStats(
      Object.entries(regimeCounts)
        .sort(([, a], [, b]) => b - a)
        .map(([name, days]) => ({
          name: name.charAt(0).toUpperCase() + name.slice(1),
          days,
          pct: Math.round((days / total) * 100),
          color: regimeColors[name] ?? "hsl(220,9%,55%)",
        }))
    );
    setOptimizerStats(
      Object.entries(optimizerCounts)
        .sort(([, a], [, b]) => b - a)
        .map(([name, days]) => ({ name, days, pct: Math.round((days / total) * 100) }))
    );
  }, [data]);

  if (data.length === 0) return null;

  const metrics = computeMetrics(data);
  const finalValue = data.length > 0 ? Math.round(data[data.length - 1].portfolio_value * 25) : 0;

  return (
    <section className="min-h-screen flex items-center justify-center px-6 py-24">
      <div className="w-full max-w-6xl space-y-16">
        {/* Título */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          <h2 className="text-3xl sm:text-4xl font-semibold text-foreground">
            Evolución de Allocations e Inversión
          </h2>
          <p className="mt-3 text-muted-foreground text-sm">
            Cómo el modelo rebalanceó el portafolio a lo largo del año e impacto en las ganancias
          </p>
        </motion.div>

        {/* Ganancias Totales Chart (New) */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8, delay: 0.1 }}
        >
          <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
            <h3 className="text-sm font-semibold text-foreground mb-6">Ganancias Totales (Portfolio IA vs Equal-Weight)</h3>
            <div className="h-[360px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
                  <XAxis
                    dataKey="month"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
                    domain={['auto', 'auto']}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(0, 0%, 100%)",
                      border: "1px solid hsl(220, 13%, 91%)",
                      borderRadius: "8px",
                      fontSize: "12px",
                      boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                      color: "#000",
                    }}
                    formatter={(value: number, name: string) => [
                      `$${value.toLocaleString()}`,
                      name === "portfolio" ? "Portafolio IA" : name === "spy" ? "S&P 500 (SPY)" : "Equal-Weight (mismo universo)",
                    ]}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line
                    type="monotone"
                    dataKey="portfolio"
                    stroke="hsl(142, 76%, 36%)"
                    strokeWidth={3}
                    dot={false}
                    isAnimationActive={true}
                    animationDuration={1500}
                  />
                  <Line
                    type="monotone"
                    dataKey="benchmark"
                    stroke="hsl(220, 9%, 65%)"
                    strokeWidth={2}
                    strokeDasharray="4 4"
                    dot={false}
                    isAnimationActive={true}
                    animationDuration={1500}
                  />
                  <Line
                    type="monotone"
                    dataKey="spy"
                    stroke="hsl(0, 84%, 60%)"
                    strokeWidth={2}
                    strokeDasharray="6 3"
                    dot={false}
                    isAnimationActive={true}
                    animationDuration={1500}
                    name="S&P 500"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </motion.div>

        {/* Métricas Reales Extraídas */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-50px" }}
          transition={{ duration: 0.6, delay: 0.15 }}
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
              label: "vs Equal-Weight",
              value: `${metrics.vsbenchmark >= 0 ? "+" : ""}${metrics.vsbenchmark}%`,
              colored: true,
              positive: metrics.vsbenchmark >= 0,
            },
          ].map(({ label, value, colored, positive }) => (
            <div key={label} className="text-center p-5 rounded-xl border border-border bg-card shadow-sm">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">{label}</p>
              <p
                className={`text-2xl font-semibold ${colored
                  ? positive
                    ? "text-success"
                    : "text-red-500"
                  : "text-foreground"
                  }`}
              >
                {value}
              </p>
            </div>
          ))}
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, margin: "-50px" }}
          transition={{ delay: 0.2 }}
          className="text-center space-y-1 mb-8"
        >
          <p className="text-sm font-medium text-foreground">
            Capital final de la simulación:{" "}
            <span className="text-primary text-xl">${finalValue.toLocaleString()}</span>
          </p>
        </motion.div>

        {/* Régimen de Mercado & Optimizador */}
        {(regimeStats.length > 0 || optimizerStats.length > 0) && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="grid grid-cols-1 sm:grid-cols-2 gap-6"
          >
            {/* Régimen */}
            <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
              <h3 className="text-sm font-semibold text-foreground mb-5">Régimen de Mercado Detectado</h3>
              <div className="space-y-3">
                {regimeStats.map(({ name, days, pct, color }) => (
                  <div key={name}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="font-medium text-foreground">{name}</span>
                      <span className="text-muted-foreground">{days} días ({pct}%)</span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${pct}%`, backgroundColor: color }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Optimizador */}
            <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
              <h3 className="text-sm font-semibold text-foreground mb-5">Optimizador Utilizado</h3>
              <div className="space-y-3">
                {optimizerStats.map(({ name, days, pct }, idx) => (
                  <div key={name}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="font-medium text-foreground">{name}</span>
                      <span className="text-muted-foreground">{days} días ({pct}%)</span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${pct}%`, backgroundColor: COLORS[idx % COLORS.length] }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-4 leading-relaxed">
                El sistema alterna automáticamente entre Black-Litterman (neutro), HRP (bear/crisis) y Kelly (bull) según las condiciones del mercado.
              </p>
            </div>
          </motion.div>
        )}

        {/* Stacked Area Chart */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8, delay: 0.2 }}
        >
          <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
            <h3 className="text-sm font-semibold text-foreground mb-6">Pesos por Activo (% del portafolio)</h3>
            <div className="h-[360px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
                  <XAxis
                    dataKey="month"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }}
                    label={{ value: "% del Portafolio", angle: -90, position: "insideLeft", offset: 0 }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(0, 0%, 100%)",
                      border: "1px solid hsl(220, 13%, 91%)",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    formatter={(value: number) => [`${value.toFixed(1)}%`, ""]}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: 12 }}
                    formatter={(v) => v}
                  />
                  {assets.map((asset, idx) => (
                    <Area
                      key={asset}
                      type="monotone"
                      dataKey={asset}
                      stackId="1"
                      stroke={COLORS[idx % COLORS.length]}
                      fill={COLORS[idx % COLORS.length]}
                      fillOpacity={0.7}
                      isAnimationActive={true}
                      animationDuration={1500}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </motion.div>

        {/* Grid: Pie Chart + Top Assets */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="grid grid-cols-1 lg:grid-cols-2 gap-8"
        >
          {/* Pie Chart - Último día */}
          <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
            <h3 className="text-sm font-semibold text-foreground mb-6 text-center">
              Rebalanceo Final - Último Día
            </h3>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={lastDayAllocs}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, value }) => `${name} ${value.toFixed(1)}%`}
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {lastDayAllocs.map((_, idx) => (
                      <Cell key={`cell-${idx}`} fill={COLORS[idx % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => `${value.toFixed(1)}%`} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Top Assets Table */}
          <div className="bg-card border border-border rounded-2xl p-6 space-y-4 shadow-sm">
            <h3 className="text-sm font-semibold text-foreground">Top Posiciones Actuales</h3>
            <div className="space-y-3">
              {lastDayAllocs.slice(0, 5).map((item, idx) => (
                <div key={item.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: COLORS[idx % COLORS.length] }}
                    />
                    <span className="text-sm font-medium text-foreground">{item.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${item.value}%`,
                          backgroundColor: COLORS[idx % COLORS.length],
                        }}
                      />
                    </div>
                    <span className="text-sm font-semibold text-foreground w-12 text-right">
                      {item.value.toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Resumen */}
            <div className="pt-4 border-t border-border mt-4">
              <p className="text-xs text-muted-foreground">
                Total de activos en portafolio de IA: <span className="font-semibold">{lastDayAllocs.length}</span>
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Foco principal: <span className="font-semibold">{lastDayAllocs.slice(0, 3).map(a => a.name).join(", ")}</span>
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
};

export default AllocationChart;
