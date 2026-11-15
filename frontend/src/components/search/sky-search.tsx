"use client";

import { useQuery } from "@tanstack/react-query";
import { Search, SlidersHorizontal } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Chip } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { exploreHref } from "@/lib/explore/href";
import { CATALOG, KINDS, kindLabel, searchCatalog, type ObjectKind } from "@/lib/sky/catalog";
import { parseCoordinates } from "@/lib/sky/coordinates";
import { formatCoords } from "@/lib/sky/format";

type Option = {
  key: string;
  primary: string;
  secondary: string;
  /** Mono text on the right, e.g. coordinates. */
  trailing?: string;
  href: string;
};

/** A place from the backend's search: a saved SPHEREx target, or a SIMBAD name when it's online. */
type Hit = {
  id: string;
  name: string;
  ra: number;
  dec: number;
  kind: string;
  blurb: string | null;
  images: boolean;
  source: "spherex" | "simbad";
};

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

const normName = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

/**
 * Search the sky by name or by coordinates, in whatever format people type
 * them. Object-type filters expand under the box. Nothing here talks to an API
 * yet: names resolve against a small local catalogue, and every choice ends in
 * a link to exploration mode.
 */
export function SkySearch({ className }: { className?: string }) {
  const router = useRouter();
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const filtersId = useId();

  const [value, setValue] = useState("");
  const [open, setOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [kinds, setKinds] = useState<ObjectKind[]>([]);
  const [active, setActive] = useState(0);

  const text = value.trim();
  const coords = useMemo(() => parseCoordinates(value), [value]);

  // Places that really have SPHEREx data (and SIMBAD names, when the backend is online).
  const debounced = useDebounced(text, 200);
  const hitsQuery = useQuery({
    queryKey: ["explore-search", debounced],
    queryFn: ({ signal }) => api<{ results: Hit[] }>(`/explore/search?q=${encodeURIComponent(debounced)}`, { signal }),
    enabled: !parseCoordinates(debounced),
    staleTime: 60_000,
    retry: 0,
  });
  const hits = useMemo(() => (kinds.length ? [] : (hitsQuery.data?.results ?? [])), [hitsQuery.data, kinds]);

  const options = useMemo<Option[]>(() => {
    const out: Option[] = [];
    if (coords) {
      out.push({
        key: "coords",
        primary: "Go to these coordinates",
        secondary: "Right ascension and declination",
        trailing: formatCoords(coords.ra, coords.dec),
        href: exploreHref({ ra: coords.ra, dec: coords.dec, fov: 1 }),
      });
      return out;
    }
    for (const h of hits) {
      // Known recommendations use the same coordinates as their feed cards
      // and prewarmed demo cache, rather than a second saved target position.
      const known = CATALOG.find((o) => o.id === h.id || normName(o.name) === normName(h.name));
      out.push({
        key: `hit-${h.id}`,
        primary: h.name,
        secondary: [h.kind, h.images ? "SPHEREx images ready" : h.source === "spherex" ? "Observation records only" : "From SIMBAD"].join(" · "),
        trailing: formatCoords(h.ra, h.dec),
        // The saved images are about a tenth of a degree wide: open with some sky around them.
        href: exploreHref({ q: h.name, ra: known?.ra ?? h.ra, dec: known?.dec ?? h.dec, fov: 0.25 }),
      });
    }
    const taken = new Set(hits.map((h) => normName(h.name)));
    for (const o of searchCatalog(value, kinds).filter((c) => !taken.has(normName(c.name)))) {
      out.push({
        key: o.id,
        primary: o.name,
        secondary: [kindLabel(o.kind), o.where].filter(Boolean).join(" · "),
        trailing: o.ra !== undefined && o.dec !== undefined ? formatCoords(o.ra, o.dec) : "Moving object",
        href: exploreHref({ q: o.name, ra: o.ra, dec: o.dec, fov: o.fov, types: kinds }),
      });
    }
    if (text) {
      out.push({
        key: "text",
        primary: `Search for “${text}”`,
        secondary: "Look it up across the catalogues",
        href: exploreHref({ q: text, types: kinds }),
      });
    }
    return out;
  }, [coords, value, kinds, text, hits]);

  // The highlighted row resets to the top whenever the input or filters change
  // (see onChange and toggleKind), and is clamped here if the list shrinks.
  const activeIndex = Math.min(active, Math.max(options.length - 1, 0));

  // Close when focus or a click moves outside the search.
  useEffect(() => {
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  // "/" jumps to search, like most sites people already know.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable)) return;
      e.preventDefault();
      inputRef.current?.focus();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const go = (href: string) => {
    setOpen(false);
    inputRef.current?.blur();
    router.push(href);
  };

  const submit = () => {
    const chosen = options[activeIndex] ?? options[0];
    if (chosen) go(chosen.href);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setOpen(true);
      if (options.length) {
        const step = e.key === "ArrowDown" ? 1 : -1;
        setActive((activeIndex + step + options.length) % options.length);
      }
    } else if (e.key === "Enter") {
      e.preventDefault();
      submit();
    } else if (e.key === "Escape") {
      if (open) setOpen(false);
      else inputRef.current?.blur();
    }
  };

  const toggleKind = (k: ObjectKind) => {
    setKinds((cur) => (cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k]));
    setActive(0);
  };

  const showList = open && options.length > 0;
  const heading = coords ? "Coordinates" : text ? "Matches" : "Try";

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      {/* `raised` with the strong hairline, so the box is clearly lighter than
          the ground it sits on. ink-muted only passes on ground and surface, so
          raised uses secondary. */}
      <div className="flex h-11 items-center gap-2.5 rounded-md border border-line-strong bg-raised pl-3 pr-1 text-ink-secondary focus-within:shadow-focus">
        <Search size={16} strokeWidth={1.5} aria-hidden="true" className="shrink-0" />
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList ? `${listId}-${activeIndex}` : undefined}
          aria-label="Search the sky by name or coordinates"
          placeholder="Name or coordinates"
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setActive(0);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className="min-w-0 flex-1 bg-transparent text-body-sm text-ink shadow-none outline-none placeholder:text-ink-secondary"
        />
        <kbd
          aria-hidden="true"
          className="hidden rounded-xs border border-line-strong px-1.5 py-0.5 font-mono text-mono-sm text-ink-secondary sm:block"
        >
          /
        </kbd>
        <button
          type="button"
          aria-label="Filters"
          aria-expanded={filtersOpen}
          aria-controls={filtersId}
          onClick={() => {
            setFiltersOpen((v) => !v);
            setOpen(true);
          }}
          className={cn(
            "relative inline-flex h-10 shrink-0 cursor-pointer items-center justify-center gap-2 rounded-sm px-2.5 text-small",
            "transition-colors duration-(--dur-feedback) ease-standard",
            filtersOpen || kinds.length
              ? "bg-ember-wash text-ink"
              : "text-ink-secondary hover:bg-overlay hover:text-ink",
          )}
        >
          <SlidersHorizontal size={16} strokeWidth={1.5} aria-hidden="true" />
          <span className="hidden sm:inline">Filters</span>
          {kinds.length > 0 && (
            <span className="font-mono text-mono-sm tabular-nums">{kinds.length}</span>
          )}
        </button>
      </div>

      {open && (filtersOpen || showList) && (
        <div className="absolute inset-x-0 top-[calc(100%+8px)] z-40 flex flex-col overflow-hidden rounded-xl border border-line-strong bg-overlay">
          {filtersOpen && (
            <div id={filtersId} className="flex flex-col gap-3 border-b border-line p-4">
              <div className="flex items-baseline justify-between">
                <p className="text-small text-ink-secondary">Show only</p>
                {kinds.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setKinds([])}
                    className="cursor-pointer rounded-xs text-small text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
                  >
                    Clear
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {KINDS.map((k) => (
                  <Chip key={k.id} selected={kinds.includes(k.id)} onClick={() => toggleKind(k.id)}>
                    {k.label}
                  </Chip>
                ))}
              </div>
            </div>
          )}

          {showList && (
            <div className="p-2">
              <p className="px-3 pb-1 pt-2 text-caption text-ink-secondary">{heading}</p>
              <ul id={listId} role="listbox" aria-label={heading} className="flex flex-col">
                {options.map((o, i) => (
                  <li
                    key={o.key}
                    id={`${listId}-${i}`}
                    role="option"
                    aria-selected={i === activeIndex}
                    // mousedown, not click, so the input keeps focus.
                    onMouseDown={(e) => {
                      e.preventDefault();
                      go(o.href);
                    }}
                    onMouseEnter={() => setActive(i)}
                    className={cn(
                      "flex min-h-12 cursor-pointer items-center justify-between gap-4 rounded-md px-3 py-2",
                      i === activeIndex && "bg-raised",
                    )}
                  >
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate text-body-sm text-ink">{o.primary}</span>
                      <span className="truncate text-small text-ink-secondary">{o.secondary}</span>
                    </span>
                    {o.trailing && (
                      <span className="hidden shrink-0 font-mono text-mono-sm tabular-nums text-ink-secondary sm:block">
                        {o.trailing}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
