// Points for explained finds, kept in the browser (spec: "stored in the
// browser"). A simple rarity table: rarer kinds of object earn more. The
// numbers are placeholders for the team to tune.

import type { ObjectType } from "./types";

export const RARITY_POINTS: Record<ObjectType, number> = {
  star: 10,
  galaxy: 20,
  asteroid: 30,
  comet: 60,
  "brown-dwarf": 80,
  planet: 100,
  empty: 0,
  artifact: 0,
};

const KEY = "pulsr.points";

export function readPoints(): number {
  try {
    return Number(localStorage.getItem(KEY)) || 0;
  } catch {
    return 0;
  }
}

/** Adds points for an explained find and returns what was awarded. */
export function awardPoints(type: ObjectType): number {
  const n = RARITY_POINTS[type] ?? 0;
  if (n === 0) return 0;
  try {
    localStorage.setItem(KEY, String(readPoints() + n));
  } catch {
    // Storage blocked: the award still shows, it just isn't kept.
  }
  return n;
}
