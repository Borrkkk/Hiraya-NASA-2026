"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight, Bookmark, Check, Pin, SlidersHorizontal } from "lucide-react";
import { Avatar, Chip, SkyImage, Verdict } from "@/components/ui";
import { exploreHref } from "@/lib/explore/href";
import { getObject } from "@/lib/sky/catalog";
import { PostDiscussion } from "@/components/discussion/post-discussion";
import { profileHref, type UserProfile, type ObservationPost } from "@/lib/profiles";

export function ProfilePosts({ profile, posts }: { profile: UserProfile; posts: ObservationPost[] }) {
  const [tab, setTab] = useState<"observations" | "saved">("observations");
  const [topic, setTopic] = useState("All topics");
  const [saved, setSaved] = useState<string[]>([]);
  const [oldestFirst, setOldestFirst] = useState(false);
  const visible = posts.filter((post) => (tab !== "saved" || saved.includes(post.id)) && (topic === "All topics" || post.topic === topic))
    .sort((a, b) => oldestFirst ? a.date.localeCompare(b.date) : b.date.localeCompare(a.date));

  function toggleSave(id: string) {
    setSaved((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  }

  return (
    <section className="min-w-0" aria-label="Researcher observation posts">
      <div className="flex items-center gap-6 border-b border-line" aria-label="Profile sections">
        {([['observations', 'Observations', posts.length], ['saved', 'Saved', saved.length]] as const).map(([value, label, count]) => (
          <button type="button" key={value} onClick={() => setTab(value)} aria-pressed={tab === value}
            className={`-mb-px flex min-h-12 cursor-pointer items-center gap-2 border-b-2 pb-3 text-small font-medium transition-colors ${tab === value ? 'border-ember text-ink' : 'border-transparent text-ink-secondary hover:text-ink'}`}>
            {label}<span className="rounded-sm bg-raised px-1.5 py-0.5 font-mono text-mono-sm text-ink-secondary">{count}</span>
          </button>
        ))}
        <span className="ml-auto hidden text-caption text-ink-muted sm:block">A public observation notebook</span>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 py-5">
        <div className="flex flex-wrap gap-2" aria-label="Filter observations by topic">
          {['All topics', ...new Set(posts.map((post) => post.topic))].map((value) => <Chip key={value} selected={topic === value} onClick={() => setTopic(value)}>{value}</Chip>)}
        </div>
        <button type="button" aria-pressed={oldestFirst} onClick={() => setOldestFirst((value) => !value)} className="inline-flex min-h-8 cursor-pointer items-center gap-2 rounded-sm px-1 text-caption text-ink-secondary hover:text-ink">
          <SlidersHorizontal size={14} aria-hidden="true" /> {oldestFirst ? 'Oldest first' : 'Latest first'}
        </button>
      </div>
      <p role="status" className="sr-only">{visible.length} {visible.length === 1 ? 'observation' : 'observations'} shown</p>
      <div className="flex flex-col gap-5">
        {visible.map((post) => {
          const object = getObject(post.objectId);
          const isSaved = saved.includes(post.id);
          return <article key={post.id} className="overflow-hidden rounded-lg border border-line bg-surface">
            {post.pinned && <p className="flex items-center gap-2 border-b border-line bg-raised/50 px-5 py-2 text-caption text-ink-secondary"><Pin size={12} aria-hidden="true" /> Pinned observation</p>}
            <div className="p-4 sm:p-5">
              <header className="flex items-center gap-3">
                <Link href={profileHref(profile.id)} aria-label={`View ${profile.name}’s profile`} className="shrink-0 rounded-full"><Avatar initials={profile.initials} tone={profile.tone} /></Link>
                <div className="min-w-0 flex-1"><p className="text-small font-medium"><Link href={profileHref(profile.id)} className="rounded-xs hover:underline">{profile.name}</Link> <span className="ml-1 font-normal text-ink-muted">· <time dateTime={post.date}>{post.dateLabel}</time></span></p><p className="text-caption text-ink-secondary">{post.topic}</p></div>
                <button type="button" aria-label={`${isSaved ? 'Unsave' : 'Save'} observation: ${post.title}`} aria-pressed={isSaved} onClick={() => toggleSave(post.id)} className={`grid size-10 shrink-0 cursor-pointer place-items-center rounded-md border transition-colors ${isSaved ? 'border-ember-line bg-ember-wash text-ember' : 'border-line text-ink-secondary hover:bg-raised hover:text-ink'}`}>
                  {isSaved ? <Check size={17} aria-hidden="true" /> : <Bookmark size={17} aria-hidden="true" />}
                </button>
              </header>
              <h2 className="mt-5 max-w-xl text-h3">{post.title}</h2>
              <p className="mt-2 text-body-sm leading-relaxed text-ink-secondary">{post.body}</p>
              <Link href={exploreHref({ q: object.name, ra: object.ra, dec: object.dec, fov: object.fov })} className="group relative mt-4 block overflow-hidden rounded-md" aria-label={`Explore ${object.name}`}>
                <SkyImage cutout={post.cutout} alt={`WISE infrared reference field around ${object.name}`} className="aspect-[2.2/1]" sizes="(max-width: 1024px) 90vw, 700px" priority={post.pinned} />
                <span className="absolute bottom-3 left-3 inline-flex items-center gap-2 rounded-sm bg-scrim px-2.5 py-1.5 text-small text-ink">{object.name} <ArrowUpRight size={14} aria-hidden="true" /></span>
              </Link>
              <footer className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <Verdict kind={post.verdict} />
                <span className="font-mono text-mono-sm text-ink-muted">{post.note}</span>
              </footer>
              <PostDiscussion postId={post.id} postTitle={post.title} />
            </div>
          </article>;
        })}
        {visible.length === 0 && <div className="rounded-lg border border-dashed border-line-strong px-6 py-14 text-center"><Bookmark size={24} className="mx-auto mb-3 text-ink-muted" aria-hidden="true" /><h2 className="text-body font-medium">{tab === 'saved' ? 'Your reading list starts here' : 'No observations in this topic'}</h2><p className="mt-2 text-small text-ink-secondary">{tab === 'saved' ? 'Save an observation to find it here during this visit.' : 'Choose another topic to see more observations.'}</p><button type="button" onClick={() => {setTab('observations'); setTopic('All topics');}} className="mt-4 cursor-pointer rounded-sm text-small text-ember hover:text-ember-hover">View all observations <span aria-hidden="true">→</span></button></div>}
      </div>
      <p className="mt-6 text-center text-caption text-ink-muted">{tab === 'saved' ? 'Saved posts are kept for this page visit.' : 'You’re all caught up with this sample notebook.'}</p>
    </section>
  );
}
