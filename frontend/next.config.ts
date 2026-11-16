import type { NextConfig } from "next";

// The deployed preview is fully static and serverless: no backend. Only when
// BACKEND_URL is set explicitly (local development against the Python API,
// with NEXT_PUBLIC_EXPLORE_API=http) is `/api/*` proxied to it.
const BACKEND_URL = process.env.BACKEND_URL;

const nextConfig: NextConfig = {
  // Cutouts are pre-baked WebP; serve them as-is.
  images: { unoptimized: true },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // The prefetched demo pictures never change between deploys of the same data:
  // let the browser and Vercel's edge keep them.
  async headers() {
    return [
      {
        source: "/demo/:path*",
        headers: [{ key: "Cache-Control", value: "public, max-age=86400, stale-while-revalidate=604800" }],
      },
    ];
  },
  async rewrites() {
    return BACKEND_URL ? [{ source: "/api/:path*", destination: `${BACKEND_URL}/:path*` }] : [];
  },
};

export default nextConfig;
