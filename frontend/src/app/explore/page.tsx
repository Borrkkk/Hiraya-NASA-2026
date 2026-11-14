import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { Logo } from "@/components/ui";
import { ExploreParams } from "./explore-params";

export const metadata: Metadata = { title: "Explore · Pulsr" };

/**
 * Placeholder for exploration mode, so links from the home screen land
 * somewhere. Replace this page when exploration is designed; the home screen
 * already builds its links with lib/explore.ts.
 */
export default function ExplorePage() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-xl flex-col justify-center gap-8 px-6 py-16">
      <Logo size={22} />
      <div className="flex flex-col gap-2">
        <h1 className="text-h1 text-ink">Exploring comes next</h1>
        <p className="text-body text-ink-secondary">
          This is where you&apos;ll fly around real SPHEREx data. For now, here&apos;s
          where you were headed.
        </p>
      </div>
      <Suspense fallback={null}>
        <ExploreParams />
      </Suspense>
      <Link
        href="/"
        className="inline-flex h-11 w-fit items-center gap-2 rounded-md border border-line-strong bg-raised px-4 text-body-sm font-medium text-ink transition-colors duration-(--dur-feedback) ease-standard hover:bg-overlay"
      >
        <ArrowLeft size={16} strokeWidth={1.5} aria-hidden="true" />
        Back to the sky
      </Link>
    </main>
  );
}
