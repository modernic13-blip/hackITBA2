import { useEffect, useRef } from "react";
import { motion } from "framer-motion";

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
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      <PortfolioLine />
      <div className="relative z-10 text-center max-w-3xl mx-auto px-6">
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="text-4xl sm:text-5xl md:text-6xl font-semibold text-foreground tracking-tight leading-[1.1]"
        >
          The market moves.
          <br />
          Your strategy should too.
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut", delay: 0.3 }}
          className="mt-6 text-base text-muted-foreground max-w-md mx-auto"
        >
          Your personal AI trader — built on real market data.
        </motion.p>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 1.2 }}
          className="mt-16"
        >
          <svg className="w-5 h-5 mx-auto text-muted-foreground/50 animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </motion.div>
      </div>
    </section>
  );
};

export default HeroSection;
