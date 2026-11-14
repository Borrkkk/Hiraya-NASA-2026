"use client";

import { useSearchParams } from "next/navigation";

/** Shows what the home screen handed over, so the wiring is easy to check. */
export function ExploreParams() {
  const params = useSearchParams();
  const entries = [...params.entries()];
  if (entries.length === 0) {
    return <p className="text-small text-ink-secondary">No target. You&apos;d start from the whole sky.</p>;
  }
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 rounded-lg border border-line bg-surface p-4">
      {entries.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="font-mono text-mono text-ink-secondary">{k}</dt>
          <dd className="font-mono text-mono tabular-nums text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
