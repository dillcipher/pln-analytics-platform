# PLN Analytics Platform — Final Stabilization Build

This package is a source-level stabilization build based on the latest consolidated revision. It intentionally does **not** include `data/`, `.venv/`, or `node_modules/`; keep those from your existing project.

## What was fixed

- Removed stale AG Grid CSS imports that were not declared in `package.json`.
- Added a guaranteed local Vite `/api` proxy to FastAPI (`127.0.0.1:8000`).
- Added a default frontend API base (`/api/v1`) so a missing `.env` no longer silently points requests at Vite.
- Reworked DuckDB API connections to be thread-local/read-only, preventing concurrent FastAPI requests from closing each other’s connection.
- Made DLPD month/filter endpoints safe when a source table is not available yet.
- Made DLPD inspection joins safe when the inspection table is absent.
- Added a visible DLPD page-level error instead of silently displaying zeros after a failed request.
- Fixed Suspect Detail so a classification selected from ANEV is matched against the measurement dataset by LOCATION_CODE.
- Added the missing `repeat_count` query parameter to the Suspect Detail backend route.
- Added local start/stop scripts.

## Clean run

1. Extract this archive over the existing project folder (do not delete your existing `data/` folder).
2. Backend:

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m compileall app
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

3. Frontend in a second terminal:

```powershell
cd frontend
npm install
npm run build
npm run dev
```

4. Open `http://127.0.0.1:5173/`.

The frontend now talks to FastAPI through `/api/v1` automatically in local development. No `VITE_API_URL` is required.

## Data expectation

The archive cannot contain your private PLN datasets. The existing `data/processed/warehouse.duckdb` and processed parquet data must remain in your project. If the warehouse is empty, run your existing ETL/upload process first.
