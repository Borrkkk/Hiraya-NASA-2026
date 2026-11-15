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
    looksFor: "Ordinary warm stars",
    whereItShows: "Almost everywhere",
    realName: "Stellar continuum",
    wavelength: "about 1 µm",
    centreUm: 1.0,
    color: "#ffe9c8",
  },
  {
    id: "hydrogen",
    name: "Hydrogen glow",
    looksFor: "Gas lit up by hot young stars",
    whereItShows: "Star-forming clouds and nebulae",
    realName: "Hydrogen lines (Paschen, Brackett)",
    wavelength: "about 1.28, 1.88 and 4.05 µm",
    centreUm: 1.88,
    color: "#ff5d8f",
  },
  {
    id: "helium",
    name: "Helium",
    looksFor: "Hot gas around young stars",
    whereItShows: "Hot nebulae",
    realName: "Helium line",
    wavelength: "about 1.08 µm",
    centreUm: 1.08,
    color: "#5fe0ff",
  },
  {
    id: "water-ice",
    name: "Water ice",
    looksFor: "Frozen water in cold clouds",
    whereItShows: "Dense, cold dust clouds",
    realName: "Water ice absorption",
    wavelength: "about 3.0 µm",
    centreUm: 3.0,
    color: "#4f86ff",
  },
  {
    id: "co2-ice",
    name: "Carbon dioxide ice",
    looksFor: "Frozen CO₂ in cold clouds",
    whereItShows: "Dense, cold dust clouds",
    realName: "CO₂ ice absorption",
    wavelength: "about 4.27 µm",
    centreUm: 4.27,
    color: "#a77bff",
  },
  {
    id: "co-ice",
    name: "Carbon monoxide ice",
    looksFor: "Frozen CO in the coldest clouds",
    whereItShows: "Coldest, densest clouds",
    realName: "CO ice absorption",
    wavelength: "about 4.67 µm",
    centreUm: 4.67,
    color: "#5cf0b4",
  },
  {
    id: "organic-dust",
    name: "Organic dust",
    looksFor: "Complex carbon molecules in dust",
    whereItShows: "Edges of glowing clouds",
    realName: "PAH emission",
    wavelength: "about 3.3 µm",
    centreUm: 3.3,
    color: "#9dff5c",
  },
  {
    id: "methane",
    name: "Methane",
    looksFor: "Very cold, dim objects",
    whereItShows: "Brown dwarfs",
    realName: "Methane absorption",
    wavelength: "about 1.7 and 3.3 µm",
    centreUm: 1.7,
    color: "#ffd447",
  },
  {
    id: "warm-glow",
    name: "Warm glow",
    looksFor: "Heat from dust and cool objects",
    whereItShows: "Dust, comets, asteroids, cool objects",
    realName: "Thermal continuum",
    wavelength: "about 4–5 µm",
    centreUm: 4.5,
    color: "#e8453c",
  },
];

export const getBand = (id: BandId) => BANDS.find((b) => b.id === id)!;

/** On at load (spec open question 2). */
export const DEFAULT_BANDS: BandId[] = ["starlight", "warm-glow"];

export const EMPTY_BAND_NOTE = "Nothing bright here at this wavelength. That's normal.";
