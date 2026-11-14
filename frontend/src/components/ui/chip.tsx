import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

/** A filter toggle. Selected uses the ember wash: it is the current selection. */
export function Chip({
  selected = false,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={cn(
        "inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-md border px-3 text-small",
        "transition-colors duration-(--dur-feedback) ease-standard",
        selected
          ? "border-ember-line bg-ember-wash text-ink"
          : "border-line-strong bg-surface text-ink-secondary hover:text-ink",
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
