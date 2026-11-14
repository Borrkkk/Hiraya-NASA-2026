import { FeedPanel } from "@/components/feed/feed-panel";
import { HomeHeader } from "@/components/home/header";
import { SkyBackdrop, SkyHint } from "@/components/home/sky-backdrop";

/**
 * Home: the interface sits on flat ground and the sky is a framed window.
 *
 * The sky ranges from near-black to blazing orange, so nothing laid over it
 * can reliably stand out: a dark panel vanishes on dark sky, and a vivid sky
 * swamps a light one. Putting the header and feed on solid ground, with the
 * sky as its own window beside them, makes them easy to find whatever the sky
 * is showing, and lets the sky be as bright as it likes.
 *
 * Phones stack: header, a short sky window, then the feed filling the rest.
 */
export default function Home() {
  return (
    <div className="flex h-dvh flex-col bg-ground">
      <HomeHeader />
      <div className="flex min-h-0 flex-1 flex-col gap-4 px-4 pb-4 sm:px-6 sm:pb-6 lg:flex-row">
        <div className="relative h-[38dvh] shrink-0 overflow-hidden rounded-xl border border-line-strong bg-sky lg:h-auto lg:min-w-0 lg:flex-1">
          <SkyBackdrop className="absolute inset-0" />
          <SkyHint className="absolute bottom-4 left-4 z-10 max-lg:hidden" />
        </div>
        <main className="min-h-0 flex-1 lg:w-[440px] lg:flex-none">
          <FeedPanel />
        </main>
      </div>
    </div>
  );
}
