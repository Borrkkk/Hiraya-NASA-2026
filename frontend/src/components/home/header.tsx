import Link from "next/link";
import { SkySearch } from "@/components/search/sky-search";
import { Avatar, Logo } from "@/components/ui";
import { currentUserId, getProfile, profileHref } from "@/lib/profiles";
import { ThemeToggle } from "@/components/ui/theme-toggle";

/**
 * Logo, search, and who you are. A solid bar on the page ground, never over
 * the sky, so the search box is always in the same place on the same colour.
 */
export function HomeHeader() {
  const currentUser = getProfile(currentUserId)!;
  return (
    <header className="relative z-30 flex h-[72px] shrink-0 items-center gap-3 px-4 sm:gap-6 sm:px-6">
      <Link href="/" aria-label="Hiraya home" className="rounded-xs">
        {/* Mark only on phones so the search gets the room. */}
        <Logo size={22} className="max-sm:[&>span:last-child]:hidden" />
      </Link>

      <SkySearch className="min-w-0 w-full max-w-[560px] flex-1" />

      <div className="ml-auto flex items-center gap-3">
        <Link href="/discussions" className="hidden h-10 items-center rounded-md px-3 text-small text-ink-secondary transition-colors duration-(--dur-feedback) ease-standard hover:bg-raised hover:text-ink sm:inline-flex">
          Discussions
        </Link>
        <ThemeToggle />
        <span className="hidden font-mono text-mono tabular-nums text-ink-secondary lg:block">
          1,240 pts
        </span>
        <Link href={profileHref(currentUser.id)} aria-label="View your profile" className="shrink-0 rounded-full"><Avatar initials={currentUser.initials} tone={currentUser.tone} /></Link>
      </div>
    </header>
  );
}
