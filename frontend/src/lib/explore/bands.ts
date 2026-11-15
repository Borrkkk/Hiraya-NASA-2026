import type { BandId } from "./types";

/**
 * The infrared "things to look for". Presentation only: names, colours and
 * copy live in the frontend; the backend only needs to know the ids.
 *
 * Wavelengths are approximate and must be validated by the SPHEREx science
 * team before launch (spec). Colours are fixed so a picture can be read from
 * its swatches. They are additive-blend friendly and avoid the ember accent.
 */
export type BandDef = {
  id: BandId;
  name: string;
  looksFor: string;
  whereItShows: string;
  realName: string;
  wavelength: string;
  /** Centre wavelength in µm, used by the mock spectrum. */
  centreUm: number;
  color: string;
};

export const BANDS: readonly BandDef[] = [
  {
    id: "starlight",
    name: "Starlight",
    looksFor: "Near-infrared light, often from stars",
    whereItShows: "Almost everywhere",
    realName: "Stellar continuum",
    wavelength: "0.75–1.30 µm",
    centreUm: 1.0,
    color: "#ffe9c8",
  },
  {
    id: "hydrogen",
    name: "Hydrogen region",
    looksFor: "Light near hydrogen emission lines",
    whereItShows: "Ionized gas can emit here; nearby stellar light also contributes. Compare with the surrounding spectrum.",
    realName: "Hydrogen lines (Paschen, Brackett)",
    wavelength: "about 1.28, 1.88 and 4.05 µm",
    centreUm: 1.88,
    color: "#ff5d8f",
  },
  {
    id: "helium",
    name: "Helium region",
    looksFor: "Light near the 1.083 µm helium line",
    whereItShows: "Helium may emit or absorb here in gas and stellar environments; brightness alone does not identify helium.",
    realName: "Helium line",
    wavelength: "about 1.08 µm",
    centreUm: 1.08,
    color: "#5fe0ff",
  },
  {
    id: "water-ice",
    name: "Water-ice region",
    looksFor: "Near the 3 µm absorption feature",
    whereItShows: "Ice can absorb light from background sources in dense clouds. Look for a dip relative to nearby wavelengths, not bright ice.",
    realName: "Water ice absorption",
    wavelength: "about 3.0 µm",
    centreUm: 3.0,
    color: "#4f86ff",
  },
  {
    id: "co2-ice",
    name: "CO₂-ice region",
    looksFor: "Near the 4.27 µm absorption feature",
    whereItShows: "CO₂ ice can absorb background light in dense clouds. Gas can also contribute; a spectrum is needed to distinguish them.",
    realName: "CO₂ ice absorption",
    wavelength: "about 4.27 µm",
    centreUm: 4.27,
    color: "#a77bff",
  },
  {
    id: "co-ice",
    name: "CO-ice region",
    looksFor: "Near the 4.67 µm absorption feature",
    whereItShows: "CO ice can absorb background light in cold clouds. Gaseous CO also has features in this region.",
    realName: "CO ice absorption",
    wavelength: "about 4.67 µm",
    centreUm: 4.67,
    color: "#5cf0b4",
  },
  {
    id: "organic-dust",
    name: "PAH region",
    looksFor: "Near aromatic emission at 3.3 µm",
    whereItShows: "Aromatic molecules can emit near 3.3 µm in illuminated dust. Continuum and other features also contribute.",
    realName: "PAH emission",
    wavelength: "about 3.3 µm",
    centreUm: 3.3,
    color: "#9dff5c",
  },
  {
    id: "methane",
    name: "Methane regions",
    looksFor: "Near methane absorption features",
    whereItShows: "Cool brown-dwarf atmospheres can absorb here. Compare the spectral shape; these windows overlap other features.",
    realName: "Methane absorption",
    wavelength: "about 1.7 and 3.3 µm",
    centreUm: 1.7,
    color: "#ffd447",
  },
  {
    id: "warm-glow",
    name: "4–5 µm light",
    looksFor: "Stars, dust and cool-object emission",
    whereItShows: "Thermal emission, stellar light, reflected sunlight and molecular features can all contribute. This is not a temperature map.",
    realName: "Long-wavelength light; mixed continuum and features",
    wavelength: "3.8–5.0 µm",
    centreUm: 4.5,
    color: "#e8453c",
  },
];

export const getBand = (id: BandId) => BANDS.find((b) => b.id === id)!;

/** On at load (spec open question 2). */
export const DEFAULT_BANDS: BandId[] = ["starlight", "warm-glow"];

export const EMPTY_BAND_NOTE = "Nothing bright here at this wavelength. That's normal.";
