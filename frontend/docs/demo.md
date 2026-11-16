# Hiraya demo: Barnard's Star

The Explore page runs on **prefetched, simulated SPHEREx data** for one place,
Barnard's Star, so the demo can't fail on a slow archive or a bad connection.
The Aladin sky stays real (it streams DSS2 / WISE / 2MASS tiles from IRSA).

> Everything marked "simulated" below is invented to look like SPHEREx. The page
> says "Demo data · simulated SPHEREx" in the corner. Say so out loud.

| | |
|---|---|
| Real | Barnard's Star's position, **proper motion (10.3″ a year, north)**, brightness (J = 5.24), the DSS2/WISE/2MASS backdrop |
| Simulated | the SPHEREx pictures (18 observations, 9 colours, 3 zoom levels), spectra, noise and glitches, a faint galaxy, and **the find**: a cold, faint object that moves 6.8″ a year |
| Faked look-ups | "Matched in SIMBAD", the near-miss 2MASS name (built from coordinates), the asteroid check |

> **Guided demo.** The header has a **Guided demo** button (desktop). A small card walks through every click below and points at the
> button to press; it moves on by itself when you do it. Deployed on Vercel with no backend: see [deploy.md](deploy.md).

## Run it

```bash
cd frontend
pnpm install
pnpm build && pnpm start          # steadier than pnpm dev for a live demo
pnpm demo:check                   # pre-flight: files, app, sky backdrop
```

* **No backend at all.** Explore, Discussions, posting and comments all run in the browser (see [deploy.md](deploy.md)).
* Use the real pipeline instead of the demo: `NEXT_PUBLIC_EXPLORE_API=http` and `BACKEND_URL` in `.env.local`.
* Regenerate the data (deterministic): `pnpm demo:data`, then `pnpm demo:community`.

## The safe path (about 4 minutes)

Start on `/` . Before going live, once: open the Explore page and click through steps 2 to 5 to warm the browser cache.

1. **Home.** The sky opens on the Orion Nebula, then dissolves to *Barnard's Star* after about 10 seconds and rests there (label and orange reticle). Type "barnard" in the search box, press Enter.
   *Say:* the closest single star system after Alpha Centauri, 6 light-years away, and it moves faster across our sky than any other star.
2. **Explore opens** on the star: bands *Starlight* and *4–5 µm light*, 12 observations, newest on the right.
   *Say:* each dot on the timeline is one SPHEREx visit, over 15 months.
3. **Scrub the timeline** (click the third or fourth dot, or press Play). Zoom in with **+** to about 0.1° and watch the star creep up the frame.
4. **Zoom out with − to about 0.4°, then Compare with → Visible light.** Drag the curtain. *Say:* this photograph is about 35 years old, and the star is drawn a long way *south* of where SPHEREx sees it now (about 0.1°). It has moved; that is what we're about to measure.
5. **Select box**, drag a square around the star. Right panel: **Star**, "a cool, red star…", spectrum with water-vapour dips.
6. **Verify: is it already known?** About 2 seconds of "Checking…", then **Explained, Known star, Barnard's Star (GJ 699), matched in SIMBAD, +10 points.**
7. **Analyze motion** (bottom right, with the whole range selected). About 2.5 seconds, then **2 found**.
   * **1**: about 10 arcseconds a year, toward the top. That is Barnard's Star.
   * **2**: about 7 arcseconds a year, toward the lower left. Nobody told the page about this one.
8. **Click mover 2.** Guess: **Brown dwarf**, "faint in starlight but bright at 4 to 5 µm, with a methane dip". Spectrum shows the methane dips.
9. **Verify** on mover 2: **Unexplained**, "Closest match, but it doesn't fit". *Say:* that is not a discovery, it means our sources don't list it. Someone else may know. That's why we have
10. **Discuss suspected motion.** (Use an example fills the note in.) Give it a title and a few words, then **Create discussion post**. The post opens with a
    still snapshot, a **Blink** GIF of the observations with the ring following the object, the colourful spectrum and a data summary.
11. **Discussions** (top right, any page) lists every discussion: the five prepared ones, yours and the notebook posts. Search, sort by newest or most replies.

## Discussions

Five simulated conversations about the Barnard's Star field ship as static files (`public/demo/community`), each with a snapshot, blink GIF,
spectrum and replies. The find itself is deliberately **not** among them, so you can post it live. What you post is saved in **your browser only**
(`localStorage`, key `hiraya:community:v1`): nothing is uploaded, and a second visitor never sees it.

* A post around the faint mover gets the baked snapshot, blink GIF and spectrum. Anywhere else it carries its own spectrum and no pictures.
* **Reset your posts:** `localStorage.removeItem("hiraya:community:v1")` in the console, or clear site data. Then the find can be posted again.

## Things that behave differently on purpose

* **Anywhere else on the sky:** Explore shows "We currently don't support access to other objects…" with a button into the Barnard's Star region.
  The home sky, the search box and the feed cards all lead there, so nothing breaks if someone clicks elsewhere.
* **Motion needs time.** Analyze finds nothing on a range shorter than about 7 months (Barnard) or 11 months (the find): the movement is under one pixel. The notice says so. Keep the full range.
* **The find needs *Starlight* or *4–5 µm light* on.** It is invisible in the narrow line bands.
* **Bands never seen together are greyed out.** Each visit sees only some colours, like real SPHEREx. The default pair has 12 shared visits, so leave it on.
* **Points** (`+10`) are kept in the browser. Reset with `localStorage.removeItem("pulsr.points")`.

## If something goes wrong

| Symptom | Do |
|---|---|
| Black around the picture, Compare layers empty | No internet for IRSA tiles. The SPHEREx steps still work; skip step 4. |
| "…isn't open in this preview" | You asked for another object. Click the button, or load `/explore?q=Barnard%27s%20Star&ra=269.4463&dec=4.7682&fov=0.2`. |
| Odd state after poking around | Reload that URL; the page rebuilds from it. |
| The find already has a discussion (you posted it before) | Clear it: `localStorage.removeItem("hiraya:community:v1")`, reload. |
| Selection box keeps following the mouse | Fixed: a drag now ends on release, on Esc, or when the window loses focus. Press Esc if it ever happens. |
| Anything else | `pnpm demo:check`, then restart `pnpm start`. |

## How it works

* `scripts/make-demo-data.py` writes `public/demo/barnard/`: `manifest.json` (area, observations, which colours each one saw,
  sources, spectrum templates) and 315 small PNGs (`frames/L<zoom>/<observation>/<band>.png`, same contract as the real API).
  Barnard's Star is drawn where its proper motion puts it on each date; the find moves the same way, at its own speed.
* `src/lib/explore/demo/demo-client.ts` implements the same `ExploreApi` as the Python backend. It answers box inspection from the
  manifest (which sources are in the box, their spectra, noise that grows with the box), motion from the proper motions with
  sub-pixel centroid error, and Verify from rules (Barnard: explained; the find: unexplained; a hot pixel: artifact; empty: nothing).
* The default Explore start, the home screen's resting place and the catalogue entry for Barnard's Star all use
  RA 269.4463°, Dec +4.7682°, where the star is now. (J2000 puts it 0.075° south.)
