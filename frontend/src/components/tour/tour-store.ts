"use client";

import { useSyncExternalStore } from "react";

// Which step of the guided demo someone is on. It survives page changes within
// the tab (sessionStorage), because the tour walks across several pages.
const KEY = "hiraya:tour:v1";
const SEEN = "hiraya:tour:seen";
const listeners = new Set<() => void>();
let memory: number | null = null;

function read(): number | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (raw === null) return memory;
    const n = Number(raw);
    return Number.isInteger(n) && n >= 0 ? n : null;
  } catch {
    return memory;
  }
}

function write(step: number | null) {
  memory = step;
  try {
    if (step === null) sessionStorage.removeItem(KEY);
    else sessionStorage.setItem(KEY, String(step));
  } catch {
    /* in-memory only */
  }
  listeners.forEach((l) => l());
}

export const tour = {
  start: () => {
    markSeen();
    write(0);
  },
  go: (step: number) => write(step),
  stop: () => write(null),
};

export function markSeen() {
  try {
    localStorage.setItem(SEEN, "1");
  } catch {
    /* ignore */
  }
  listeners.forEach((l) => l());
}
export const hasSeen = () => {
  try {
    return localStorage.getItem(SEEN) === "1";
  } catch {
    return true;
  }
};

const subscribe = (cb: () => void) => {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
};

/** The current step index, or null when the tour isn't running. */
export const useTourStep = () => useSyncExternalStore(subscribe, read, () => null);
export const useTourSeen = () => useSyncExternalStore(subscribe, hasSeen, () => true);
