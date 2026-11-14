import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { FaceStack, SkyImage } from "@/components/ui";
import { exploreHref } from "@/lib/explore";
import { forYou } from "@/lib/feed/mock";
import { formatCoords } from "@/lib/sky/format";
import { getObject } from "@/lib/sky/catalog";
import { FeedSection } from "./section";

/** One large pick with the reticle on its object, then a row of smaller ones. */
export function ForYou() {
  const { hero, picks, basis } = forYou;
  const heroObj = getObject(hero.objectId);

  return (
    <FeedSection title="For you" subtitle={basis}>
      <Link
        href={exploreHref({ q: heroObj.name, ra: heroObj.ra, dec: heroObj.dec, fov: hero.fov })}
        className="group overflow-hidden rounded-lg border border-line bg-surface transition-colors duration-(--dur-feedback) ease-standard hover:border-line-strong"
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
          <div className="absolute inset-x-0 bottom-0 flex flex-col gap-1 bg-linear-to-t from-ground via-ground/80 to-transparent px-4 pb-3 pt-16">
            <p className="font-mono text-mono-sm tabular-nums text-ink-secondary">
              {formatCoords(heroObj.ra!, heroObj.dec!)}
            </p>
            <h4 className="text-h2 text-ink">{heroObj.name}</h4>
          </div>
        </div>
        <div className="flex flex-col gap-3 p-4">
          <p className="text-body-sm text-ink-secondary">{hero.why}</p>
          <div className="flex items-center justify-between gap-3">
            <FaceStack people={hero.social.people}>{hero.social.text}</FaceStack>
            <ChevronRight
              size={18}
              strokeWidth={1.5}
              aria-hidden="true"
              className="shrink-0 text-ink-secondary transition-colors duration-(--dur-feedback) ease-standard group-hover:text-ink"
            />
          </div>
        </div>
      </Link>

      <ul className="grid grid-cols-3 gap-3">
        {picks.map((p) => {
          const o = getObject(p.objectId);
          return (
            <li key={p.objectId}>
              <Link
                href={exploreHref({ q: o.name, ra: o.ra, dec: o.dec, fov: p.fov })}
                className="group flex flex-col gap-2 rounded-lg"
              >
                <SkyImage
                  cutout={p.cutout}
                  alt={`${o.name} in infrared`}
                  className="aspect-square rounded-md border border-line transition-colors duration-(--dur-feedback) ease-standard group-hover:border-line-strong"
                  sizes="160px"
                  tag={false}
                />
                <span className="flex flex-col px-0.5">
                  <span className="text-small text-ink">{o.name}</span>
                  <span className="line-clamp-2 text-caption text-ink-secondary">{p.short}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </FeedSection>
  );
}
