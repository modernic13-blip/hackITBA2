import { motion } from "framer-motion";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useState } from "react";
import { Link } from "react-router-dom";

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
