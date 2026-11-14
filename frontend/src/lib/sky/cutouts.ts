import spec from "@/data/cutouts.json";

// Real survey cutouts baked by `pnpm bake:cutouts` into public/sky/<id>.webp.
// Infrared (WISE, 2MASS) where infrared is the point, DSS2 where it simply
// looks best. Each image's tag names the survey it came from.
export type Cutout = {
  id: string;
  src: string;
  width: number;
  height: number;
  /** Field of view of the image, degrees. */
  fov: number;
  /** Shown in image tags, e.g. "WISE". */
  surveyLabel: string;
};

export function getCutout(id: string): Cutout {
  const c = spec.cutouts.find((x) => x.id === id);
  if (!c) throw new Error(`No cutout "${id}". Add it to src/data/cutouts.json and run pnpm bake:cutouts.`);
  const survey = spec.surveys[c.survey as keyof typeof spec.surveys];
  return {
    id,
    src: `/sky/${id}.webp`,
    width: spec.width,
    height: spec.height,
    fov: c.fov,
    surveyLabel: survey.label,
  };
}
