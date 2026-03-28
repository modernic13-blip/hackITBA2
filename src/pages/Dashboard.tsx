import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { supabase } from "@/lib/supabase";
import { LogOut, LayoutDashboard, Wallet, UserCircle } from "lucide-react";
import { Session } from "@supabase/supabase-js";

export default function Dashboard() {
    const navigate = useNavigate();
    const [session, setSession] = useState<Session | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchSession = async () => {
            const { data: { session: currentSession } } = await supabase.auth.getSession();
            if (!currentSession) {
                navigate("/login");
            } else {
                setSession(currentSession);
            }
            setLoading(false);
        };

        fetchSession();

        const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
            if (!session) {
                navigate("/login");
            } else {
                setSession(session);
            }
        });

        return () => subscription.unsubscribe();
    }, [navigate]);

    const handleLogout = async () => {
        await supabase.auth.signOut();
        navigate("/");
    };

    if (loading) {
        return <div className="min-h-screen flex items-center justify-center bg-background"><span className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin"></span></div>;
    }

    if (!session) return null;

    // Extraer metadata provista por Google
    const { user } = session;
    const metadata = user.user_metadata || {};
    const fullName = metadata.full_name || metadata.name || "Inversor";
    const avatarUrl = metadata.avatar_url || metadata.picture;
    const email = user.email;

    return (
        <div className="min-h-screen bg-background text-foreground flex">
            {/* Sidebar Lateral */}
            <aside className="w-64 border-r border-border bg-card/30 p-6 flex flex-col">
                <div className="flex items-center gap-2 mb-12">
                    <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center border border-primary/40">
                        <div className="w-2.5 h-2.5 rounded-sm bg-primary" />
                    </div>
                    <span className="font-semibold tracking-tight">Smart Capital</span>
                </div>

                <nav className="flex-1 space-y-2">
                    <Link to="/dashboard" className="flex items-center gap-3 bg-primary/10 text-primary px-4 py-2.5 rounded-lg text-sm font-medium transition-colors">
                        <LayoutDashboard size={18} />
                        Panel Principal
                    </Link>
                    <Link to="/simulacion" className="flex items-center gap-3 text-muted-foreground hover:bg-muted px-4 py-2.5 rounded-lg text-sm font-medium transition-colors">
                        <Wallet size={18} />
                        Mis Simulaciones
                    </Link>
                </nav>

                <div className="mt-auto pt-6 border-t border-border">
                    <div className="flex justify-between items-center bg-card p-3 rounded-xl border border-border">
                        <div className="flex items-center gap-3">
                            {avatarUrl ? (
                                <img src={avatarUrl} alt="Avatar" className="w-9 h-9 rounded-full object-cover" />
                            ) : (
                                <div className="w-9 h-9 rounded-full bg-muted flex items-center justify-center">
                                    <UserCircle size={20} className="text-muted-foreground" />
                                </div>
                            )}
                            <div className="flex flex-col">
                                <span className="text-sm font-medium leading-none truncate w-24">{fullName}</span>
                                <span className="text-[10px] text-muted-foreground mt-1 truncate w-24">{email}</span>
                            </div>
                        </div>
                        <button onClick={handleLogout} className="p-2 text-muted-foreground hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors">
                            <LogOut size={16} />
                        </button>
                    </div>
                </div>
            </aside>

            {/* Contenido Principal */}
            <main className="flex-1 p-8 lg:p-12 overflow-y-auto">
                <header className="mb-10">
                    <h1 className="text-3xl font-semibold">Hola, {fullName.split(' ')[0]} 👋</h1>
                    <p className="text-muted-foreground mt-1">Aquí tienes un resumen de tu capital y rendimiento actual.</p>
                </header>

                {/* Stats Cards Fake (Mocked Data for visual filling) */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
                    <div className="bg-card border border-border p-6 rounded-2xl">
                        <div className="text-sm font-medium text-muted-foreground mb-4">Capital Total</div>
                        <div className="text-4xl font-bold">$0.00</div>
                        <div className="text-xs text-muted-foreground mt-4">Aún no has depositado fondos reales.</div>
                    </div>
                    <div className="bg-card border border-border p-6 rounded-2xl">
                        <div className="text-sm font-medium text-muted-foreground mb-4">Ganancias Generadas</div>
                        <div className="text-4xl font-bold text-success">+$0.00</div>
                        <div className="text-xs text-muted-foreground mt-4">Profit histórico acumulado.</div>
                    </div>
                    <div className="bg-card border border-border p-6 rounded-2xl flex flex-col justify-between">
                        <div>
                            <div className="text-sm font-medium text-muted-foreground mb-4">Próximo paso</div>
                            <p className="text-sm">Prueba simulando tu rendimiento antes de invertir de verdad.</p>
                        </div>
                        <Link to="/simulacion" className="mt-4 bg-primary text-primary-foreground text-center py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors">
                            Crear Simulación
                        </Link>
                    </div>
                </div>

                {/* Table or Chart Placeholders */}
                <div className="bg-card border border-border p-8 rounded-2xl min-h-[300px] flex items-center justify-center text-muted-foreground text-sm">
                    Tus transacciones y gráficas de rendimiento aparecerán aquí pronto.
                </div>
            </main>
        </div>
    );
}
