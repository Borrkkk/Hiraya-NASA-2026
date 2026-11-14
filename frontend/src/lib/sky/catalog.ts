// A small local catalogue so search works with no backend. Coordinates are
// J2000 in degrees. Replace `searchCatalog` with the real name-resolver API later
// and keep the shapes.

export type ObjectKind =
  | "brown-dwarf"
  | "star"
  | "nebula"
  | "galaxy"
  | "cluster"
  | "small-body";

export const KINDS: { id: ObjectKind; label: string; singular: string }[] = [
  { id: "brown-dwarf", label: "Brown dwarfs", singular: "Brown dwarf" },
  { id: "star", label: "Stars", singular: "Star" },
  { id: "nebula", label: "Nebulae", singular: "Nebula" },
  { id: "galaxy", label: "Galaxies", singular: "Galaxy" },
  { id: "cluster", label: "Star clusters", singular: "Star cluster" },
  { id: "small-body", label: "Asteroids and comets", singular: "Comet" },
];

export const kindLabel = (kind: ObjectKind) => KINDS.find((k) => k.id === kind)!.singular;

export type SkyObject = {
  id: string;
  name: string;
  aliases?: string[];
  kind: ObjectKind;
  /** Constellation, for the search result meta line. */
  where?: string;
  /** Degrees. Missing for moving objects, which have no fixed position. */
  ra?: number;
  dec?: number;
  /** Sensible field of view (degrees) when exploring this object. */
  fov?: number;
  /** Shown in the empty-search suggestions. */
  suggested?: boolean;
};

export const CATALOG: SkyObject[] = [
  // Brown dwarfs
  { id: "luhman-16", name: "Luhman 16", aliases: ["WISE 1049-5319", "WISE J104915.57-531906.1"], kind: "brown-dwarf", where: "Vela", ra: 162.3279, dec: -53.3194, fov: 0.1, suggested: true },
  { id: "wise-0855", name: "WISE 0855−0714", aliases: ["WISE 0855", "WISE J085510.83-071442.5"], kind: "brown-dwarf", where: "Hydra", ra: 133.7951, dec: -7.2451, fov: 0.1 },

  // Stars
  { id: "proxima", name: "Proxima Centauri", aliases: ["Proxima", "Alpha Centauri C"], kind: "star", where: "Centaurus", ra: 217.4289, dec: -62.6795, fov: 0.2 },
  { id: "barnard", name: "Barnard's Star", aliases: ["Barnards Star", "GJ 699"], kind: "star", where: "Ophiuchus", ra: 269.4521, dec: 4.6934, fov: 0.2 },
  { id: "ross-128", name: "Ross 128", aliases: ["GJ 447"], kind: "star", where: "Virgo", ra: 176.9358, dec: 0.8044, fov: 0.2 },
  { id: "sirius", name: "Sirius", aliases: ["Alpha Canis Majoris"], kind: "star", where: "Canis Major", ra: 101.2872, dec: -16.7161, fov: 0.5 },
  { id: "betelgeuse", name: "Betelgeuse", aliases: ["Alpha Orionis"], kind: "star", where: "Orion", ra: 88.7929, dec: 7.4071, fov: 0.5 },
  { id: "vega", name: "Vega", aliases: ["Alpha Lyrae"], kind: "star", where: "Lyra", ra: 279.2347, dec: 38.7837, fov: 0.5 },
  { id: "polaris", name: "Polaris", aliases: ["North Star"], kind: "star", where: "Ursa Minor", ra: 37.9546, dec: 89.2641, fov: 0.5 },

  // Nebulae
  { id: "orion-nebula", name: "Orion Nebula", aliases: ["M42", "NGC 1976"], kind: "nebula", where: "Orion", ra: 83.8221, dec: -5.3911, fov: 1, suggested: true },
  { id: "horsehead", name: "Horsehead Nebula", aliases: ["Barnard 33", "IC 434"], kind: "nebula", where: "Orion", ra: 85.2458, dec: -2.4583, fov: 0.7 },
  { id: "crab", name: "Crab Nebula", aliases: ["M1", "NGC 1952"], kind: "nebula", where: "Taurus", ra: 83.6331, dec: 22.0145, fov: 0.3 },
  { id: "eagle", name: "Eagle Nebula", aliases: ["M16", "Pillars of Creation", "NGC 6611"], kind: "nebula", where: "Serpens", ra: 274.7, dec: -13.8167, fov: 0.7 },
  { id: "carina", name: "Carina Nebula", aliases: ["NGC 3372", "Eta Carinae Nebula"], kind: "nebula", where: "Carina", ra: 161.283, dec: -59.868, fov: 1.5, suggested: true },
  { id: "rosette", name: "Rosette Nebula", aliases: ["NGC 2237"], kind: "nebula", where: "Monoceros", ra: 98.4375, dec: 4.9983, fov: 1.5 },
  { id: "lagoon", name: "Lagoon Nebula", aliases: ["M8", "NGC 6523"], kind: "nebula", where: "Sagittarius", ra: 270.904, dec: -24.387, fov: 0.8 },
  { id: "trifid", name: "Trifid Nebula", aliases: ["M20", "NGC 6514"], kind: "nebula", where: "Sagittarius", ra: 270.675, dec: -23.03, fov: 0.5 },
  { id: "ring", name: "Ring Nebula", aliases: ["M57", "NGC 6720"], kind: "nebula", where: "Lyra", ra: 283.396, dec: 33.029, fov: 0.15 },
  { id: "tarantula", name: "Tarantula Nebula", aliases: ["30 Doradus", "NGC 2070"], kind: "nebula", where: "Dorado", ra: 84.658, dec: -69.083, fov: 0.5 },

  // Galaxies
  { id: "m31", name: "Andromeda Galaxy", aliases: ["M31", "NGC 224"], kind: "galaxy", where: "Andromeda", ra: 10.6847, dec: 41.2687, fov: 3.2, suggested: true },
  { id: "m33", name: "Triangulum Galaxy", aliases: ["M33", "NGC 598"], kind: "galaxy", where: "Triangulum", ra: 23.4621, dec: 30.6602, fov: 1.2 },
  { id: "m51", name: "Whirlpool Galaxy", aliases: ["M51", "NGC 5194"], kind: "galaxy", where: "Canes Venatici", ra: 202.4696, dec: 47.1952, fov: 0.3 },
  { id: "lmc", name: "Large Magellanic Cloud", aliases: ["LMC"], kind: "galaxy", where: "Dorado", ra: 80.894, dec: -69.756, fov: 8 },
  { id: "smc", name: "Small Magellanic Cloud", aliases: ["SMC"], kind: "galaxy", where: "Tucana", ra: 13.1867, dec: -72.8286, fov: 5 },
  { id: "galactic-centre", name: "Galactic Centre", aliases: ["Sagittarius A*", "Sgr A*", "Milky Way core", "Galactic Center"], kind: "galaxy", where: "Sagittarius", ra: 266.4168, dec: -29.0078, fov: 2.5, suggested: true },

  // Star clusters
  { id: "pleiades", name: "Pleiades", aliases: ["M45", "Seven Sisters"], kind: "cluster", where: "Taurus", ra: 56.75, dec: 24.1167, fov: 2.5 },
  { id: "omega-centauri", name: "Omega Centauri", aliases: ["NGC 5139"], kind: "cluster", where: "Centaurus", ra: 201.6968, dec: -47.4795, fov: 1 },
  { id: "beehive", name: "Beehive Cluster", aliases: ["M44", "Praesepe"], kind: "cluster", where: "Cancer", ra: 130.1, dec: 19.667, fov: 1.5 },

  // Moving objects have no fixed coordinates.
  { id: "3i-atlas", name: "3I/ATLAS", aliases: ["C/2025 N1", "Interstellar comet"], kind: "small-body", suggested: true },
];

