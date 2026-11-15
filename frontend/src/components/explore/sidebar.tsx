"use client";

import { ScanSearch } from "lucide-react";
import { MotionNotice } from "./motion-notice";
import { MotionPanel } from "./motion-panel";
import { NoSelection, ObjectPanel } from "./object-panel";
import { Collapsible, buttonPrimary } from "./panel-parts";
import { VerifyPanel } from "./verify-panel";
import { useExplore } from "./use-explore";
import { FindingActions } from './finding-actions';

/**
 * One sidebar for every explanation and result. What it shows follows what
 * the user has done (see `sidebarMode` in use-explore.tsx):
 *   none    a hint to drag a box
 *   object  the object panel
 *   motion  motion panel above the object panel, each collapsible
 *   verify  the results panel on its own, with Back
 */
export function Sidebar() {
  const ex = useExplore();
  const mode = ex.sidebarMode;

  return (
    <aside aria-label="Explanations and results" className="flex min-h-0 w-[400px] flex-1 shrink-0 flex-col overflow-hidden rounded-xl border border-line-strong bg-surface">
      {mode === "verify" ? (
        <VerifyPanel />
      ) : (
        <>
          <div className="scroll-pulsr flex min-h-0 flex-1 flex-col overflow-y-auto">
            <div className="flex flex-col gap-3 px-4 pt-4 empty:hidden">
              <MotionNotice />
            </div>
            {mode === "none" && (
              <div className="p-4">
                <NoSelection />
              </div>
            )}
            {mode === "object" && (
              <div className="flex flex-col p-4">
                <ObjectPanel />
              </div>
            )}
            {mode === "motion" && (
              <>
                <Collapsible title="Movement" meta={`${ex.movers.length} found`}>
                  <MotionPanel />
                </Collapsible>
                <Collapsible title="What you selected" defaultOpen={!!ex.box} key={ex.box ? "open" : "closed"}>
                  <ObjectPanel />
                </Collapsible>
              </>
            )}
          </div>

          {ex.box && (
            <footer className="shrink-0 border-t border-line p-4">
              <button type="button" onClick={ex.verify} className={buttonPrimary + " w-full"}>
                <ScanSearch size={16} strokeWidth={1.5} aria-hidden="true" />
                Verify: is it already known?
              </button>
            </footer>
          )}
        </>
      )}
      <FindingActions />
    </aside>
  );
}
