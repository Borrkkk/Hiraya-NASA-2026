import { ChevronRight, Crosshair } from "lucide-react";
import Link from "next/link";
import { exploreHref } from "@/lib/explore";
import { news } from "@/lib/feed/mock";
import type { ObjectKind } from "@/lib/sky/catalog";
import { FeedSection } from "./section";

/**
 * Headline-led cards in a sideways scroller. Each leads with a big number when
 * there's a real one, since a figure is what stops a thumb. No images: these
 * stories aren't about one patch of sky, and Pulsr never fakes the sky.
 */
export function News() {
  return (
    <FeedSection title="In the news" subtitle="What's happening up there">
      <ul className="no-scrollbar -mx-4 flex scroll-pl-4 snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-1">
        {news.map((n) => (
          <li key={n.id} className="flex w-[272px] shrink-0 snap-start">
            <Link
              href={exploreHref({ ...n.target, types: n.target.types as ObjectKind[] | undefined })}
              className="group flex w-full flex-col gap-4 rounded-lg border border-line bg-surface p-4 transition-colors duration-(--dur-feedback) ease-standard hover:border-line-strong hover:bg-raised"
            >
              <p className="text-small text-ink-secondary">{n.kicker}</p>

              {n.figure && (
                <p className="flex flex-col">
                  <span className="font-mono text-mono-figure tabular-nums text-ink">
                    {n.figure.value}
                  </span>
                  <span className="text-small text-ink-secondary">{n.figure.caption}</span>
                </p>
              )}

              <div className="flex flex-col gap-2">
                <h4 className="text-h3 text-ink">{n.title}</h4>
                <p className="line-clamp-3 text-body-sm text-ink-secondary">{n.body}</p>
              </div>

              <p className="mt-auto flex items-center justify-between border-t border-line pt-3 text-small text-ink-secondary">
                <span className="inline-flex items-center gap-2">
                  <Crosshair size={16} strokeWidth={1.5} aria-hidden="true" />
                  {n.where}
                </span>
                <ChevronRight
                  size={16}
                  strokeWidth={1.5}
                  aria-hidden="true"
                  className="transition-colors duration-(--dur-feedback) ease-standard group-hover:text-ink"
                />
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </FeedSection>
  );
}
