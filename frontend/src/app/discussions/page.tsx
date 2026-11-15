"use client";

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { MessageSquare, Search } from "lucide-react";
import { api } from "@/lib/api";
import { BANDS } from "@/lib/explore/bands";
import type { Finding } from "@/lib/findings";
import { HomeHeader } from "@/components/home/header";
import { Avatar, Segmented } from "@/components/ui";
import { observationPosts, profiles, getProfile } from "@/lib/profiles";

type Row = {
  id: string;
  title: string;
  excerpt: string;
  author: string;
  initials: string;
  tone: 1 | 2 | 3 | 4;
  when: number;
  replies: number | null;
  image: string | null;
  bands: string[];
  note: string | null;
  place: string | null;
};
type Sort = "new" | "active";

const initialsOf = (name: string) =>
  name.split(" ").filter((v) => v !== "Dr.").map((v) => v[0]).slice(0, 2).join("");

function toRow(f: Finding & { replies?: number }): Row {
  const known = profiles.find((p) => p.name === f.author);
  return {
    id: f.id,
    title: f.title,
    excerpt: f.body.split("\n\n")[0],
    author: f.author,
    initials: known?.initials ?? initialsOf(f.author),
    tone: known?.tone ?? 3,
    when: Date.parse(f.created_at),
    replies: f.replies ?? 0,
    image: f.evidence.image ? `/api${f.evidence.image.url}` : null,
    bands: f.evidence.bands,
    note: f.evidence.demo ? "Simulated demo data" : f.evidence.sample ? "Sample discussion" : null,
    place: `RA ${f.box.ra.toFixed(3)}° · Dec ${f.box.dec.toFixed(3)}°`,
  };
}

function notebookRows(): Row[] {
  return observationPosts.map((p) => {
    const who = getProfile(p.authorId);
    return {
      id: p.id,
      title: p.title,
      excerpt: p.body,
      author: who?.name ?? p.authorId,
      initials: who?.initials ?? "?",
      tone: who?.tone ?? 3,
      when: Date.parse(p.date),
      replies: null,
      image: null,
      bands: [],
      note: p.topic,
      place: null,
    };
  });
}

const ago = (t: number) => {
  const days = Math.max(0, Math.round((Date.now() - t) / 864e5));
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  return new Date(t).toLocaleDateString(undefined, { dateStyle: "medium" });
};

export default function DiscussionsPage() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-5xl px-6 py-12" role="status">Loading discussions…</main>}>
      <Discussions />
    </Suspense>
  );
}

function Discussions() {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<Sort>("new");
  const query = useQuery({
    queryKey: ["all-findings"],
    queryFn: ({ signal }) => api<{ findings: (Finding & { replies: number })[] }>("/explore/findings", { signal }),
    refetchInterval: 15000,
    retry: 0,
  });
  const rows = useMemo(() => {
    const all = [...(query.data?.findings.map(toRow) ?? []), ...notebookRows()];
    const needle = q.trim().toLowerCase();
    const shown = needle
      ? all.filter((r) => `${r.title} ${r.excerpt} ${r.author}`.toLowerCase().includes(needle))
      : all;
    return shown.sort((a, b) => (sort === "active" ? (b.replies ?? -1) - (a.replies ?? -1) || b.when - a.when : b.when - a.when));
  }, [query.data, q, sort]);

  return (
    <div className="min-h-dvh bg-ground">
      <HomeHeader />
      <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 pb-16 pt-4 sm:px-6">
        <header className="flex flex-col gap-2">
          <p className="text-small uppercase tracking-widest text-ink-secondary">Field notes · SPHEREx</p>
          <h1 className="text-h1 text-ink">All discussions</h1>
          <p className="max-w-2xl text-body text-ink-secondary">
            Things people spotted, how they checked them, and what others replied. To start one, select a region in{" "}
            <Link href="/explore" className="underline">Explore</Link>, then choose “Discuss suspected motion”.
          </p>
        </header>

        <div className="flex flex-wrap items-center gap-3">
          <label className="relative min-w-[240px] flex-1">
            <span className="sr-only">Search discussions</span>
            <Search size={16} strokeWidth={1.5} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-secondary" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search titles, notes and people"
              className="h-11 w-full rounded-lg border border-line-strong bg-surface pl-9 pr-3 text-body-sm text-ink placeholder:text-ink-secondary"
            />
          </label>
          <Segmented
            label="Sort discussions"
            value={sort}
            onChange={setSort}
            options={[
              { value: "new", label: "Newest" },
              { value: "active", label: "Most replies" },
            ]}
          />
        </div>

        {query.isError && (
          <p role="status" className="rounded-lg border border-line bg-surface p-4 text-small text-ink-secondary">
            Community discussions could not be loaded (is the backend running?). Showing notebook posts only.{" "}
            <button className="underline" onClick={() => query.refetch()}>Retry</button>
          </p>
        )}

        <ul className="flex flex-col gap-3" aria-label="Discussions">
          {query.isPending && <li role="status" className="text-ink-secondary">Loading discussions…</li>}
          {rows.map((r) => (
            <li key={r.id}>
              <Link
                href={`/findings/${encodeURIComponent(r.id)}`}
                className="group flex gap-4 rounded-xl border border-line bg-surface p-3 transition-colors duration-(--dur-feedback) ease-standard hover:border-line-strong hover:bg-raised sm:p-4"
              >
                {r.image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={r.image} alt="" className="size-24 shrink-0 rounded-lg bg-black object-cover sm:size-28" />
                ) : (
                  <span aria-hidden="true" className="flex size-24 shrink-0 items-center justify-center rounded-lg bg-raised text-ink-secondary sm:size-28">
                    <MessageSquare size={26} strokeWidth={1.25} />
                  </span>
                )}
                <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                  <h2 className="text-h3 text-ink group-hover:underline">{r.title}</h2>
                  <p className="line-clamp-2 text-body-sm text-ink-secondary">{r.excerpt}</p>
                  <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 pt-1 text-caption text-ink-secondary">
                    <span className="inline-flex items-center gap-1.5">
                      <Avatar initials={r.initials} tone={r.tone} size="sm" />
                      {r.author}
                    </span>
                    <span>{ago(r.when)}</span>
                    {r.replies !== null && (
                      <span className="inline-flex items-center gap-1">
                        <MessageSquare size={13} strokeWidth={1.5} aria-hidden="true" />
                        {r.replies} {r.replies === 1 ? "reply" : "replies"}
                      </span>
                    )}
                    {r.bands.length > 0 && (
                      <span className="inline-flex items-center gap-1" aria-label={`Wavelengths: ${r.bands.join(", ")}`}>
                        {r.bands.map((b) => (
                          <span key={b} className="size-2 rounded-full" style={{ background: BANDS.find((x) => x.id === b)?.color }} title={BANDS.find((x) => x.id === b)?.name} />
                        ))}
                      </span>
                    )}
                    {r.place && <span className="hidden font-mono sm:inline">{r.place}</span>}
                    {r.note && <span className="rounded-full border border-line px-2 py-0.5">{r.note}</span>}
                  </div>
                </div>
              </Link>
            </li>
          ))}
          {!query.isPending && rows.length === 0 && <li className="text-ink-secondary">Nothing matches “{q}”.</li>}
        </ul>
      </main>
    </div>
  );
}
