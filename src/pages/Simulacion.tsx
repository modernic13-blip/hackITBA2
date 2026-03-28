import { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import { ArrowLeft, Play, Square, RefreshCcw, Check } from "lucide-react";
import { supabase } from "@/lib/supabase";

const AI_MODELS = [
    { id: "low", name: "Modelo Conservador", fee: "1%", multiplier: 1.0005, volatility: 0.002, desc: "Bajo riesgo" },
    { id: "mid", name: "Modelo Dinámico", fee: "10%", multiplier: 1.002, volatility: 0.01, desc: "Balance medio" },
    { id: "high", name: "Modelo Agresivo", fee: "30%", multiplier: 1.005, volatility: 0.03, desc: "Alto riesgo" },
];

type DataPoint = { day: number; value: number; neto: number; feePaga: number };

export default function Simulacion() {
    const location = useLocation();
    const navigate = useNavigate();
    const [userId, setUserId] = useState<string | null>(null);
    const [capitalInput, setCapitalInput] = useState<number>(6000);
    const [selectedModel, setSelectedModel] = useState(
        AI_MODELS.find(m => m.id === location.state?.selectedModelId) || AI_MODELS[1]
    );
    const [isPlaying, setIsPlaying] = useState(false);
    const [gameData, setGameData] = useState<DataPoint[]>([]);
    const [dayCounter, setDayCounter] = useState(0);
    const [isLoadingData, setIsLoadingData] = useState(true);

    // Auth Guard & Fetch DB
    useEffect(() => {
        let mounted = true;
        const loadUserAndData = async () => {
            const { data } = await supabase.auth.getSession();
            if (!data.session) {
                navigate("/login");
                return;
            }
            const uid = data.session.user.id;
            setUserId(uid);

            // Fetch cloud progress
            const { data: dbData } = await supabase
                .from('simulations')
                .select('*')
                .eq('user_id', uid)
                .single();

            if (mounted) {
                if (dbData) {
                    setGameData(dbData.game_data || []);
                    setDayCounter(dbData.day_counter || 0);
                    setCapitalInput(dbData.capital_input || 6000);
                    const model = AI_MODELS.find(m => m.id === dbData.selected_model_id);
                    if (model) setSelectedModel(model);
                }
                setIsLoadingData(false);
            }
        };
        loadUserAndData();
        return () => { mounted = false; };
    }, [navigate]);

    // Save logic
    const saveToSupabase = async (overrideData?: any) => {
        if (!userId) return;
        await supabase.from('simulations').upsert({
            user_id: userId,
            selected_model_id: selectedModel.id,
            day_counter: overrideData?.dayCounter ?? dayCounter,
            game_data: overrideData?.gameData ?? gameData,
            capital_input: capitalInput,
            is_playing: false
        });
    };

    // Auto-save debounced / on pause
    useEffect(() => {
        if (isLoadingData || !userId) return;

        let interval: NodeJS.Timeout | null = null;
        if (isPlaying) {
            // Backup as it runs every 5s so we don't spam Supabase API linearly on every tick
            interval = setInterval(() => {
                saveToSupabase();
            }, 5000);
        } else if (!isPlaying && gameData.length > 0) {
            // Save immediately when paused 
            saveToSupabase();
        }

        return () => {
            if (interval) clearInterval(interval);
        };
    }, [isPlaying, gameData, dayCounter, selectedModel, capitalInput, isLoadingData]);

    // Cleanup localstorage as it's legacy
    useEffect(() => {
        localStorage.removeItem("smart_capital_simulation_v2");
    }, []);

    // Game Loop
    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (isPlaying) {
            interval = setInterval(() => {
                setDayCounter(prev => {
                    const newDay = prev + 1;
                    setGameData(current => {
                        const last = current.length > 0 ? current[current.length - 1] : { day: 0, value: capitalInput, neto: capitalInput, feePaga: 0 };

                        let baseGrowth = (selectedModel.multiplier - 1);
                        let randomWalk = (Math.random() - 0.45) * selectedModel.volatility;
                        let dailyReturn = baseGrowth + randomWalk;

                        let newValue = last.value * (1 + dailyReturn);
                        if (newValue < capitalInput * 0.1) newValue = capitalInput * 0.1;

                        const gananciaCruda = newValue - capitalInput;
                        const hasProfit = gananciaCruda > 0;
                        const feePercentage = parseFloat(selectedModel.fee) / 100;

                        let curFeePaga = hasProfit ? gananciaCruda * feePercentage : 0;
                        let curNeto = newValue - curFeePaga;

                        const nextNodes = [...current, { day: newDay, value: newValue, neto: curNeto, feePaga: curFeePaga }];
                        if (nextNodes.length > 100) nextNodes.shift();
                        return nextNodes;
                    });
                    return newDay;
                });
            }, 300);
        }
        return () => clearInterval(interval);
    }, [isPlaying, selectedModel, capitalInput]);

    const handleRestart = async () => {
        setIsPlaying(false);
        setGameData([]);
        setDayCounter(0);
        await saveToSupabase({ dayCounter: 0, gameData: [] });
    };

    if (isLoadingData) {
        return <div className="min-h-screen flex items-center justify-center bg-background"><span className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin"></span></div>;
    }

    const currentData = gameData.length > 0 ? gameData[gameData.length - 1] : { value: capitalInput, neto: capitalInput, feePaga: 0 };
    const maxProfit = gameData.length > 0 ? Math.max(...gameData.map(d => d.neto)) : capitalInput;
    const isLosing = currentData.neto < capitalInput;

    return (
        <div className="min-h-screen bg-background text-foreground flex flex-col font-sans">
            <header className="p-6 border-b border-border flex items-center justify-between sticky top-0 bg-background/80 backdrop-blur-md z-10">
                <Link to="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors">
                    <ArrowLeft size={16} />
                    Volver al inicio
                </Link>
                <div className="flex bg-muted p-1 rounded-xl">
                    {AI_MODELS.map(m => (
                        <button
                            key={m.id}
                            onClick={() => { setSelectedModel(m); handleRestart(); }}
                            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${selectedModel.id === m.id ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                        >
                            {m.name}
                        </button>
                    ))}
                </div>
            </header>

            <main className="flex-1 w-full max-w-7xl mx-auto p-6 md:p-10 grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-10">

                {/* Visualizer Area */}
                <div className="flex flex-col space-y-6">
                    <div className="flex justify-between items-end">
                        <div>
                            <h2 className="text-sm font-medium text-muted-foreground">Tu Capital Neto Actual</h2>
                            <div className={`text-5xl font-bold tracking-tight mt-2 flex items-baseline gap-3 ${isLosing ? 'text-red-500' : 'text-foreground'}`}>
                                ${currentData.neto.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </div>
                        </div>
                        <div className="text-right">
                            <div className="text-sm text-muted-foreground">Día Operativo</div>
                            <div className="text-2xl font-mono font-medium">{dayCounter}</div>
                        </div>
                    </div>

                    <div className="bg-card w-full border border-border rounded-2xl h-[400px] p-6 flex flex-col relative overflow-hidden">
                        {gameData.length === 0 ? (
                            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                                Presiona Iniciar para ver el mercado.
                            </div>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={gameData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                                    <XAxis dataKey="day" axisLine={false} tickLine={false} tickFormatter={(v) => `Día ${v}`} tick={{ fontSize: 12, fill: "hsl(220, 9%, 46%)" }} minTickGap={30} />
                                    <YAxis domain={['auto', 'auto']} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "hsl(220, 9%, 46%)" }} tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} width={50} />
                                    <Tooltip
                                        contentStyle={{ background: "hsl(0, 0%, 100%)", border: "1px solid hsl(220, 13%, 91%)", borderRadius: "12px", boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1)", color: "#000" }}
                                        formatter={(value: number) => [`$${value.toFixed(2)}`, "Neto (Tuyo)"]}
                                        labelFormatter={(label) => `Día Operable ${label}`}
                                    />
                                    <Line type="monotone" dataKey="neto" stroke="hsl(217, 91%, 60%)" strokeWidth={3} dot={false} isAnimationActive={false} />
                                </LineChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>

                {/* Control Panel */}
                <div className="space-y-6">
                    <div className="bg-card border border-border rounded-2xl p-6">
                        <div className="mb-8">
                            <label className="text-sm font-medium text-muted-foreground mb-4 block">Inversión Ficticia Inicial</label>
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

                        <div className="space-y-4 mb-8">
                            <div className="flex justify-between items-center text-sm border-b border-border pb-3">
                                <span className="text-muted-foreground">Performance Fee Automático</span>
                                <span className="font-semibold">{selectedModel.fee} de las ganancias</span>
                            </div>
                            <div className="flex justify-between items-center text-sm border-b border-border pb-3">
                                <span className="text-muted-foreground">Volatilidad Estructurada</span>
                                <span className="font-medium text-foreground">{selectedModel.desc}</span>
                            </div>
                            <div className="flex justify-between items-center text-sm">
                                <span className="text-muted-foreground">Costo Pagado a I.A</span>
                                <span className="font-medium text-red-500">${currentData.feePaga.toFixed(2)}</span>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            {isPlaying ? (
                                <button
                                    onClick={() => setIsPlaying(false)}
                                    className="col-span-2 bg-red-500 hover:bg-red-600 text-white font-medium py-3.5 rounded-xl flex items-center justify-center gap-2 transition-colors duration-200"
                                >
                                    <Square fill="currentColor" size={16} /> Detener Simulación
                                </button>
                            ) : (
                                <button
                                    onClick={() => setIsPlaying(true)}
                                    className="col-span-2 bg-foreground text-background hover:bg-foreground/90 font-medium py-3.5 rounded-xl flex items-center justify-center gap-2 transition-colors duration-200"
                                >
                                    <Play fill="currentColor" size={16} /> Iniciar IA
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

                    <div className="bg-primary/5 border border-primary/20 rounded-2xl p-6">
                        <h4 className="text-sm font-medium text-primary flex items-center gap-2 mb-2">
                            <Check size={16} /> Simulación Autónoma Activa
                        </h4>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                            A medida que avanzan los días operables, se te descontará el {selectedModel.fee} automáticamente única y exclusivamente si los retornos son positivos.
                        </p>
                    </div>
                </div>
            </main>
        </div>
    );
}
