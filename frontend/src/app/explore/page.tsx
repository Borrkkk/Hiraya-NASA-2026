import type { Metadata } from "next";
import { Suspense } from "react";
import { ExploreApp } from "@/components/explore/explore-app";

export const metadata: Metadata = { title: "Explore · Pulsr" };

/**
 * Exploration mode. Desktop only (see the spec). The page reads its starting
 * area from the URL, which the home screen builds with lib/explore/href.ts.
 */
export default function ExplorePage() {
  return (
    <Suspense fallback={<div className="h-dvh bg-ground" />}>
      <ExploreApp />
    </Suspense>
  );
}
