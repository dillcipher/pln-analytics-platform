# PLN Analytics Platform - Consolidated Revision

This revision is based on the uploaded `pln-analytics-source.zip`.

## Changes

### 1. DLPD API normalization
`frontend/src/api/dlpd.ts`
- Accepts raw responses and `{data: ...}`, `{result: ...}`, `{payload: ...}` envelopes.
- Normalizes dashboard, ULP, filters, months, customer list/detail, and map responses.
- Normalizes map coordinates and coordinate source.
- Prevents valid backend data from becoming UI zeros because of response-shape mismatch.

### 2. DLPD map coordinate matching
`backend/app/infrastructure/duckdb/dlpd_repository.py`
- Primary coordinate source: `fact_customer_location`.
- Fallback coordinate source: latest valid `fact_pengecekan`.
- Primary coordinates win.
- X/Y reversal is handled for customer-location data.
- Coordinates are restricted to the PLN Lampung operating area.
- Coverage counts use the same coordinate rules as the points query.
- `coordinate_source` is returned for every mapped point.

### 3. Suspect map coordinate validation
`backend/app/infrastructure/duckdb/suspect_repository.py`
- Keeps IDPEL/LOCATIONCODE matching and pengecekan fallback.
- Rejects malformed/out-of-area coordinates that were producing markers in unrelated regions/ocean.
- Uses the same Lampung coordinate envelope for map points and coverage.
- Existing primary/fallback precedence remains intact.

### 4. Executive KPI fallback
`backend/app/infrastructure/duckdb/executive_repository.py`
- Existing `executive_kpis` snapshot is still preferred.
- If the snapshot is missing/unavailable for the selected month, KPI values are derived from `fact_anev` + latest `fact_pengecekan`.
- This prevents Executive Dashboard KPI cards from showing all zeros while the ANEV charts contain data.

## Validation

- All Python files in the revision package compile successfully with `py_compile`.
- Frontend dependency installation/TypeScript validation was attempted in the isolated environment but timed out, so the final TypeScript build must be run in the project's existing frontend environment.

## Apply

Replace the corresponding files from this package into the project, then run:

```powershell
cd C:\Users\fadil\Documents\pln-analytics-platform\backend
.\.venv\Scripts\Activate.ps1
python -m compileall app
```

Then:

```powershell
cd C:\Users\fadil\Documents\pln-analytics-platform\frontend
npx tsc --noEmit
npm run build
```

Backend endpoint checks:

```powershell
cd C:\Users\fadil\Documents\pln-analytics-platform\backend

curl.exe "http://127.0.0.1:8000/api/v1/suspect/analytics?month=202606"
curl.exe "http://127.0.0.1:8000/api/v1/suspect/map?month=202606"
curl.exe "http://127.0.0.1:8000/api/v1/dlpd/dashboard?customer_type=prabayar&month=202606"
curl.exe "http://127.0.0.1:8000/api/v1/dlpd/map?customer_type=prabayar&month=202606"
curl.exe "http://127.0.0.1:8000/api/v1/executive/kpis?month=202606"
curl.exe "http://127.0.0.1:8000/api/v1/executive/charts?month=202606"
```
