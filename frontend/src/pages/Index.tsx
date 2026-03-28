import { useState, useCallback } from "react";
import HeroSection from "@/components/HeroSection";
import AllocationChart from "@/components/AllocationChart";
import ConversionSection from "@/components/ConversionSection";
import { UserNav } from "@/components/UserNav";
import { useBacktestData } from "@/hooks/useBacktestData";
import { Slider } from "@/components/ui/slider";

const Index = () => {
  // We keep Capital statically for the Index demonstration 
  const capital = 25000;
  const [risk, setRisk] = useState(50);

  const handleRiskChange = useCallback((value: number[]) => setRisk(value[0]), []);
  const riskLabel = risk < 34 ? "Conservador" : risk < 67 ? "Balanceado" : "Agresivo";

  // Cargar datos para AllocationChart
  const { data: backtestData } = useBacktestData(risk);

  return (
    <div className="min-h-screen bg-background relative">
      <UserNav />
      <HeroSection />

      {/* Risk Slider Inject */}
      <section className="pt-24 pb-8 flex justify-center px-6">
        <div className="w-full max-w-xl bg-card border border-border rounded-2xl p-8 space-y-6 shadow-sm">
          <div className="text-center">
            <h3 className="text-xl font-semibold mb-2">Seleccioná tu nivel de riesgo</h3>
            <p className="text-muted-foreground text-sm">Visualizá cómo reacciona nuestro modelo a los cambios de volatilidad de tu portafolio.</p>
          </div>
          <div className="space-y-4 pt-4">
            <div className="flex justify-between items-center text-sm font-medium">
              <span className="text-muted-foreground">Perfil de Inversión</span>
              <span className="text-primary text-lg">{riskLabel}</span>
            </div>
            <Slider
              value={[risk]}
              onValueChange={handleRiskChange}
              min={0}
              max={100}
              step={1}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-muted-foreground pt-1">
              <span>Más Conservador</span>
              <span>Más Arriesgado</span>
            </div>
          </div>
        </div>
      </section>

      <AllocationChart data={backtestData} />
      <ConversionSection />
    </div>
  );
};

export default Index;
