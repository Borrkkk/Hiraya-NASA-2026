import type { BandId } from './types';

/** Keep one window on while allowing an exclusive switch to any available one. */
export function toggleWindow(active: readonly BandId[], id: BandId, canCombine: boolean): BandId[] {
  if (active.includes(id)) return active.length > 1 ? active.filter((band) => band !== id) : [...active];
  return canCombine ? [...active, id] : [id];
}
