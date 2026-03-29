import { createClient } from '@supabase/supabase-js';

// Usamos placeholders si no hay entorno para que el bundle de Vite no crashee React entero
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://placeholder.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'placeholder';

console.log("Supabase URL cargada en Vite:", supabaseUrl); // Debug

if (supabaseUrl === 'https://placeholder.supabase.co') {
    console.warn("Aviso: Faltan variables de entorno de Supabase (VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY).");
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
