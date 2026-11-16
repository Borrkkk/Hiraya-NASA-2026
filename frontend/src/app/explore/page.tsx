import type { Metadata } from "next";
import { Suspense } from "react";
import { ExploreApp } from "@/components/explore/explore-app";
import { PreviewLimit } from "@/components/explore/preview-limit";
import { inPreviewRegion } from "@/lib/explore/preview-region";

export const metadata: Metadata = { title: "Explore · Hiraya" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

/**
 * Exploration mode. Desktop only. The page reads its starting area from the URL
 * (built with lib/explore/href.ts). Only the Barnard's Star region has data in the
 * preview; any other target shows <PreviewLimit /> instead.
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
  const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? null;
  const target = { q: one(params.q), ra: one(params.ra), dec: one(params.dec) };
  if (!inPreviewRegion(target)) return <PreviewLimit name={target.q} />;
  // Route navigation must create a fresh controller and sky viewer. Native
  // replaceState updates made while panning do not re-run this server page.
  const targetKey = JSON.stringify([params.q, params.ra, params.dec]);
  return <ExploreApp key={targetKey} />;
}
