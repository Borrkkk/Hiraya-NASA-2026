import Image from "next/image";
import { cn } from "@/lib/cn";
import { formatFov } from "@/lib/sky/format";
import { getCutout } from "@/lib/sky/cutouts";
import { Reticle } from "./reticle";

/**
 * A real sky cutout in a `sky` well. Never decorative: the image is survey
 * data, the reticle marks the object it's centred on, and the tag says what
 * you're looking at (survey and field of view) on a scrim.
 */
export function SkyImage({
  cutout,
  alt,
  className,
  sizes = "400px",
  priority,
  reticle,
  tag = true,
}: {
  cutout: string;
  alt: string;
  className?: string;
  sizes?: string;
  priority?: boolean;
  /** Draw the Pulsr reticle on the centre of the image. Omit on small thumbnails. */
  reticle?: { size?: number };
  tag?: boolean;
}) {
  const c = getCutout(cutout);
  return (
    <div className={cn("relative overflow-hidden bg-sky", className)}>
      <Image
        src={c.src}
        alt={alt}
        fill
        sizes={sizes}
        priority={priority}
        className="object-cover"
      />
      {reticle && (
        <div className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <Reticle size={reticle.size ?? 44} />
        </div>
      )}
      {tag && (
        <span className="absolute left-3 top-3 rounded-xs bg-scrim px-2 py-1 font-mono text-mono-sm text-ink tabular-nums">
          {c.surveyLabel} · {formatFov(c.fov)} field
        </span>
      )}
    </div>
  );
}
