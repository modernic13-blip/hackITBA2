import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import { ArrowLeft, Play, Square, RefreshCcw, Check } from "lucide-react";

const AI_MODELS = [
    { id: "low", name: "Modelo Conservador", fee: "1%", desc: "Dedicamos el 1% de tus ganancias. Estable, ideal para empezar.", multiplier: 1.0005, volatility: 0.002, features: ["Bajo riesgo", "Retiros gratis", "Soporte 24/7"] },
    { id: "mid", name: "Modelo Dinámico", fee: "10%", desc: "Dedicamos el 10% de tus ganancias. Balance perfecto riesgo-retorno.", multiplier: 1.002, volatility: 0.01, features: ["Volatilidad media", "Ajustes diarios", "Prioridad de red"] },
    { id: "high", name: "Modelo Agresivo", fee: "30%", desc: "Dedicamos el 30% de tus ganancias. Más poderoso. Da más plata.", multiplier: 1.005, volatility: 0.03, features: ["Alto riesgo", "Algoritmo avanzado", "Asesor IA VIP"] },
];

type DataPoint = { day: number; value: number; neto: number; feePaga: number };

export default function Simulacion() {
    const [capitalInput, setCapitalInput] = useState<number>(6000);
    const [selectedModel, setSelectedModel] = useState(AI_MODELS[1]);
    const [isPlaying, setIsPlaying] = useState(false);
    const [gameData, setGameData] = useState<DataPoint[]>([]);
    const [dayCounter, setDayCounter] = useState(0);

    // Initialize or load from local storage
    useEffect(() => {
        const saved = localStorage.getItem("smart_capital_simulation_v2");
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                if (parsed.data && parsed.data.length > 0) {
                    setGameData(parsed.data);
                    setDayCounter(parsed.data[parsed.data.length - 1].day);
                    setCapitalInput(parsed.data[0].value);
                }
            } catch (e) {
                console.error("Local storage error");
            }
        } else {
            resetSimulation();
        }
    }, []);

    // Save to local storage on change
    useEffect(() => {
        if (gameData.length > 0) {
            localStorage.setItem("smart_capital_simulation_v2", JSON.stringify({ data: gameData }));
        }
    }, [gameData]);

    // Game Loop
    useEffect(() => {
        if (!isPlaying) return;

        const interval = setInterval(() => {
            setGameData(prev => {
                const currentData = prev.length > 0 ? prev : [{ day: 0, value: capitalInput, neto: capitalInput, feePaga: 0 }];
                const lastPoint = currentData[currentData.length - 1];

                // AI Decition (Random Variance + Model Multiplier)
                const marketNoise = (Math.random() * 2 - 1) * selectedModel.volatility;
                const grossValue = lastPoint.value * (selectedModel.multiplier + marketNoise);

                // Calculate Fees on Profit
                let currentNeto = grossValue;
                let diff = grossValue - capitalInput;
                let feeAmount = 0;

                if (diff > 0) {
                    const feeRate = parseInt(selectedModel.fee) / 100;
                    feeAmount = diff * feeRate;
                    currentNeto = grossValue - feeAmount;
                }

                const newPoint = {
                    day: lastPoint.day + 1,
                    value: Math.max(0, grossValue),
                    neto: Math.max(0, currentNeto),
                    feePaga: Math.max(0, feeAmount)
                };

                setDayCounter(newPoint.day);
                return [...currentData, newPoint];
            });
        }, 500); // 1 Day = 0.5s

        return () => clearInterval(interval);
    }, [isPlaying, capitalInput, selectedModel]);

    const resetSimulation = () => {
        setIsPlaying(false);
        setDayCounter(0);
        setGameData([{ day: 0, value: capitalInput, neto: capitalInput, feePaga: 0 }]);
    };

    const currentNeto = gameData.length > 0 ? gameData[gameData.length - 1].neto : capitalInput;
    const currentFee = gameData.length > 0 ? gameData[gameData.length - 1].feePaga : 0;
    const profit = currentNeto - capitalInput;
    const profitPercentage = ((profit / capitalInput) * 100).toFixed(2);

    return (
        <div className="min-h-screen bg-background text-foreground flex flex-col">
            {/* Header */}
            <header className="p-6 flex items-center justify-between border-b border-border/40">
                <Link to="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors">
                    <ArrowLeft size={16} />
                    Volver
                </Link>
                <div className="font-semibold text-sm tracking-widest uppercase opacity-70">Trading Game AI</div>
                <div className="w-16"></div> {/* Spacer */}
            </header>

            <main className="flex-1 max-w-7xl w-full mx-auto p-6 lg:p-12">

                {/* Pricing Header */}
                {!isPlaying && dayCounter === 0 && (
                    <div className="text-center max-w-2xl mx-auto mb-16">
                        <h1 className="text-3xl sm:text-4xl font-semibold mb-4">Elige tu IA de Inversión</h1>
                        <p className="text-muted-foreground">
                            Solo cobramos un porcentaje de tus ganancias. Si tú no ganas, nosotros tampoco. Empecemos con tu simulación.
                        </p>
                    </div>
                )}

                {/* Pricing Cards */}
                <section className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-16">
                    {AI_MODELS.map(model => (
                        <div
                            key={model.id}
                            onClick={() => !isPlaying && setSelectedModel(model)}
                            className={`relative flex flex-col p-6 rounded-2xl border transition-all cursor-pointer ${selectedModel.id === model.id
                                    ? "bg-card border-primary ring-1 ring-primary shadow-lg scale-[1.02]"
                                    : "bg-card border-border hover:border-primary/50"
                                } ${isPlaying ? 'opacity-50 cursor-not-allowed' : ''}`}
                        >
                            {selectedModel.id === model.id && (
                                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground text-xs font-bold px-3 py-1 rounded-full">
                                    Seleccionado
                                </div>
                            )}
                            <h3 className="text-lg font-medium">{model.name}</h3>
                            <div className="mt-4 flex items-baseline text-4xl font-bold">
                                {model.fee}
                                <span className="ml-1 text-sm font-medium text-muted-foreground">de las ganancias</span>
                            </div>
                            <p className="mt-4 text-sm text-muted-foreground flex-1">{model.desc}</p>

                            <ul className="mt-6 space-y-3 mb-8">
                                {model.features.map(feat => (
                                    <li key={feat} className="flex gap-3 text-sm">
                                        <Check size={16} className="text-primary flex-shrink-0" />
                                        <span>{feat}</span>
                                    </li>
                                ))}
                            </ul>

                            <button
                                disabled={isPlaying}
                                className={`w-full py-3 rounded-lg font-medium transition-colors ${selectedModel.id === model.id ? "bg-primary text-primary-foreground hover:bg-primary/90" : "bg-muted text-muted-foreground hover:bg-muted/80"
                                    }`}
                            >
                                {selectedModel.id === model.id ? "Modelo Elegido" : "Elegir Modelo"}
                            </button>
                        </div>
                    ))}
                </section>

                {/* Simulador Dashboard */}
                <section className="grid grid-cols-1 lg:grid-cols-4 gap-8">

                    {/* Controles Laterales */}
                    <div className="lg:col-span-1 space-y-8">
                        <div className="space-y-4">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-muted-foreground">Capital Inicial</h3>
                            <div className="relative">
                                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground">$</span>
                                <input
                                    type="number"
                                    disabled={isPlaying || dayCounter > 0}
                                    className="w-full bg-card border border-border rounded-lg py-3 pl-8 pr-4 text-lg font-semibold focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
                                    value={capitalInput}
                                    onChange={(e) => setCapitalInput(Number(e.target.value))}
                                />
                            </div>
                        </div>

                        <div className="pt-2 flex flex-col gap-3">
                            <button
                                onClick={() => setIsPlaying(!isPlaying)}
                                className="w-full flex items-center justify-center gap-2 bg-foreground text-background py-4 rounded-xl font-medium hover:opacity-90 transition-opacity"
                            >
                                {isPlaying ? <><Square size={20} fill="currentColor" /> Detener Simulación</> : <><Play size={20} fill="currentColor" /> Iniciar Inversión IA</>}
                            </button>
                            <button
                                onClick={resetSimulation}
                                className="w-full flex items-center justify-center gap-2 py-3 border border-border bg-card hover:bg-muted text-foreground rounded-xl transition-colors"
                            >
                                <RefreshCcw size={16} /> Reiniciar
                            </button>
                        </div>
                    </div>

                    {/* Panel Derecho: Dashboard */}
                    <div className="lg:col-span-3 space-y-6 flex flex-col">
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                            <div className="bg-card border border-border p-5 rounded-xl">
                                <div className="text-xs text-muted-foreground uppercase mb-1">Días Operando</div>
                                <div className="text-2xl font-bold">{dayCounter}</div>
                            </div>
                            <div className="bg-card border border-border p-5 rounded-xl">
                                <div className="text-xs text-muted-foreground uppercase mb-1">Balance Neto (Tuyo)</div>
                                <div className="text-2xl font-bold">${currentNeto.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                            </div>
                            <div className="bg-card border border-border p-5 rounded-xl relative overflow-hidden">
                                <div className="text-xs font-semibold text-primary uppercase mb-1">Nuestra Comisión</div>
                                <div className="text-2xl font-bold text-foreground">
                                    ${currentFee.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                                </div>
                            </div>
                            <div className="bg-card border border-border p-5 rounded-xl">
                                <div className="text-xs text-muted-foreground uppercase mb-1">Tus Ganancias Limpias</div>
                                <div className={`text-2xl font-bold ${profit >= 0 ? 'text-success' : 'text-red-500'}`}>
                                    {profit >= 0 ? '+' : ''}${profit.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                                </div>
                            </div>
                        </div>

                        <div className="flex-1 bg-card border border-border rounded-xl p-6 min-h-[400px] flex flex-col">
                            <h3 className="text-sm font-medium mb-6">Gráfico de Inversión (En Vivo)</h3>
                            <div className="flex-1 w-full relative">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={gameData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                                        <XAxis dataKey="day" axisLine={false} tickLine={false} tickFormatter={(v) => `Día ${v}`} tick={{ fontSize: 12, fill: "hsl(220, 9%, 46%)" }} minTickGap={30} />
                                        <YAxis domain={['auto', 'auto']} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "hsl(220, 9%, 46%)" }} tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} width={50} />
                                        <Tooltip
                                            contentStyle={{ background: "hsl(0, 0%, 100%)", border: "1px solid hsl(220, 13%, 91%)", borderRadius: "8px", color: "#000" }}
                                            formatter={(value: number) => [`$${value.toFixed(2)}`, "Neto (Tuyo)"]}
                                            labelFormatter={(label) => `Día Operable ${label}`}
                                        />
                                        <Line type="monotone" dataKey="neto" stroke="hsl(217, 91%, 60%)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
                                    </LineChart>
                                </ResponsiveContainer>
                                {gameData.length <= 1 && (
                                    <div className="absolute inset-0 flex items-center justify-center bg-background/50 backdrop-blur-sm rounded-lg">
                                        <div className="text-muted-foreground">Inicia la IA para ver las transacciones</div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </section>
            </main>
        </div>
    );
}
