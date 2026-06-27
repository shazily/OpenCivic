/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  experimental: { typedRoutes: false },
  images: { domains: ["localhost"] },
};

export default nextConfig;