export const getObject = (id: string) => {
  const o = CATALOG.find((c) => c.id === id);
  if (!o) throw new Error(`Unknown sky object: ${id}`);
  return o;
};

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

/**
 * Typeahead over the local catalogue. Empty query returns suggestions.
 * `kinds` narrows results to the selected object types (empty = all).
 */
export function searchCatalog(query: string, kinds: ObjectKind[] = [], limit = 6): SkyObject[] {
  const pool = kinds.length ? CATALOG.filter((o) => kinds.includes(o.kind)) : CATALOG;
  const q = norm(query);
  if (!q) return pool.filter((o) => o.suggested).concat(pool.filter((o) => !o.suggested)).slice(0, limit);

  const scored: { o: SkyObject; score: number }[] = [];
  for (const o of pool) {
    const names = [o.name, ...(o.aliases ?? [])].map(norm);
    let score = 0;
    for (const n of names) {
      if (n === q) score = Math.max(score, 100);
      else if (n.startsWith(q)) score = Math.max(score, 80);
      else if (n.split(" ").some((w) => w.startsWith(q))) score = Math.max(score, 60);
      else if (n.includes(q)) score = Math.max(score, 40);
    }
    // "nebula", "brown dwarf" and constellation names match too.
    if (!score && norm(kindLabel(o.kind)).includes(q)) score = 20;
    if (!score && o.where && norm(o.where).startsWith(q)) score = 20;
    if (score) scored.push({ o, score });
  }
  return scored.sort((a, b) => b.score - a.score).slice(0, limit).map((s) => s.o);
}
