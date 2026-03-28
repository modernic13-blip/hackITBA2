export const portfolioGrowthData = [
  { month: "Jan 21", value: 10000 },
  { month: "Mar 21", value: 11200 },
  { month: "Jun 21", value: 12800 },
  { month: "Sep 21", value: 11900 },
  { month: "Dec 21", value: 13400 },
  { month: "Mar 22", value: 12100 },
  { month: "Jun 22", value: 10800 },
  { month: "Sep 22", value: 9600 },
  { month: "Dec 22", value: 10900 },
  { month: "Mar 23", value: 12300 },
  { month: "Jun 23", value: 13800 },
  { month: "Sep 23", value: 14200 },
  { month: "Dec 23", value: 15600 },
  { month: "Mar 24", value: 16100 },
  { month: "Jun 24", value: 17400 },
  { month: "Sep 24", value: 16800 },
  { month: "Dec 24", value: 18200 },
];

export const heroChartData = [
  { x: 0, y: 20 }, { x: 1, y: 22 }, { x: 2, y: 21 }, { x: 3, y: 25 },
  { x: 4, y: 24 }, { x: 5, y: 28 }, { x: 6, y: 26 }, { x: 7, y: 30 },
  { x: 8, y: 29 }, { x: 9, y: 33 }, { x: 10, y: 31 }, { x: 11, y: 35 },
  { x: 12, y: 34 }, { x: 13, y: 38 }, { x: 14, y: 36 }, { x: 15, y: 40 },
  { x: 16, y: 42 }, { x: 17, y: 41 }, { x: 18, y: 45 }, { x: 19, y: 48 },
];

export interface Asset {
  symbol: string;
  name: string;
  allocation: number;
  color: string;
}

export const getPortfolioAllocation = (capital: number, risk: number): Asset[] => {
  // risk: 0 (conservative) to 100 (aggressive)
  const stockWeight = 0.3 + (risk / 100) * 0.4;
  const cryptoWeight = (risk / 100) * 0.25;
  const bondWeight = 1 - stockWeight - cryptoWeight;

  return [
    { symbol: "AAPL", name: "Apple Inc.", allocation: Math.round(stockWeight * 30), color: "hsl(217, 91%, 60%)" },
    { symbol: "MSFT", name: "Microsoft", allocation: Math.round(stockWeight * 25), color: "hsl(217, 91%, 50%)" },
    { symbol: "GOOGL", name: "Alphabet", allocation: Math.round(stockWeight * 20), color: "hsl(217, 91%, 40%)" },
    { symbol: "BTC", name: "Bitcoin", allocation: Math.round(cryptoWeight * 60), color: "hsl(35, 92%, 50%)" },
    { symbol: "ETH", name: "Ethereum", allocation: Math.round(cryptoWeight * 40), color: "hsl(250, 60%, 55%)" },
    { symbol: "BONDS", name: "US Treasury", allocation: Math.round(bondWeight * 60), color: "hsl(160, 84%, 39%)" },
    { symbol: "TIPS", name: "Inflation Protected", allocation: Math.round(bondWeight * 40), color: "hsl(160, 84%, 30%)" },
  ].filter(a => a.allocation > 0);
};

export const backtestAnnotations = [
  { index: 6, label: "Market drawdown detected → allocation adjusted" },
  { index: 8, label: "Recovery phase — exposure increased" },
  { index: 13, label: "Volatility spike → hedging activated" },
];

export const backtestMetrics = {
  totalReturn: 82,
  maxDrawdown: -18.4,
  sharpeRatio: 1.42,
};

export const formatCurrency = (value: number): string => {
  if (value >= 1000) {
    return `$${(value / 1000).toFixed(0)}k`;
  }
  return `$${value.toLocaleString()}`;
};
