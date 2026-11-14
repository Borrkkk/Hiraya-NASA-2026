/** A feed section: a short title, and at most a few words of meta on the right. */
export function FeedSection({
  title,
  meta,
  children,
}: {
  title: string;
  meta?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <header className="flex items-baseline justify-between gap-4 px-1">
        <h3 className="text-body font-medium text-ink">{title}</h3>
        {meta && <p className="text-small text-ink-muted">{meta}</p>}
      </header>
      {children}
    </section>
  );
}
