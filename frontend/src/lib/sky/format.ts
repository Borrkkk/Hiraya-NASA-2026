// Pulsr number formats: 08h55m10.8s −07°14′42″, 8.1″ / yr, 1,240 pts.

const pad2 = (n: number) => String(n).padStart(2, "0");

/** Right ascension in degrees → `08h55m10.8s`. */
export function formatRa(deg: number) {
  // Work in tenths of a second so rounding carries cleanly (23h59m59.96s → 00h00m00.0s).
  const day = 24 * 36000;
  const t = Math.round((((deg % 360) + 360) % 360) * (day / 360)) % day;
  const hh = Math.floor(t / 36000);
  const mm = Math.floor((t % 36000) / 600);
  const ss = (t % 600) / 10;
  return `${pad2(hh)}h${pad2(mm)}m${ss.toFixed(1).padStart(4, "0")}s`;
}

/** Declination in degrees → `−07°14′42″` (true minus sign). */
export function formatDec(deg: number) {
  const total = Math.round(Math.abs(deg) * 3600);
  const dd = Math.floor(total / 3600);
  const mm = Math.floor((total % 3600) / 60);
  const ss = total % 60;
  const sign = deg < 0 && total > 0 ? "−" : "+";
  return `${sign}${pad2(dd)}°${pad2(mm)}′${pad2(ss)}″`;
}

export function formatCoords(ra: number, dec: number) {
  return `${formatRa(ra)} ${formatDec(dec)}`;
}

/** Field of view in degrees → `24°`, `18′`, `40″`. */
export function formatFov(deg: number) {
  if (deg >= 1) return `${deg.toFixed(deg >= 10 ? 0 : 1).replace(/\.0$/, "")}°`;
  const arcmin = deg * 60;
  if (arcmin >= 1) return `${arcmin.toFixed(arcmin >= 10 ? 0 : 1).replace(/\.0$/, "")}′`;
  return `${Math.round(arcmin * 60)}″`;
}

export function formatCount(n: number) {
  return n.toLocaleString("en-US");
}
