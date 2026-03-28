import { useState, useCallback } from "react";
import HeroSection from "@/components/HeroSection";
import OnboardingFlow from "@/components/OnboardingFlow";
import BacktestingReveal from "@/components/BacktestingReveal";
import AllocationChart from "@/components/AllocationChart";
import ConversionSection from "@/components/ConversionSection";
import { UserNav } from "@/components/UserNav";
import { useBacktestData } from "@/hooks/useBacktestData";

const Index = () => {
  const [capital, setCapital] = useState(25000);
  const [risk, setRisk] = useState(50);

  const handleCapitalChange = useCallback((c: number) => setCapital(c), []);
  const handleRiskChange = useCallback((r: number) => setRisk(r), []);

  // Cargar datos para AllocationChart
  const { data: backtestData } = useBacktestData(risk);

  return (
    <div className="min-h-screen bg-background relative">
      <UserNav />
      <HeroSection />
      <OnboardingFlow
        capital={capital}
        risk={risk}
        onCapitalChange={handleCapitalChange}
        onRiskChange={handleRiskChange}
      />
      <BacktestingReveal capital={capital} risk={risk} />
      <AllocationChart data={backtestData} />
      <ConversionSection />
    </div>
  );
};

export default Index;
