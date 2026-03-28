import { useState, useEffect, useRef } from "react";
import { motion, useInView } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, ResponsiveContainer, ReferenceDot, Tooltip,
} from "recharts";
import { portfolioGrowthData, backtestMetrics, backtestAnnotations } from "@/data/mockData";

const BacktestingReveal = ({ capital, risk }: { capital: number; risk: number }) => {
  const [visiblePoints, setVisiblePoints] = useState(0);
  const [showMetrics, setShowMetrics] = useState(false);
  const [showAnnotation, setShowAnnotation] = useState(-1);
  const sectionRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(sectionRef, { once: true, margin: "-200px" });
  const hasStarted = useRef(false);

  const multiplier = capital / 10000;
  const riskMultiplier = 0.8 + (risk / 100) * 0.4;

  const chartData = portfolioGrowthData.map((d) => ({
    ...d,
    value: Math.round(d.value * multiplier * riskMultiplier),
  }));

  useEffect(() => {
    if (!isInView || hasStarted.current) return;
    hasStarted.current = true;

    const interval = setInterval(() => {
      setVisiblePoints((prev) => {
        if (prev >= chartData.length) {
          clearInterval(interval);
          setTimeout(() => setShowMetrics(true), 500);
          return prev;
        }
        const annotation = backtestAnnotations.find((a) => a.index === prev);
        if (annotation) {
          setShowAnnotation(prev);
          setTimeout(() => setShowAnnotation(-1), 2000);
        }
        return prev + 1;
      });
    }, 200);
    return () => clearInterval(interval);
  }, [isInView, chartData.length]);

  const animatedData = chartData.slice(0, visiblePoints);
  const finalValue = chartData[chartData.length - 1]?.value ?? 0;
  const totalReturn = ((finalValue - chartData[0].value) / chartData[0].value * 100).toFixed(1);

  return (
    <section ref={sectionRef} className="min-h-screen flex items-center justify-center px-6 py-24">
      <div className="w-full max-w-4xl space-y-16">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          <h2 className="text-3xl sm:text-4xl font-semibold text-foreground">
            If you had started in 2021…
          </h2>
          <p className="mt-3 text-muted-foreground text-sm">
            Simulated performance based on your profile.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, delay: 0.3 }}
          className="relative"
        >
          <div className="h-[360px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={animatedData} margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }} interval="preserveStartEnd" />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "hsl(220, 9%, 46%)" }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} width={50} />
                <Tooltip
                  contentStyle={{ background: "hsl(0, 0%, 100%)", border: "1px solid hsl(220, 13%, 91%)", borderRadius: "8px", fontSize: "12px", boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
                  formatter={(value: number) => [`$${value.toLocaleString()}`, "Portfolio Value"]}
                />
                <Line type="monotone" dataKey="value" stroke="hsl(217, 91%, 60%)" strokeWidth={2.5} dot={false} animationDuration={0} />
                {backtestAnnotations.map((ann) =>
                  visiblePoints > ann.index ? (
                    <ReferenceDot key={ann.index} x={chartData[ann.index]?.month} y={chartData[ann.index]?.value * multiplier * riskMultiplier} r={4} fill="hsl(217, 91%, 60%)" stroke="hsl(0, 0%, 100%)" strokeWidth={2} />
                  ) : null
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {showAnnotation >= 0 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="absolute top-4 left-1/2 -translate-x-1/2 bg-card border border-border rounded-lg px-4 py-2 text-xs text-muted-foreground shadow-sm"
            >
              {backtestAnnotations.find((a) => a.index === showAnnotation)?.label}
            </motion.div>
          )}
        </motion.div>

        {showMetrics && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div className="text-center p-6 rounded-xl border border-border bg-card">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Total Return</p>
              <p className="text-3xl font-semibold text-success">+{totalReturn}%</p>
            </div>
            <div className="text-center p-6 rounded-xl border border-border bg-card">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Worst temporary drop</p>
              <p className="text-3xl font-semibold text-foreground">{backtestMetrics.maxDrawdown}%</p>
            </div>
            <div className="text-center p-6 rounded-xl border border-border bg-card">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Consistency of returns</p>
              <p className="text-3xl font-semibold text-foreground">{backtestMetrics.sharpeRatio}</p>
            </div>
          </motion.div>
        )}

        {showMetrics && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }} className="text-center space-y-1">
            <p className="text-sm text-muted-foreground">Not perfect. But adaptive.</p>
            <p className="text-xs text-muted-foreground/70">Designed to respond, not predict.</p>
          </motion.div>
        )}
      </div>
    </section>
  );
};

export default BacktestingReveal;
