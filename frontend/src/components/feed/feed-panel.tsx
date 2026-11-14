import { Findings } from "./findings";
import { ForYou } from "./for-you";
import { News } from "./news";
import { Popular } from "./popular";

/**
 * The exploration feed. A solid panel over the map: on desktop a column on the
 * right, on phones a sheet over the lower part of the screen. Depth comes from
 * the surface step and a hairline, never a shadow or blur.
 */
export function FeedPanel() {
  return (
    <aside
      aria-label="Where to look"
      className="absolute z-20 flex flex-col overflow-hidden border border-line bg-ground max-lg:inset-x-0 max-lg:bottom-0 max-lg:h-[56dvh] max-lg:rounded-t-xl max-lg:border-b-0 lg:bottom-6 lg:right-6 lg:top-[72px] lg:w-[440px] lg:rounded-xl"
    >
      <div className="scroll-pulsr flex-1 overflow-y-auto overscroll-contain px-4 pb-8">
        <header className="px-1 pb-5 pt-5">
          <h2 className="text-h2 text-ink">Where to look</h2>
          <p className="text-body-sm text-ink-secondary">
            Start anywhere. Every patch here is real sky.
          </p>
        </header>
        <div className="flex flex-col gap-8">
          <ForYou />
          <Popular />
          <News />
          <Findings />
        </div>
      </div>
    </aside>
  );
}
