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
  const riskLabel = risk < 30 ? "Conservador" : risk < 70 ? "Balanceado" : "Agresivo";

  const handleCapitalInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value.replace(/[^0-9]/g, ""), 10);
    onCapitalChange(isNaN(val) ? 0 : val);
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
                  Definamos tu posición.
                </h2>
                <p className="mt-3 text-muted-foreground text-sm">
                  ¿Cuánto capital te gustaría asignar?
                </p>
              </div>
              <div className="space-y-6">
                <div>
                  <div className="relative inline-flex items-center">
                    <span className="absolute left-6 text-5xl font-semibold text-muted-foreground pointer-events-none">$</span>
                    <input
                      type="text"
                      inputMode="numeric"
                      value={capital === 0 ? "" : capital}
                      onChange={handleCapitalInput}
                      className="bg-transparent border-none outline-none text-5xl font-semibold text-foreground tracking-tight w-full py-2 pl-16 focus:ring-0 placeholder:text-muted-foreground/30"
                      placeholder="6000"
                    />
                  </div>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground pt-4">
                  <span>Introduce tu capital inicial (Ej. $6000)</span>
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
                  ¿Cómo manejas la volatilidad?
                </h2>
                <p className="mt-3 text-muted-foreground text-sm">
                  Define tu nivel de comodidad con las fluctuaciones del mercado.
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
                  <span>Conservador</span>
                  <span>Agresivo</span>
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
              Tu distribución
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
