import { useState, useEffect, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import { ArrowLeft, Play, Square, RefreshCcw, Check } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { useBacktestData, modelIdToProfile, type BacktestDay } from "@/hooks/useBacktestData";

const AI_MODELS = [
  { id: "low", name: "Modelo Conservador", fee: "6%", feeRate: 0.06, desc: "Bajo riesgo" },
  { id: "mid", name: "Modelo Dinámico", fee: "3%", feeRate: 0.03, desc: "Balance medio" },
  { id: "high", name: "Modelo Agresivo", fee: "1%", feeRate: 0.01, desc: "Alto riesgo" },
];

const REGIME_LABELS: Record<string, { label: string; color: string }> = {
  bull:    { label: "Bull 📈",   color: "text-success" },
  bear:    { label: "Bear 📉",   color: "text-red-500" },
  crisis:  { label: "Crisis ⚠️", color: "text-orange-500" },
  neutral: { label: "Neutral ⚖️", color: "text-muted-foreground" },
};

type DataPoint = { day: number; value: number; neto: number; feePaga: number };

function buildGameData(raw: BacktestDay[], capital: number, feeRate: number): DataPoint[] {
  if (raw.length === 0) return [];
  const scale = capital / raw[0].portfolio_value;
  return raw.map((d, i) => {
    const value = d.portfolio_value * scale;
    const ganancia = Math.max(0, value - capital);
    const feePaga = ganancia * feeRate;
    const neto = value - feePaga;
    return { day: i + 1, value, neto, feePaga };
  });
}

export default function Simulacion() {
  const location = useLocation();
  const navigate = useNavigate();

  const [userId, setUserId] = useState<string | null>(null);
  const [capitalInput, setCapitalInput] = useState<number>(6000);
  const [selectedModel, setSelectedModel] = useState(
    AI_MODELS.find((m) => m.id === location.state?.selectedModelId) || AI_MODELS[1],
  );
  const [isPlaying, setIsPlaying] = useState(false);
  const [cursor, setCursor] = useState(0);
  const [gameData, setGameData] = useState<DataPoint[]>([]);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);

  const { data: rawData, loading: loadingBacktest } = useBacktestData(selectedModel.id);

  const fullData = useRef<DataPoint[]>([]);
  useEffect(() => {
    if (rawData.length === 0) return;
    fullData.current = buildGameData(rawData, capitalInput, selectedModel.feeRate);
    if (cursor > 0) {
      setGameData(fullData.current.slice(0, cursor + 1));
    }
  }, [rawData, capitalInput, selectedModel.id, cursor]);

  // Intentar cargar sesión (opcional — funciona sin login)
  useEffect(() => {
    let mounted = true;
    const initSession = async () => {
      try {
        const { data } = await supabase.auth.getSession();
        if (data.session && mounted) {
          const currentUserId = data.session.user.id;
          setUserId(currentUserId);
          const { data: dbData } = await supabase
            .from("simulations")
            .select("*")
            .eq("user_id", currentUserId)
            .single();
          if (dbData) {
            if (dbData.capital_input) setCapitalInput(dbData.capital_input);
            if (dbData.selected_model_id) {
              const m = AI_MODELS.find(x => x.id === dbData.selected_model_id);
              if (m) setSelectedModel(m);
            }
            if (dbData.day_counter && dbData.game_data) {
              setCursor(dbData.day_counter);
            }
          }
        }
      } catch {
        // Sin sesión — funciona igual sin guardar en nube
      }
      if (mounted) setIsLoadingAuth(false);
    };
    initSession();
    return () => { mounted = false; };
  }, [navigate]);

  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setCursor((prev) => {
        const next = prev + 1;
        if (next >= fullData.current.length) {
          setIsPlaying(false);
          return prev;
        }
        setGameData(fullData.current.slice(0, next + 1));
        return next;
      });
    }, 300);
    return () => clearInterval(interval);
  }, [isPlaying]);

  useEffect(() => {
    if (isLoadingAuth || !userId || isPlaying || gameData.length === 0) return;
    supabase.from("simulations").upsert({
      user_id: userId,
      selected_model_id: selectedModel.id,
      day_counter: cursor,
      game_data: gameData,
      capital_input: capitalInput,
      is_playing: false,
    });
  }, [isPlaying, cursor, gameData, userId, isLoadingAuth, selectedModel.id, capitalInput]);

  const handleRestart = async () => {
    setIsPlaying(false);
    setCursor(0);
    setGameData([]);
    if (userId) {
      await supabase.from("simulations").upsert({
        user_id: userId,
        selected_model_id: selectedModel.id,
        day_counter: 0,
        game_data: [],
        capital_input: capitalInput,
        is_playing: false,
      });
    }
  };

  const handleModelChange = (model: typeof AI_MODELS[0]) => {
    setSelectedModel(model);
    handleRestart();
  };

  if (isLoadingAuth || loadingBacktest) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <span className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const current = gameData[gameData.length - 1] ?? { value: capitalInput, neto: capitalInput, feePaga: 0 };
  const isLosing = current.neto < capitalInput;
  const totalDays = fullData.current.length;
  const progressPct = totalDays > 0 ? (cursor / totalDays) * 100 : 0;

  // Métricas en tiempo real desde gameData
  const returnPct = capitalInput > 0 ? ((current.neto / capitalInput) - 1) * 100 : 0;
  let maxDD = 0;
  if (gameData.length > 1) {
    let peak = gameData[0].neto;
    for (const pt of gameData) {
      if (pt.neto > peak) peak = pt.neto;
      const dd = (pt.neto - peak) / peak;
      if (dd < maxDD) maxDD = dd;
    }
  }

  // Datos del día actual desde rawData (régimen, optimizador, allocations, confianza)
  const currentRaw: BacktestDay | null = cursor > 0 && cursor - 1 < rawData.length
    ? rawData[cursor - 1]
    : null;

  const regimeKey = (currentRaw?.regime ?? "neutral").toLowerCase();
  const regimeInfo = REGIME_LABELS[regimeKey] ?? { label: regimeKey, color: "text-foreground" };

  const topAllocations = currentRaw
    ? Object.entries(currentRaw.allocations)
        .filter(([, w]) => w > 0.005)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 5)
    : [];

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans">

      {/* Header */}
      <header className="p-6 border-b border-border flex items-center justify-between sticky top-0 bg-background/80 backdrop-blur-md z-10">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft size={16} />
          Volver al inicio
        </Link>
        <div className="flex bg-muted p-1 rounded-xl">
          {AI_MODELS.map((m) => (
            <button
              key={m.id}
              onClick={() => handleModelChange(m)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${selectedModel.id === m.id
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
                }`}
            >
              {m.name}
            </button>
          ))}
        </div>
      </header>

      <main className="flex-1 w-full max-w-7xl mx-auto p-6 md:p-10 grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-10">

        {/* Área del gráfico */}
        <div className="flex flex-col space-y-6">
          <div className="flex justify-between items-end">
            <div>
              <h2 className="text-sm font-medium text-muted-foreground">Tu Capital Neto Actual</h2>
              <div
                className={`text-5xl font-bold tracking-tight mt-2 flex items-baseline gap-3 ${isLosing ? "text-red-500" : "text-foreground"}`}
              >
                ${current.neto.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                {gameData.length > 1 && (
                  <span className={`text-lg font-medium ${returnPct >= 0 ? "text-success" : "text-red-500"}`}>
                    {returnPct >= 0 ? "+" : ""}{returnPct.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm text-muted-foreground">Día Operativo</div>
              <div className="text-2xl font-mono font-medium">
                {cursor} / {totalDays}
              </div>
            </div>
          </div>

          {/* Barra de progreso */}
          <div className="space-y-1">
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-300"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Inicio</span>
              <span>{Math.round(progressPct)}% completado</span>
              <span>Fin</span>
            </div>
          </div>

          <div className="bg-card w-full border border-border rounded-2xl h-[400px] p-6 flex flex-col relative overflow-hidden">
            {gameData.length === 0 ? (
              <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                Presiona Iniciar para reproducir el backtest real.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={gameData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                  <XAxis
                    dataKey="day"
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `Día ${v}`}
                    tick={{ fontSize: 12, fill: "hsl(220, 9%, 46%)" }}
                    minTickGap={30}
                  />
                  <YAxis
                    domain={["auto", "auto"]}
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 12, fill: "hsl(220, 9%, 46%)" }}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
                    width={50}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(0, 0%, 100%)",
                      border: "1px solid hsl(220, 13%, 91%)",
                      borderRadius: "12px",
                      boxShadow: "0 10px 15px -3px rgba(0,0,0,0.1)",
                      color: "#000",
                    }}
                    formatter={(value: number) => [`$${value.toFixed(2)}`, "Neto (Tuyo)"]}
                    labelFormatter={(label) => `Día Operable ${label}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="neto"
                    stroke="hsl(217, 91%, 60%)"
                    strokeWidth={3}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Panel de control */}
        <div className="space-y-4">
          <div className="bg-card border border-border rounded-2xl p-6">
            <div className="mb-6">
              <label className="text-sm font-medium text-muted-foreground mb-4 block">
                Inversión Ficticia Inicial
              </label>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground text-lg">$</span>
                <input
                  type="number"
                  value={capitalInput}
                  onChange={(e) => {
                    setCapitalInput(Number(e.target.value));
                    handleRestart();
                  }}
                  className="w-full bg-background border border-input rounded-xl h-14 pl-8 pr-4 text-xl font-medium focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>

            {/* Info del modelo */}
            <div className="space-y-3 mb-6">
              <div className="flex justify-between items-center text-sm border-b border-border pb-3">
                <span className="text-muted-foreground">Performance Fee</span>
                <span className="font-semibold">{selectedModel.fee} de ganancias</span>
              </div>
              <div className="flex justify-between items-center text-sm border-b border-border pb-3">
                <span className="text-muted-foreground">Perfil de Riesgo</span>
                <span className="font-medium text-foreground">{selectedModel.desc}</span>
              </div>
              <div className="flex justify-between items-center text-sm border-b border-border pb-3">
                <span className="text-muted-foreground">Datos del modelo</span>
                <span className="font-medium text-foreground">
                  {modelIdToProfile(selectedModel.id).replace("_", " ")}
                </span>
              </div>
              <div className="flex justify-between items-center text-sm border-b border-border pb-3">
                <span className="text-muted-foreground">Costo Pagado a I.A</span>
                <span className="font-medium text-red-500">${current.feePaga.toFixed(2)}</span>
              </div>
              {/* Régimen de mercado */}
              <div className="flex justify-between items-center text-sm border-b border-border pb-3">
                <span className="text-muted-foreground">Régimen Detectado</span>
                <span className={`font-semibold ${regimeInfo.color}`}>
                  {currentRaw ? regimeInfo.label : "—"}
                </span>
              </div>
              {/* Optimizador activo */}
              <div className="flex justify-between items-center text-sm border-b border-border pb-3">
                <span className="text-muted-foreground">Optimizador Activo</span>
                <span className="font-medium text-foreground text-right text-xs">
                  {currentRaw?.optimizer ?? "—"}
                </span>
              </div>
              {/* Confianza del modelo */}
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Confianza IA</span>
                <span className="font-medium text-foreground">
                  {currentRaw ? `${(currentRaw.confidence * 100).toFixed(0)}%` : "—"}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {isPlaying ? (
                <button
                  onClick={() => setIsPlaying(false)}
                  className="col-span-2 bg-red-500 hover:bg-red-600 text-white font-medium py-3.5 rounded-xl flex items-center justify-center gap-2 transition-colors duration-200"
                >
                  <Square fill="currentColor" size={16} /> Detener
                </button>
              ) : (
                <button
                  onClick={() => setIsPlaying(true)}
                  disabled={cursor >= totalDays - 1}
                  className="col-span-2 bg-foreground text-background hover:bg-foreground/90 font-medium py-3.5 rounded-xl flex items-center justify-center gap-2 transition-colors duration-200 disabled:opacity-40"
                >
                  <Play fill="currentColor" size={16} />
                  {cursor === 0 ? "Iniciar IA" : cursor >= totalDays - 1 ? "Simulación completa" : "Continuar"}
                </button>
              )}
              <button
                onClick={handleRestart}
                className="col-span-2 mt-2 bg-muted hover:bg-muted/80 text-foreground font-medium py-3.5 rounded-xl flex items-center justify-center gap-2 transition-colors border border-border"
              >
                <RefreshCcw size={16} /> Reiniciar de cero
              </button>
            </div>
          </div>

          {/* Métricas en tiempo real */}
          {gameData.length > 1 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-card border border-border rounded-2xl p-5 space-y-3"
            >
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Rendimiento en Tiempo Real
              </h4>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Retorno</p>
                  <p className={`text-lg font-bold ${returnPct >= 0 ? "text-success" : "text-red-500"}`}>
                    {returnPct >= 0 ? "+" : ""}{returnPct.toFixed(1)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Max DD</p>
                  <p className="text-lg font-bold text-red-400">
                    {(maxDD * 100).toFixed(1)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Confianza</p>
                  <p className="text-lg font-bold text-foreground">
                    {currentRaw ? `${(currentRaw.confidence * 100).toFixed(0)}%` : "—"}
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* Top Allocations del día actual */}
          {topAllocations.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-card border border-border rounded-2xl p-5"
            >
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-4">
                Pesos Actuales (Top 5)
              </h4>
              <div className="space-y-2.5">
                {topAllocations.map(([ticker, weight]) => (
                  <div key={ticker} className="flex items-center gap-3">
                    <span className="text-xs font-medium text-foreground w-10 shrink-0">{ticker}</span>
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all duration-500"
                        style={{ width: `${weight * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground w-10 text-right shrink-0">
                      {(weight * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          <div className="bg-primary/5 border border-primary/20 rounded-2xl p-5">
            <h4 className="text-sm font-medium text-primary flex items-center gap-2 mb-2">
              <Check size={16} /> Datos Reales de Backtest
            </h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Esta simulación reproduce el backtest real del modelo ML ({selectedModel.desc}).
              El fee del {selectedModel.fee} se descuenta solo sobre ganancias positivas.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
