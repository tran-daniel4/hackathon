import type { NextConfig } from "next";
import dotenv from "dotenv";
import path from "path";

// Load .env from the monorepo root (two levels up from app/web/)
dotenv.config({ path: path.resolve(__dirname, "../../.env") });

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
