"use client";

import { Check, ChevronDown, Layers } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { useExplore } from "./use-explore";

/**
 * Like the Google Maps layer button: shows the current second sensor, opens a
 * list with a thumbnail and one line each. One at a time, or none.
 */
export function LayerPicker() {
  const { area, layerId, setLayerId } = useExplore();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!area) return null;
  const current = area.layers.find((l) => l.id === layerId && l.coverage.ok);

  return (
    <div ref={ref} className="absolute right-3 top-3 z-[5]">
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((v) => !v)}
        className="flex h-12 cursor-pointer items-center gap-2.5 rounded-lg border border-line-strong bg-ground/90 py-1 pl-1 pr-3 text-small text-ink transition-colors duration-(--dur-feedback) ease-standard hover:bg-raised"
      >
        <Thumb src={current?.thumbnail} />
        <span className="flex flex-col items-start leading-tight">
          <span className="text-caption text-ink-secondary">Compare with</span>
          <span>{current ? current.name : "No layer"}</span>
        </span>
        <ChevronDown size={16} strokeWidth={1.5} aria-hidden="true" className="text-ink-secondary" />
      </button>

      {open && (
        <ul
          role="listbox"
          aria-label="Other sensors"
          className="absolute right-0 top-[calc(100%+8px)] flex w-[340px] flex-col gap-1 rounded-xl border border-line-strong bg-overlay p-2"
        >
          <Option
            selected={!current}
            name="No layer"
            blurb="Just the SPHEREx image."
            onSelect={() => {
              setLayerId(null);
              setOpen(false);
            }}
          />
          {area.layers.map((l) => (
            <Option
              key={l.id}
              selected={current?.id === l.id}
              name={l.name}
              blurb={l.blurb}
              thumb={l.thumbnail}
              disabledReason={l.coverage.ok ? undefined : l.coverage.reason}
              onSelect={() => {
                setLayerId(l.id);
                setOpen(false);
              }}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function Thumb({ src }: { src?: string }) {
  return (
    <span className="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-sm bg-sky text-ink-secondary">
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element -- a survey preview tile from the HiPS mirror
        <img src={src} alt="" className="size-full object-cover brightness-[2.2] contrast-110" loading="lazy" />
      ) : (
        <Layers size={18} strokeWidth={1.5} aria-hidden="true" />
      )}
    </span>
  );
}

function Option({
  selected,
  name,
  blurb,
  thumb,
  disabledReason,
  onSelect,
}: {
  selected: boolean;
  name: string;
  blurb: string;
  thumb?: string;
  disabledReason?: string;
  onSelect: () => void;
}) {
  const disabled = !!disabledReason;
  return (
    <li role="option" aria-selected={selected} aria-disabled={disabled}>
      <button
        type="button"
        disabled={disabled}
        onClick={onSelect}
        className={cn(
          "flex w-full cursor-pointer items-center gap-3 rounded-md p-2 text-left transition-colors duration-(--dur-feedback) ease-standard",
          "disabled:cursor-not-allowed disabled:opacity-60",
          selected ? "bg-raised" : "hover:bg-raised",
        )}
      >
        <Thumb src={thumb} />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-body-sm text-ink">{name}</span>
          <span className="text-small text-ink-secondary">{disabledReason ?? blurb}</span>
        </span>
        {selected && <Check size={16} strokeWidth={1.5} aria-hidden="true" className="shrink-0 text-ink" />}
      </button>
    </li>
  );
}
