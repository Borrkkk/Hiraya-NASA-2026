// Plain-language descriptions of how a mover moves.

import type { Mover } from "./types";

const UNITS = [
  { label: "year", hours: 24 * 365.25 },
  { label: "month", hours: (24 * 365.25) / 12 },
  { label: "week", hours: 24 * 7 },
  { label: "day", hours: 24 },
  { label: "hour", hours: 1 },
] as const;

/** An angle in the plainest unit: degrees, then arcminutes, then arcseconds. */
function angle(arcsec: number): string {
  if (arcsec >= 360) return `${round(arcsec / 3600)}°`;
  if (arcsec >= 60) return `${round(arcsec / 60)} arcminutes`;
  return `${round(arcsec)} arcseconds`;
}

/**
 * "about 0.4° per year". The time unit is the longest one in which the
 * movement is at least an arcminute, so the number stays readable.
 */
export function speedPlain(arcsecPerHour: number): string {
  for (const u of UNITS) {
    const arc = arcsecPerHour * u.hours;
    if (arc >= 60) return `about ${angle(arc)} per ${u.label}`;
  }
  return `about ${angle(arcsecPerHour * UNITS[0].hours)} per year`;
}

/** Short form for the list: "0.4° a year". */
export function speedShort(arcsecPerHour: number): string {
  return speedPlain(arcsecPerHour).replace("about ", "").replace(" per ", " a ");
}

export function speedReal(arcsecPerHour: number): string {
  const perDay = arcsecPerHour * 24;
  return `${fmt(arcsecPerHour)} arcseconds per hour, ${fmt(perDay)} per day`;
}

const fmt = (n: number) => (n >= 100 ? n.toFixed(0) : n >= 10 ? n.toFixed(1) : n.toFixed(2));
const round = (n: number) => (n >= 10 ? Math.round(n) : Math.round(n * 10) / 10);

/**
 * Compass direction as the user sees it on screen (north up, east left).
 * Arrow rotation is clockwise from up, so east (PA 90) points left (-90).
 */
export function screenAngle(positionAngleDeg: number) {
  return -positionAngleDeg;
}

const DIRECTIONS = [
  "toward the top",
  "toward the upper right",
  "toward the right",
  "toward the lower right",
  "toward the bottom",
  "toward the lower left",
  "toward the left",
  "toward the upper left",
];

export function directionLabel(positionAngleDeg: number) {
  const a = ((screenAngle(positionAngleDeg) % 360) + 360) % 360;
  return DIRECTIONS[Math.round(a / 45) % 8];
}

/**
 * The "What this suggests" hint. THE THRESHOLDS ARE PLACEHOLDERS: they have to
 * come from the science team (spec Q10). The page always labels this a hint.
 */
export const SUGGESTION_THRESHOLDS = {
  /** Faster than this (arcsec/hour) points to something close in our solar system. */
  solarSystemAbove: 0.2,
  /** Slower than this points to something far away, like a star or brown dwarf. */
  distantBelow: 0.01,
};

export function suggestion(m: Pick<Mover, "speedArcsecPerHour">): string {
  const v = m.speedArcsecPerHour;
  if (v >= SUGGESTION_THRESHOLDS.solarSystemAbove)
    return "Fast movement like this usually points to something close, inside our solar system, such as an asteroid or a comet.";
  if (v <= SUGGESTION_THRESHOLDS.distantBelow)
    return "Almost no movement usually points to something very far away, such as a distant star or a brown dwarf.";
  return "Movement at this speed could be a nearby star, a cold brown dwarf, or a distant solar system object. It doesn't narrow things down much.";
}
