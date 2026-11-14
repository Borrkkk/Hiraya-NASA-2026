import { FeedPanel } from "@/components/feed/feed-panel";
import { HomeHeader } from "@/components/home/header";
import { SkyBackdrop, SkyHint } from "@/components/home/sky-backdrop";

/**
 * Home: a full-bleed infrared sky with the exploration feed on top.
 *
 * The sky stage is wider (or taller on phones) than the screen and shifted so
 * its centre lands in the free part of the screen, not behind the feed. That
 * keeps the reticle, and whatever the tour is showing, in view.
 */
export default function Home() {
  return (
    <div className="relative h-dvh overflow-hidden bg-sky">
      <SkyBackdrop className="absolute max-lg:inset-x-0 max-lg:-top-[56dvh] max-lg:bottom-0 lg:inset-y-0 lg:right-0 lg:left-[calc(var(--feed-w)*-1)]" />
      <SkyHint className="absolute bottom-6 left-6 z-10 max-lg:hidden" />
      <HomeHeader />
      <main>
        <FeedPanel />
      </main>
    </div>
  );
}
