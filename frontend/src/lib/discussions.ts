"use client";

import { useSyncExternalStore } from "react";
import { currentUserId, getProfile, observationPosts } from "@/lib/profiles";

export type DiscussionComment = {
  id: string;
  authorId: string;
  body: string;
  createdAt: string;
  parentId: string | null;
};

// Fictional conversations accompanying the sample observation posts.
const seeds: Record<string, DiscussionComment[]> = {
  "barnard-moves": [
    { id: "barnard-question", authorId: "jordan-kim", body: "How do you tell the star’s motion apart from a small alignment error between the frames?", createdAt: "2026-11-14T15:10:00Z", parentId: null },
    { id: "barnard-answer", authorId: "maya-rao", body: "I’d check several background sources first. If those stay aligned while the target shifts, that supports motion. The dates and pixel scale are the next checks I’d share.", createdAt: "2026-11-14T15:24:00Z", parentId: "barnard-question" },
    { id: "barnard-followup", authorId: "alex-rivera", body: "The background-star check helps. I’d love to see the same crop with a fixed brightness scale, too.", createdAt: "2026-11-14T16:05:00Z", parentId: null },
  ],
  "betelgeuse-spikes": [
    { id: "spikes-question", authorId: "alex-rivera", body: "Does the cross follow the image orientation rather than the surrounding sky? That could be a useful comparison.", createdAt: "2026-11-13T18:15:00Z", parentId: null },
    { id: "spikes-answer", authorId: "jordan-kim", body: "That’s the check I want to document next, along with the saturated-pixel flags. I’ll keep the reference field attached to the note.", createdAt: "2026-11-13T18:32:00Z", parentId: "spikes-question" },
  ],
  "luhman-notebook": [
    { id: "luhman-question", authorId: "alex-rivera", body: "Could you include the survey’s angular resolution in the comparison? It would help explain why the sources blend together.", createdAt: "2026-11-12T17:00:00Z", parentId: null },
  ],
};
const EMPTY: DiscussionComment[] = [];
const cache = new Map<string, { raw: string | null; comments: DiscussionComment[] }>();
const EVENT = "pulsr-discussion-changed";
const storageKey = (postId: string) => `pulsr:discussion:v1:${postId}`;
const seedFor = (postId: string) => seeds[postId] ?? EMPTY;

function isComment(value: unknown): value is DiscussionComment {
  if (!value || typeof value !== "object") return false;
  const c = value as DiscussionComment;
  return typeof c.id === "string" && typeof c.authorId === "string" && !!getProfile(c.authorId) &&
    typeof c.body === "string" && c.body.trim().length > 0 && c.body.length <= 2000 &&
    typeof c.createdAt === "string" && Number.isFinite(Date.parse(c.createdAt)) &&
    (c.parentId === null || typeof c.parentId === "string");
}

function readComments(postId: string): DiscussionComment[] {
  let raw: string | null;
  try { raw = localStorage.getItem(storageKey(postId)); } catch { return seedFor(postId); }
  const previous = cache.get(postId);
  if (previous?.raw === raw) return previous.comments;
  let comments = seedFor(postId);
  if (raw !== null) {
    try {
      const parsed: unknown = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.every(isComment)) {
        const ids = new Set(parsed.map((comment) => comment.id));
        const roots = new Set(parsed.filter((comment) => comment.parentId === null).map((comment) => comment.id));
        if (ids.size === parsed.length && parsed.every((comment) => comment.parentId === null || roots.has(comment.parentId))) comments = parsed;
      }
    } catch { /* A malformed cache falls back to the sample discussion. */ }
  }
  cache.set(postId, { raw, comments });
  return comments;
}

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(EVENT, callback);
  };
}

export function useDiscussion(postId: string) {
  return useSyncExternalStore(subscribe, () => readComments(postId), () => seedFor(postId));
}

export function addComment(postId: string, body: string, parentId: string | null) {
  if (!observationPosts.some((post) => post.id === postId)) throw new Error("This observation is unavailable.");
  const text = body.trim();
  if (!text || text.length > 2000) throw new Error("Write a comment between 1 and 2,000 characters.");
  const comments = readComments(postId);
  if (parentId && !comments.some((comment) => comment.id === parentId && comment.parentId === null)) throw new Error("This comment is no longer available. Try a new comment instead.");
  const comment: DiscussionComment = {
    id: crypto.randomUUID(), authorId: currentUserId, body: text, parentId, createdAt: new Date().toISOString(),
  };
  const next = [...comments, comment];
  const raw = JSON.stringify(next);
  try { localStorage.setItem(storageKey(postId), raw); }
  catch { throw new Error("Your browser could not save this comment. Your draft is still here; allow site storage and try again."); }
  cache.set(postId, { raw, comments: next });
  window.dispatchEvent(new Event(EVENT));
  return comment;
}
