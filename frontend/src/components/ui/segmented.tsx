import { cn } from "@/lib/cn";

export type SegmentedOption<T extends string> = { value: T; label: string; hint?: string };

/**
 * Switches between views of the same thing. Two to four short options.
 * The selected segment gets the overlay step and a hairline, not the accent.
 */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  className,
}: {
  options: readonly SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  className?: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        "inline-flex h-11 gap-1 rounded-lg border border-line bg-surface p-1",
        className,
      )}
    >
      {options.map((o) => {
        const selected = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={selected}
            title={o.hint}
            onClick={() => onChange(o.value)}
            className={cn(
              "flex-1 cursor-pointer whitespace-nowrap rounded-md px-3 text-small font-medium",
              "transition-colors duration-(--dur-move) ease-standard",
              selected
                ? "bg-overlay text-ink shadow-[inset_0_0_0_1px_var(--color-line-strong)]"
                : "text-ink-secondary hover:text-ink",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
