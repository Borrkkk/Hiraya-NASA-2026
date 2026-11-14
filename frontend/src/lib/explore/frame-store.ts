"use client";

import type { ExploreApi } from "./api";
import type { BandId } from "./types";

export type FrameState =
  | { status: "loading" }
  | { status: "ready"; bitmap: ImageBitmap }
  | { status: "error"; error: unknown };

const CONCURRENCY = 3;

/**
 * Loads and caches frames (one image per epoch and band) for one area.
 * Bands are blended on a canvas, so toggling one never needs the network.
 * Requests run a few at a time, in the order they are asked for: the page asks
 * for the visible epoch first and the others after, in the background.
 */
export class FrameStore {
  private frames = new Map<string, FrameState>();
  private tinted = new Map<string, HTMLCanvasElement>();
  private queue: { key: string; epochId: string; band: BandId }[] = [];
  private active = 0;
  private subs = new Set<() => void>();
  private version = 0;
  private controller = new AbortController();

  /** Strict Mode runs effects twice: dispose() then this, on the same store. */
  revive() {
    if (this.controller.signal.aborted) this.controller = new AbortController();
  }

  constructor(
    private api: ExploreApi,
    private areaId: string,
  ) {}

  static key = (epochId: string, band: BandId) => `${epochId}|${band}`;

  subscribe = (fn: () => void) => {
    this.subs.add(fn);
    return () => {
      this.subs.delete(fn);
    };
  };
  getVersion = () => this.version;

  get(epochId: string, band: BandId): FrameState | undefined {
    return this.frames.get(FrameStore.key(epochId, band));
  }

  isReady(epochId: string, band: BandId) {
    return this.get(epochId, band)?.status === "ready";
  }

  /** Any frame that failed, so the page can show its error and a Retry. */
  hasError() {
    for (const f of this.frames.values()) if (f.status === "error") return true;
    return false;
  }

  /** Ask for frames. Already requested ones are skipped. Earlier calls go first. */
  request(epochId: string, band: BandId) {
    const key = FrameStore.key(epochId, band);
    if (this.frames.has(key)) return;
    this.frames.set(key, { status: "loading" });
    this.queue.push({ key, epochId, band });
    this.pump();
  }

  /** Re-queue everything that failed. */
  retry() {
    for (const [key, f] of [...this.frames]) {
      if (f.status !== "error") continue;
      const [epochId, band] = key.split("|") as [string, BandId];
      this.frames.delete(key);
      this.request(epochId, band);
    }
    this.emit();
  }

  /** The band's frame as a coloured canvas, ready to add into the blend. */
  tintedFrame(epochId: string, band: BandId, color: string): HTMLCanvasElement | null {
    const f = this.get(epochId, band);
    if (f?.status !== "ready") return null;
    const key = `${FrameStore.key(epochId, band)}|${color}`;
    let c = this.tinted.get(key);
    if (!c) {
      c = document.createElement("canvas");
      c.width = f.bitmap.width;
      c.height = f.bitmap.height;
      const g = c.getContext("2d")!;
      g.drawImage(f.bitmap, 0, 0);
      g.globalCompositeOperation = "multiply";
      g.fillStyle = color;
      g.fillRect(0, 0, c.width, c.height);
      this.tinted.set(key, c);
    }
    return c;
  }

  dispose() {
    this.controller.abort();
    this.queue = [];
    for (const f of this.frames.values()) if (f.status === "ready") f.bitmap.close();
    this.frames.clear();
    this.tinted.clear();
    this.subs.clear();
  }

  private emit() {
    this.version++;
    this.subs.forEach((f) => f());
  }

  private pump() {
    while (this.active < CONCURRENCY && this.queue.length) {
      const job = this.queue.shift()!;
      this.active++;
      this.api
        .fetchFrame(
          { areaId: this.areaId, epochId: job.epochId, band: job.band },
          { signal: this.controller.signal },
        )
        .then((blob) => createImageBitmap(blob))
        .then((bitmap) => {
          if (this.controller.signal.aborted) return bitmap.close();
          this.frames.set(job.key, { status: "ready", bitmap });
        })
        .catch((error) => {
          if (this.controller.signal.aborted) return;
          this.frames.set(job.key, { status: "error", error });
        })
        .finally(() => {
          this.active--;
          if (!this.controller.signal.aborted) {
            this.emit();
            this.pump();
          }
        });
    }
  }
}
