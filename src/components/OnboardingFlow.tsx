import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getPortfolioAllocation, formatCurrency, type Asset } from "@/data/mockData";
import { Slider } from "@/components/ui/slider";

const microcopyPhrases = [
  "Adjusting your allocation…",
  "Rebalancing based on your profile…",
  "Optimizing risk-return ratio…",
];

const AssetCard = ({ asset, index }: { asset: Asset; index: number }) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -8 }}
    transition={{ duration: 0.4, delay: index * 0.06, ease: "easeOut" }}
    className="flex items-center justify-between py-3 px-4 rounded-lg border border-border/60 bg-card"
  >
    <div className="flex items-center gap-3">
      <div
        className="w-2 h-2 rounded-full"
        style={{ backgroundColor: asset.color }}
      />
      <div>
        <span className="text-sm font-medium text-foreground">{asset.symbol}</span>
        <span className="ml-2 text-xs text-muted-foreground">{asset.name}</span>
      </div>
    </div>
    <span className="text-sm font-medium text-foreground tabular-nums">{asset.allocation}%</span>
  </motion.div>
);

const OnboardingFlow = ({ onComplete }: { onComplete: (capital: number, risk: number) => void }) => {
  const [step, setStep] = useState(0);
  const [capital, setCapital] = useState(25000);
  const [risk, setRisk] = useState(50);
  const [microcopy, setMicrocopy] = useState("");
  const [assets, setAssets] = useState<Asset[]>(getPortfolioAllocation(25000, 50));

  const updatePortfolio = useCallback((newCapital: number, newRisk: number) => {
    setAssets(getPortfolioAllocation(newCapital, newRisk));
    const phrase = microcopyPhrases[Math.floor(Math.random() * microcopyPhrases.length)];
    setMicrocopy(phrase);
    setTimeout(() => setMicrocopy(""), 2000);
  }, []);

  const handleCapitalChange = (value: number[]) => {
    const v = value[0];
    setCapital(v);
    updatePortfolio(v, risk);
  };

  const handleRiskChange = (value: number[]) => {
    const v = value[0];
    setRisk(v);
    updatePortfolio(capital, v);
  };

  const riskLabel = risk < 30 ? "Conservative" : risk < 70 ? "Balanced" : "Aggressive";

  return (
    <section className="min-h-screen flex items-center justify-center px-6 py-24">
      <div className="w-full max-w-4xl">
        <AnimatePresence mode="wait">
          {step === 0 && (
            <motion.div
              key="step-0"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.5 }}
              className="space-y-16"
            >
              <div className="text-center">
                <h2 className="text-3xl sm:text-4xl font-semibold text-foreground">
                  Let's define your position.
                </h2>
                <p className="mt-3 text-muted-foreground text-sm">
                  How much capital would you like to allocate?
                </p>
              </div>

              <div className="max-w-lg mx-auto space-y-8">
                <div className="text-center">
                  <span className="text-5xl font-semibold text-foreground tabular-nums">
                    {capital >= 100000 ? "$100k+" : `$${capital.toLocaleString()}`}
                  </span>
                </div>
                <Slider
                  value={[capital]}
                  onValueChange={handleCapitalChange}
                  min={1000}
                  max={100000}
                  step={1000}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>$1,000</span>
                  <span>$100,000+</span>
                </div>
              </div>

              <div className="text-center">
                <button
                  onClick={() => setStep(1)}
                  className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors duration-200"
                >
                  Continue
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 12H5m7 7l7-7-7-7" />
                  </svg>
                </button>
              </div>
            </motion.div>
          )}

          {step === 1 && (
            <motion.div
              key="step-1"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.5 }}
              className="space-y-12"
            >
              <div className="text-center">
                <h2 className="text-3xl sm:text-4xl font-semibold text-foreground">
                  How do you handle volatility?
                </h2>
                <p className="mt-3 text-muted-foreground text-sm">
                  Define your comfort with market fluctuations.
                </p>
              </div>

              <div className="max-w-lg mx-auto space-y-8">
                <div className="text-center">
                  <span className="text-2xl font-semibold text-foreground">{riskLabel}</span>
                </div>
                <Slider
                  value={[risk]}
                  onValueChange={handleRiskChange}
                  min={0}
                  max={100}
                  step={1}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Conservative</span>
                  <span>Aggressive</span>
                </div>
              </div>

              {/* Live portfolio preview */}
              <div className="max-w-lg mx-auto space-y-3">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-xs text-muted-foreground uppercase tracking-wider">Your allocation</span>
                  <AnimatePresence>
                    {microcopy && (
                      <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="text-xs text-accent"
                      >
                        {microcopy}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </div>
                <AnimatePresence mode="popLayout">
                  {assets.map((asset, i) => (
                    <AssetCard key={asset.symbol} asset={asset} index={i} />
                  ))}
                </AnimatePresence>
              </div>

              <div className="text-center pt-4">
                <button
                  onClick={() => onComplete(capital, risk)}
                  className="inline-flex items-center gap-2 rounded-full bg-foreground text-background px-8 py-4 text-sm font-medium transition-all duration-300 hover:opacity-90 hover:scale-[1.02]"
                >
                  See your backtest results
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                  </svg>
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
};

export default OnboardingFlow;
