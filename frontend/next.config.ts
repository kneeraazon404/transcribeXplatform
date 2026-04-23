import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["0.0.0.0"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
