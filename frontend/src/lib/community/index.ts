// The community layer, with no server. The five sample discussions are static
// files baked by scripts/export-community.py (public/demo/community). A
// discussion or comment you add is saved in THIS browser only (localStorage),
// so nothing a visitor types ever leaves their device.

import type { Finding, FindingComment } from "../findings";
import type { SkyBox, Spectrum } from "../explore/types";

export const COMMUNITY_BASE = "/demo/community";
const STORE_KEY = "hiraya:community:v1";
const MAX_POSTS = 20;
const MAX_COMMENTS = 100;
/** The signed-in demo profile (see lib/profiles.ts). */
export const DEMO_ACCOUNT = { id: "alex-rivera", name: "Alex Rivera", mode: "demo" } as const;

type Stored = Finding & { comments: FindingComment[] };
type Seed = { findings: Stored[]; live: { box: SkyBox; evidence: Finding["evidence"] } };
type Local = { posts: Stored[]; comments: Record<string, FindingComment[]> };

let seedLoad: Promise<Seed> | null = null;
function seed(): Promise<Seed> {
  seedLoad ??= fetch(`${COMMUNITY_BASE}/community.json`)
    .then((r) => {
      if (!r.ok) throw new Error("The sample discussions are missing. Run `pnpm demo:community`.");
      return r.json() as Promise<Seed>;
    })
    .catch((e) => {
      seedLoad = null;
      throw e;
    });
  return seedLoad;
}

// If storage is blocked (private window), keep the session's posts in memory.
let memory: Local = { posts: [], comments: {} };
function read(): Local {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return memory;
    const v = JSON.parse(raw) as Local;
    if (Array.isArray(v.posts) && v.comments && typeof v.comments === "object") return v;
  } catch {
    /* unreadable: fall back to memory */
  }
  return memory;
}
function write(next: Local) {
  memory = next;
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(next));
  } catch {
    /* quota or blocked: memory still holds it for this visit */
  }
}

function asFinding(f: Stored): Finding {
  const copy: Partial<Stored> = { ...f };
  delete copy.comments;
  return copy as Finding;
}

function separation(ra1: number, dec1: number, ra2: number, dec2: number) {
  const d = (((ra2 - ra1 + 180) % 360) + 360) % 360 - 180;
  const a = (dec1 * Math.PI) / 180;
  const b = (dec2 * Math.PI) / 180;
  const h = Math.sin((b - a) / 2) ** 2 + Math.cos(a) * Math.cos(b) * Math.sin((d * Math.PI) / 360) ** 2;
  return (2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, h)))) * 180) / Math.PI;
}

/** One thread per spot: selections within a native pixel, or overlapping within a minute of arc. */
function sameSpot(box: SkyBox, other: SkyBox) {
  const arcsec = separation(box.ra, box.dec, other.ra, other.dec) * 3600;
  if (arcsec <= 6.15) return true;
  if (arcsec > 60) return false;
  const east = Math.abs((((box.ra - other.ra + 180) % 360) + 360) % 360 - 180) * Math.abs(Math.cos((((box.dec + other.dec) / 2) * Math.PI) / 180));
  return east <= (box.width + other.width) / 2 && Math.abs(box.dec - other.dec) <= (box.height + other.height) / 2;
}

async function all(): Promise<Stored[]> {
  const [s, local] = [await seed(), read()];
  return [...local.posts, ...s.findings]
    .map((f) => ({ ...f, comments: [...f.comments, ...(local.comments[f.id] ?? [])] }))
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}

export async function listFindings(): Promise<(Finding & { replies: number })[]> {
  return (await all()).map((f) => ({ ...asFinding(f), replies: f.comments.length }));
}

export async function getFinding(id: string): Promise<{ finding: Finding; comments: FindingComment[] } | null> {
  const found = (await all()).find((f) => f.id === id);
  return found ? { finding: asFinding(found), comments: found.comments } : null;
}

export async function matchFinding(box: SkyBox): Promise<Finding | null> {
  const found = (await all()).find((f) => sameSpot(box, f.box));
  return found ? asFinding(found) : null;
}

export async function findingMarkers(ra: number, dec: number, radius: number) {
  return (await all())
    .filter((f) => separation(ra, dec, f.box.ra, f.box.dec) <= radius)
    .map((f) => ({ id: f.id, ra: f.box.ra, dec: f.box.dec, name: f.title, kind: "finding" as const }));
}

export type NewFinding = {
  box: SkyBox;
  title: string;
  body: string;
  bands: string[];
  epochs: string[];
  track: { ra: number; dec: number; epochId: string; date: string }[];
  view: { ra: number; dec: number; fov: number } | null;
  spectrum: Spectrum | null;
};

export async function createFinding(input: NewFinding): Promise<{ finding: Finding; created: boolean }> {
  if (new Set(input.epochs).size < 2) throw new Error("Select at least two different observations.");
  const title = input.title.trim().slice(0, 120);
  const body = input.body.trim().slice(0, 6000);
  if (title.length < 3 || body.length < 10) throw new Error("Add a title and a few words about what changed.");
  const dup = await matchFinding(input.box);
  if (dup) return { finding: dup, created: false };

  const s = await seed();
  // Around the faint mover the attached pictures are the ones baked for it. Anywhere else
  // there is no baked snapshot, so the post carries the measurements it was made with.
  const atFind = separation(input.box.ra, input.box.dec, s.live.box.ra, s.live.box.dec) * 3600 <= 60;
  const evidence: Finding["evidence"] = atFind
    ? { ...s.live.evidence, demo: true, authorId: DEMO_ACCOUNT.id, view: input.view ?? s.live.evidence.view }
    : {
        bands: input.bands,
        epochs: input.epochs,
        track: input.track,
        view: input.view,
        demo: true,
        authorId: DEMO_ACCOUNT.id,
        ...(input.spectrum && input.spectrum.points.length
          ? {
              spectrum: input.spectrum,
              summary: `This post compares ${input.epochs.length} selected observations in ${input.bands.length} wavelength window(s). The brightness plot has ${input.spectrum.points.length} samples. All images and measurements here are simulated for the demo.`,
              summaryMethod: "data" as const,
            }
          : {}),
      };
  const post: Stored = {
    id: `local-${crypto.randomUUID()}`,
    title,
    body,
    author: DEMO_ACCOUNT.name,
    created_at: new Date().toISOString(),
    box: input.box,
    status: "suspected-motion",
    evidence,
    comments: [],
  };
  const local = read();
  write({ ...local, posts: [post, ...local.posts].slice(0, MAX_POSTS) });
  return { finding: asFinding(post), created: true };
}

export async function addFindingComment(id: string, body: string): Promise<FindingComment> {
  const text = body.trim().slice(0, 2000);
  if (!text) throw new Error("Write a comment first.");
  if (!(await getFinding(id))) throw new Error("This discussion is unavailable.");
  const comment: FindingComment = {
    id: `local-${crypto.randomUUID()}`,
    author: DEMO_ACCOUNT.name,
    body: text,
    created_at: new Date().toISOString(),
  };
  const local = read();
  const mine = [...(local.comments[id] ?? []), comment].slice(-MAX_COMMENTS);
  write({ ...local, comments: { ...local.comments, [id]: mine } });
  return comment;
}

/** Clear everything this browser added (used by the guided tour's reset). */
export function resetLocalCommunity() {
  write({ posts: [], comments: {} });
}
