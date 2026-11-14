import Link from "next/link";
import { exploreHref } from "@/lib/explore";
import { news } from "@/lib/feed/mock";
import type { ObjectKind } from "@/lib/sky/catalog";
import { FeedSection } from "./section";

/**
 * Headlines in one box with hairline dividers: a topic line, then the story.
 * Text only. These stories aren't about one patch of sky, so there's no image,
 * and nothing scrolls sideways inside the vertical feed.
 */
export function News() {
  return (
    <FeedSection title="In the news">
      <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-lg bg-raised">
        {news.map((n) => (
          <li key={n.id}>
            <Link
              href={exploreHref({ ...n.target, types: n.target.types as ObjectKind[] | undefined })}
              className="flex flex-col gap-1 p-4 transition-colors duration-(--dur-feedback) ease-standard hover:bg-overlay"
            >
              <span className="text-small text-ink-secondary">{n.kicker}</span>
              <span className="text-body-sm text-ink">{n.title}</span>
            </Link>
          </li>
        ))}
      </ul>
    </FeedSection>
  );
}
