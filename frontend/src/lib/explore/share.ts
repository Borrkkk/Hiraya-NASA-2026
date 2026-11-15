import type { Inspection, Mover, SkyBox, BandId } from "./types";

/**
 * What "Share this find" hands to the Share flow (built elsewhere): the view,
 * the spectrum, the track and the epochs. The Share flow isn't built yet, so
 * the page links to a placeholder route and parks the payload in
 * sessionStorage under SHARE_KEY. The Share flow can read it from there, or
 * the team can replace `openShare` with a real call.
 */
export type ShareDraft = {
  areaName: string | null;
  box: SkyBox;
  bands: BandId[];
  epochs: string[];
  spectrum: Inspection["spectrum"] | null;
  mover: Mover | null;
  viewUrl: string;
};

export const SHARE_KEY = "pulsr.share-draft";

export function openShare(draft: ShareDraft): string {
  try {
    sessionStorage.setItem(SHARE_KEY, JSON.stringify(draft));
  } catch {
    // Storage blocked: the placeholder page still opens.
  }
  return "/share";
}
