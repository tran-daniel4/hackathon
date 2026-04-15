"use client";

import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { WaveBackground } from "@/components/WaveBackground";
import { LoginPage } from "./pages/login";
import { SignUpPage } from "./pages/signup";
import { Dashboard } from "./pages/dashboard";

export default function Home() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [showLogin, setShowLogin] = useState(false);
  const [showSignUp, setShowSignUp] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    if (localStorage.getItem("access_token")) {
      setIsLoggedIn(true);
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setIsLoggedIn(false);
  };

  if (isLoggedIn) {
    return <Dashboard onLogout={handleLogout} />;
  }

  if (showLogin) {
    return (
      <LoginPage
        onClose={() => setShowLogin(false)}
        onLogin={() => { setShowLogin(false); setIsLoggedIn(true); }}
        onSwitchToSignUp={() => {
          setShowLogin(false);
          setShowSignUp(true);
        }}
      />
    );
  }

  if (showSignUp) {
    return (
      <SignUpPage
        onClose={() => setShowSignUp(false)}
        onSignUp={() => { setShowSignUp(false); setIsLoggedIn(true); }}
        onSwitchToLogin={() => {
          setShowSignUp(false);
          setShowLogin(true);
        }}
      />
    );
  }

  return (
    <div ref={containerRef} className="bg-[#0a0a0f] text-white min-h-screen">
      {/* Sparse Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 px-8 py-6 flex justify-between items-center mix-blend-difference">
        <div className="tracking-tight">DynoDocs</div>
        <div className="flex items-center gap-12">
          <div className="flex gap-12 uppercase text-[11px] tracking-[0.15em] opacity-60">
            <button className="hover:opacity-100 transition-opacity">Platform</button>
            <button className="hover:opacity-100 transition-opacity">Docs</button>
            <button className="hover:opacity-100 transition-opacity">Demo</button>
          </div>
          <button
            onClick={() => setShowLogin(true)}
            className="px-6 py-2 border border-white/20 bg-white/5 uppercase text-[11px] tracking-[0.15em] hover:bg-white/10 transition-colors"
          >
            Login
          </button>
        </div>
      </nav>

      {/* Hero - Full Bleed */}
      <section className="relative h-screen flex items-center overflow-hidden">
        {/* Static Wave Background */}
        <div className="absolute inset-0 w-full h-full">
          <WaveBackground />
          <div className="absolute inset-0 bg-gradient-to-b from-[#0a0a0f]/20 via-[#0a0a0f]/60 to-[#0a0a0f]" />
        </div>

        {/* Hero Content */}
        <div className="relative z-10 px-8 md:px-16 max-w-[1600px] mx-auto w-full">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 1.2, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="uppercase text-[11px] tracking-[0.2em] opacity-40 mb-8">
              [ ARCHITECTURE INTELLIGENCE PLATFORM ]
            </div>

            <h1 className="text-[clamp(3rem,10vw,9rem)] leading-[0.95] tracking-[-0.04em] mb-12 max-w-[1400px]">
              See your system.
              <br />
              Not just your code.
            </h1>

            <p className="text-[clamp(1.1rem,2vw,1.5rem)] opacity-60 max-w-[600px] mb-16 leading-relaxed">
              Turn scattered architecture knowledge into a living visual map.
              Diagnose production issues in minutes, not hours.
            </p>

            <button
              onClick={() => setShowLogin(true)}
              className="px-12 py-5 border border-white/20 backdrop-blur-sm bg-white/5 uppercase text-[11px] tracking-[0.2em] hover:bg-white/15 transition-colors"
            >
              Sign up
            </button>
          </motion.div>
        </div>

        {/* Scroll Indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 2, duration: 1 }}
          className="absolute bottom-12 left-1/2 -translate-x-1/2 flex flex-col items-center gap-3 opacity-30"
        >
          <div className="text-[9px] uppercase tracking-[0.2em]">Scroll</div>
          <div className="w-[1px] h-12 bg-white animate-pulse" />
        </motion.div>
      </section>

      {/* Feature Grid - Modular Panels */}
      <section className="px-8 md:px-16 py-32 max-w-[1600px] mx-auto">
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8 }}
        >
          <div className="uppercase text-[11px] tracking-[0.2em] opacity-40 mb-16">
            [ HOW IT WORKS ]
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-[1px] bg-white/5">
            {[
              {
                num: "01",
                title: "Living System Map",
                desc: "Analyzes your repository to generate an interactive architecture diagram. Every component, every connection, visualized."
              },
              {
                num: "02",
                title: "Animated Flow",
                desc: "Watch API requests, events, and queue jobs move through your system in real time. Understand the path, not just the code."
              },
              {
                num: "03",
                title: "Visual Diagnosis",
                desc: "Bottlenecks and failures overlaid directly on the map. See database slowdowns, overloaded services, and queue congestion instantly."
              },
            ].map((item, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: idx * 0.15 }}
                className="bg-[#0f0f15] p-12 hover:bg-white/3 transition-colors group cursor-pointer"
              >
                <div className="text-[11px] tracking-[0.2em] opacity-30 mb-8 group-hover:opacity-50 transition-opacity">
                  {item.num}
                </div>
                <h3 className="text-[clamp(1.5rem,3vw,2.5rem)] mb-6 leading-tight">
                  {item.title}
                </h3>
                <p className="opacity-50 leading-relaxed text-[15px]">
                  {item.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* Architecture Visualization */}
      <section className="px-8 md:px-16 py-32 max-w-[1600px] mx-auto">
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8 }}
        >
          <div className="uppercase text-[11px] tracking-[0.2em] opacity-40 mb-6">
            [ PLATFORM CAPABILITIES ]
          </div>

          <h2 className="text-[clamp(2.5rem,6vw,5rem)] leading-[1.05] tracking-[-0.03em] mb-20">
            From chaos
            <br />
            to clarity.
          </h2>

          {/* Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-32">
            {[
              { label: "Component Detection", value: "15+", unit: "types" },
              { label: "Diagnosis Speed", value: "10x", unit: "faster" },
              { label: "System Coverage", value: "100", unit: "%" },
              { label: "Flow Visualization", value: "Real", unit: "time" },
            ].map((metric, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: idx * 0.08 }}
                className="border border-white/10 p-8 hover:border-white/20 hover:bg-white/[0.02] transition-all group"
              >
                <div className="text-[11px] uppercase tracking-[0.15em] opacity-40 mb-4 group-hover:opacity-60 transition-opacity">
                  {metric.label}
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[clamp(2rem,4vw,3rem)] leading-none tracking-tight">
                    {metric.value}
                  </span>
                  <span className="text-[13px] opacity-50">{metric.unit}</span>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Product Screenshot Placeholder */}
          <div className="relative border border-white/10 aspect-[16/9] bg-white/[0.02] flex items-center justify-center">
            <div className="text-[11px] uppercase tracking-[0.2em] opacity-20">
              Product preview coming soon
            </div>
          </div>
        </motion.div>
      </section>

      {/* Philosophy Section */}
      <section className="px-8 md:px-16 py-32 max-w-[900px] mx-auto">
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8 }}
          className="space-y-16"
        >
          <div className="uppercase text-[11px] tracking-[0.2em] opacity-40">
            [ THE PROBLEM ]
          </div>

          <p className="text-[clamp(1.3rem,3vw,2rem)] leading-[1.4] opacity-70">
            Knowledge is scattered.
            <br />
            Diagnosis is guesswork.
          </p>

          <p className="text-[17px] leading-relaxed opacity-50 max-w-[600px]">
            Architecture understanding lives in source code, cloud dashboards, logs, and tribal knowledge.
            When production breaks, engineers know something is wrong — but not where, or how it&apos;s cascading.
            DynoDocs turns that scattered context into a single, visual source of truth.
          </p>

          <div className="flex flex-col md:flex-row gap-16 pt-8">
            {[
              { label: "Onboarding Time", value: "3 days → 30 min" },
              { label: "Components Mapped", value: "Frontend, APIs, DBs, Queues" },
              { label: "Issue Resolution", value: "Hours → Minutes" },
            ].map((stat, idx) => (
              <div key={idx} className="flex-1">
                <div className="text-[11px] uppercase tracking-[0.15em] opacity-40 mb-3">
                  {stat.label}
                </div>
                <div className="text-[clamp(1rem,2.5vw,1.5rem)] tracking-tight leading-tight">
                  {stat.value}
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* Final CTA */}
      <section className="px-8 md:px-16 py-32 max-w-[1600px] mx-auto border-t border-white/10">
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="flex flex-col md:flex-row justify-between items-start md:items-center gap-12"
        >
          <div>
            <h2 className="text-[clamp(2rem,5vw,4rem)] leading-[1.1] tracking-[-0.02em] mb-6">
              Stop guessing.
              <br />
              Start seeing.
            </h2>
            <p className="opacity-50 text-[15px]">
              Map your system. Diagnose visually. Ship with confidence.
            </p>
          </div>

          <div className="flex flex-col gap-4">
            <button
              onClick={() => setShowLogin(true)}
              className="px-12 py-5 bg-white text-black uppercase text-[11px] tracking-[0.2em] hover:bg-white/90 transition-colors"
            >
              Try DynoDocs
            </button>
            <button className="px-12 py-5 border border-white/20 uppercase text-[11px] tracking-[0.2em] hover:bg-white/5 transition-colors">
              Watch Demo
            </button>
          </div>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="px-8 md:px-16 py-16 border-t border-white/5">
        <div className="max-w-[1600px] mx-auto flex flex-col md:flex-row justify-between items-start gap-8">
          <div className="text-[11px] uppercase tracking-[0.2em] opacity-30">
            DynoDocs © 2026
          </div>

          <div className="flex gap-12 text-[11px] uppercase tracking-[0.15em] opacity-30">
            <a href="#" className="hover:opacity-60 transition-opacity">Privacy</a>
            <a href="#" className="hover:opacity-60 transition-opacity">Terms</a>
            <a href="#" className="hover:opacity-60 transition-opacity">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
