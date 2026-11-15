import type { Inspection, Mover, SkyBox, BandId } from "./types";

/**
 * Carry a selection to the finding composer. Drafts stay in this tab;
 * submitted findings and discussion are persisted by the backend.
 */
export type ShareDraft = {
  areaName: string | null;
  box: SkyBox;
  bands: BandId[];
  epochs: string[];
  spectrum: Inspection["spectrum"] | null;
  mover: Mover | null;
  viewUrl: string;
  view?: { ra: number; dec: number; fov: number };
};

export const SHARE_KEY = "pulsr.share-draft";

export function openShare(draft: ShareDraft): string {
  try {
    sessionStorage.setItem(SHARE_KEY, JSON.stringify(draft));
  } catch {
    // The composer explains that a draft could not be recovered.
  }
  return "/share";
}
