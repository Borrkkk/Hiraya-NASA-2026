"use client";

import { Suspense, useState, type FormEvent } from 'react';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { addFindingComment, getFinding } from '@/lib/community';
import { observationPosts } from '@/lib/profiles';
import { NotebookThread } from '@/components/discussion/notebook-thread';
import { useAccount } from '@/lib/account';
import { HomeHeader } from '@/components/home/header';
import { SpectrumChart } from '@/components/explore/spectrum-chart';
import { getBand } from '@/lib/explore/bands';
import type { BandId } from '@/lib/explore/types';

export default function FindingPage() {
  return <Suspense fallback={<main className="mx-auto max-w-7xl px-6 py-12" role="status">Loading discussion…</main>}><FindingContent /></Suspense>;
}

function FindingContent() {
  const { id } = useParams<{ id: string }>();
  const account = useAccount();
  const [body, setBody] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [media, setMedia] = useState<'still' | 'blink'>('still');
  const query = useQuery({ queryKey: ['finding', id],
    queryFn: () => getFinding(id), retry: 0 });
  async function submit(event: FormEvent) {
    event.preventDefault(); if (saving) return;
    setSaving(true); setMessage('');
    try {
      await addFindingComment(id, body);
      setBody(''); await query.refetch();
    } catch { setMessage('Could not save your comment. Your draft is still here. Please retry.'); }
    finally { setSaving(false); }
  }
  const post = query.data?.finding;
  const notebookPost = observationPosts.find((entry) => entry.id === id);
  if (query.data === null && notebookPost) return <NotebookThread post={notebookPost} />;
  const href = post ? `/explore?${new URLSearchParams({ ra: String(post.evidence.view?.ra ?? post.box.ra), dec: String(post.evidence.view?.dec ?? post.box.dec),
    fov: String(post.evidence.view?.fov ?? Math.max(.1, post.box.width*4)), bands: post.evidence.bands.join(','), epoch: post.evidence.epochs[0] ?? '' })}` : '/explore';

  return <div className="min-h-dvh bg-ground">
    <HomeHeader />
    <main className="mx-auto flex max-w-7xl flex-col gap-6 px-4 pb-12 pt-5 sm:px-6">
      <nav className="flex items-center justify-between text-small text-ink-secondary"><Link href="/discussions" className="hover:text-ink">← All discussions</Link><Link href={href} className="rounded-full border border-line-strong px-4 py-2 hover:text-ink">Explore this region ↗</Link></nav>
      {query.isPending ? <p role="status">Loading discussion…</p> : query.data === null ? <div role="alert">This discussion doesn’t exist in the preview. <Link href="/discussions" className="underline">See all discussions</Link></div> : query.isError ? <div role="alert">This post could not be loaded. <button className="underline" onClick={() => query.refetch()}>Retry</button></div> : post && <>
        <header className="flex flex-col gap-4">
          <p className="text-small uppercase tracking-widest text-ink-secondary">Field notes · SPHEREx{post.evidence.sample ? ' · Sample conversation' : ''}</p>
          <h1 className="max-w-4xl text-h1 text-ink">{post.title}</h1>
          <div className="flex items-center gap-3"><span className="flex size-10 items-center justify-center rounded-full border border-line-strong bg-raised text-small font-medium">{post.author.split(' ').filter((v) => v !== 'Dr.').map((v) => v[0]).slice(0, 2).join('')}</span>
            <div><p className="text-body-sm font-medium text-ink">{post.author}</p><p className="text-caption text-ink-secondary">{new Date(post.created_at).toLocaleDateString(undefined, { dateStyle: 'long' })} · {query.data?.comments.length ?? 0} replies</p></div>
          </div>
        </header>

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(340px,1fr)]" data-testid="post-columns">
          <div className="flex min-w-0 flex-col gap-7" data-testid="post-main-column">
            {post.evidence.image && <figure className="overflow-hidden rounded-xl border border-line bg-surface">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3"><span className="text-small font-medium">Observation viewer</span><div className="flex gap-1 rounded-full bg-raised p-1" aria-label="Observation display">
                <button type="button" aria-pressed={media === 'still'} className={`rounded-full px-3 py-1 text-small ${media === 'still' ? 'bg-overlay text-ink' : 'text-ink-secondary'}`} onClick={() => setMedia('still')}>Still frame</button>
                {post.evidence.animation && <button type="button" aria-pressed={media === 'blink'} className={`rounded-full px-3 py-1 text-small ${media === 'blink' ? 'bg-overlay text-ink' : 'text-ink-secondary'}`} onClick={() => setMedia('blink')}>▶ Blink {post.evidence.animation.frameCount} frames</button>}
              </div></div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={media === 'blink' && post.evidence.animation ? post.evidence.animation.url : post.evidence.image.url} alt={media === 'blink' ? 'Comparison observations with a small ring at the discussed sky position in every frame' : 'Tight observation crop with a point marker at the discussed object position'} className="h-[340px] w-full bg-black object-contain [image-rendering:pixelated]" />
              <figcaption className="space-y-2 p-4 text-[15px] leading-relaxed text-ink-secondary">{post.evidence.sourceReference && <p className="font-medium text-ink">Highlighted source · detected in {post.evidence.sourceReference.positions.length} observations</p>}{media === 'blink' && post.evidence.animation ? post.evidence.animation.caption : post.evidence.image.caption}<br />
                {media === 'still' ? <>{post.evidence.image.date.slice(0, 10)} · D{post.evidence.image.detector} · {post.evidence.image.wavelengthUm.toFixed(2)} µm · {post.evidence.image.extentDeg.toFixed(2)}° crop</> : 'Date, detector and wavelength are shown in large text beneath each frame.'}
                {post.evidence.image.contextUrl && <a href={post.evidence.image.contextUrl} target="_blank" rel="noreferrer" className="mt-2 block w-fit underline">View wider context image ↗</a>}
              </figcaption>
            </figure>}

            <section className="flex flex-col gap-4"><h2 className="text-h2">Observation notes</h2><p className="whitespace-pre-wrap text-body leading-relaxed text-ink">{post.body}</p></section>
            <div className="flex items-center justify-between border-y border-line py-4"><span className="text-small text-ink-secondary">{post.evidence.epochs.length} observations attached</span>
              <button type="button" className="rounded-md border border-line-strong px-4 py-2 text-small" onClick={async () => {
                try { await navigator.clipboard.writeText(window.location.href); setMessage('Post link copied.'); }
                catch { setMessage('Copy the URL from your address bar to share this post.'); }
              }}>Copy post link</button>
            </div>
            <section className="flex flex-col gap-4" aria-label="Discussion">
              <h2 className="text-h2">Discussion ({query.data?.comments.length ?? 0})</h2>
              {(query.data?.comments ?? []).map((comment) => <article key={comment.id} className="rounded-xl border border-line bg-surface p-5">
                <p className="text-small font-medium text-ink">{comment.author}<span className="ml-2 font-normal text-ink-secondary">{new Date(comment.created_at).toLocaleDateString()}</span></p>
                <p className="mt-2 whitespace-pre-wrap text-body-sm">{comment.body}</p>
              </article>)}
              <form onSubmit={submit} className="flex flex-col gap-3">
                <p className="text-small text-ink-secondary">Commenting as {account.data.account.name} · saved in this browser only</p>
                <label className="flex flex-col gap-1">Add evidence or discuss<textarea required maxLength={2000} rows={4} value={body} onChange={(e) => setBody(e.target.value)} className="rounded-md border border-line-strong bg-surface p-3" /></label>
                <button disabled={saving} className="rounded-md bg-primary px-4 py-3 text-on-primary disabled:opacity-50">{saving ? 'Saving…' : 'Post comment'}</button>
              </form>
            </section>
            {message && <p role="status">{message}</p>}
          </div>

          <aside aria-label="Observation data and evidence" className="flex min-w-0 flex-col gap-5" data-testid="post-evidence-column">
            <section className="grid grid-cols-2 gap-4 rounded-xl border border-line bg-surface p-5 text-body-sm">
              <div><p className="text-caption text-ink-secondary">Observation set</p><p className="mt-1 font-medium">{post.evidence.epochs.length} observations</p></div>
              <div><p className="text-caption text-ink-secondary">Measured colours</p><p className="mt-1 font-medium">{post.evidence.observationFacts?.measurementCount ?? post.evidence.spectrum?.points.length ?? '—'} samples</p></div>
              <div><p className="text-caption text-ink-secondary">Detectors</p><p className="mt-1 font-medium">{post.evidence.observationFacts?.detectors.map((d) => `D${d}`).join(' · ') ?? 'See evidence'}</p></div>
              <div><p className="text-caption text-ink-secondary">Selected region</p><p className="mt-1 font-medium">{(post.box.width*60).toFixed(1)}′ × {(post.box.height*60).toFixed(1)}′</p></div>
            </section>
            {post.evidence.spectrum && post.evidence.spectrum.points.length > 0 && <section className="rounded-xl border border-line bg-surface p-5">
              <h2 className="mb-4 text-body-sm font-medium">Brightness across infrared colours</h2>
              <SpectrumChart spectrum={post.evidence.spectrum} />
              <p className="mt-3 text-caption text-ink-secondary">Each dot measures the average brightness of the selected patch at one wavelength. Samples can come from different dates.</p>
            </section>}
            <section className="rounded-xl border border-line bg-surface p-5">
              <h2 className="text-body-sm font-medium">{post.evidence.summaryMethod === 'ai' ? 'AI explanation of the observation data' : 'Observation data, explained'}</h2>
              <p className="mt-2 text-body-sm text-ink-secondary">{post.evidence.summary ?? 'No summary has been prepared yet.'}</p>
            </section>
            <section className="rounded-xl border border-line bg-surface p-5 text-body-sm">
              <h2 className="mb-3 font-medium">Observation details</h2>
              <p className="font-mono text-caption">RA {post.box.ra.toFixed(5)}° · Dec {post.box.dec.toFixed(5)}°</p>
              <p className="mt-2">{post.evidence.bands.map((b) => getBand(b as BandId)?.name ?? b).join(', ')}</p>
              {post.evidence.observationFacts && <p className="mt-1 text-ink-secondary">{post.evidence.observationFacts.firstDate.slice(0, 10)} — {post.evidence.observationFacts.lastDate.slice(0, 10)}</p>}
              {post.evidence.track.length > 0 && <p>{post.evidence.track.length} recorded motion-track positions</p>}
              <details className="mt-3"><summary className="cursor-pointer">Observation evidence</summary><ul className="mt-2 space-y-1">{post.evidence.epochs.map((epoch) => <li key={epoch} className="break-all font-mono text-caption">{epoch}</li>)}</ul>
                {post.evidence.track.map((point, index) => <p key={index} className="font-mono text-caption">{point.date} · {point.ra.toFixed(5)}°, {point.dec.toFixed(5)}°</p>)}</details>
            </section>
            {post.evidence.demo ? <p className="text-caption text-ink-secondary">Provenance: simulated demo images and measurements{post.evidence.sample ? '; conversation prepared for the app demonstration' : ''}.</p> : post.evidence.sample && <p className="text-caption text-ink-secondary">Provenance: real SPHEREx observations and calculated measurements; conversation prepared for the app demonstration.</p>}
          </aside>
        </div>
      </>}
    </main>
  </div>;
}
