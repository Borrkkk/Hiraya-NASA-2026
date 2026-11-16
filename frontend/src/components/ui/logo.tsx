import { cn } from "@/lib/cn";

/**
 * Hiraya logo: a reticle frame with an ember dot, then the name.
 * Size 22–24 in app headers, 40 on slides. Never recolour the dot, and never
 * put it on a sky image without a scrim.
 */
export function Logo({
  size = 22,
  wordmark = true,
  className,
}: {
  size?: number;
  wordmark?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn("inline-flex items-center gap-2.5 text-ink", className)}
      aria-label={wordmark ? undefined : "Hiraya"}
      role={wordmark ? undefined : "img"}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
        className="shrink-0"
      >
        <path
          d="M3 8V3h5M16 3h5v5M21 16v5h-5M8 21H3v-5"
          className="stroke-ink"
          strokeWidth={1.5}
        />
        <circle cx="12" cy="12" r="2.5" className="fill-ember" />
      </svg>
      {wordmark && (
        <span
          className="font-medium tracking-[-0.01em]"
          style={{ fontSize: size * 0.78, lineHeight: 1 }}
        >
          Hiraya
        </span>
      )}
    </span>
  );
}
