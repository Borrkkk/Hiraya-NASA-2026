"use client";

import { ArrowLeft, Check, Link2, MapPin } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { exploreHref } from "@/lib/explore/href";
import { separationDeg } from "@/lib/explore/projection";
import { useStore } from "@/lib/explore/store";
import { Logo } from "@/components/ui";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { formatCoords } from "@/lib/sky/format";
import { useExplore } from "./use-explore";

/** Back to the sky, where we are, and a link to this exact view. */
export function TopBar() {
  const { area, params, viewStore } = useExplore();
  const router = useRouter();
  const view = useStore(viewStore);
  const [copied, setCopied] = useState(false);
  const name = params.fallback ? "Orion (default sky)" : params.q ?? area?.name ?? "This patch of sky";
  // The camera can pan inside one loaded cutout, but panning does not fetch
  // images for a NEW sky region. Offer an explicit refresh at the new centre.
  const moved = !!area && separationDeg(area.center, view) > Math.max(0.02, area.extentDeg * 0.15);
  const c = view;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard blocked: the address bar already holds the link.
    }
  };

  return (
    <header className="flex h-14 shrink-0 items-center gap-4">
      <Link
        href="/"
        className="inline-flex h-10 items-center gap-2 rounded-md px-3 text-small text-ink-secondary transition-colors duration-(--dur-feedback) ease-standard hover:bg-raised hover:text-ink"
      >
        <ArrowLeft size={16} strokeWidth={1.5} aria-hidden="true" />
        Home
      </Link>
      <Logo size={20} wordmark={false} className="max-lg:hidden" />
      <h1 className="flex min-w-0 items-baseline gap-3">
        <span className="truncate text-h3 text-ink">{name}</span>
        <span className="hidden shrink-0 font-mono text-mono tabular-nums text-ink-secondary md:inline">
          {formatCoords(c.ra, c.dec)}
        </span>
      </h1>
      {moved && (
        <button
          type="button"
          onClick={() => router.push(exploreHref({ ra: view.ra, dec: view.dec, fov: view.fov }))}
          title="Load new SPHEREx images at the centre of this view"
          className="inline-flex h-10 shrink-0 items-center gap-2 rounded-md border border-line-strong bg-raised px-3 text-small text-ink transition-colors duration-(--dur-feedback) ease-standard hover:bg-overlay"
        >
          <MapPin size={15} strokeWidth={1.5} aria-hidden="true" />
          Load this sky area
        </button>
      )}
      <button
        type="button"
        onClick={copy}
        className="ml-auto inline-flex h-10 shrink-0 cursor-pointer items-center gap-2 rounded-md border border-line-strong bg-raised px-3 text-small text-ink transition-colors duration-(--dur-feedback) ease-standard hover:bg-overlay"
      >
        {copied ? <Check size={16} strokeWidth={1.5} aria-hidden="true" /> : <Link2 size={16} strokeWidth={1.5} aria-hidden="true" />}
        {copied ? "Link copied" : "Copy link"}
      </button>
      <ThemeToggle />
    </header>
  );
}
