import { ArrowLeft, Monitor } from "lucide-react";
import Link from "next/link";
import { HomeHeader } from "@/components/home/header";

/** What Explore shows on a phone or a small window. */
export function DesktopOnly() {
  return (
    <div className="min-h-dvh bg-ground">
      <HomeHeader />
      <main className="mx-auto flex max-w-md flex-col gap-6 px-6 pb-16 pt-8 text-center">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/demo/explore-preview.jpg"
          alt="The Explore page: a map of Barnard's Star with a timeline underneath and results on the right."
          className="w-full rounded-xl border border-line-strong bg-sky"
        />
        <div className="flex flex-col items-center gap-3">
          <span aria-hidden="true" className="flex size-11 items-center justify-center rounded-full border border-line-strong bg-raised text-ink-secondary">
            <Monitor size={20} strokeWidth={1.5} />
          </span>
          <h1 className="text-h2 text-ink">Explore needs a bigger screen</h1>
          <p className="text-body-sm text-ink-secondary">
            Drawing boxes on the sky, scrubbing the timeline and reading results side by side takes room. Open Hiraya on a laptop or desktop
            to try it. On this device you can still browse the sky and read the discussions.
          </p>
        </div>
        <div className="flex flex-col gap-3">
          <Link href="/discussions" className="inline-flex h-12 items-center justify-center rounded-md bg-primary px-6 text-body-sm font-medium text-on-primary">
            Read the discussions
          </Link>
          <Link href="/" className="inline-flex h-12 items-center justify-center gap-2 rounded-md text-body-sm text-ink-secondary hover:text-ink">
            <ArrowLeft size={16} strokeWidth={1.5} aria-hidden="true" />
            Back to the sky
          </Link>
        </div>
      </main>
    </div>
  );
}
