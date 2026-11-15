import Link from "next/link";
import { Avatar, SkyImage, Verdict } from "@/components/ui";
import { exploreHref } from "@/lib/explore/href";
import { profileHref } from "@/lib/profiles";
import { findings } from "@/lib/feed/mock";
import { getObject } from "@/lib/sky/catalog";
import { FeedSection } from "./section";
import { PostDiscussion } from "@/components/discussion/post-discussion";

/**
 * Post-style cards: who found it and the verdict, the evidence, a line of
 * facts. The image carries no reticle or tag here, since the feed already has
 * one reticle (the hero's) and the map has another.
 */
export function Findings() {
  return (
    <FeedSection title="New findings">
      <ul className="flex flex-col gap-3">
        {findings.map((f) => {
          const o = getObject(f.objectId);
          return (
            <li key={f.id}>
              <article className="relative flex flex-col gap-3 rounded-lg bg-raised p-4 transition-colors duration-(--dur-feedback) ease-standard hover:bg-overlay">
                <header className="flex items-center gap-3">
                  <Link href={profileHref(f.author.id)} aria-label={`View ${f.author.name}’s profile`} className="relative z-10 shrink-0 rounded-full"><Avatar initials={f.author.initials} tone={f.author.tone} /></Link>
                  <div className="flex min-w-0 flex-col">
                    <Link href={profileHref(f.author.id)} className="relative z-10 rounded-xs text-small text-ink hover:underline">{f.author.name}</Link>
                    <span className="text-small text-ink-secondary">{f.activity}</span>
                  </div>
                  <Verdict kind={f.verdict} className="ml-auto" />
                </header>

                <SkyImage
                  cutout={f.cutout}
                  alt={`${o.name} in infrared, as shared`}
                  className="aspect-[2/1] rounded-xs"
                  sizes="400px"
                  tag={false}
                />

                <div className="flex flex-col gap-1">
                  <h4 className="text-body text-ink">
                    {/* Author links sit above the stretched observation link. */}
                    <Link
                      href={exploreHref({ q: o.name, ra: o.ra, dec: o.dec, fov: f.fov })}
                      className="rounded-xs after:absolute after:inset-0 after:content-['']"
                    >
                      {f.title}
                    </Link>
                  </h4>
                  <p className="line-clamp-2 text-body-sm text-ink-secondary">{f.body}</p>
                </div>

                <p className="font-mono text-mono tabular-nums text-ink-secondary">
                  {f.facts.join(" · ")}
                </p>
                <PostDiscussion postId={f.id} postTitle={f.title} />
              </article>
            </li>
          );
        })}
      </ul>
    </FeedSection>
  );
}
