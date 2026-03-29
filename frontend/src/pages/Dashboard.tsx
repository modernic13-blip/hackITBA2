import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { supabase } from "@/lib/supabase";
import { UserNav } from "@/components/UserNav";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import { ArrowLeft } from "lucide-react";

type DataPoint = { day: number; value: number; neto: number; feePaga: number };

export default function Dashboard() {
    const [userName, setUserName] = useState("Inversor");
    const [loading, setLoading] = useState(true);
    const [viewMode, setViewMode] = useState<"real" | "simulacion">("simulacion");
    const [simData, setSimData] = useState<DataPoint[]>([]);
    const [initialCapital, setInitialCapital] = useState<number>(0);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const { data: { session } } = await supabase.auth.getSession();
                if (session) {
                    const user = session.user;
                    setUserName(user.user_metadata?.full_name || user.user_metadata?.name || "Inversor");

                    const { data: dbData } = await supabase
                        .from('simulations')
                        .select('game_data, capital_input')
                        .eq('user_id', user.id)
                        .single();

                    if (dbData) {
                        if (dbData.game_data) setSimData(dbData.game_data);
                        if (dbData.capital_input) setInitialCapital(dbData.capital_input);
                    }
                }
            } catch {
                // Sin sesión — dashboard funciona igual con datos vacíos
            }
            setLoading(false);
        };
        fetchData();
    }, []);

    if (loading) {
        return <div className="min-h-screen flex items-center justify-center bg-background"><span className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin"></span></div>;
    }

    const currentNeto = simData.length > 0 ? simData[simData.length - 1].neto : 0;
    const profit = currentNeto - initialCapital;
    const returnPct = initialCapital > 0 ? ((currentNeto - initialCapital) / initialCapital) * 100 : 0;

    return (
        <div className="min-h-screen bg-background text-foreground flex flex-col relative font-sans">
            <header className="p-6 flex items-center justify-between sticky top-0 bg-background/80 backdrop-blur-md z-40">
                <Link
                    to="/"
                    className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                    <ArrowLeft size={16} />
                    Volver al inicio
                </Link>
            </header>

            <UserNav />

            <main className="flex-1 max-w-7xl w-full mx-auto px-6 lg:px-12 pt-10 pb-12">
                <header className="mb-10 flex flex-col md:flex-row md:justify-between md:items-end gap-6">
                    <div>
                        <h1 className="text-3xl font-semibold">Hola, {userName.split(' ')[0]} 👋</h1>
                        <p className="text-muted-foreground mt-1 gap-2 flex items-center">
                            Visualiza de forma global tus estrategias conectadas a la DB.
                        </p>
                    </div>

                    <div className="flex bg-muted p-1 rounded-xl w-max border border-border">
                        <button
                            onClick={() => setViewMode("simulacion")}
                            className={`px-6 py-2 rounded-lg text-sm font-medium transition-all ${viewMode === 'simulacion' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                        >
                            Simulación
                        </button>
                        <button
                            onClick={() => setViewMode("real")}
                            className={`px-6 py-2 rounded-lg text-sm font-medium transition-all ${viewMode === 'real' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                        >
                            Plata de Verdad
                        </button>
                    </div>
                </header>

                {viewMode === "real" ? (
                    <div className="bg-card w-full border border-border rounded-2xl min-h-[400px] flex flex-col items-center justify-center text-center p-8">
                        <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mb-4 border border-border/50">
                            <span className="text-2xl">🏦</span>
                        </div>
                        <h3 className="text-lg font-medium mb-2">No has depositado fondos</h3>
                        <p className="text-sm text-muted-foreground max-w-sm mb-6">Aún no tienes capital real en administración. Inicia una simulación para ver cómo operaría la IA o fondea tu cuenta.</p>
                        <button className="bg-foreground text-background font-medium px-8 py-3 rounded-xl opacity-50 cursor-not-allowed">
                            Depositar Capital (Próximamente)
                        </button>
                    </div>
                ) : (
                    <div className="space-y-6">
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                            <div className="bg-card border border-border p-5 rounded-xl">
                                <div className="text-xs text-muted-foreground uppercase mb-1">Capital Inicial</div>
                                <div className="text-2xl font-bold">${initialCapital.toLocaleString('en-US', { minimumFractionDigits: 0 })}</div>
                            </div>
                            <div className="bg-card border border-border p-5 rounded-xl">
                                <div className="text-xs text-muted-foreground uppercase mb-1">Balance Actual</div>
                                <div className="text-2xl font-bold text-primary">${currentNeto.toLocaleString('en-US', { minimumFractionDigits: 0 })}</div>
                            </div>
                            <div className="bg-card border border-border p-5 rounded-xl">
                                <div className="text-xs text-muted-foreground uppercase mb-1">Ganancias (Profit)</div>
                                <div className={`text-2xl font-bold ${profit >= 0 ? 'text-success' : 'text-red-500'}`}>
                                    {profit >= 0 ? '+' : ''}${profit.toLocaleString('en-US', { minimumFractionDigits: 0 })}
                                </div>
                            </div>
                            <div className="bg-card border border-border p-5 rounded-xl">
                                <div className="text-xs text-muted-foreground uppercase mb-1">Retorno %</div>
                                <div className={`text-2xl font-bold ${returnPct >= 0 ? 'text-success' : 'text-red-500'}`}>
                                    {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(1)}%
                                </div>
                            </div>
                        </div>

                        <div className="bg-card border border-border rounded-xl p-6 min-h-[400px] flex flex-col">
                            <div className="flex justify-between items-center mb-6">
                                <h3 className="text-sm font-medium flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-primary animate-pulse"></div>
                                    Ultima Simulación Guardada en la Nube
                                </h3>
                                <Link to="/simulacion" className="text-xs border border-border bg-muted hover:bg-muted/80 px-4 py-2 rounded-lg transition-colors">
                                    Modificar Simulación
                                </Link>
                            </div>

                            <div className="flex-1 w-full relative">
                                {simData.length > 1 ? (
                                    <ResponsiveContainer width="100%" height="400px">
                                        <LineChart data={simData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                                            <XAxis dataKey="day" axisLine={false} tickLine={false} tickFormatter={(v) => `Día ${v}`} tick={{ fontSize: 12, fill: "hsl(220, 9%, 46%)" }} minTickGap={30} />
                                            <YAxis domain={['auto', 'auto']} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "hsl(220, 9%, 46%)" }} tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} width={50} />
                                            <Tooltip
                                                contentStyle={{ background: "hsl(0, 0%, 100%)", border: "1px solid hsl(220, 13%, 91%)", borderRadius: "8px", color: "#000" }}
                                                formatter={(value: number) => [`$${value.toFixed(2)}`, "Neto"]}
                                                labelFormatter={(label) => `Día ${label}`}
                                            />
                                            <Line type="monotone" dataKey="neto" stroke="hsl(217, 91%, 60%)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                ) : (
                                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/30 rounded-lg">
                                        <p className="text-muted-foreground mb-4">No hay datos guardados. Corré una simulación primero.</p>
                                        <Link to="/simulacion" className="bg-primary hover:bg-primary/90 text-primary-foreground px-6 py-2 rounded-lg text-sm font-medium transition-colors">
                                            Correr Primera Simulación
                                        </Link>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
