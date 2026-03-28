export interface Asset {
  symbol: string;
  name: string;
  allocation: number;
  color: string;
}

export const getPortfolioAllocation = (capital: number, risk: number): Asset[] => {
  const stockWeight  = 0.3 + (risk / 100) * 0.4;
  const cryptoWeight = (risk / 100) * 0.25;
  const bondWeight   = 1 - stockWeight - cryptoWeight;

  return [
    { symbol: "AAPL",  name: "Apple Inc.",          allocation: Math.round(stockWeight * 30),  color: "hsl(217, 91%, 60%)" },
    { symbol: "MSFT",  name: "Microsoft",            allocation: Math.round(stockWeight * 25),  color: "hsl(217, 91%, 50%)" },
    { symbol: "GOOGL", name: "Alphabet",             allocation: Math.round(stockWeight * 20),  color: "hsl(217, 91%, 40%)" },
    { symbol: "BTC",   name: "Bitcoin",              allocation: Math.round(cryptoWeight * 60), color: "hsl(35, 92%, 50%)"  },
    { symbol: "ETH",   name: "Ethereum",             allocation: Math.round(cryptoWeight * 40), color: "hsl(250, 60%, 55%)" },
    { symbol: "BONDS", name: "US Treasury",          allocation: Math.round(bondWeight * 60),   color: "hsl(160, 84%, 39%)" },
    { symbol: "TIPS",  name: "Inflation Protected",  allocation: Math.round(bondWeight * 40),   color: "hsl(160, 84%, 30%)" },
  ].filter(a => a.allocation > 0);
};
