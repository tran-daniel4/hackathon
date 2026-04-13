import { motion } from "motion/react";
import { useState } from "react";
import { WaveBackground } from "@/components/WaveBackground";
import { FaGithub } from "react-icons/fa";
import { Mail, Lock, ArrowRight } from "lucide-react";

interface LoginPageProps {
  onClose?: () => void;
  onSwitchToSignUp?: () => void;
}

export function LoginPage({ onClose, onSwitchToSignUp }: LoginPageProps) {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Form submitted:", { email, password, name, isSignUp });
  };

  const handleGithubLogin = () => {
    console.log("GitHub login initiated");
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-[#0a0a0f] flex">
      {/* Background */}
      <WaveBackground />

      {/* Content */}
      <div className="relative z-10 w-full max-w-[900px] px-8 my-auto py-16 mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className="relative grid grid-cols-1 md:grid-cols-2 gap-0 border border-white/10 bg-[#0f0f15]/80 backdrop-blur-xl overflow-hidden"
        >
          {/* Left Side - Branding */}
          <div className="p-12 md:p-16 bg-gradient-to-br from-white/[0.02] to-transparent border-r border-white/10">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            >
              <div className="mb-16">
                <h2 className="text-[clamp(2rem,4vw,3rem)] leading-[1.1] tracking-[-0.02em] mb-4 text-white">
                  DynoDocs
                </h2>
                <div className="uppercase text-[10px] tracking-[0.2em] text-white/60">
                  [ ARCHITECTURE INTELLIGENCE ]
                </div>
              </div>

              <div className="space-y-8">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.15em] text-white/60 mb-2">
                    Platform
                  </div>
                  <p className="text-[15px] text-white/80 leading-relaxed">
                    Turn scattered architecture knowledge into living visual maps
                  </p>
                </div>

                <div>
                  <div className="text-[11px] uppercase tracking-[0.15em] text-white/60 mb-2">
                    Benefits
                  </div>
                  <ul className="space-y-2 text-[14px] text-white/80">
                    <li className="flex items-start gap-2">
                      <span className="text-blue-400 mt-1">•</span>
                      <span>Real-time system visualization</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-400 mt-1">•</span>
                      <span>Instant bottleneck detection</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-400 mt-1">•</span>
                      <span>10x faster diagnosis</span>
                    </li>
                  </ul>
                </div>
              </div>
            </motion.div>
          </div>

          {/* Right Side - Form */}
          <div className="p-12 md:p-16">
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
            >
              {/* Toggle Sign In / Sign Up */}
              <div className="mb-8">
                <h3 className="text-[clamp(1.5rem,3vw,2rem)] mb-2 leading-tight text-white">
                  {isSignUp ? "Create Account" : "Welcome Back"}
                </h3>
                <p className="text-[13px] text-white/70">
                  {isSignUp
                    ? "Start mapping your system today"
                    : "Continue to your dashboard"}
                </p>
              </div>

              {/* GitHub Login */}
              <motion.button
                whileHover={{ scale: 1.02, backgroundColor: "rgba(255, 255, 255, 0.08)" }}
                whileTap={{ scale: 0.98 }}
                onClick={handleGithubLogin}
                className="w-full mb-8 px-6 py-4 border border-white/20 bg-white/5 backdrop-blur-sm flex items-center justify-center gap-3 uppercase text-[11px] tracking-[0.15em] transition-colors group text-white"
              >
                <FaGithub className="w-4 h-4 opacity-80 group-hover:opacity-100 transition-opacity" />
                Continue with GitHub
              </motion.button>

              {/* Divider */}
              <div className="relative mb-8">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-white/10"></div>
                </div>
                <div className="relative flex justify-center text-[10px] uppercase tracking-[0.2em]">
                  <span className="bg-[#0f0f15] px-4 text-white/60">Or</span>
                </div>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} className="space-y-5">
                {isSignUp && (
                  <div>
                    <label className="block text-[11px] uppercase tracking-[0.15em] text-white/60 mb-2">
                      Full Name
                    </label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="w-full px-4 py-3 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                      placeholder="John Doe"
                      required={isSignUp}
                    />
                  </div>
                )}

                <div>
                  <label className="block text-[11px] uppercase tracking-[0.15em] text-white/60 mb-2">
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                      placeholder="you@company.com"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] uppercase tracking-[0.15em] text-white/60 mb-2">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                      placeholder="••••••••"
                      required
                    />
                  </div>
                </div>

                {!isSignUp && (
                  <div className="flex items-center justify-between text-[12px]">
                    <label className="flex items-center gap-2 text-white/70 cursor-pointer">
                      <input
                        type="checkbox"
                        className="w-4 h-4 bg-white/5 border border-white/20 rounded"
                      />
                      Remember me
                    </label>
                    <a href="#" className="text-white/70 hover:text-white transition-opacity">
                      Forgot password?
                    </a>
                  </div>
                )}

                <motion.button
                  whileHover={{ scale: 1.02, backgroundColor: "rgba(255, 255, 255, 1)" }}
                  whileTap={{ scale: 0.98 }}
                  type="submit"
                  className="w-full mt-6 px-6 py-4 bg-white text-black uppercase text-[11px] tracking-[0.2em] hover:text-black transition-all group flex items-center justify-center gap-2"
                >
                  {isSignUp ? "Create Account" : "Sign In"}
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </motion.button>
              </form>

              {/* Toggle Link */}
              <div className="mt-8 text-center text-[13px] text-white/70">
                {isSignUp ? "Already have an account?" : "Don't have an account?"}{" "}
                <button
                  onClick={() => {
                    if (isSignUp) {
                      setIsSignUp(false);
                    } else {
                      onSwitchToSignUp?.();
                    }
                  }}
                  className="text-white hover:underline transition-all"
                >
                  {isSignUp ? "Sign in" : "Sign up"}
                </button>
              </div>

              {/* Terms */}
              {isSignUp && (
                <p className="mt-6 text-[11px] text-white/50 text-center leading-relaxed">
                  By creating an account, you agree to our Terms of Service and Privacy Policy
                </p>
              )}
            </motion.div>
          </div>
          {/* Back Button */}
          <motion.button
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            onClick={onClose}
            className="absolute top-0 left-0 px-6 py-3 border-r border-b border-white/10 bg-white/5 backdrop-blur-sm uppercase text-[11px] tracking-[0.15em] text-white hover:bg-white/10 transition-colors z-10"
          >
            ← Back
          </motion.button>
        </motion.div>
      </div>
    </div>
  );
}
