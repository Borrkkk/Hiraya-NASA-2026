import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Logo } from "@/components/ui";

export const metadata: Metadata = { title: "Share · Pulsr" };

/**
 * Placeholder for the Share flow, so "Share this find" on the Explore page
 * lands somewhere. The draft (view, spectrum, track, epochs) is in
 * sessionStorage under lib/explore/share.ts SHARE_KEY.
 */
export default function SharePage() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-xl flex-col justify-center gap-8 px-6 py-16">
      <Logo size={22} />
      <div className="flex flex-col gap-2">
        <h1 className="text-h1 text-ink">Sharing comes next</h1>
        <p className="text-body text-ink-secondary">
          Your find is saved with this tab. The share flow will pick it up from here.
        </p>
      </div>
      <Link
        href="/explore"
        className="inline-flex h-11 w-fit items-center gap-2 rounded-md border border-line-strong bg-raised px-4 text-body-sm font-medium text-ink transition-colors duration-(--dur-feedback) ease-standard hover:bg-overlay"
      >
        <ArrowLeft size={16} strokeWidth={1.5} aria-hidden="true" />
        Back to exploring
      </Link>
    </main>
  );
}
