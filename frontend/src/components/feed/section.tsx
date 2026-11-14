/** A feed section: a short title and one line on why these are here. */
export function FeedSection({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <header className="px-1">
        <h3 className="text-body font-medium text-ink">{title}</h3>
        {subtitle && <p className="text-small text-ink-secondary">{subtitle}</p>}
      </header>
      {children}
    </section>
  );
}
