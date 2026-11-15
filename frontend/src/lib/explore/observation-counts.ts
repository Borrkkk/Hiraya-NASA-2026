import type { BandId, Epoch } from './types';

/** Count observations, not detectors or successful image downloads. */
export function countBandObservations(all: readonly Epoch[], selected: readonly Epoch[], band: BandId) {
  const available = new Set(all.filter((e) => !e.bands || e.bands.includes(band)).map((e) => e.id));
  return {
    selected: new Set(selected.filter((e) => available.has(e.id)).map((e) => e.id)).size,
    total: available.size,
  };
}
