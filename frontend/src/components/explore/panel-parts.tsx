"use client";

import { ChevronDown } from "lucide-react";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

/** A sidebar section that folds away. */
export function Collapsible({
  title,
  meta,
  defaultOpen = true,
  children,
}: {
  title: string;
  meta?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="flex flex-col border-b border-line last:border-b-0">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex h-12 shrink-0 cursor-pointer items-center justify-between gap-3 px-4 text-left transition-colors duration-(--dur-feedback) ease-standard hover:bg-raised"
      >
        <span className="text-body-sm font-medium text-ink">{title}</span>
        <span className="flex items-center gap-2 text-small text-ink-secondary">
          {meta}
          <ChevronDown size={16} strokeWidth={1.5} aria-hidden="true" className={cn("transition-transform duration-(--dur-move) ease-standard", open && "rotate-180")} />
        </span>
      </button>
      {open && <div className="flex flex-col gap-4 px-4 pb-4">{children}</div>}
    </section>
  );
}

/** A "show the real value" toggle: the plain words lead, this reveals the number. */
export function Reveal({
  label,
  children,
  mono = false,
}: {
  label: string;
  children: ReactNode;
  /** Numbers read in mono; explanations in the interface font. */
  mono?: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="w-fit cursor-pointer rounded-xs text-small text-ink-secondary underline underline-offset-4 transition-colors duration-(--dur-feedback) ease-standard hover:text-ink"
      >
        {open ? "Hide" : label}
      </button>
      {open && (
        <p className={mono ? "font-mono text-mono tabular-nums text-ink-secondary" : "text-small text-ink-secondary"}>{children}</p>
      )}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-md bg-raised", className)} />;
}

export function Notice({ children, tone = "plain" }: { children: ReactNode; tone?: "plain" | "error" }) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn("flex flex-col gap-3 rounded-lg border p-4 text-small text-ink", tone === "error" ? "border-ember-line bg-ember-wash" : "border-line-strong bg-raised")}
    >
      {children}
    </div>
  );
}

export const buttonPrimary =
  "inline-flex h-11 cursor-pointer items-center justify-center gap-2 rounded-md bg-primary px-4 text-body-sm font-medium text-on-primary transition-colors duration-(--dur-feedback) ease-standard hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60";
export const buttonSecondary =
  "inline-flex h-11 cursor-pointer items-center justify-center gap-2 rounded-md border border-line-strong bg-raised px-4 text-body-sm font-medium text-ink transition-colors duration-(--dur-feedback) ease-standard hover:bg-overlay disabled:cursor-not-allowed disabled:opacity-60";
