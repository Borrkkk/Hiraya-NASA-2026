import Link from "next/link";
import { SkyImage } from "@/components/ui";
import { exploreHref } from "@/lib/explore";
import { popular } from "@/lib/feed/mock";
import { getObject } from "@/lib/sky/catalog";
import { formatCount } from "@/lib/sky/format";
import { FeedSection } from "./section";

/** A leaderboard: rank, thumbnail, name, and a bar for how many people looked. */
export function Popular() {
  const max = Math.max(...popular.map((p) => p.looks));
  return (
    <FeedSection title="Popular right now" subtitle="Where people are looking this week">
      <ol className="flex flex-col rounded-lg border border-line bg-surface p-1">
        {popular.map((p, i) => {
          const o = getObject(p.objectId);
          return (
            <li key={p.objectId}>
              <Link
                href={exploreHref({ q: o.name, ra: o.ra, dec: o.dec, fov: p.fov })}
                className="grid grid-cols-[20px_48px_1fr_auto] items-center gap-3 rounded-md p-2 transition-colors duration-(--dur-feedback) ease-standard hover:bg-raised"
              >
                <span className="font-mono text-mono-sm tabular-nums text-ink-muted">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <SkyImage
                  cutout={p.cutout}
                  alt=""
                  className="size-12 rounded-sm"
                  sizes="48px"
                  tag={false}
                />
                <span className="flex min-w-0 flex-col gap-1.5">
                  <span className="flex flex-col">
                    <span className="truncate text-body-sm text-ink">{o.name}</span>
                    <span className="truncate text-small text-ink-secondary">{p.why}</span>
                  </span>
                  <span aria-hidden="true" className="h-1 overflow-hidden rounded-full bg-raised">
                    <span
                      className="block h-full rounded-full bg-ink-muted"
                      style={{ width: `${Math.round((p.looks / max) * 100)}%` }}
                    />
                  </span>
                </span>
                <span className="text-right">
                  <span className="block font-mono text-mono tabular-nums text-ink">
                    {formatCount(p.looks)}
                  </span>
                  <span className="block text-caption text-ink-muted">looks</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </FeedSection>
  );
}
