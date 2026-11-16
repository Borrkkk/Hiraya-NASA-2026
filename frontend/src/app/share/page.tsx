"use client";

import { useMemo, useState, useSyncExternalStore, type FormEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { createFinding, matchFinding } from '@/lib/community';
import { SHARE_KEY, type ShareDraft } from '@/lib/explore/share';
import { useAccount } from '@/lib/account';

const noopSubscribe = () => () => {};
const readDraft = () => { try { return sessionStorage.getItem(SHARE_KEY); } catch { return null; } };

const inputStyle = 'w-full rounded-md border border-line-strong bg-surface p-3 text-ink';

export default function SharePage() {
  const router = useRouter();
  // The draft lives in this tab's sessionStorage. Server snapshot `undefined` = "not read yet".
  const raw = useSyncExternalStore(noopSubscribe, readDraft, () => undefined);
  const draft = useMemo<ShareDraft | null>(() => {
    try {
      const value = JSON.parse(raw ?? 'null');
      return value?.box && Array.isArray(value.epochs) && Array.isArray(value.bands) ? value : null;
    } catch { return null; }
  }, [raw]);
  const loaded = raw !== undefined;
  const [titleEdit, setTitleEdit] = useState<string | null>(null);
  const title = titleEdit ?? `Suspected motion${draft?.areaName ? ` near ${draft.areaName}` : ''}`.slice(0, 120);
  const setTitle = setTitleEdit;
  const [body, setBody] = useState('');
  const account = useAccount();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const existing = useQuery({
    queryKey: ['finding-match', draft?.box],
    queryFn: () => matchFinding(draft!.box),
    enabled: !!draft,
    retry: 0,
  });
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!draft || saving) return;
    setSaving(true); setError('');
    try {
      // A short pause, like a real upload, then the post is saved in this browser only.
      await new Promise((resolve) => setTimeout(resolve, 900));
      const result = await createFinding({ box: draft.box, title, body, bands: draft.bands,
        epochs: draft.epochs, track: draft.mover?.points ?? [], view: draft.view ?? null, spectrum: draft.spectrum });
      router.replace(`/findings/${result.finding.id}`);
    } catch { setError('Could not save the post. Your draft is still here; try again.'); }
    finally { setSaving(false); }
  }
  return <main className="mx-auto flex min-h-dvh max-w-2xl flex-col gap-6 px-6 py-12">
    <Link href="/explore" className="text-small underline">Back to Explore</Link>
    <h1 className="text-h1 text-ink">Discuss suspected motion</h1>
    {!loaded ? <p role="status">Loading your selection…</p> : !draft ? <p>Select a region in Explore, then choose “Discuss suspected motion.” Your selection must be in this tab.</p> : <>
      <p className="text-body-sm text-ink-secondary">Share the observations you want others to check. This post records a suspected signal, not a confirmed discovery.</p>
      <p className="text-small text-ink-secondary">The brightness plot is attached automatically, and around the faint mover a snapshot and a blink animation are added too. This is a preview: your post is saved in this browser only and is never uploaded.</p>
      <p className="font-mono text-small">RA {draft.box.ra.toFixed(5)}° · Dec {draft.box.dec.toFixed(5)}° · {draft.epochs.length} observations</p>
      {existing.isPending ? <p role="status">Checking for an existing discussion…</p> : existing.isError ? <div role="alert"><p>Could not check existing discussions.</p><button className="underline" onClick={() => existing.refetch()}>Retry</button></div> : existing.data ?
        <div className="rounded-lg border border-line-strong bg-surface p-5"><p>This region already has a post. Add your evidence there.</p><Link className="mt-3 block underline" href={`/findings/${existing.data.id}`}>{existing.data.title}</Link></div> :
        <form onSubmit={submit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-2">Title<input required minLength={3} maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} className={inputStyle} /></label>
          <label className="flex flex-col gap-2">What changed between observations?<textarea required minLength={10} maxLength={6000} rows={6} value={body} onChange={(e) => setBody(e.target.value)} className={inputStyle} placeholder="Describe the apparent movement, dates, and checks against alignment errors or artifacts." /></label>
          <button type="button" className="w-fit text-small underline" onClick={() => setBody('A faint source that is not in the catalogues slides toward the lower left across the twelve visits, about 7 arcseconds a year, while the stars around it stay put. It is brightest at 4–5 µm and has a dip near 3.3 µm. Could someone check it against the Verify step or repeat it with another pair of colours?')}>Use an example</button>
          <p className="text-small text-ink-secondary">Posting as {account.data.account.name}</p>
          {new Set(draft.epochs).size < 2 && <p role="alert">Select at least two different observations in Explore before submitting.</p>}
          {error && <p role="alert">{error}</p>}
          <button disabled={saving || new Set(draft.epochs).size < 2} className="rounded-md bg-primary px-4 py-3 text-on-primary disabled:opacity-50">{saving ? 'Saving…' : 'Create discussion post'}</button>
        </form>}
    </>}
  </main>;
}
