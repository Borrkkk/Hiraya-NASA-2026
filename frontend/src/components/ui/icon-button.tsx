import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

const variants = {
  primary: "bg-primary text-on-primary hover:bg-primary-hover",
  secondary: "border-line-strong bg-raised text-ink hover:bg-overlay",
  quiet: "bg-transparent text-ink-secondary hover:bg-raised hover:text-ink",
} as const;

/**
 * Square button with one icon. `label` is required: it is the accessible name
 * and the tooltip. 40px, or 44px (`size="lg"`) for primary actions on mobile.
 */
export function IconButton({
  label,
  variant = "secondary",
  size = "md",
  className,
  children,
  ...rest
}: Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  label: string;
  variant?: keyof typeof variants;
  size?: "md" | "lg";
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex shrink-0 cursor-pointer items-center justify-center rounded-md border border-transparent",
        "transition-[background-color,color,border-color,transform] duration-(--dur-feedback) ease-standard active:scale-[0.98]",
        "disabled:cursor-not-allowed disabled:opacity-60",
        size === "lg" ? "size-11" : "size-10",
        variants[variant],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
