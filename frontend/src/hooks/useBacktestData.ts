import { useState, useEffect } from "react";

export interface BacktestDay {
  date: string;
  portfolio_value: number;
  benchmark_value: number;
  allocations: Record<string, number>;
  confidence: number;
  regime?: string;
  optimizer?: string;
  spy_value?: number;
}

export type RiskProfile = "low_risk" | "med_risk" | "high_risk";

export function getRiskProfile(risk: number): RiskProfile {
  if (risk < 34) return "low_risk";
  if (risk < 67) return "med_risk";
  return "high_risk";
}

export function modelIdToProfile(modelId: string): RiskProfile {
  if (modelId === "low") return "low_risk";
  if (modelId === "high") return "high_risk";
  return "med_risk";
}

export interface BacktestMetrics {
  totalReturn: number;
  maxDrawdown: number;
  sharpeRatio: number;
  vsbenchmark: number;
}

export function computeMetrics(data: BacktestDay[]): BacktestMetrics {
  if (data.length < 2) return { totalReturn: 0, maxDrawdown: 0, sharpeRatio: 0, vsbenchmark: 0 };

  const initial = data[0].portfolio_value;
  const final   = data[data.length - 1].portfolio_value;
  const totalReturn = ((final - initial) / initial) * 100;

  // Max drawdown
  let peak = initial, maxDD = 0;
  for (const d of data) {
    if (d.portfolio_value > peak) peak = d.portfolio_value;
    const dd = (d.portfolio_value - peak) / peak;
    if (dd < maxDD) maxDD = dd;
  }

  // Daily returns for Sharpe
  const rets: number[] = [];
  for (let i = 1; i < data.length; i++) {
    rets.push((data[i].portfolio_value - data[i - 1].portfolio_value) / data[i - 1].portfolio_value);
  }
  const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
  const std  = Math.sqrt(rets.reduce((a, b) => a + (b - mean) ** 2, 0) / rets.length);
  const sharpe = std > 0 ? (mean / std) * Math.sqrt(252) : 0;

  // vs benchmark
  const benchInitial = data[0].benchmark_value;
  const benchFinal   = data[data.length - 1].benchmark_value;
  const vsB = totalReturn - ((benchFinal - benchInitial) / benchInitial) * 100;

  return {
    totalReturn: Math.round(totalReturn * 10) / 10,
    maxDrawdown: Math.round(maxDD * 1000) / 10,
    sharpeRatio: Math.round(sharpe * 100) / 100,
    vsbenchmark:  Math.round(vsB * 10) / 10,
  };
}

export function useBacktestData(riskOrProfileId: number | string) {
  const profile: RiskProfile =
    typeof riskOrProfileId === "number"
      ? getRiskProfile(riskOrProfileId)
      : modelIdToProfile(riskOrProfileId);

  const [data,    setData]    = useState<BacktestDay[]>([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`/data/results_${profile}.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: BacktestDay[]) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [profile]);

  return { data, loading, error, profile };
}
