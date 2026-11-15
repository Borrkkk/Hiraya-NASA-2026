import Link from "next/link";

export default function ProfileNotFound() {
  return <main className="mx-auto flex min-h-dvh max-w-xl flex-col justify-center gap-4 px-6">
    <h1 className="text-h2">Profile not found</h1>
    <p className="text-body text-ink-secondary">This observer does not have a profile here.</p>
    <Link href="/" className="w-fit rounded-sm text-small text-ember">Back to the sky →</Link>
  </main>;
}
