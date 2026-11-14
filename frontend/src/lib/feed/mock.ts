// PLACEHOLDER CONTENT. Nothing on the home feed is wired to an API yet.
//
// What is real: the sky objects, their coordinates and every fact about them
// (distances, motions, what they are), and the cutout images.
// What is made up and must be replaced or removed before this goes public:
//   - every count ("looked this week", "saw it too", comments)
//   - the people (Maya, Jordan, ...) and the personalisation line
//   - the news blurbs, which are evergreen copy rather than dated stories
//   - the two findings, which are seeded examples
//
// The shapes below are what the real endpoints should return.

import type { Person } from "@/components/ui";
import type { VerdictKind } from "@/components/ui";

export const people: Record<string, Person> = {
  maya: { initials: "MR", tone: 1, name: "Maya R." },
  jordan: { initials: "JK", tone: 2, name: "Jordan K." },
  sam: { initials: "ST", tone: 3, name: "Sam T." },
  priya: { initials: "PN", tone: 4, name: "Priya N." },
};

/** For you: one hero and a few smaller picks. */
export type Pick = {
  objectId: string;
  cutout: string;
  /** One line on why it's worth a look. */
  why: string;
  /** Short line under the name on small cards. */
  short: string;
  /** Field of view to open it at, degrees. */
  fov: number;
};

export const forYou = {
  /** Why these were picked. Mock personalisation. */
  basis: "Because you looked at brown dwarfs",
  hero: {
    objectId: "luhman-16",
    cutout: "luhman-16",
    why: "Two failed stars circling each other, only 6.5 light years away. Watch them drift between frames.",
    short: "",
    fov: 0.1,
    social: { people: [people.maya, people.jordan, people.sam], text: "Maya and 38 others looked this week" },
  },
  picks: [
    { objectId: "ross-128", cutout: "ross-128", short: "A quiet red dwarf with a planet next door", why: "", fov: 0.2 },
    { objectId: "proxima", cutout: "proxima", short: "The closest star to the Sun", why: "", fov: 0.2 },
    { objectId: "eagle", cutout: "eagle", short: "Where the Pillars of Creation hide", why: "", fov: 0.7 },
  ] satisfies Pick[],
};

/** Popular right now: ranked by how many people looked. */
export type PopularItem = {
  objectId: string;
  cutout: string;
  why: string;
  looks: number;
  fov: number;
};

export const popular: PopularItem[] = [
  { objectId: "orion-nebula", cutout: "orion", why: "Stars being born in dust", looks: 1204, fov: 1 },
  { objectId: "galactic-centre", cutout: "galactic-centre", why: "Our galaxy's crowded heart", looks: 986, fov: 2.5 },
  { objectId: "carina", cutout: "carina", why: "A brilliant stellar nursery", looks: 742, fov: 1.5 },
  { objectId: "m31", cutout: "m31", why: "The galaxy next door", looks: 655, fov: 3.2 },
];

/** In the news. Evergreen blurbs for now; no dates, no invented headlines. */
export type NewsItem = {
  id: string;
  kicker: string;
  /** Big number and what it counts. Optional. */
  figure?: { value: string; caption: string };
  title: string;
  body: string;
  /** Where the card sends you, shown in the footer. */
  where: string;
  target: { q?: string; ra?: number; dec?: number; fov?: number; types?: string[] };
};

export const news: NewsItem[] = [
  {
    id: "3i-atlas",
    kicker: "Interstellar comet",
    figure: { value: "3rd", caption: "interstellar visitor we've ever spotted" },
    title: "3I/ATLAS is on its way out of the solar system",
    body: "It came from another star and won't be back. Its path is too fast for the Sun to hold on to it.",
    where: "A moving target",
    target: { q: "3I/ATLAS" },
  },
  {
    id: "spherex",
    kicker: "SPHEREx",
    figure: { value: "102", caption: "infrared colours in every image" },
    title: "SPHEREx sees the whole sky in 102 colours",
    body: "NASA's telescope maps the sky in infrared over and over, so anything that moves or changes stands out.",
    where: "The whole sky",
    target: {},
  },
  {
    id: "volunteers",
    kicker: "Citizen science",
    title: "Volunteers keep finding brown dwarfs in old data",
    body: "People with no telescope have spotted cold objects that automated searches missed. Your eyes count.",
    where: "Brown dwarfs",
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
  facts: { label: string; value: string }[];
  saw: number;
  comments: number;
  fov: number;
};

export const findings: Finding[] = [
  {
    id: "barnard-moves",
    author: people.maya,
    activity: "Blinked two frames",
    verdict: "explained",
    cutout: "barnard",
    objectId: "barnard",
    title: "One dot slid up the screen",
    body: "Flicked between two dates and a single star moved. It's Barnard's Star, the fastest-moving star we know.",
    facts: [
      { label: "Kind", value: "Red dwarf" },
      { label: "Motion", value: "10.4″ / yr" },
      { label: "Distance", value: "6 ly" },
    ],
    saw: 38,
    comments: 6,
    fov: 0.2,
  },
  {
    id: "betelgeuse-spikes",
    author: people.jordan,
    activity: "Ran Verify",
    verdict: "artifact",
    cutout: "betelgeuse",
    objectId: "betelgeuse",
    title: "A giant cross over Orion's shoulder",
    body: "Looked like something huge. The check says it's the detector: the star is so bright it floods the image.",
    facts: [
      { label: "Cause", value: "Bright star" },
      { label: "Flag", value: "Saturated" },
      { label: "Star", value: "Betelgeuse" },
    ],
    saw: 12,
    comments: 3,
    fov: 0.5,
  },
];
