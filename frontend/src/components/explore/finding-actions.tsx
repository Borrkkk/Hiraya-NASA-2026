"use client";

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { matchFinding } from '@/lib/community';
import { useExplore } from './use-explore';
import { buttonSecondary } from './panel-parts';

export function FindingActions() {
  const ex = useExplore();
  const router = useRouter();
  const box = ex.box;
  const existing = useQuery({
    queryKey: ['finding-match', box],
    queryFn: () => matchFinding(box!),
    enabled: !!box,
    retry: 0,
  });
  if (!box) return null;
  const found = existing.data;
  const explained = ex.verifyState.status === 'done' && ex.verifyState.result.outcome === 'explained';
  return <div className="flex flex-col gap-2 border-t border-line p-4">
    {found ? <>
      <p className="text-small text-ink-secondary">This region already has a discussion.</p>
      <Link className={buttonSecondary} href={`/findings/${found.id}`}>Open existing finding</Link>
    </> : <>
      <button className={buttonSecondary} type="button"
        disabled={existing.isPending || existing.isError || ex.rangeEpochCount < 2 || explained}
        onClick={() => { const href = ex.share(ex.inspectQuery.data?.spectrum ?? null); if (href) router.push(href); }}>
        {existing.isPending ? 'Checking for existing posts…' : 'Discuss suspected motion'}
      </button>
      <p className="text-caption text-ink-secondary">{existing.isError ? 'Could not check existing posts. Try again before submitting.' : explained ? 'This selection has a known match.' : ex.rangeEpochCount < 2 ? 'Select at least two observations to report suspected motion.' : 'Share your evidence for others to check; this does not confirm a discovery.'}</p>
      {existing.isError && <button type="button" className="text-small underline" onClick={() => existing.refetch()}>Retry post lookup</button>}
    </>}
  </div>;
}
