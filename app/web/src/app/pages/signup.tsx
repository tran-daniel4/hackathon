import { motion } from "motion/react";
import { useState } from "react";
import { WaveBackground } from "@/app/components/WaveBackground";
import { FaGithub } from "react-icons/fa";
import { Mail, Lock, User, ArrowRight } from "lucide-react";

interface SignUpPageProps {
  onClose?: () => void;
  onSwitchToLogin?: () => void;
}

export function SignUpPage({ onClose, onSwitchToLogin }: SignUpPageProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      alert("Passwords do not match");
      return;
    }
    if (!acceptedTerms) {
      alert("Please accept the terms and conditions");
      return;
    }
    console.log("Sign up submitted:", { email, password, fullName });
  };

  const handleGithubSignUp = () => {
    console.log("GitHub sign up initiated");
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-[#0a0a0f] flex">
      {/* Background */}
      <WaveBackground />

      {/* Content */}
      <div className="relative z-10 w-full max-w-[900px] px-8 my-auto py-6 mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className="relative grid grid-cols-1 md:grid-cols-2 gap-0 border border-white/10 bg-[#0f0f15]/80 backdrop-blur-xl overflow-hidden"
        >
          {/* Left Side - Branding */}
          <div className="p-8 md:p-10 bg-linear-to-br from-white/2 to-transparent border-r border-white/10">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            >
              <div className="mb-8 mt-8">
                <h2 className="text-[clamp(1.8rem,4vw,2.5rem)] leading-[1.1] tracking-[-0.02em] mb-3 text-white">
                  DynoDocs
                </h2>
                <div className="uppercase text-[10px] tracking-[0.2em] text-white/60">
                  [ ARCHITECTURE INTELLIGENCE ]
                </div>
              </div>

              <div className="space-y-6">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.15em] text-white/60 mb-2">
                    What You Get
                  </div>
                  <p className="text-[14px] text-white/80 leading-relaxed">
                    Join teams transforming how they understand and debug complex systems
                  </p>
                </div>

                <div>
                  <div className="text-[11px] uppercase tracking-[0.15em] text-white/60 mb-2">
                    Features Included
                  </div>
                  <ul className="space-y-2 text-[13px] text-white/80">
                    <li className="flex items-start gap-2">
                      <span className="text-blue-400 mt-0.5">•</span>
                      <span>Interactive architecture diagrams</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-400 mt-0.5">•</span>
                      <span>Real-time flow visualization</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-400 mt-0.5">•</span>
                      <span>Automated bottleneck detection</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-400 mt-0.5">•</span>
                      <span>Team collaboration tools</span>
                    </li>
                  </ul>
                </div>
              </div>
            </motion.div>
          </div>

          {/* Right Side - Form */}
          <div className="p-8 md:p-10">
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
            >
              {/* Header */}
              <div className="mb-5">
                <h3 className="text-[clamp(1.3rem,3vw,1.8rem)] mb-1 leading-tight text-white">
                  Create Your Account
                </h3>
                <p className="text-[13px] text-white/70">
                  Start visualizing your architecture in minutes
                </p>
              </div>

              {/* GitHub Sign Up */}
              <motion.button
                whileHover={{ scale: 1.02, backgroundColor: "rgba(255, 255, 255, 0.08)" }}
                whileTap={{ scale: 0.98 }}
                onClick={handleGithubSignUp}
                className="w-full mb-4 px-6 py-3 border border-white/20 bg-white/5 backdrop-blur-sm flex items-center justify-center gap-3 uppercase text-[11px] tracking-[0.15em] transition-colors group text-white"
              >
                <FaGithub className="w-4 h-4 opacity-80 group-hover:opacity-100 transition-opacity" />
                Sign up with GitHub
              </motion.button>

              {/* Divider */}
              <div className="relative mb-4">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-white/10"></div>
                </div>
                <div className="relative flex justify-center text-[10px] uppercase tracking-[0.2em]">
                  <span className="bg-[#0f0f15] px-4 text-white/60">Or</span>
                </div>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} className="space-y-3">
                <div>
                  <label className="block text-[11px] uppercase tracking-[0.15em] text-white/60 mb-1.5">
                    Full Name
                  </label>
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full pl-12 pr-4 py-2.5 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                      placeholder="John Doe"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] uppercase tracking-[0.15em] text-white/60 mb-1.5">
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full pl-12 pr-4 py-2.5 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                      placeholder="you@company.com"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] uppercase tracking-[0.15em] text-white/60 mb-1.5">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full pl-12 pr-4 py-2.5 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                      placeholder="••••••••"
                      required
                      minLength={8}
                    />
                  </div>
                  <p className="mt-1 text-[11px] text-white/40">Minimum 8 characters</p>
                </div>

                <div>
                  <label className="block text-[11px] uppercase tracking-[0.15em] text-white/60 mb-1.5">
                    Confirm Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="w-full pl-12 pr-4 py-2.5 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                      placeholder="••••••••"
                      required
                      minLength={8}
                    />
                  </div>
                </div>

                <div>
                  <label className="flex items-start gap-3 text-white/70 cursor-pointer text-[12px]">
                    <input
                      type="checkbox"
                      checked={acceptedTerms}
                      onChange={(e) => setAcceptedTerms(e.target.checked)}
                      className="mt-0.5 w-4 h-4 bg-white/5 border border-white/20 rounded shrink-0"
                      required
                    />
                    <span className="leading-relaxed">
                      I agree to the{" "}
                      <a href="#" className="text-white hover:underline">Terms of Service</a>
                      {" "}and{" "}
                      <a href="#" className="text-white hover:underline">Privacy Policy</a>
                    </span>
                  </label>
                </div>

                <motion.button
                  whileHover={{ scale: 1.02, backgroundColor: "rgba(255, 255, 255, 1)" }}
                  whileTap={{ scale: 0.98 }}
                  type="submit"
                  className="w-full mt-2 px-6 py-3 bg-white text-black uppercase text-[11px] tracking-[0.2em] hover:text-black transition-all group flex items-center justify-center gap-2"
                >
                  Create Account
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </motion.button>
              </form>

              {/* Switch to Login */}
              <div className="mt-5 text-center text-[13px] text-white/70">
                Already have an account?{" "}
                <button
                  onClick={onSwitchToLogin}
                  className="text-white hover:underline transition-all"
                >
                  Sign in
                </button>
              </div>
            </motion.div>
          </div>

          {/* Back Button */}
          <motion.button
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            onClick={onClose}
            className="absolute top-3 left-0 px-6 py-3 uppercase text-[11px] tracking-[0.15em] text-white/60 hover:text-white transition-colors z-10"
          >
            ← Back
          </motion.button>
        </motion.div>
      </div>
    </div>
  );
}
