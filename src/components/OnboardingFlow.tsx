import { useCallback } from "react";
import { motion } from "framer-motion";
import { getPortfolioAllocation, type Asset } from "@/data/mockData";
import { Slider } from "@/components/ui/slider";

interface OnboardingFlowProps {
  capital: number;
  risk: number;
  onCapitalChange: (capital: number) => void;
  onRiskChange: (risk: number) => void;
}

const AssetCard = ({ asset, index }: { asset: Asset; index: number }) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.4, delay: index * 0.06, ease: "easeOut" }}
    className="flex items-center justify-between py-3 px-4 rounded-lg border border-border/60 bg-card"
  >
    <div className="flex items-center gap-3">
      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: asset.color }} />
      <div>
        <span className="text-sm font-medium text-foreground">{asset.symbol}</span>
        <span className="ml-2 text-xs text-muted-foreground">{asset.name}</span>
      </div>
    </div>
    <span className="text-sm font-medium text-foreground tabular-nums">{asset.allocation}%</span>
  </motion.div>
);

const OnboardingFlow = ({ capital, risk, onCapitalChange, onRiskChange }: OnboardingFlowProps) => {
  const assets = getPortfolioAllocation(capital, risk);
  const riskLabel = risk < 30 ? "Conservative" : risk < 70 ? "Balanced" : "Aggressive";

  const handleCapitalChange = useCallback((value: number[]) => {
    onCapitalChange(value[0]);
  }, [onCapitalChange]);

  const handleRiskChange = useCallback((value: number[]) => {
    onRiskChange(value[0]);
  }, [onRiskChange]);

  return (
    <section className="min-h-screen flex items-center justify-center px-6 py-24">
      <div className="w-full max-w-4xl">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-24">
          {/* Left: Controls */}
          <div className="space-y-16">
            {/* Capital */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 0.6 }}
              className="space-y-8"
            >
              <div>
                <h2 className="text-3xl sm:text-4xl font-semibold text-foreground">
                  Let's define your position.
                </h2>
                <p className="mt-3 text-muted-foreground text-sm">
                  How much capital would you like to allocate?
                </p>
              </div>
              <div className="space-y-6">
                <div>
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
            </motion.div>

            {/* Risk */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 0.6 }}
              className="space-y-8"
            >
              <div>
                <h2 className="text-2xl sm:text-3xl font-semibold text-foreground">
                  How do you handle volatility?
                </h2>
                <p className="mt-3 text-muted-foreground text-sm">
                  Define your comfort with market fluctuations.
                </p>
              </div>
              <div className="space-y-6">
                <span className="text-2xl font-semibold text-foreground">{riskLabel}</span>
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
            </motion.div>
          </div>

          {/* Right: Live portfolio preview */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="space-y-3 lg:sticky lg:top-24 lg:self-start"
          >
            <span className="text-xs text-muted-foreground uppercase tracking-wider">
              Your allocation
            </span>
            <div className="space-y-2 mt-4">
              {assets.map((asset, i) => (
                <AssetCard key={asset.symbol} asset={asset} index={i} />
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
};

export default OnboardingFlow;
