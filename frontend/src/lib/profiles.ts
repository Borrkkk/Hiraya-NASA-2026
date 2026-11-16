import type { Person, VerdictKind } from "@/components/ui";

// Fictional accounts for the profile and feed preview; no authentication implied.
export type UserProfile = Person & {
  handle: string;
  role: string;
  bio: string;
  notebook: string;
  interests: string[];
  joined: string;
  verified: boolean;
};
export const profiles: UserProfile[] = [
  { id: "maya-rao", initials: "MR", tone: 1, name: "Dr. Maya Rao", handle: "mayarao", role: "Research astronomer", verified: true,
    bio: "Looking for the quiet things that move. I study nearby stars and brown dwarfs, and share the checks behind each observation.",
    notebook: "Small changes, carefully checked. This notebook follows nearby objects across infrared surveys.",
    interests: ["Brown dwarfs", "Stellar motion", "Infrared surveys"], joined: "September 2026" },
  { id: "jordan-kim", initials: "JK", tone: 2, name: "Jordan Kim", handle: "jordankim", role: "Citizen scientist", verified: false,
    bio: "Learning to tell a sky signal from an image artifact. I share the surprises, the checks, and the things that turned out to be the detector.",
    notebook: "A practical notebook of bright stars, image artifacts, and the questions worth checking twice.",
    interests: ["Image artifacts", "Bright stars", "Survey imaging"], joined: "October 2026" },
  { id: "alex-rivera", initials: "AR", tone: 1, name: "Alex Rivera", handle: "alexrivera", role: "Sky explorer", verified: false,
    bio: "Finding my way around the infrared sky, one observation at a time. Currently exploring star-forming regions and keeping a notebook of interesting fields.",
    notebook: "Coordinates, reference fields, and questions from a growing observing notebook.",
    interests: ["Star formation", "Nebulae", "Infrared surveys"], joined: "November 2026" },
];
export const currentUserId = "alex-rivera";
export const profileHref = (id: string) => "/profile/" + encodeURIComponent(id);
export const getProfile = (id: string) => profiles.find((profile) => profile.id === id);

// Seeded UI content; these are examples of observation notes, not new findings.
export type ObservationPost = {
  authorId: string;
  activity?: string;
  facts?: string[];
  fov?: number;
  id: string;
  objectId: string;
  cutout: string;
  topic: string;
  title: string;
  body: string;
  date: string;
  dateLabel: string;
  verdict: VerdictKind;
  note: string;
  pinned?: boolean;
};
export const observationPosts: ObservationPost[] = [
  {
    authorId: "jordan-kim", id: "sample-orion-light", objectId: "orion-nebula", cutout: "orion-nebula", topic: "Star formation",
    title: "Different infrared views of the Orion field",
    body: "Comparing real SPHEREx revisits of the Orion field. The marked crop and labelled blink help us check which differences follow wavelength and which deserve a closer look across dates.",
    date: "2026-11-15", dateLabel: "15 Nov 2026", verdict: "unexplained", note: "Sample discussion · Real SPHEREx observations", fov: .8,
  },
  {
    authorId: "alex-rivera", id: "sample-andromeda-core", objectId: "m31", cutout: "m31", topic: "Galaxies",
    title: "Comparing the inner Andromeda field",
    body: "A notebook comparison of the inner Andromeda field in infrared light. I attached a marked image, a blink sequence, and brightness measurements to discuss how to choose a fair comparison region.",
    date: "2026-11-15", dateLabel: "15 Nov 2026", verdict: "unexplained", note: "Sample discussion · Real SPHEREx observations", fov: .8,
  },
  {
    authorId: "maya-rao", id: "barnard-moves", activity: "Blinked two frames", facts: ["Red dwarf", "10.4″ / yr", "6 ly"], fov: 0.2, objectId: "barnard", cutout: "barnard", topic: "Stellar motion",
    title: "One dot slid up the screen",
    body: "Flicked between two dates and a single star moved. It's Barnard's Star, the fastest-moving star we know.",
    date: "2026-11-14", dateLabel: "14 Nov 2026", verdict: "explained",
    note: "Method note · Astrometric alignment", pinned: true,
  },
  {
    authorId: "maya-rao", id: "luhman-notebook", objectId: "luhman-16", cutout: "luhman-16", topic: "Brown dwarfs",
    title: "Two close neighbours. One careful comparison.",
    body: "Adding Luhman 16 to my nearby-object notebook. The first check is what the survey actually resolves: a bright spot in a wide-field cutout is not evidence that both components are separately visible.",
    date: "2026-11-12", dateLabel: "12 Nov 2026", verdict: "explained",
    note: "Field note · Source blending",
  },
  {
    authorId: "maya-rao", id: "proxima-question", objectId: "proxima", cutout: "proxima", topic: "Stellar motion",
    title: "A brighter pixel deserves a second look, not a discovery claim.",
    body: "A comparison exercise around Proxima Centauri: before interpreting a brightness change, check the flags, the local background, and the calibration. Leaving this notebook question open until those checks are complete.",
    date: "2026-11-10", dateLabel: "10 Nov 2026", verdict: "unexplained",
    note: "Open question · Image quality checks",
  },
  {
    authorId: "jordan-kim", id: "betelgeuse-spikes", objectId: "betelgeuse", cutout: "betelgeuse", topic: "Image artifacts",
    title: "A giant cross over Orion's shoulder",
    body: "Looked like something huge. The check says it's the detector: the star is so bright it floods the image.",
    date: "2026-11-13", dateLabel: "13 Nov 2026", verdict: "artifact", activity: "Ran Verify",
    facts: ["Bright star", "Saturated", "Betelgeuse"], fov: 0.5, note: "Field note · Saturation", pinned: true,
  },
  {
    authorId: "alex-rivera", id: "eagle-field", objectId: "eagle", cutout: "eagle", topic: "Star formation",
    title: "Starting a notebook in the Eagle Nebula.",
    body: "My first field note: mapping the bright sources and dark lanes in this reference image. Saving the coordinates so I can return to the same patch of sky for a closer comparison.",
    date: "2026-11-14", dateLabel: "14 Nov 2026", verdict: "unexplained", note: "Open notebook · Reference field",
  },
];
