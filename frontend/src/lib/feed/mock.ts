// PLACEHOLDER CONTENT. Nothing on the home feed is wired to an API yet.
//
// What is real: the sky objects, their coordinates and every fact about them
// (distances, motions, what they are), and the cutout images.
// What is made up and must be replaced or removed before this goes public:
//   - every count ("looked this week", the Popular numbers)
//   - the people (Maya, Jordan) and the "Based on brown dwarfs" line
//   - the news blurbs, which are evergreen copy rather than dated stories
//   - the two findings, which are seeded examples
//
// The shapes below are what the real endpoints should return.

import type { Person, VerdictKind } from "@/components/ui";
import { getProfile, observationPosts } from "@/lib/profiles";

export const people: Record<string, Person> = {
  maya: getProfile("maya-rao")!,
  jordan: getProfile("jordan-kim")!,
};

/** For you: one hero, then a couple of quieter picks. */
export type Pick = {
  objectId: string;
  cutout: string;
  /** One line under the name. */
  short: string;
  /** Field of view to open it at, degrees. */
  fov: number;
};

export const forYou = {
  /** What the picks are based on. Mock personalisation. */
  basis: "Based on brown dwarfs",
  hero: {
    objectId: "luhman-16",
    cutout: "luhman-16",
    why: "Two failed stars circling each other, only 6.5 light years away. Watch them drift between frames.",
    fov: 0.1,
    social: "Maya and 38 others looked this week",
  },
  picks: [
    { objectId: "proxima", cutout: "proxima", short: "The closest star to the Sun", fov: 0.2 },
    { objectId: "eagle", cutout: "eagle", short: "Where the Pillars of Creation hide", fov: 0.7 },
  ] satisfies Pick[],
};

/** Popular right now: ranked by how many people looked. Text only. */
export type PopularItem = {
  objectId: string;
  why: string;
  looks: number;
  fov: number;
};

export const popular: PopularItem[] = [
  { objectId: "orion-nebula", why: "Stars being born in dust", looks: 1204, fov: 1 },
  { objectId: "galactic-centre", why: "Our galaxy's crowded heart", looks: 986, fov: 2.5 },
  { objectId: "carina", why: "A brilliant stellar nursery", looks: 742, fov: 1.5 },
  { objectId: "m31", why: "The galaxy next door", looks: 655, fov: 3.2 },
];

/** In the news. Evergreen headlines for now; no dates, no invented stories. */
export type NewsItem = {
  id: string;
  /** Topic, with the one real number folded in when there is one. */
  kicker: string;
  title: string;
  target: { q?: string; ra?: number; dec?: number; fov?: number; types?: string[] };
};

export const news: NewsItem[] = [
  {
    id: "3i-atlas",
    kicker: "Interstellar comet · the 3rd we've ever spotted",
    title: "3I/ATLAS is on its way out of the solar system",
    target: { q: "3I/ATLAS" },
  },
  {
    id: "spherex",
    kicker: "SPHEREx · 102 infrared colours in every image",
    title: "SPHEREx sees the whole sky in 102 colours",
    target: {},
  },
  {
    id: "volunteers",
    kicker: "Citizen science",
    title: "Volunteers keep finding brown dwarfs in old data",
    target: { types: ["brown-dwarf"] },
  },
];

/** New findings: seeded examples of what people share. */
export type Finding = {
  id: string;
  author: Person;
  /** What they were doing, shown under their name. */
  activity: string;
  verdict: VerdictKind;
  cutout: string;
  objectId: string;
  title: string;
  body: string;
  /** Short facts, shown on one mono line. */
  facts: string[];
  fov: number;
};

export const findings: Finding[] = observationPosts
  .filter((post) => ["barnard-moves", "betelgeuse-spikes"].includes(post.id))
  .map((post) => ({
    id: post.id,
    author: getProfile(post.authorId)!,
    activity: post.activity ?? "Shared an observation",
    verdict: post.verdict,
    cutout: post.cutout,
    objectId: post.objectId,
    title: post.title,
    body: post.body,
    facts: post.facts ?? [],
    fov: post.fov ?? 0.2,
  }));
