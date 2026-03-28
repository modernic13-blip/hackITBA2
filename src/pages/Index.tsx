import { useState, useCallback, useEffect } from "react";
import HeroSection from "@/components/HeroSection";
import OnboardingFlow from "@/components/OnboardingFlow";
import BacktestingReveal from "@/components/BacktestingReveal";
import ConversionSection from "@/components/ConversionSection";
import { Link } from "react-router-dom";
import { supabase } from "@/lib/supabase";
import { UserCircle } from "lucide-react";

const AuthHeader = () => {
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setUser(data.session?.user));
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_, session) => {
      setUser(session?.user);
    });
    return () => subscription.unsubscribe();
  }, []);

  return (
    <div className="absolute top-0 w-full p-6 flex justify-end z-50 pointer-events-auto">
      {user ? (
        <Link to="/dashboard" className="flex items-center gap-3 bg-card border border-border px-5 py-2.5 rounded-full hover:bg-muted transition-colors shadow-sm">
          <span className="text-sm font-medium">{user.user_metadata?.full_name?.split(' ')[0] || "Mi Panel"}</span>
          {user.user_metadata?.avatar_url ? (
            <img src={user.user_metadata.avatar_url} alt="Avatar" className="w-7 h-7 rounded-full" />
          ) : (
            <UserCircle size={24} className="text-muted-foreground" />
          )}
        </Link>
      ) : (
        <Link to="/login" className="text-sm font-medium border border-border bg-card/50 backdrop-blur-md hover:bg-muted px-8 py-3 rounded-full transition-colors shadow-sm">
          Ingresar
        </Link>
      )}
    </div>
  );
};

const Index = () => {
  const [capital, setCapital] = useState(25000);
  const [risk, setRisk] = useState(50);

  const handleCapitalChange = useCallback((c: number) => setCapital(c), []);
  const handleRiskChange = useCallback((r: number) => setRisk(r), []);

  return (
    <div className="min-h-screen bg-background relative">
      <AuthHeader />
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
