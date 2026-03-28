import { useEffect, useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { supabase } from "@/lib/supabase";
import { UserCircle, LogOut } from "lucide-react";

export const UserNav = () => {
    const [user, setUser] = useState<any>(null);
    const navigate = useNavigate();
    const location = useLocation();

    const isDashboard = location.pathname === "/dashboard";

    useEffect(() => {
        supabase.auth.getSession().then(({ data }) => setUser(data.session?.user));
        const { data: { subscription } } = supabase.auth.onAuthStateChange((_, session) => {
            setUser(session?.user);
        });
        return () => subscription.unsubscribe();
    }, []);

    const handleLogout = async () => {
        if (window.confirm("¿Estás seguro de que deseas cerrar sesión?")) {
            await supabase.auth.signOut();
            setUser(null);
            navigate("/");
        }
    };

    return (
        <div className="absolute top-0 w-full p-6 flex justify-end z-50 pointer-events-auto">
            {user ? (
                <div className="flex items-center gap-3">
                    {!isDashboard && (
                        <Link to="/dashboard" className="flex items-center gap-3 bg-card border border-border px-5 py-2 rounded-full hover:bg-muted transition-colors shadow-sm">
                            <span className="text-sm font-medium">{user.user_metadata?.full_name?.split(' ')[0] || "Mi Panel"}</span>
                            {user.user_metadata?.avatar_url ? (
                                <img src={user.user_metadata.avatar_url} alt="Avatar" className="w-6 h-6 rounded-full object-cover" />
                            ) : (
                                <UserCircle size={24} className="text-muted-foreground" />
                            )}
                        </Link>
                    )}
                    {isDashboard && (
                        <button
                            onClick={handleLogout}
                            className="flex items-center justify-center px-5 py-2 gap-2 bg-muted border border-border rounded-full text-muted-foreground hover:text-red-500 hover:bg-red-500/10 transition-colors shadow-sm"
                            title="Cerrar Sesión"
                        >
                            <LogOut size={16} />
                            <span className="text-sm font-medium">Cerrar Sesión</span>
                        </button>
                    )}
                </div>
            ) : (
                <Link to="/login" className="text-sm font-medium border border-border bg-card/80 backdrop-blur-md hover:bg-muted px-8 py-3 rounded-full transition-colors shadow-sm">
                    Ingresar
                </Link>
            )}
        </div>
    );
};
