"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { NoDataError, exploreApi, usingMockData, type Area, type BandId, type Inspection, type MotionResult, type Mover, type SkyBox, type VerifyOutcome } from "@/lib/explore";
import { BANDS } from "@/lib/explore/bands";
import { FrameStore } from "@/lib/explore/frame-store";
import { awardPoints } from "@/lib/explore/points";
import { clampView, offsetDeg, type View } from "@/lib/explore/projection";
import { openShare } from "@/lib/explore/share";
import { createStore, type Store } from "@/lib/explore/store";
import { readParams, writeParams } from "@/lib/explore/url-state";
import { fovLimits } from "@/lib/explore/fov";
import { clamp } from "@/lib/explore/projection";

export type MotionState =
  | { status: "idle" }
  | { status: "running"; step: string }
  | { status: "done"; result: MotionResult; range: [number, number] }
  | { status: "failed"; error: string };

export type VerifyState =
  | { status: "idle" }
  | { status: "running"; step: string }
  | { status: "done"; result: VerifyOutcome; points: number }
  | { status: "failed"; error: string };

export type SidebarMode = "none" | "object" | "motion" | "verify";
export type DataStatus = "loading" | "ready" | "error";

type Size = { w: number; h: number };

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function useController() {
  const search = useSearchParams();
  // Read once: the page owns the URL after load.
  const params = useMemo(() => readParams(new URLSearchParams(search.toString())), []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- the area
  const areaQuery = useQuery({
    queryKey: ["explore-area", params.target],
    queryFn: ({ signal }) => exploreApi.getArea(params.target, { signal }),
    // "Nothing saved here" won't change on a retry.
    retry: (count, error) => !(error instanceof NoDataError) && count < 1,
  });
  const area: Area | undefined = areaQuery.data;

  // ---- the view (a store, so panning doesn't re-render the page)
  const [viewStore] = useState<Store<View>>(() => createStore<View>(params.target));
  const [sizeStore] = useState<Store<Size>>(() => createStore<Size>({ w: 1000, h: 600 }));

  const limits = useMemo(
    () => (area ? fovLimits(area, sizeStore.get().w) : null),
    [area, sizeStore],
  );
  const size = useSyncExternalStore(sizeStore.subscribe, sizeStore.get, sizeStore.get);
  const liveLimits = useMemo(() => (area ? fovLimits(area, size.w) : null), [area, size.w]);

  const normalizeView = useCallback(
    (v: View): View => {
      if (!area) return v;
      const l = fovLimits(area, sizeStore.get().w);
      return clampView({ ...v, fov: clamp(v.fov, l.min, l.max) }, area);
    },
    [area, sizeStore],
  );
  const setView = useCallback(
    (v: View) => viewStore.set(normalizeView(v)),
    [normalizeView, viewStore],
  );

  // ---- frames
  const frames = useMemo(() => (area ? new FrameStore(exploreApi, area.id) : null), [area]);
  useEffect(() => {
    frames?.revive();
    return () => frames?.dispose();
  }, [frames]);
  const frameVersion = useSyncExternalStore(
    frames?.subscribe ?? noopSubscribe,
    frames?.getVersion ?? zero,
    zero,
  );

  // ---- user choices
  const [bandsOn, setBandsOn] = useState<BandId[]>(params.bands);
  // Kept as ids, not positions, because the list of observations changes when bands do.
  const [playheadId, setPlayheadId] = useState<string | null>(null);
  const [rangeIds, setRangeIds] = useState<[string, string] | null>(null);
  const [playing, setPlaying] = useState(false);
  const [layerId, setLayerId] = useState<string | null>(params.layer);
  const [curtain, setCurtain] = useState(0.5);
  const [mode, setMode] = useState<"move" | "select">("move");
  const [box, setBoxState] = useState<SkyBox | null>(null);
  const [moverId, setMoverId] = useState<string | null>(null);
  // Each SPHEREx exposure sees a spot at one wavelength, so a spectrum needs them combined.
  const [allEpochs, setAllEpochs] = useState(true);
  const [motion, setMotion] = useState<MotionState>({ status: "idle" });
  const [verifyState, setVerify] = useState<VerifyState>({ status: "idle" });

  // ---- bands and observations
  const everyEpoch = useMemo(
    () => (area ? [...area.epochs].sort((a, b) => Date.parse(a.date) - Date.parse(b.date)) : []),
    [area],
  );
  const bandStatus = useCallback(
    (id: BandId) => area?.bands.find((b) => b.id === id),
    [area],
  );
  const seenTogether = useCallback(
    (bands: BandId[]) => everyEpoch.some((e) => !e.bands || bands.every((b) => e.bands!.includes(b))),
    [everyEpoch],
  );
  const activeBands = useMemo(() => {
    if (!area) return bandsOn;
    const ok = bandsOn.filter((b) => bandStatus(b)?.state !== "no-coverage");
    const first = BANDS.find((b) => bandStatus(b.id)?.state !== "no-coverage");
    const picked = ok.length ? ok : first ? [first.id] : [];
    // Bands that are never seen in the same observation can't be shown together.
    return seenTogether(picked) ? picked : picked.slice(0, 1);
  }, [area, bandsOn, bandStatus, seenTogether]);

  // Only observations that have EVERY band that is on. Fewer bands, more observations.
  const epochs = useMemo(
    () => everyEpoch.filter((e) => !e.bands || activeBands.every((b) => e.bands!.includes(b))),
    [everyEpoch, activeBands],
  );
  const lastIdx = Math.max(0, epochs.length - 1);
  const idxOf = useCallback(
    (id: string | null) => {
      if (!id || !epochs.length) return -1;
      const exact = epochs.findIndex((e) => e.id === id);
      if (exact >= 0) return exact;
      // The observation dropped out (a band was added): take the nearest one in time.
      const when = Date.parse(everyEpoch.find((e) => e.id === id)?.date ?? "");
      if (!Number.isFinite(when)) return -1;
      let best = 0;
      epochs.forEach((e, i) => {
        if (Math.abs(Date.parse(e.date) - when) < Math.abs(Date.parse(epochs[best].date) - when)) best = i;
      });
      return best;
    },
    [epochs, everyEpoch],
  );
  const range = useMemo<[number, number]>(() => {
    const a = idxOf(rangeIds?.[0] ?? null);
    const b = idxOf(rangeIds?.[1] ?? null);
    return a >= 0 && b >= 0 ? [Math.min(a, b), Math.max(a, b)] : [0, lastIdx];
  }, [rangeIds, idxOf, lastIdx]);
  const urlIdx = idxOf(params.epoch);
  // Open on the observation with the most data (the latest if they are equal).
  const fullestIdx = useMemo(() => {
    let best = lastIdx;
    epochs.forEach((e, i) => {
      if ((e.coverage ?? 0) >= (epochs[best]?.coverage ?? 0)) best = i;
    });
    return best;
  }, [epochs, lastIdx]);
  const playheadIdx = clamp(idxOf(playheadId) >= 0 ? idxOf(playheadId) : urlIdx >= 0 ? urlIdx : fullestIdx, 0, lastIdx);
  const playheadEpoch = epochs[playheadIdx];

  // Bands that can't join the ones that are on, because no observation has both.
  const bandBlocked = useMemo(() => {
    const out: Record<string, string> = {};
    for (const b of area?.bands ?? []) {
      if (b.state !== "ok" || activeBands.includes(b.id)) continue;
      if (!seenTogether([...activeBands, b.id])) out[b.id] = "Never seen in the same observation as the bands that are on.";
    }
    return out;
  }, [area, activeBands, seenTogether]);

  // ---- frame size follows the zoom: a bigger frame when you zoom out
  const levels = useMemo(
    () =>
      area?.levels ?? (area ? [{ level: 0, extentDeg: area.extentDeg, sizePx: area.sizePx, pixelScaleArcsec: area.pixelScaleArcsec }] : []),
    [area],
  );
  const getLevel = useCallback(() => {
    const fov = viewStore.get().fov;
    return (levels.find((l) => l.extentDeg >= fov * 1.05) ?? levels[levels.length - 1])?.level ?? 0;
  }, [levels, viewStore]);
  const level = useSyncExternalStore(viewStore.subscribe, getLevel, getLevel);

  // Ask for what is on screen first (this frame size, then the small one as a fallback),
  // then the other observations in the background.
  useEffect(() => {
    if (!frames || !epochs.length) return;
    const others = epochs.map((_, i) => i).filter((i) => i !== playheadIdx).sort((a, b) => Math.abs(a - playheadIdx) - Math.abs(b - playheadIdx));
    const ask = (i: number, lv: number) => {
      for (const b of activeBands) if (!epochs[i].bands || epochs[i].bands!.includes(b)) frames.request(lv, epochs[i].id, b);
    };
    ask(playheadIdx, level);
    if (level > 0) ask(playheadIdx, 0);
    for (const i of others) ask(i, 0);
    if (level > 0) for (const i of others) ask(i, level);
  }, [frames, epochs, playheadIdx, activeBands, level]);

  const epochLoaded = useCallback(
    (i: number) => !!frames && !!epochs[i] && activeBands.every((b) => frames.isReady(0, epochs[i].id, b)),
    // frameVersion makes this re-evaluate as frames arrive.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [frames, epochs, activeBands, frameVersion],
  );
  const loadedEpochs = epochs.map((_, i) => epochLoaded(i));

  const anyShown =
    !!frames &&
    !!playheadEpoch &&
    activeBands.some((b) => levels.some((l) => frames.isReady(l.level, playheadEpoch.id, b))) &&
    frameVersion >= 0;
  const dataStatus: DataStatus = areaQuery.isError
    ? "error"
    : frames?.hasError() && !anyShown
      ? "error"
      : anyShown
        ? "ready"
        : "loading";
  // "Nothing is saved for this spot" is an answer, not a failure: say so, don't offer Retry.
  const noData = areaQuery.error instanceof NoDataError ? areaQuery.error : null;
  const toolsEnabled = dataStatus === "ready";
  const retryData = useCallback(() => {
    if (areaQuery.isError) areaQuery.refetch();
    frames?.retry();
  }, [areaQuery, frames]);

  // ---- playback: step over loaded epochs inside the range
  const playRef = useRef({ playheadIdx, range, loaded: loadedEpochs, ids: epochs.map((e) => e.id) });
  useEffect(() => {
    playRef.current = { playheadIdx, range, loaded: loadedEpochs, ids: epochs.map((e) => e.id) };
  });
  const loadedInRange = loadedEpochs.filter((l, i) => l && i >= range[0] && i <= range[1]).length;
  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => {
      const { playheadIdx: cur, range: [a, b], loaded } = playRef.current;
      for (let step = 1; step <= b - a + 1; step++) {
        const i = a + ((cur - a + step) % (b - a + 1));
        if (loaded[i]) return setPlayheadId(playRef.current.ids[i]);
      }
    }, 1100);
    return () => clearInterval(t);
  }, [playing]);
  const canPlay = toolsEnabled && loadedInRange >= 2;
  const isPlaying = playing && canPlay;

  // ---- motion
  const motionRange = motion.status === "done" ? motion.range : null;
  const outdated = !!motionRange && (motionRange[0] !== range[0] || motionRange[1] !== range[1]);
  const movers = useMemo<Mover[]>(() => (motion.status === "done" ? motion.result.movers : []), [motion]);
  const motionVisible = motion.status === "done" && movers.length > 0;
  const rangeEpochCount = range[1] - range[0] + 1;
  const abortMotion = useRef<AbortController>(null);

  const analyze = useCallback(async () => {
    if (!area || rangeEpochCount < 2) return;
    abortMotion.current?.abort();
    const ctl = new AbortController();
    abortMotion.current = ctl;
    const ids = epochs.slice(range[0], range[1] + 1).map((e) => e.id);
    setMotion({ status: "running", step: "Getting started…" });
    setVerify({ status: "idle" });
    try {
      const result = await exploreApi.analyzeMotion(
        { areaId: area.id, epochs: ids, bands: activeBands },
        { signal: ctl.signal, onStep: (step) => setMotion({ status: "running", step }) },
      );
      if (ctl.signal.aborted) return;
      setMotion({ status: "done", result, range: [range[0], range[1]] });
      // New movers leave "object selected": the box goes, the list takes over.
      setBoxState(null);
      setMoverId(null);
    } catch (e) {
      if (ctl.signal.aborted) return;
      setMotion({ status: "failed", error: errorMessage(e) });
    }
  }, [area, epochs, range, rangeEpochCount, activeBands]);

  const clearMotion = useCallback(() => {
    abortMotion.current?.abort();
    setMotion({ status: "idle" });
    setMoverId(null);
  }, []);

  // ---- selection
  const setBox = useCallback((b: SkyBox | null, opts?: { moverId?: string | null }) => {
    setBoxState(b);
    setMoverId(opts?.moverId ?? null);
    setVerify((v) => (v.status === "idle" ? v : { status: "idle" }));
  }, []);

  const selectMover = useCallback(
    (id: string) => {
      const m = movers.find((x) => x.id === id);
      if (!m || !playheadEpoch) return;
      const pt = m.points.find((p) => p.epochId === playheadEpoch.id) ?? m.points[0];
      const view = viewStore.get();
      const half = view.fov * 0.035;
      setBox({ ra: pt.ra, dec: pt.dec, width: half * 2, height: half * 2 }, { moverId: id });
      const o = offsetDeg(view, pt);
      if (Math.abs(o.east) > view.fov * 0.42 || Math.abs(o.north) > view.fov * 0.42 * (size.h / size.w)) {
        setView({ ...view, ra: pt.ra, dec: pt.dec });
      }
    },
    [movers, playheadEpoch, setBox, setView, size, viewStore],
  );

  // ---- object panel
  const debouncedBox = useDebounced(box, 220);
  const inspectEpoch = allEpochs ? "all" : (playheadEpoch?.id ?? "all");
  const inspectQuery = useQuery<Inspection>({
    queryKey: [
      "explore-inspect",
      area?.id,
      debouncedBox && [debouncedBox.ra, debouncedBox.dec, debouncedBox.width, debouncedBox.height].map((n) => n.toFixed(5)),
      moverId,
      inspectEpoch,
      activeBands,
    ],
    queryFn: ({ signal }) =>
      exploreApi.inspect(
        {
          areaId: area!.id,
          target: moverId ? { kind: "mover", moverId, box: debouncedBox! } : { kind: "box", box: debouncedBox! },
          epoch: inspectEpoch,
          bands: activeBands,
        },
        { signal },
      ),
    enabled: !!area && !!debouncedBox && toolsEnabled,
    retry: 1,
  });

  // ---- verify
  const abortVerify = useRef<AbortController>(null);
  const verify = useCallback(async () => {
    if (!area || !box) return;
    abortVerify.current?.abort();
    const ctl = new AbortController();
    abortVerify.current = ctl;
    setVerify({ status: "running", step: "Getting started…" });
    try {
      const result = await exploreApi.verify(
        {
          areaId: area.id,
          target: moverId ? { kind: "mover", moverId, box } : { kind: "box", box },
          epoch: inspectEpoch,
          bands: activeBands,
          moverId: moverId ?? undefined,
        },
        { signal: ctl.signal, onStep: (step) => setVerify({ status: "running", step }) },
      );
      if (ctl.signal.aborted) return;
      const points = result.outcome === "explained" ? awardPoints(result.objectType) : 0;
      setVerify({ status: "done", result, points });
    } catch (e) {
      if (ctl.signal.aborted) return;
      setVerify({ status: "failed", error: errorMessage(e) });
    }
  }, [area, box, moverId, inspectEpoch, activeBands]);
  const closeVerify = useCallback(() => {
    abortVerify.current?.abort();
    setVerify({ status: "idle" });
  }, []);

  const selectedMover = movers.find((m) => m.id === moverId) ?? null;

  const sidebarMode: SidebarMode =
    verifyState.status !== "idle" ? "verify" : motionVisible && !outdated ? "motion" : box ? "object" : "none";

  // ---- sharing
  const share = useCallback(
    (spectrum: Inspection["spectrum"] | null) => {
      if (!box) return null;
      return openShare({
        areaName: params.q ?? area?.name ?? null,
        box,
        bands: activeBands,
        epochs: epochs.slice(range[0], range[1] + 1).map((e) => e.id),
        spectrum,
        mover: selectedMover,
        viewUrl: window.location.href,
      });
    },
    [box, params.q, area, activeBands, epochs, range, selectedMover],
  );

  // ---- keep the URL current, so "Copy link" is the address bar
  const selectedLayer = layerId;
  useEffect(() => {
    if (!area) return;
    let timer: ReturnType<typeof setTimeout>;
    const write = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const v = viewStore.get();
        const next = writeParams(new URLSearchParams(window.location.search), {
          ...v,
          bands: activeBands,
          epoch: playheadEpoch?.id ?? null,
          layer: selectedLayer,
        });
        window.history.replaceState(window.history.state, "", `?${next.toString()}`);
      }, 350);
    };
    write();
    const off = viewStore.subscribe(write);
    return () => {
      off();
      clearTimeout(timer);
    };
  }, [area, activeBands, playheadEpoch?.id, selectedLayer, viewStore]);

  // Esc clears the selection (or the verify results first).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
      if (box) setBox(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [box, setBox]);

  const toggleBand = useCallback(
    (id: BandId) => {
      if (!activeBands.includes(id) && bandBlocked[id]) return;
      setBandsOn(() => {
        if (activeBands.includes(id)) return activeBands.length > 1 ? activeBands.filter((b) => b !== id) : activeBands;
        return [...activeBands, id];
      });
    },
    [activeBands, bandBlocked],
  );

  return {
    params,
    usingMock: usingMockData,
    area,
    areaQuery,
    viewStore: viewStore,
    sizeStore: sizeStore,
    setView,
    normalizeView,
    limits: liveLimits ?? limits,
    frames,
    frameVersion,
    dataStatus,
    noData,
    toolsEnabled,
    retryData,
    // choices
    bandsOn: activeBands,
    toggleBand,
    epochs,
    playheadIdx,
    playheadEpoch,
    setPlayhead: (i: number) => {
      const e = epochs[clamp(i, range[0], range[1])];
      if (e) setPlayheadId(e.id);
    },
    range,
    setRange: (r: [number, number]) => {
      setRangeIds([epochs[r[0]].id, epochs[r[1]].id]);
      const e = epochs[clamp(playheadIdx, r[0], r[1])];
      if (e) setPlayheadId(e.id);
    },
    loadedEpochs,
    level,
    levels,
    bandBlocked,
    playing: isPlaying,
    canPlay,
    play: () => setPlaying(true),
    stop: () => setPlaying(false),
    layerId,
    setLayerId,
    curtain,
    setCurtain,
    mode,
    setMode,
    // selection
    box,
    setBox,
    moverId,
    selectMover,
    selectedMover,
    allEpochs,
    setAllEpochs,
    inspectQuery,
    // motion
    motion,
    movers,
    outdated,
    rangeEpochCount,
    analyze,
    clearMotion,
    // verify
    verifyState,
    verify,
    closeVerify,
    share,
    sidebarMode,
  };
}

const noopSubscribe = () => () => {};
const zero = () => 0;

function errorMessage(e: unknown) {
  return e instanceof Error && e.message ? e.message : "Something went wrong.";
}

export type Explore = ReturnType<typeof useController>;
const Ctx = createContext<Explore | null>(null);

export function ExploreProvider({ children }: { children: ReactNode }) {
  const value = useController();
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useExplore() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useExplore must be used inside <ExploreProvider>");
  return v;
}
