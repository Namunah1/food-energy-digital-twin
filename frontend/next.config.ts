import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://food-energy-backend:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;