import type { NextConfig } from "next";

const isVercel = process.env.VERCEL === "1";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "cdn.sportmonks.com",
      },
    ],
  },
  reactStrictMode: true,

  async rewrites() {
    if (!isVercel) {
      return [];
    }

    return [
      {
        source: "/bff/:path*",
        destination: "http://163.176.59.174/:path*",
      },
    ];
  },
};

export default nextConfig;