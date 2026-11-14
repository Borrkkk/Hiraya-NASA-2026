export type SkyCoord = { ra: number; dec: number };

/**
 * Parses coordinates typed in almost any format. Returns degrees (ICRS), or
 * null when the text isn't a coordinate pair.
 *
 *   83.82 -5.39                         decimal degrees (comma optional)
 *   05h35m17.3s -05°23′28″              h m s / ° ′ ″
 *   05 35 17.3 -05 23 28                plain spaces: RA is read as hours
 *   5:35:17.3 -5:23:28                  colons
 *   83°49′ −5°23′                       degrees for both when no "h" is used
 *   RA 83.82 Dec -5.39                  labels are ignored
 */
export function parseCoordinates(input: string): SkyCoord | null {
  let s = input
    .trim()
    .replace(/[−–—﹣－]/g, "-")
    .replace(/\b(right ascension|declination|ra|dec)\b\s*[:=]?/gi, " ")
    .replace(/[,;]/g, " ");
  if (!s.trim()) return null;

  // Only digits, signs, dots, spaces and the unit letters h m s d may remain.
  if (/[a-z]/i.test(s.replace(/[hmsd]/gi, ""))) return null;

  const hoursMarked = /h/i.test(s);
  const degreesMarked = /°/.test(s);
  s = s.replace(/[hmsd°′'’″":]/gi, " ").replace(/\s+/g, " ").trim();

  const tokens = s.split(" ");
  if (tokens.some((t) => !/^[+-]?\d+(\.\d+)?$/.test(t))) return null;

  const n = tokens.length;
  if (n !== 2 && n !== 4 && n !== 6) return null;
  const half = n / 2;
  const raTokens = tokens.slice(0, half);
  const decTokens = tokens.slice(half);

  // Sexagesimal parts: first part is a whole number, the rest are 0–59.99.
  const toValue = (parts: string[]) => {
    const [head, ...rest] = parts;
    const negative = head.startsWith("-");
    const abs = [Math.abs(parseFloat(head)), ...rest.map(Number)];
    if (rest.some((v, i) => !/^\d/.test(rest[i]) || Number(v) >= 60)) return null;
    const value = abs.reduce((sum, v, i) => sum + v / 60 ** i, 0);
    return { value, negative };
  };

  const rawRa = toValue(raTokens);
  const rawDec = toValue(decTokens);
  if (!rawRa || !rawDec || rawRa.negative) return null;

  // RA is hours when marked with h, or when written without any ° (the usual
  // astronomy convention for "05 35 17.3"). A bare decimal pair is degrees.
  const raInHours = hoursMarked || (n > 2 && !degreesMarked);
  const ra = raInHours ? rawRa.value * 15 : rawRa.value;
  const dec = rawDec.negative ? -rawDec.value : rawDec.value;

  if (ra < 0 || ra >= 360 || dec < -90 || dec > 90) return null;
  return { ra, dec };
}
