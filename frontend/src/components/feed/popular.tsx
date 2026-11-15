import Link from "next/link";
import { exploreHref } from "@/lib/explore/href";
import { popular } from "@/lib/feed/mock";
import { getObject } from "@/lib/sky/catalog";
import { formatCount } from "@/lib/sky/format";
import { FeedSection } from "./section";

/**
 * A plain ranked list: rank, name, one line, and how many looked. Text only,
 * no thumbnails, bars or box, so it reads as a quick scan between the hero
 * above and the stories below.
 */
export function Popular() {
  return (
    <FeedSection title="Popular right now" meta="Looks this week">
      <ol className="flex flex-col">
        {popular.map((p, i) => {
          const o = getObject(p.objectId);
          return (
            <li key={p.objectId}>
              <Link
                href={exploreHref({ q: o.name, ra: o.ra, dec: o.dec, fov: p.fov })}
                className="grid grid-cols-[24px_1fr_auto] items-center gap-3 rounded-lg p-2 transition-colors duration-(--dur-feedback) ease-standard hover:bg-raised"
              >
                <span className="font-mono text-mono-sm tabular-nums text-ink-secondary">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="flex min-w-0 flex-col">
                  <span className="truncate text-body-sm text-ink">{o.name}</span>
                  <span className="truncate text-small text-ink-secondary">{p.why}</span>
                </span>
                <span className="font-mono text-mono tabular-nums text-ink-secondary">
                  {formatCount(p.looks)}
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </FeedSection>
  );
}
