import Link from "next/link";
import { ArrowLeft, ArrowUpRight, BadgeCheck, BookOpen, CalendarDays, GraduationCap, Telescope } from "lucide-react";
import { Avatar, Logo } from "@/components/ui";
import { ProfilePosts } from "@/components/profile/observation-posts";
import { observationPosts, profiles, profileHref, type UserProfile } from "@/lib/profiles";
import { ThemeToggle } from "@/components/ui/theme-toggle";

export function ProfileScreen({ profile }: { profile: UserProfile }) {
  const posts = observationPosts.filter((post) => post.authorId === profile.id);
  const explained = posts.filter((post) => post.verdict === "explained").length;
  const open = posts.filter((post) => post.verdict === "unexplained").length;
  return (
    <main className="mx-auto w-full max-w-[1200px] px-4 pb-16 sm:px-8">
      <header className="flex h-[88px] items-center justify-between border-b border-line">
        <Link href="/" aria-label="Pulsr home"><Logo /></Link>
        <div className="flex items-center gap-4"><ThemeToggle /><Link href="/" className="inline-flex items-center gap-2 text-small text-ink-secondary transition-colors hover:text-ink">
          <ArrowLeft size={16} aria-hidden="true" /> Back to the sky
        </Link></div>
      </header>

      <div className="flex items-center gap-2 pt-7 font-mono text-mono-sm uppercase tracking-[0.14em] text-ink-muted">
        <span className="size-1.5 rounded-full bg-ember" aria-hidden="true" /> The people behind the observations
      </div>
      <section className="border-b border-line pb-8 pt-7 sm:pb-10" aria-labelledby="profile-name">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:gap-6">
          <Avatar initials={profile.initials} tone={profile.tone} className="size-20 text-[26px] sm:size-24 sm:text-[30px]" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <h1 id="profile-name" className="text-h2 sm:text-h1">{profile.name}</h1>
              {profile.verified && <span className="inline-flex items-center gap-1.5 rounded-md border border-explained/25 bg-explained/10 px-2.5 py-1 text-caption text-explained">
                <BadgeCheck size={15} aria-hidden="true" /> Verified researcher
              </span>}
            </div>
            <p className="mt-1 font-mono text-mono text-ink-muted">@{profile.handle}</p>
            <p className="mt-4 max-w-2xl text-body text-ink-secondary">
              {profile.bio}
            </p>
            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-small text-ink-secondary">
              <span className="inline-flex items-center gap-2"><GraduationCap size={16} aria-hidden="true" /> {profile.role}</span>
              <span className="inline-flex items-center gap-2"><CalendarDays size={15} aria-hidden="true" /> Joined {profile.joined}</span>
            </div>
          </div>
          <Link href="/explore" className="inline-flex min-h-11 w-fit items-center gap-2 rounded-md bg-primary px-4 text-small font-medium text-on-primary transition-colors hover:bg-primary-hover">
            <Telescope size={16} aria-hidden="true" /> Explore the sky <ArrowUpRight size={15} aria-hidden="true" />
          </Link>
        </div>
        <div className="mt-8 flex flex-wrap gap-x-8 gap-y-4 sm:pl-[120px]">
          {[[posts.length, "Observations"], [explained, "Explained"], [open, "Open questions"]].map(([value, label]) => (
            <div key={label} className="flex items-baseline gap-2">
              <span className="font-mono text-h3 tabular-nums text-ink">{value}</span>
              <span className="text-small text-ink-secondary">{label}</span>
            </div>
          ))}
        </div>
      </section>

      <div className="grid items-start gap-8 pt-8 lg:grid-cols-[minmax(0,1fr)_280px] lg:gap-10">
        <ProfilePosts key={profile.id} profile={profile} posts={posts} />
        <aside className="flex flex-col gap-6 lg:sticky lg:top-6" aria-label="About this observer">
          <section className="rounded-lg border border-line bg-surface p-5">
            <h2 className="flex items-center gap-2 text-body font-medium"><BookOpen size={16} className="text-ink-secondary" aria-hidden="true" /> Research notebook</h2>
            <p className="mt-3 text-small text-ink-secondary">{profile.notebook}</p>
            <h3 className="mt-5 text-caption text-ink-muted">Areas of interest</h3>
            <ul className="mt-2 flex flex-wrap gap-2">
              {profile.interests.map((topic) => <li key={topic} className="rounded-sm border border-line-strong px-2 py-1 text-caption text-ink-secondary">{topic}</li>)}
            </ul>
          </section>
          <section className="border-t border-line pt-5">
            <h2 className="flex items-center gap-2 text-small font-medium text-explained"><BadgeCheck size={16} aria-hidden="true" /> About verification</h2>
            <p className="mt-2 text-small text-ink-secondary">A researcher badge identifies an account. Individual observations still need evidence and review.</p>
          </section>
          <section className="border-t border-line pt-5">
            <h2 className="mb-4 text-small font-medium">More sky observers</h2>
            <ul className="space-y-4">{profiles.filter((person) => person.id !== profile.id).map((person) => <li key={person.id}>
              <Link href={profileHref(person.id)} className="flex items-center gap-3 rounded-md text-small hover:text-ember">
                <Avatar initials={person.initials} tone={person.tone} />
                <span><span className="flex items-center gap-1.5">{person.name}{person.verified && <BadgeCheck size={14} className="text-explained" aria-label="Verified researcher" />}</span><span className="block text-caption text-ink-secondary">{person.role}</span></span>
              </Link>
            </li>)}</ul>
          </section>
          <p className="text-caption text-ink-muted">Sample profile. These accounts, researcher badges, and all posts shown here are fictional preview content. Sky images are real WISE reference cutouts.</p>
        </aside>
      </div>
    </main>
  );
}
