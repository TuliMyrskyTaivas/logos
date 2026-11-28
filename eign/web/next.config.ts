import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The container runs `node server.js` from the standalone bundle.
  output: "standalone",
  reactStrictMode: true,
};

export default nextConfig;
