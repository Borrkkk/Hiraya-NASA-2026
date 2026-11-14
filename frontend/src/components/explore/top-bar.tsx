"use client";

import { ArrowLeft, Check, Link2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Logo } from "@/components/ui";
import { formatCoords } from "@/lib/sky/format";
import { useExplore } from "./use-explore";

/** Back to the sky, where we are, and a link to this exact view. */
export function TopBar() {
  const { area, params } = useExplore();
  const [copied, setCopied] = useState(false);
  const name = params.q ?? area?.name ?? "This patch of sky";
  const c = area?.center ?? params.target;

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
      <button
        type="button"
        onClick={copy}
        className="ml-auto inline-flex h-10 shrink-0 cursor-pointer items-center gap-2 rounded-md border border-line-strong bg-raised px-3 text-small text-ink transition-colors duration-(--dur-feedback) ease-standard hover:bg-overlay"
      >
        {copied ? <Check size={16} strokeWidth={1.5} aria-hidden="true" /> : <Link2 size={16} strokeWidth={1.5} aria-hidden="true" />}
        {copied ? "Link copied" : "Copy link"}
      </button>
    </header>
  );
}
