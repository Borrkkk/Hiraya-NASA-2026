"use client";

import { Play } from "lucide-react";
import { tour } from "./tour-store";

/** Header button that (re)starts the guided demo. Desktop only. */
export function TourLauncher() {
  return (
    <button
      type="button"
      onClick={tour.start}
      className="hidden h-10 cursor-pointer items-center gap-2 rounded-md border border-line-strong px-3 text-small text-ink transition-colors duration-(--dur-feedback) ease-standard hover:bg-raised lg:inline-flex"
    >
      <Play size={14} strokeWidth={1.75} aria-hidden="true" />
      Guided demo
    </button>
  );
}
