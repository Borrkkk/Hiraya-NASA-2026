import { ArrowLeft, Telescope } from "lucide-react";
import Link from "next/link";
import { HomeHeader } from "@/components/home/header";
import { PREVIEW_NAME, previewHref } from "@/lib/explore/preview-region";

/**
 * Shown instead of Explore when someone asks for any other part of the sky.
 * The preview ships data for one region only, so it says so and offers it.
 */
export function PreviewLimit({ name }: { name: string | null }) {
  return (
    <div className="min-h-dvh bg-ground">
      <HomeHeader />
      <main className="mx-auto flex max-w-xl flex-col items-center gap-6 px-6 py-16 text-center sm:py-24">
        <span aria-hidden="true" className="flex size-14 items-center justify-center rounded-full border border-line-strong bg-raised text-ink-secondary">
          <Telescope size={26} strokeWidth={1.25} />
        </span>
        <div className="flex flex-col gap-3">
          <h1 className="text-h1 text-ink">
            {name ? `${name} isn’t open in this preview` : "That part of the sky isn’t open yet"}
          </h1>
          <p className="text-body text-ink-secondary">
            We currently don’t support access to other objects. In this limited preview you can explore one region in depth:{" "}
            <strong className="font-medium text-ink">{PREVIEW_NAME}</strong> and the sky around it. You can still browse the whole sky on the home page.
          </p>
        </div>
        <div className="flex flex-col items-center gap-3 sm:flex-row">
          <Link
            href={previewHref()}
            className="inline-flex h-12 items-center justify-center gap-2 rounded-md bg-primary px-6 text-body-sm font-medium text-on-primary transition-opacity hover:opacity-90"
          >
            Open the {PREVIEW_NAME} region
          </Link>
          <Link href="/" className="inline-flex h-12 items-center gap-2 rounded-md px-4 text-body-sm text-ink-secondary hover:text-ink">
            <ArrowLeft size={16} strokeWidth={1.5} aria-hidden="true" />
            Back to the sky
          </Link>
        </div>
      </main>
    </div>
  );
}
