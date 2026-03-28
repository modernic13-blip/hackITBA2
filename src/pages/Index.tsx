import { useState, useRef } from "react";
import HeroSection from "@/components/HeroSection";
import OnboardingFlow from "@/components/OnboardingFlow";
import BacktestingReveal from "@/components/BacktestingReveal";
import ConversionSection from "@/components/ConversionSection";

type AppStage = "hero" | "onboarding" | "backtest" | "conversion";

const Index = () => {
  const [stage, setStage] = useState<AppStage>("hero");
  const [capital, setCapital] = useState(25000);
  const [risk, setRisk] = useState(50);
  const mainRef = useRef<HTMLDivElement>(null);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleCTA = () => {
    setStage("onboarding");
    scrollToTop();
  };

  const handleOnboardingComplete = (c: number, r: number) => {
    setCapital(c);
    setRisk(r);
    setStage("backtest");
    scrollToTop();
  };

  return (
    <div ref={mainRef} className="min-h-screen bg-background">
      {stage === "hero" && <HeroSection onCTA={handleCTA} />}
      {stage === "onboarding" && <OnboardingFlow onComplete={handleOnboardingComplete} />}
      {stage === "backtest" && (
        <>
          <BacktestingReveal capital={capital} risk={risk} />
          <ConversionSection />
        </>
      )}
    </div>
  );
};

export default Index;
