# Hiraya

> **Deployed preview:** the app in `frontend/` is a static, serverless preview (simulated Barnard's Star data, no backend).
> To deploy it on Vercel see [frontend/docs/deploy.md](frontend/docs/deploy.md); to present it see [frontend/docs/demo.md](frontend/docs/demo.md).
> Everything below describes the **real SPHEREx pipeline** used for local development.

Explore the sky with Aladin Lite and retrieve SPHEREx observations by coordinates.

For a new Windows computer, follow [backend/QUICKSTART.md](backend/QUICKSTART.md).
Run `.\backend\setup.cmd` once, add an optional API key to `backend/.env`, then
start with `.\backend\run.cmd`. The launcher loads the settings automatically.

With backend dependencies installed and an exposure index downloaded,
start the backend from PowerShell in this directory:

```powershell
.\backend\run.cmd
```

The script selects the newest installed index, enables S3 image caching, and
starts the backend on port 8000. Press Ctrl+C to stop it. Start the frontend
separately with `npm run dev` in `frontend/`.

- [Frontend](frontend/README.md): Next.js sky explorer.
- [Backend](backend/README.md): Python API for exposure search, aligned time-lapse
  frames, blink comparisons, median stacks, and difference images.

## Run Explore with the science pipeline

From the project root:

```sh
source backend/.venv/bin/activate
pip install -e '.[dev]'
uvicorn api.app:app --reload --port 8000
```

In another terminal, run `pnpm dev` in `frontend/`. The default proxy sends
`/api/*` to port 8000. For another port, set `BACKEND_URL` in
`frontend/.env.local` and restart Next.js. Leave `NEXT_PUBLIC_EXPLORE_API`
unset to use real data.

The unified `api.app:app` serves both `/inspect`, `/inspect/frames`, `/context`
and the existing `/explore/*` contract. Explore's Inspect and Verify use
`spherex_inspect` on the selected, already cached FITS files. Image rendering,
timeline metadata, and field-wide mover detection reuse `backend/app/explore`.
There is no second image download or discovery pass for analysis.

The sidebar reports point-source photometry **at the box centre**, with usable
frame counts, flags, and a spectrum in Jy. This is different from summing an
entire box. The existing morphology-based object guess remains a heuristic;
it is not a calibrated probability. Verify uses measured positions and catalog
matches, and reports inconclusive or unavailable checks instead of confirming
a discovery. Complete measurements, uncertainties, motion fits, and context
are retained in the analysis response's `science` field.

The saved cutouts can be measured offline. Catalog verification and new sky
fields need network access. Live catalog results have not been validated as
part of the offline integration checks.

Checks: `python -m pytest tests` and, in `backend/`, `python -m pytest tests`.
The legacy `app.main:app` entry point still serves its existing analysis;
start `api.app:app` to use the integrated science pipeline.
