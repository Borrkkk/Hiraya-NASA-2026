import Link from "next/link";
import { cn } from "@/lib/cn";

export type FaceTone = 1 | 2 | 3 | 4;
export type Person = { id: string; initials: string; tone: FaceTone; name: string };

const tones: Record<FaceTone, string> = {
  1: "bg-face-1",
  2: "bg-face-2",
  3: "bg-face-3",
  4: "bg-face-4",
};

/** Initials on a face tone. Pulsr shows no photos of people. */
export function Avatar({
  initials,
  tone,
  size = "md",
  className,
}: {
  initials: string;
  tone: FaceTone;
  size?: "md" | "sm";
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-on-face",
        size === "md" ? "size-8 text-[13px]" : "size-5 text-[9px]",
        tones[tone],
        className,
      )}
    >
      {initials}
    </span>
  );
}

/** Overlapping avatars plus one line of social text. */
export function FaceStack({
  people,
  max = 3,
  children,
  className,
}: {
  people: Person[];
  max?: number;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span className="flex">
        {people.slice(0, max).map((p) => (
          <Link key={p.id} href={`/profile/${encodeURIComponent(p.id)}`} aria-label={`View ${p.name}’s profile`} className="-ml-1.5 rounded-full first:ml-0">
            <Avatar initials={p.initials} tone={p.tone} size="sm" className="border-2 border-ground" />
          </Link>
        ))}
      </span>
      {children && <span className="text-small text-ink-secondary">{children}</span>}
    </span>
  );
}
