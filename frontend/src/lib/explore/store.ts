"use client";

import { useSyncExternalStore } from "react";

/**
 * A tiny external store, for state that changes on every pointer move (the
 * map view). Keeping it out of React context means panning doesn't re-render
 * the sidebar, the band picker and the timeline.
 */
export type Store<T> = {
  get: () => T;
  set: (next: T) => void;
  subscribe: (fn: () => void) => () => void;
};

export function createStore<T>(initial: T): Store<T> {
  let value = initial;
  const subs = new Set<() => void>();
  return {
    get: () => value,
    set(next) {
      if (Object.is(next, value)) return;
      value = next;
      subs.forEach((f) => f());
    },
    subscribe(fn) {
      subs.add(fn);
      return () => subs.delete(fn);
    },
  };
}

export function useStore<T>(store: Store<T>): T {
  return useSyncExternalStore(store.subscribe, store.get, store.get);
}
