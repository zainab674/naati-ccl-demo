import type { NextConfig } from "next";

// Where the Next.js server forwards /api/* (the FastAPI backend). In production Caddy routes /api/* straight to the
// backend, so this rewrite only matters in development and as a fallback.
const API_URL = process.env.API_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Same-origin proxy to FastAPI: the httpOnly session cookie then travels with
  // every media request, which is what binds audio URLs to the login session.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "microphone=(self), camera=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
