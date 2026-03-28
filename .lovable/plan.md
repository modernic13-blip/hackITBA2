

# hackITBA — AI-Powered Investment Platform

## Overview
A calm, precise, and powerful AI investment platform that builds trust through showing before asking. Designed to feel like a private financial terminal designed by Apple.

## Design System
- **Primary**: Deep charcoal `#0B0B0C` — authority
- **Background**: Pure white `#FFFFFF` — clarity
- **Accent**: Soft blue `#3B82F6` — intelligence
- **Success**: Muted green `#10B981` — subtle growth
- **Typography**: Clean geometric sans-serif headings (Inter), generous spacing, ≥1.5 line-height
- **Motion**: 200–300ms ease-in-out, smooth and calm throughout

## Pages & Features

### 1. Homepage
- Minimal hero with dominant headline: *"The market moves. Your strategy should too."*
- Subtle subtext: *"Your personal AI trader — built on real market data."*
- Soft animated portfolio growth line in the background (SVG/canvas, slow elegant curve)
- Single CTA: "See how it would work for you"
- Apple-like whitespace, centered layout

### 2. Conversational Onboarding (multi-step flow)
- **Step 1 — Capital**: "Let's define your position." with a smooth slider ($1,000–$100,000+)
- **Step 2 — Risk**: "How do you handle volatility?" with a dial/slider (Conservative ↔ Aggressive)
- Live portfolio preview updates as user interacts — assets fade in (AAPL, BTC, ETH, etc.)
- Microcopy animations: "Adjusting your allocation…", "Rebalancing based on your profile…"
- Scene-based transitions between steps

### 3. Backtesting Reveal
- "If you had started in 2021…" with animated chart that pauses during downturns, then recovers
- Subtle annotations on chart: "Market drawdown detected → allocation adjusted"
- Human-readable metrics: Total Return, "Worst temporary drop" (Max Drawdown), "Consistency of returns" (Sharpe Ratio)
- Microcopy: "Not perfect. But adaptive." / "Designed to respond, not predict."
- All data is simulated/mock for demo purposes

### 4. Conversion Step
- Zero-pressure CTA: "Start with simulation"
- Secondary: "Go live when you're ready."
- Clean, minimal layout reinforcing user control

### 5. "How It Works" (collapsible section)
- Simple diagrams explaining the AI approach
- No jargon — plain language: "We analyze patterns across assets and adjust your portfolio accordingly."

### 6. Authentication
- Email/password signup and login via Lovable Cloud
- Clean, minimal auth pages matching the design system

## Interactions & Motion
- Portfolio line chart animates on scroll with slow growth curve
- Sliders feel responsive with smooth easing
- Hover states: soft opacity shift + slight scale
- Asset cards fade in with staggered timing
- Chart annotations appear sequentially during the backtesting reveal

## Technical Approach
- All pages built as React components with React Router
- Recharts for portfolio charts and backtesting visualization
- Framer Motion for animations and transitions
- Mock data for portfolio allocations, backtesting results, and asset breakdowns
- Lovable Cloud for auth and future backend needs

