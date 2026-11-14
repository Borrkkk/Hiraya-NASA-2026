import Link from "next/link";
import { SkySearch } from "@/components/search/sky-search";
import { Avatar, Logo } from "@/components/ui";

/**
 * Logo, search, and who you are. A solid bar on the page ground, never over
 * the sky, so the search box is always in the same place on the same colour.
 */
export function HomeHeader() {
  return (
    <header className="relative z-30 flex h-[72px] shrink-0 items-center gap-3 px-4 sm:gap-6 sm:px-6">
      <Link href="/" aria-label="Pulsr home" className="rounded-xs">
        {/* Mark only on phones so the search gets the room. */}
        <Logo size={22} className="max-sm:[&>span:last-child]:hidden" />
      </Link>

      <SkySearch className="w-full max-w-[560px] flex-1" />

      <div className="ml-auto flex items-center gap-3">
        <span className="hidden font-mono text-mono tabular-nums text-ink-secondary lg:block">
          1,240 pts
        </span>
        <Avatar initials="AR" tone={1} />
      </div>
    </header>
  );
}
