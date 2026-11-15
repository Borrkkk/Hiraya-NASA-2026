"use client";

import { useEffect, useState, type FormEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { SHARE_KEY, type ShareDraft } from '@/lib/explore/share';
import { type Finding, regionQuery } from '@/lib/findings';
import { useAccount } from '@/lib/account';

const inputStyle = 'w-full rounded-md border border-line-strong bg-surface p-3 text-ink';

export default function SharePage() {
  const router = useRouter();
  const [draft, setDraft] = useState<ShareDraft | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const account = useAccount();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    try {
      const value = JSON.parse(sessionStorage.getItem(SHARE_KEY) ?? 'null');
      if (value?.box && Array.isArray(value.epochs) && Array.isArray(value.bands)) {
        setDraft(value);
        setTitle(`Suspected motion${value.areaName ? ` near ${value.areaName}` : ''}`.slice(0, 120));
      }
    } catch { /* Explain a missing draft below. */ }
    setLoaded(true);
  }, []);
  const existing = useQuery({
    queryKey: ['finding-match', draft?.box],
    queryFn: ({ signal }) => api<{ finding: Finding | null }>(`/explore/findings/match?${regionQuery(draft!.box)}`, { signal }),
    enabled: !!draft,
    retry: 0,
  });
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!draft || saving) return;
    setSaving(true); setError('');
    try {
      const result = await api<{ finding: Finding; created: boolean }>('/explore/findings', {
        method: 'POST', json: { box: draft.box, title, body, bands: draft.bands,
          epochs: draft.epochs, track: draft.mover?.points ?? [], view: draft.view ?? null },
      });
      // The server repeats the duplicate check atomically, so concurrent
      // submissions also converge on one shared discussion.
      router.replace(`/findings/${result.finding.id}`);
    } catch { setError('Could not save the finding. Check your connection and try again; your draft is still here.'); }
    finally { setSaving(false); }
  }
  return <main className="mx-auto flex min-h-dvh max-w-2xl flex-col gap-6 px-6 py-12">
    <Link href="/explore" className="text-small underline">Back to Explore</Link>
    <h1 className="text-h1 text-ink">Discuss suspected motion</h1>
    {!loaded ? <p role="status">Loading your selection…</p> : !draft ? <p>Select a region in Explore, then choose “Discuss suspected motion.” Your selection must be in this tab.</p> : <>
      <p className="text-body-sm text-ink-secondary">Share the observations you want others to check. This post records a suspected signal, not a confirmed discovery.</p>
      <p className="font-mono text-small">RA {draft.box.ra.toFixed(5)}° · Dec {draft.box.dec.toFixed(5)}° · {draft.epochs.length} observations</p>
      {existing.isPending ? <p role="status">Checking for an existing discussion…</p> : existing.isError ? <div role="alert"><p>Could not check existing discussions.</p><button className="underline" onClick={() => existing.refetch()}>Retry</button></div> : existing.data?.finding ?
        <div className="rounded-lg border border-line-strong bg-surface p-5"><p>This region already has a post. Add your evidence there.</p><Link className="mt-3 block underline" href={`/findings/${existing.data.finding.id}`}>{existing.data.finding.title}</Link></div> :
        <form onSubmit={submit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-2">Title<input required minLength={3} maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} className={inputStyle} /></label>
          <label className="flex flex-col gap-2">What changed between observations?<textarea required minLength={10} maxLength={6000} rows={6} value={body} onChange={(e) => setBody(e.target.value)} className={inputStyle} placeholder="Describe the apparent movement, dates, and checks against alignment errors or artifacts." /></label>
          <p className="text-small text-ink-secondary">Posting as {account.data?.account.name ?? 'your current account'}</p>
          {new Set(draft.epochs).size < 2 && <p role="alert">Select at least two different observations in Explore before submitting.</p>}
          {error && <p role="alert">{error}</p>}
          <button disabled={saving || !account.data || new Set(draft.epochs).size < 2} className="rounded-md bg-primary px-4 py-3 text-on-primary disabled:opacity-50">{saving ? 'Saving…' : 'Create discussion post'}</button>
        </form>}
    </>}
  </main>;
}
