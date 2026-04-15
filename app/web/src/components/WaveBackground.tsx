"use client";

import { MeshGradient } from "@paper-design/shaders-react";

// 1280×720 pixel cap — prevents full-resolution rendering on large/retina screens
const MAX_PIXEL_COUNT = 1280 * 720;

export function WaveBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden bg-[#0a0a0f]">
      <MeshGradient
        className="absolute inset-0 w-full h-full"
        colors={["#0a0a0f", "#1e3a8a", "#4338ca", "#06b6d4", "#312e81", "#6366f1"]}
        speed={0.3}
        minPixelRatio={1}
        maxPixelCount={MAX_PIXEL_COUNT}
      />
    </div>
  );
}
