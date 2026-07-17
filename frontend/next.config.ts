import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "cdn.sportmonks.com",
      },
    ],
  },
  reactStrictMode: true,
  async redirects() {
    return [
      {
        source: "/coaches/:path*",
        destination: "/teams",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
