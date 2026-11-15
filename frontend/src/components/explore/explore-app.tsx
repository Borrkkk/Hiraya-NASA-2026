"use client";

import { useSearchParams } from "next/navigation";

import { BandPicker } from "./band-picker";
import { FovControl } from "./fov-control";
import { Sidebar } from "./sidebar";
import { SkyView } from "./sky-view";
import { Timeline } from "./timeline";
import { TopBar } from "./top-bar";
import { ExploreProvider } from "./use-explore";

/**
 * The Explore page, desktop only. The sky view fills the screen; controls
 * sit around it; one sidebar on the right holds every explanation and result.
 * All data comes through useExplore(), which talks to `exploreApi`
 * (lib/explore). See docs/explore-backend-integration.md.
 */
export function ExploreApp() {
  const search = useSearchParams();
  // Next.js may reuse this page component when navigating from one Explore
  // link to another. Remount the controller only when the DATA target changes,
  // never on a pan/zoom or a timeline change.
  const targetKey = [
    search.get("ra") ?? "",
    search.get("dec") ?? "",
    search.get("fov") ?? "",
    search.get("q") ?? "",
  ].join("|");
  return (
    <ExploreProvider key={targetKey}>
      <Layout />
    </ExploreProvider>
  );
}

function Layout() {
  return (
    <div className="flex h-dvh min-w-[1100px] gap-4 bg-ground p-4">
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <TopBar />
        <div className="flex min-h-0 flex-1 gap-3">
          <BandPicker />
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <SkyView />
            <div className="flex h-14 shrink-0 items-center justify-end px-1">
              <FovControl />
            </div>
          </div>
        </div>
        <Timeline />
      </div>
      <div className="flex min-h-0 flex-col">
        <Sidebar />
      </div>
    </div>
  );
}
