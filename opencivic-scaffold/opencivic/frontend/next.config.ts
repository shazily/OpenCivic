import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  output: "standalone",
  experimental: { typedRoutes: true },
  images: { domains: ["localhost"] },
};
export default nextConfig;
