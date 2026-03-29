import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link } from "react-router-dom";

const PortfolioLine = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width = canvas.offsetWidth * 2;
      canvas.height = canvas.offsetHeight * 2;
      ctx.scale(2, 2);
    };
    resize();
    window.addEventListener("resize", resize);

    const points = [20, 22, 21, 25, 24, 28, 26, 30, 29, 33, 31, 35, 34, 38, 36, 40, 42, 41, 45, 48, 50, 49, 53, 55, 54, 58, 60];
    let progress = 0;

    const draw = () => {
      const w = canvas.offsetWidth;
      const h = canvas.offsetHeight;
      ctx.clearRect(0, 0, w, h);
      const segmentWidth = w / (points.length - 1);
      const minY = Math.min(...points);
      const maxY = Math.max(...points);
      const range = maxY - minY;
      const currentPoints = Math.min(Math.floor(progress * points.length), points.length);

      if (currentPoints < 2) {
        progress += 0.003;
        animationRef.current = requestAnimationFrame(draw);
        return;
      }

      ctx.beginPath();
      ctx.strokeStyle = "hsla(217, 91%, 60%, 0.3)";
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";

      for (let i = 0; i < currentPoints; i++) {
        const x = i * segmentWidth;
        const y = h - ((points[i] - minY) / range) * h * 0.6 - h * 0.2;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      const lastX = (currentPoints - 1) * segmentWidth;
      ctx.lineTo(lastX, h);
      ctx.lineTo(0, h);
      ctx.closePath();

      const gradient = ctx.createLinearGradient(0, 0, 0, h);
      gradient.addColorStop(0, "hsla(217, 91%, 60%, 0.06)");
      gradient.addColorStop(1, "hsla(217, 91%, 60%, 0)");
      ctx.fillStyle = gradient;
      ctx.fill();

      if (progress < 1) progress += 0.003;
      animationRef.current = requestAnimationFrame(draw);
    };

    animationRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(animationRef.current);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{ opacity: 0.7 }}
    />
  );
};

const HeroSection = () => {
  const words = ["PRECISA", "EFICAZ", "CONSTANTE", "INTELIGENTE"];
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setIndex((prev) => (prev + 1) % words.length);
    }, 2500);
    return () => clearInterval(interval);
  }, [words.length]);

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden bg-background">
      <PortfolioLine />
      <div className="relative z-10 text-center max-w-5xl mx-auto px-6 flex flex-col items-center">

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-muted border border-border text-xs font-semibold text-muted-foreground mb-8"
        >
          <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          Modelo Backtesteado 2021-2025
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="text-6xl sm:text-7xl md:text-[5.5rem] font-bold text-foreground tracking-tighter leading-[1.05]"
        >
          El mercado se mueve.
          <br className="hidden sm:block" />
          <span className="text-muted-foreground">Tu estrategia también.</span>
        </motion.h1>

        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
          className="mt-8 text-xl md:text-3xl font-medium tracking-tight flex flex-wrap items-center justify-center gap-2 text-foreground/80"
        >
          <span>CONSTRUYE UN PORTAFOLIO</span>
          <div className="relative inline-flex overflow-hidden h-10 items-center justify-center text-primary min-w-[200px]">
            <AnimatePresence mode="popLayout">
              <motion.span
                key={words[index]}
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -30 }}
                transition={{ duration: 0.4 }}
                className="font-semibold block"
              >
                {words[index]}
              </motion.span>
            </AnimatePresence>
          </div>
        </motion.div>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut", delay: 0.5 }}
          className="mt-6 text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto font-medium"
        >
          Tu sistema de trading automatizado impulsado por Inteligencia Artificial y datos de mercado reales.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.7 }}
          className="mt-8"
        >
          <Link to="/metodologia" className="group inline-flex items-center gap-2 text-sm font-mono tracking-tight text-muted-foreground hover:text-foreground transition-colors pb-1 border-b border-transparent hover:border-foreground/30">
            Leer Metodología de Validación
            <span className="transition-transform group-hover:translate-x-1">→</span>
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 1 }}
          className="mt-16"
        >
          <svg className="w-6 h-6 mx-auto text-muted-foreground/30 animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </motion.div>
      </div>
    </section>
  );
};

export default HeroSection;
