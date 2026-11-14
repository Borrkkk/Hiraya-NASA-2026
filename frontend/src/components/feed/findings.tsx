import { Eye, MessageCircle } from "lucide-react";
import Link from "next/link";
import { Avatar, SkyImage, Verdict } from "@/components/ui";
import { exploreHref } from "@/lib/explore";
import { findings } from "@/lib/feed/mock";
import { getObject } from "@/lib/sky/catalog";
import { FeedSection } from "./section";

/** Post-style cards: who found it, the verdict, the evidence, the facts. */
export function Findings() {
  return (
    <FeedSection title="New findings" subtitle="What people found and checked">
      <ul className="flex flex-col gap-3">
        {findings.map((f) => {
          const o = getObject(f.objectId);
          return (
            <li key={f.id}>
              <article className="group relative flex flex-col gap-4 rounded-lg border border-line bg-surface p-3 transition-colors duration-(--dur-feedback) ease-standard hover:border-line-strong hover:bg-raised">
                <header className="flex items-center gap-2.5 px-1 pt-1">
                  <Avatar initials={f.author.initials} tone={f.author.tone} />
                  <div className="flex min-w-0 flex-col">
                    <span className="text-small font-medium text-ink">{f.author.name}</span>
                    <span className="text-caption text-ink-secondary">{f.activity}</span>
                  </div>
                  <Verdict kind={f.verdict} className="ml-auto" />
                </header>

                <SkyImage
                  cutout={f.cutout}
                  alt={`${o.name} in infrared, as shared`}
                  className="aspect-[8/5] rounded-xs"
                  sizes="420px"
                  reticle={{ size: 40 }}
                />

                <div className="flex flex-col gap-1.5 px-1">
                  <h4 className="text-h3 text-ink">
                    {/* The whole card is the link. */}
                    <Link
                      href={exploreHref({ q: o.name, ra: o.ra, dec: o.dec, fov: f.fov })}
                      className="rounded-xs after:absolute after:inset-0 after:content-['']"
                    >
                      {f.title}
                    </Link>
                  </h4>
                  <p className="text-body-sm text-ink-secondary">{f.body}</p>
                </div>

                <dl className="grid grid-cols-3 gap-px overflow-hidden rounded-md bg-line">
                  {f.facts.map((x) => (
                    <div key={x.label} className="flex flex-col gap-0.5 bg-raised px-3 py-2.5 transition-colors duration-(--dur-feedback) ease-standard group-hover:bg-overlay">
                      <dt className="text-caption text-ink-secondary">{x.label}</dt>
                      <dd className="font-mono text-mono tabular-nums text-ink">{x.value}</dd>
                    </div>
                  ))}
                </dl>

                <footer className="flex items-center gap-4 px-1 pb-1 text-small text-ink-secondary">
                  <span className="inline-flex items-center gap-1.5">
                    <Eye size={16} strokeWidth={1.5} aria-hidden="true" />
                    <span className="font-mono text-mono tabular-nums">{f.saw}</span> saw it too
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <MessageCircle size={16} strokeWidth={1.5} aria-hidden="true" />
                    <span className="font-mono text-mono tabular-nums">{f.comments}</span>
                  </span>
                </footer>
              </article>
            </li>
          );
        })}
      </ul>
    </FeedSection>
  );
}
