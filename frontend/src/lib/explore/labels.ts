import type { ObjectType } from "./types";

export const TYPE_LABELS: Record<ObjectType, string> = {
  star: "Star",
  "brown-dwarf": "Brown dwarf",
  planet: "Planet",
  comet: "Comet",
  asteroid: "Asteroid",
  galaxy: "Galaxy",
  empty: "Empty space or noise",
  artifact: "Artifact",
};
