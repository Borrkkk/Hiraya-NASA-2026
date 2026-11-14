import { cn } from "@/lib/cn";

export type VerdictKind = "explained" | "artifact" | "unexplained";

const styles: Record<VerdictKind, { text: string; label: string }> = {
  explained: { text: "text-explained", label: "Explained" },
  artifact: { text: "text-artifact", label: "Artifact" },
  unexplained: { text: "text-unexplained", label: "Unexplained" },
};

/**
 * The outcome of a check. A status dot, never an icon. The three kinds differ
 * in lightness as well as hue, and Unexplained is never dressed up as a win.
 */
export function Verdict({ kind, className }: { kind: VerdictKind; className?: string }) {
  const v = styles[kind];
  return (
    <span className={cn("inline-flex items-center gap-2 text-small font-medium", v.text, className)}>
      <span aria-hidden="true" className="size-2 shrink-0 rounded-full bg-current" />
      {v.label}
    </span>
  );
}
