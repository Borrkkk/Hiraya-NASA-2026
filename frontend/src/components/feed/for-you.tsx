import Link from "next/link";
import { SkyImage } from "@/components/ui";
import { exploreHref } from "@/lib/explore/href";
import { forYou } from "@/lib/feed/mock";
import { getObject } from "@/lib/sky/catalog";
import { formatCoords } from "@/lib/sky/format";
import { FeedSection } from "./section";

/**
 * The one image-led moment in the feed: a hero with the reticle on its object,
 * then two quiet rows. Everything below it is calmer on purpose, so the eye
 * lands here first and the sky behind stays the brightest thing on screen.
 */
export function ForYou() {
  const { hero, picks, basis } = forYou;
  const heroObj = getObject(hero.objectId);

  return (
    <FeedSection title="For you" meta={basis}>
      <Link
        href={exploreHref({ q: heroObj.name, ra: heroObj.ra, dec: heroObj.dec, fov: hero.fov })}
        className="group flex flex-col overflow-hidden rounded-lg bg-raised transition-colors duration-(--dur-feedback) ease-standard hover:bg-overlay"
      >
        <div className="relative">
          <SkyImage
            cutout={hero.cutout}
            alt={`${heroObj.name} in infrared`}
            className="aspect-[8/5]"
            sizes="440px"
            reticle={{ size: 40 }}
            priority
          />
          {/* Ground-to-transparent scrim keeps the caption readable. */}
          <div className="absolute inset-x-0 bottom-0 flex flex-col gap-1 bg-linear-to-t from-raised via-raised/80 to-transparent px-4 pb-3 pt-16">
            <p className="font-mono text-mono-sm tabular-nums text-ink-secondary">
              {formatCoords(heroObj.ra!, heroObj.dec!)}
            </p>
            <h4 className="text-h3 text-ink">{heroObj.name}</h4>
          </div>
        </div>
        <div className="flex flex-col gap-2 p-4">
          <p className="text-body-sm text-ink-secondary">{hero.why}</p>
          <p className="text-small text-ink-secondary">{hero.social}</p>
        </div>
      </Link>

      <ul className="flex flex-col">
        {picks.map((p) => {
          const o = getObject(p.objectId);
          return (
            <li key={p.objectId}>
              <Link
                href={exploreHref({ q: o.name, ra: o.ra, dec: o.dec, fov: p.fov })}
                className="grid grid-cols-[48px_1fr] items-center gap-3 rounded-lg p-2 transition-colors duration-(--dur-feedback) ease-standard hover:bg-raised"
              >
                <SkyImage
                  cutout={p.cutout}
                  alt=""
                  className="size-12 rounded-xs"
                  sizes="48px"
                  tag={false}
                />
                <span className="flex min-w-0 flex-col">
                  <span className="truncate text-body-sm text-ink">{o.name}</span>
                  <span className="truncate text-small text-ink-secondary">{p.short}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </FeedSection>
  );
}
