import { useState, useCallback } from "react";
import HeroSection from "@/components/HeroSection";
import OnboardingFlow from "@/components/OnboardingFlow";
import BacktestingReveal from "@/components/BacktestingReveal";
import ConversionSection from "@/components/ConversionSection";

const Index = () => {
  const [capital, setCapital] = useState(25000);
  const [risk, setRisk] = useState(50);

  const handleCapitalChange = useCallback((c: number) => setCapital(c), []);
  const handleRiskChange = useCallback((r: number) => setRisk(r), []);

  return (
    <div className="min-h-screen bg-background">
      <HeroSection />
      <OnboardingFlow
        capital={capital}
        risk={risk}
        onCapitalChange={handleCapitalChange}
        onRiskChange={handleRiskChange}
      />
      <BacktestingReveal capital={capital} risk={risk} />
      <ConversionSection />
    </div>
  );
};

export default Index;
