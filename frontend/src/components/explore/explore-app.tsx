"use client";

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
  return (
    <ExploreProvider>
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
