"use client";

import { MeshGradient } from "@paper-design/shaders-react";

export function WaveBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden bg-[#0a0a0f]">
      <MeshGradient
        className="absolute inset-0 w-full h-full"
        colors={["#0a0a0f", "#1e3a8a", "#4338ca", "#312e81", "#1e1b4b"]}
        speed={0.3}
      />

      <MeshGradient
        className="absolute inset-0 w-full h-full opacity-50"
        colors={["#0a0a0f", "#06b6d4", "#3b82f6", "#8b5cf6", "#6366f1"]}
        speed={0.2}
      />
    </div>
  );
}
