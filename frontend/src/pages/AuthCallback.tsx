import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/lib/supabase";

export default function AuthCallback() {
    const navigate = useNavigate();

    useEffect(() => {
        // Al cargar esta vista (que es a la que redirige Google), comprobamos la sesión
        const hydrateSession = async () => {
            const { data, error } = await supabase.auth.getSession();

            if (error) {
                console.error("Error validando sesión:", error);
                navigate("/login");
                return;
            }

            if (data.session) {
                // Intercambio exitoso, redigimos al usuario a su cuenta
                navigate("/dashboard");
            } else {
                // En algunos entornos el token se procesa mediante hash en hashChange. 
                // Supabase-js maneja automáticamente la extracción de la URL.
                // Damos un pequeño delay por si el evento onAuthStateChange lo agarra.
                setTimeout(() => {
                    navigate("/login");
                }, 1500);
            }
        };

        hydrateSession();
    }, [navigate]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-background">
            <div className="flex flex-col items-center gap-4">
                <span className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin"></span>
                <p className="text-sm font-medium text-muted-foreground animate-pulse">Verificando credenciales...</p>
            </div>
        </div>
    );
}
