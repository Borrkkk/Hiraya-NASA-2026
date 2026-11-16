import type { Metadata } from "next";
import { Suspense } from "react";
import { ExploreApp } from "@/components/explore/explore-app";

export const metadata: Metadata = { title: "Explore · Hiraya" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

/**
 * Exploration mode. Desktop only (see the spec). The page reads its starting
 * area from the URL, which the home screen builds with lib/explore/href.ts.
 */
export default function ExplorePage({ searchParams }: { searchParams: SearchParams }) {
  return (
    <Suspense fallback={<div className="h-dvh bg-ground" />}>
      <Explore searchParams={searchParams} />
    </Suspense>
  );
}

// The URL is read inside Suspense, so the shell can be prerendered.
async function Explore({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  // Route navigation must create a fresh controller and sky viewer. Native
  // replaceState updates made while panning do not re-run this server page.
  const targetKey = JSON.stringify([params.q, params.ra, params.dec]);
  return <ExploreApp key={targetKey} />;
}
