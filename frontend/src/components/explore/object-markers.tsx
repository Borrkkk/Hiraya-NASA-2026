"use client";

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { Finding, FindingComment } from '@/lib/findings';
import { useStore } from '@/lib/explore/store';
import type { Projection } from '@/lib/explore/projection';
import { useExplore } from './use-explore';
import { observationPosts, getProfile } from '@/lib/profiles';
import { getObject } from '@/lib/sky/catalog';

type Marker = { id: string; ra: number; dec: number; name: string; kind: 'finding' | 'identified'; basis?: 'catalog' | 'selection'; source?: string; epoch?: string };

export function ObjectMarkers({ proj }: { proj: Projection }) {
  const ex = useExplore();
  const router = useRouter();
  const [selected, setSelected] = useState<Marker | null>(null);
  const size = useStore(ex.sizeStore);
  const samplePost = observationPosts.find((post) => post.id === selected?.id);
  const preview = useQuery({
    queryKey: ['finding', selected?.id],
    queryFn: ({ signal }) => api<{ finding: Finding; comments: FindingComment[] }>(`/explore/findings/${encodeURIComponent(selected!.id)}`, { signal }),
    enabled: selected?.kind === 'finding', retry: 0,
  });
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setSelected(null); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, []);
  const centre = ex.area?.center;
  const query = useQuery({
    queryKey: ['object-markers', centre, ex.verifyState.status],
    queryFn: ({ signal }) => api<{ markers: Marker[] }>(`/explore/markers?ra=${centre!.ra}&dec=${centre!.dec}&radius=2`, { signal }),
    enabled: !!centre,
    refetchInterval: 15000,
    retry: 0,
  });
  const markers: Marker[] = [...(query.data?.markers ?? [])];
  for (const post of observationPosts) {
    if (markers.some((marker) => marker.id === post.id)) continue;
    const object = getObject(post.objectId);
    if (object.ra === undefined || object.dec === undefined) continue;
    markers.push({ id: post.id, ra: object.ra, dec: object.dec, name: post.title, kind: 'finding' });
  }
  return <g aria-label="Known matches and community findings">
    {markers.map((marker) => {
      if (marker.kind === 'finding' && !ex.showDiscussionPosts) return null;
      if (marker.kind === 'identified' && marker.epoch !== 'all' && marker.epoch !== ex.playheadEpoch?.id) return null;
      const [x, y] = proj.toScreen(marker.ra, marker.dec);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
      const label = marker.kind === 'finding' ? `Discussion: ${marker.name}` : `${marker.basis === 'selection' ? 'Match in selection' : 'Catalog match'}: ${marker.name}`;
      const open = () => marker.kind === 'finding' ? setSelected(marker) : ex.setBox({ ra: marker.ra, dec: marker.dec, width: .005, height: .005 });
      return <g key={marker.id} transform={`translate(${x},${y})`} role="button"
        tabIndex={0} aria-label={label} style={{ pointerEvents: 'all', cursor: 'pointer' }}
        onPointerDown={(event) => event.stopPropagation()} onClick={open}
        onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); open(); } }}>
        <title>{label}{marker.source ? ` (${marker.source})` : ''}</title>
        <circle r={9} fill="var(--color-ground)" stroke={marker.kind === 'finding' ? '#f6aa56' : '#5fe0ff'} strokeWidth={2}
          strokeDasharray={marker.basis === 'selection' ? '3 2' : undefined} />
        <text x={14} y={4} fontSize={12} fill="var(--color-ink)" stroke="var(--color-ground)" strokeWidth={3} paintOrder="stroke">{marker.kind === 'finding' ? 'Discussion' : marker.name}</text>
      </g>;
    })}
    {selected && <foreignObject x={Math.max(8, Math.min(size.w-328, proj.toScreen(selected.ra, selected.dec)[0]+16))}
      y={Math.max(8, Math.min(size.h-368, proj.toScreen(selected.ra, selected.dec)[1]+16))} width={320} height={360} style={{ pointerEvents: 'all' }}>
      <div role="dialog" aria-label="Discussion preview" className="flex h-full flex-col overflow-hidden rounded-xl border border-line-strong bg-surface shadow-xl"
        onPointerDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-line px-3 py-2">
          <span className="text-small font-medium text-ink">Observation discussion</span>
          <button type="button" aria-label="Close discussion preview" className="px-2 py-1 text-ink-secondary" onClick={() => setSelected(null)}>×</button>
        </div>
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-auto p-3 text-ink">
          {samplePost && preview.isError ? <>
            <p className="text-caption text-ink-secondary">Sample notebook post</p>
            <h3 className="text-body-sm font-medium">{samplePost.title}</h3>
            <p className="text-caption text-ink-secondary">{getProfile(samplePost.authorId)?.name} · {samplePost.dateLabel}</p>
            <p className="line-clamp-3 text-small text-ink-secondary">{samplePost.body}</p>
          </> : preview.isPending ? <p role="status" className="text-small">Loading preview…</p> : preview.isError ? <p className="text-small">Could not load this discussion. <button className="underline" onClick={() => preview.refetch()}>Retry</button></p> : preview.data && <>
            {preview.data.finding.evidence.image && <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/api${preview.data.finding.evidence.image.url}`} alt="SPHEREx discussion region" className="h-24 w-full rounded-md bg-black object-contain" />
            </>}
            <h3 className="text-body-sm font-medium">{preview.data.finding.title}</h3>
            <p className="text-caption text-ink-secondary">{preview.data.finding.author} · {preview.data.comments.length} comments</p>
            <p className="line-clamp-3 text-small text-ink-secondary">{preview.data.finding.body}</p>
            <p className="text-caption text-ink-secondary">{preview.data.finding.evidence.epochs.length} observations · {preview.data.finding.evidence.track.length} track positions</p>
          </>}
        </div>
        <button type="button" className="m-3 rounded-md bg-primary px-3 py-2 text-small text-on-primary" onClick={() => router.push(`/findings/${selected.id}`)}>Open discussion</button>
      </div>
    </foreignObject>}
  </g>;
}
