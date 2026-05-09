import type { NextConfig } from "next";
import dotenv from "dotenv";
import path from "path";
import fs from "fs";

const rootEnvPath = path.resolve(__dirname, "../../.env");

// Load the monorepo root .env for local development only. Vercel provides env vars separately.
if (process.env.VERCEL !== "1" && fs.existsSync(rootEnvPath)) {
  dotenv.config({ path: rootEnvPath, quiet: true });
}

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
