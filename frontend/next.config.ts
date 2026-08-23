import type { NextConfig } from "next";

// Standalone output is for Docker only; Vercel uses its own deployment bundler.
const nextConfig: NextConfig = {
  ...(process.env.DOCKER_BUILD === "true" ? { output: "standalone" as const } : {}),
};

export default nextConfig;
