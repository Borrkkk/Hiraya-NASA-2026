# Deploying the Hiraya preview to Vercel

The preview is a **static, serverless** Next.js app. There is no backend, database or API key.

| Part | Where it comes from |
|---|---|
| Explore (images, spectra, motion, Verify) | simulated Barnard's Star data in `public/demo/barnard` |
| Discussions, comments, posting | five sample discussions in `public/demo/community`; anything a visitor adds is saved in **their** browser (`localStorage`) and never uploaded |
| The sky on the home page | Aladin Lite streaming DSS2 tiles from IRSA at runtime (needs internet on the visitor's side) |
| Fonts | `next/font/google`, fetched at build time |

## Deploy

1. Push the repo to GitHub and **Import** it in Vercel.
2. **Root Directory:** `frontend`. Framework preset: Next.js (detected). Package manager: pnpm (from `packageManager`).
3. Leave every environment variable empty. In particular do **not** set `BACKEND_URL` or `NEXT_PUBLIC_EXPLORE_API`.
4. Deploy. Build command `pnpm build`, nothing to configure.

Check before sharing the link: `/` loads, search "barnard" opens Explore, search "vega" shows the limited-preview page, `/discussions` lists six or more posts.

## What visitors can and can't do

* **Free:** the home sky (drag, zoom, search), the guided demo (button in the header, desktop), Explore in the Barnard's Star region, posting a (fake) discussion, commenting.
* **Closed on purpose:** every other object or coordinate leads to a "this limited preview only opens Barnard's Star" page with a button into the region (`src/lib/explore/preview-region.ts`, `src/components/explore/preview-limit.tsx`).
* **Phones:** the home page, discussions and posts work. Explore shows a friendly "needs a bigger screen" page with a screenshot.
* **Posts around the faint mover** get the baked snapshot, blink GIF and spectrum. A post anywhere else carries its own spectrum and no pictures.
* Visitors' posts and comments are per browser. Clearing site data resets them.

## Regenerating the baked data (only if you change the simulation)

```bash
pnpm demo:data        # public/demo/barnard   (needs backend/.venv for numpy/PIL)
pnpm demo:community   # public/demo/community (needs backend/.data from a local run: seed + post once around the faint mover)
```

`demo:community` turns the sample discussions (and the newest non-sample post, used as the live template) into static JSON, PNGs and GIFs.
Seed locally first: `cd backend && .venv/bin/python -m app.explore.seed_demo_discussions`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Black around the SPHEREx picture, Compare layers empty | The visitor can't reach IRSA's tile servers. The rest still works. |
| Discussions page says "sample discussions could not be loaded" | `public/demo/community/community.json` is missing: run `pnpm demo:community` and commit the output. |
| A visitor's post vanished | Different browser or cleared site data: posts live in `localStorage` (`hiraya:community:v1`). |
