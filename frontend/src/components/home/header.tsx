import Link from "next/link";
import { SkySearch } from "@/components/search/sky-search";
import { Avatar, Logo } from "@/components/ui";

/**
 * Logo, search, and who you are. It floats over the sky: the wrapper ignores
 * pointer events so the map stays draggable underneath, and only the controls
 * take clicks.
 */
export function HomeHeader() {
  return (
    <header className="pointer-events-none absolute inset-x-0 top-0 z-30 flex h-[72px] items-center gap-3 px-4 sm:gap-6 sm:px-6">
      <Link
        href="/"
        aria-label="Pulsr home"
        className="pointer-events-auto rounded-xs"
      >
        {/* Mark only on phones so the search gets the room. */}
        <Logo size={22} className="max-sm:[&>span:last-child]:hidden" />
      </Link>

      <SkySearch className="pointer-events-auto w-full max-w-[560px] flex-1" />

      <div className="pointer-events-auto ml-auto flex items-center gap-3">
        <span className="hidden font-mono text-mono tabular-nums text-ink-secondary lg:block">
          1,240 pts
        </span>
        <Avatar initials="AR" tone={1} />
      </div>
    </header>
  );
}
