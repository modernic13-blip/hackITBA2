import { motion } from "framer-motion";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Check } from "lucide-react";

export const AI_MODELS = [
  { id: "low", name: "Modelo Conservador", fee: "6%", desc: "Dedicamos el 6% de tus ganancias. Estable.", features: ["Bajo riesgo", "Retiros gratis", "Soporte 24/7"] },
  { id: "mid", name: "Modelo Dinámico", fee: "3%", desc: "Dedicamos el 3% de tus ganancias. Balance perfecto.", features: ["Volatilidad media", "Ajustes diarios", "Prioridad de red"] },
  { id: "high", name: "Modelo Agresivo", fee: "1%", desc: "Dedicamos el 1% de tus ganancias. Da más plata.", features: ["Alto riesgo", "Algoritmo avanzado", "Asesor IA VIP"] },
];

const ConversionSection = () => {
  const [howOpen, setHowOpen] = useState(false);

  return (
    <section className="min-h-screen flex flex-col items-center justify-center px-6 py-24">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="text-center space-y-12 max-w-lg"
      >
        <div>
          <h2 className="text-3xl sm:text-4xl font-semibold text-foreground">
            Listos cuando tú lo estés.
          </h2>
          <p className="mt-3 text-muted-foreground text-sm">
            Sin compromisos. Empieza con una simulación y da el salto cuando confíes en el sistema.
          </p>
        </div>

        <div className="flex flex-col items-center gap-4">
          <Link to="/simulacion" className="inline-flex items-center gap-2 rounded-full bg-foreground text-background px-10 py-4 text-sm font-medium transition-all duration-300 hover:opacity-90 hover:scale-[1.02]">
            Iniciar Simulación
          </Link>
          <button className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-200">
            Invierte con dinero real.
          </button>
        </div>
      </motion.div>

      {/* Pricing Header */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ delay: 0.2, duration: 0.6 }}
        className="mt-24 text-center max-w-2xl mx-auto mb-16"
      >
        <h1 className="text-3xl sm:text-4xl font-semibold mb-4 text-foreground">Elige tu IA de Inversión</h1>
        <p className="text-muted-foreground">
          Solo cobramos un porcentaje de tus ganancias. Si tú no ganas, nosotros tampoco. Empecemos con tu simulación.
        </p>
      </motion.div>

      {/* Pricing Cards */}
      <motion.section
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ delay: 0.3, duration: 0.6 }}
        className="w-full max-w-6xl grid grid-cols-1 md:grid-cols-3 gap-6 mb-16"
      >
        {AI_MODELS.map(model => (
          <div
            key={model.id}
            className="relative flex flex-col p-6 rounded-2xl border bg-card border-border hover:border-primary/50 transition-all text-left"
          >
            <h3 className="text-lg font-medium text-foreground">{model.name}</h3>
            <div className="mt-4 flex items-baseline text-4xl font-bold text-foreground">
              {model.fee}
              <span className="ml-1 text-sm font-medium text-muted-foreground">de las ganancias</span>
            </div>
            <p className="mt-4 text-sm text-muted-foreground flex-1">{model.desc}</p>

            <ul className="mt-6 space-y-3 mb-8">
              {model.features.map(feat => (
                <li key={feat} className="flex gap-3 text-sm text-foreground">
                  <Check size={16} className="text-primary flex-shrink-0" />
                  <span>{feat}</span>
                </li>
              ))}
            </ul>

            <Link
              to="/simulacion"
              state={{ selectedModelId: model.id }}
              className="w-full py-3 rounded-lg font-medium text-center transition-colors bg-muted text-foreground hover:bg-muted/80 border border-border mt-auto"
            >
              Elegir y Simular Modelo
            </Link>
          </div>
        ))}
      </motion.section>

      {/* How it works — collapsible */}
      <motion.div
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ delay: 0.4, duration: 0.5 }}
        className="mt-32 w-full max-w-2xl"
      >
        <Collapsible open={howOpen} onOpenChange={setHowOpen}>
          <CollapsibleTrigger className="w-full flex items-center justify-between py-4 text-sm text-muted-foreground hover:text-foreground transition-colors">
            <span>¿Cómo funciona?</span>
            <svg
              className={`w-4 h-4 transition-transform duration-200 ${howOpen ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="space-y-8 py-8 border-t border-border">
              <HowStep
                number="01"
                title="Recolección de Datos"
                description="Monitoreamos continuamente datos de mercado en acciones, cripto y renta fija."
              />
              <HowStep
                number="02"
                title="Análisis de Patrones"
                description="Analizamos patrones entre activos y ajustamos tu portafolio en consecuencia. Sin predicciones — pura adaptación."
              />
              <HowStep
                number="03"
                title="Rebalanceo Automático"
                description="Cuando las condiciones cambian, las posiciones se ajustan automáticamente. El sistema responde al cambio para que tú no tengas que hacerlo."
              />
            </div>
          </CollapsibleContent>
        </Collapsible>
      </motion.div>

      {/* Footer */}
      <div className="mt-32 text-center">
        <p className="text-xs text-muted-foreground/50">
          hackITBA — Todas las simulaciones utilizan datos históricos. El rendimiento pasado no garantiza resultados futuros.
        </p>
      </div>
    </section>
  );
};

const HowStep = ({ number, title, description }: { number: string; title: string; description: string }) => (
  <div className="flex gap-6">
    <span className="text-xs text-muted-foreground/40 font-mono mt-1">{number}</span>
    <div>
      <h3 className="text-sm font-medium text-foreground">{title}</h3>
      <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{description}</p>
    </div>
  </div>
);

export default ConversionSection;
