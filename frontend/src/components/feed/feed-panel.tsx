import { Findings } from "./findings";
import { ForYou } from "./for-you";
import { News } from "./news";
import { Popular } from "./popular";

/**
 * The exploration feed: a solid `surface` panel on the page ground, one step
 * lighter than everything around it, with a strong hairline. Cards inside are
 * one step lighter again (`raised`), so there are always two clear edges
 * between the feed and the page, whatever the sky beside it is doing.
 */
export function FeedPanel() {
  return (
    <aside
      aria-label="Where to look"
      className="flex h-full flex-col overflow-hidden rounded-xl border border-line-strong bg-surface"
    >
      <div className="scroll-pulsr flex-1 overflow-y-auto overscroll-contain px-4 pb-8">
        <h2 className="px-1 pb-5 pt-5 text-h2 text-ink">Where to look</h2>
        <div className="flex flex-col gap-10">
          <ForYou />
          <Popular />
          <News />
          <Findings />
        </div>
      </div>
    </aside>
  );
}
