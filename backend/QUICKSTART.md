# Running on another Windows computer

Install Python 3.11+ first. Then, from the project root:

```powershell
.\backend\setup.cmd
```

That creates the local Python environment, installs dependencies and creates
`backend/.env`. Set your optional `OPENAI_API_KEY` in that file once. The model
and other defaults are already filled in. Keep `.env` private; it is ignored by Git.

Every time you want to run the backend:

```powershell
.\backend\run.cmd
```

No environment commands or virtual-environment activation are needed. The
launcher reads `.env`, resolves relative paths from `backend/`, finds the newest
installed index and starts port 8000. Explicit terminal settings override `.env`.
Use `run.cmd -Check` to validate configuration without starting the server.

## Bring the fast demo data

Git does not include the downloaded data. Stop the backend on the original
computer before copying the SQLite database. Copy these folders into the same
locations on the new computer:

| Folder | Contents |
| --- | --- |
| `backend/.cache/` | Exposure index, observation metadata, FITS cutouts and rendered demo frames |
| `backend/.data/` | Discussion database, observation snapshots and GIFs |

Do not copy `.venv`; setup recreates it for the new machine. Configure `.env`
locally on that machine. The default blank index setting discovers the copied
snapshot automatically; no machine-specific paths need to be changed.

The frontend still starts separately: install Node.js, run `npm install` once
inside `frontend/`, then `npm run dev`. Open http://localhost:3000/explore.

The cached SPHEREx demo works without re-downloading its images. Context sky
surveys and optional AI explanations still require their respective network services.
