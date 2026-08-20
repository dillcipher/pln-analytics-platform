# PLN Enterprise Analytics Platform — Architecture & Roadmap
**Phase 0 Deliverable: Technology Recommendation, Architecture, Folder Structure, Roadmap**

---

## 1. Requirements Recap (what actually drives the stack decision)

Before comparing tools, the constraints that matter most:

1. **ETL and Dashboard are hard-separated.** Colab does all processing; the app never touches raw Excel. So the dashboard stack only needs to be good at *reading processed columnar data fast*, not at Excel parsing.
2. **Data volume**: "hundreds of thousands to millions of rows" for detail tables (Suspect Analytics detail page has 28 numeric columns per reading — this is timeseries-like, not a small lookup table).
3. **Multiple linked, filterable modules** (Executive, DLPD Monitoring, Suspect Analytics x3 pages) with **cross-component synchronization** (select a row → other panels update) and **global filters shared across pages**.
4. **Enterprise-grade tables**: pinned columns, resize, export, pagination, no horizontal scroll pain — this is an AG Grid problem, not a "st.dataframe" problem.
5. **Auth required, no anonymous access.**
6. **Free/open-source only, and must be deployable on Vercel/Render/Railway/HF Spaces/Cloudflare Pages/GH Pages tier.**
7. **Must grow**: new modules added later without re-architecting.

Given #3, #4, and #7 in particular, this is a **multi-page enterprise SPA with client-side interactivity and cross-filtering** — which is a fundamentally different engineering problem than a script-driven dashboard.

---

## 2. Technology Comparison

### 2.1 Backend

| Option | Verdict | Reasoning |
|---|---|---|
| **Flask** | ❌ | No async, no built-in validation/serialization, you'd hand-roll everything an enterprise API needs (schemas, docs, dependency injection). |
| **Django** | ❌ | Batteries-included ORM/admin is wasted weight here — you have no relational writes from users, just read-heavy analytical queries over Parquet/DuckDB. Django ORM actively fights a DuckDB/Parquet backend. |
| **FastAPI** | ✅ **Selected** | Async I/O (matters for concurrent large-query loads), Pydantic schemas give you typed, self-documenting contracts between ETL output and frontend, auto OpenAPI docs, first-class DuckDB/Arrow/Parquet integration, dependency-injection auth is clean, and it's the de facto standard for Python analytics backends in 2025-2026. |

### 2.2 Frontend

| Option | Verdict | Reasoning |
|---|---|---|
| **Streamlit** | ❌ (explicitly excluded per brief, and correctly so) | Streamlit re-runs the whole script top-to-bottom on every interaction — this is architecturally incompatible with "selecting a row updates 3 other components" without hacky session-state gymnastics, and it cannot deliver AG Grid-grade tables, true multi-page routing with shared global filter state, or a Power-BI-grade dark UI. It's fine for internal single-analyst tools, not for what's being asked here. |
| **Vue** | ❌ | Smaller enterprise-component ecosystem (AG Grid, chart wrappers) than React; no strong reason to pick it over React/Next given the team will want the largest available library surface. |
| **Next.js** | ❌ (for this specific case) | Next's main value is SSR/SEO/edge-rendering for public-facing sites. This is an internal, authenticated, data-dense SPA — SSR adds deployment complexity (server runtime, ISR caching) with no benefit here. |
| **React (Vite SPA)** | ✅ **Selected** | Pure client-rendered SPA is the right shape for an authenticated internal tool: simpler deploy (static files + CDN), instant client-side filtering/cross-referencing via shared state (Zustand/Context), full access to AG Grid Community, Plotly, ECharts. Vite gives fast dev/build vs CRA. |

### 2.3 Visualization

| Option | Verdict | Reasoning |
|---|---|---|
| **Chart.js** | ❌ for core charts | Fine for simple KPI sparklines, but weak for heatmaps and lacks the interaction depth (zoom, brush, linked selection) needed for Suspect Analytics trend charts. |
| **Plotly** | ⚠️ Secondary | Excellent for statistical/trend charts (Voltage Trend, Current Trend) with built-in zoom/pan/export-to-png — use it specifically for the Detail Page trend charts. |
| **Apache ECharts** | ✅ **Selected as primary** | Best-in-class for exactly what's listed: bar/pie/donut/heatmap/ranking, GPU-accelerated for large series, native dark-theme support, small bundle relative to capability, used in production BI tools at this scale. |
| **Decision** | **ECharts for dashboard/KPI/ranking/heatmap charts, Plotly for the two Detail-page scientific trend charts.** Two libraries is acceptable here because they serve genuinely different chart classes — don't force one tool to do both jobs badly. |

### 2.4 Interactive Tables

| Option | Verdict | Reasoning |
|---|---|---|
| **DataTables (jQuery)** | ❌ | jQuery-based, awkward in a React tree, weaker column-pinning/virtualization for millions of rows. |
| **AG Grid Community** | ✅ **Selected** | Column pinning, resize, sort/filter, row selection, CSV export, and **row virtualization** (renders only visible rows — critical for the detail tables with 28+ columns × hundreds of thousands of rows) all ship free in Community edition. Enterprise features (Excel export, pivoting) are paywalled — see workaround below. |

**Excel export workaround (staying free):** AG Grid Community only exports CSV natively. For "Export Excel" buttons, generate `.xlsx` server-side via FastAPI (using `openpyxl`/`xlsxwriter` on the already-filtered dataset) and stream it down — this is actually *better* for large filtered exports than client-side generation anyway.

### 2.5 Storage

| Option | Verdict | Reasoning |
|---|---|---|
| **SQLite** | ⚠️ Fallback only | Fine for small lookup tables (unit hierarchy, tariff lookup) but row-store engines are the wrong shape for wide analytical scans across millions of rows. |
| **PostgreSQL** | ❌ (optional, not needed) | Would work, but adds a stateful server you must host/back up/pay-tier-manage. Nothing here requires transactional writes from users — everything is ETL-produced, read-only analytical data. |
| **Parquet + DuckDB** | ✅ **Selected** | Colab ETL writes columnar **Parquet** partitioned by month (`suspect_detail/year=2026/month=07/*.parquet`). FastAPI queries them through **DuckDB** running in-process (no server, just a library) using SQL directly over the Parquet files — this gets you Postgres-grade analytical query speed on millions of rows with zero database to operate, and DuckDB reads Parquet natively with predicate pushdown (only scans the month/columns actually requested). This is the standard modern pattern for exactly this workload. |

### 2.6 Deployment

| Layer | Choice | Reasoning |
|---|---|---|
| **Frontend (React SPA)** | **Cloudflare Pages** | Free tier, unlimited bandwidth, global CDN — best fit for a static SPA build. |
| **Backend (FastAPI + DuckDB)** | **Render** (free/hobby web service) or **Railway** | Both support long-running Python processes (needed — DuckDB needs a persistent process, unlike serverless functions which don't suit repeated Parquet scans well). Render's free tier is the more predictable of the two for a persistent service. |
| **Processed data + code** | **GitHub** (private repo) | Parquet files under a size budget can live in the repo (or GitHub Releases / Git LFS if they grow large); backend pulls/mounts them at deploy or startup. |
| **ETL** | **Google Colab** (per brief) | Stays exactly as specified — a separate, disconnected environment from the dashboard runtime, satisfying the security requirement of never exposing raw Excel to the app layer. |

---

## 3. Recommended Stack (final)

```
ETL:            Python (pandas) in Google Colab
Storage format:  Parquet (partitioned by month + dataset)
Query engine:    DuckDB (embedded, in-process SQL over Parquet)
Backend API:     FastAPI + Pydantic + Uvicorn
Auth:            FastAPI + JWT (OAuth2PasswordBearer) + bcrypt password hashing
Frontend:        React 18 + Vite + TypeScript
State mgmt:      Zustand (global filter sync across pages)
Tables:          AG Grid Community
Charts:          Apache ECharts (primary) + Plotly.js (detail-page scientific trends)
Styling:         Tailwind CSS + a small design-token layer (PLN brand colors, dark mode)
Deployment:      Cloudflare Pages (frontend) + Render (backend) + GitHub (source + processed data)
```

**Why this beats "just use Streamlit"**: every one of the brief's harder requirements — synchronized cross-page filters, row-click-drills-into-detail-page, AG-Grid-grade tables, millions-of-rows performance, Power-BI-grade dark UI — is something Streamlit fights against structurally, while a FastAPI+React SPA is the native shape for all of them.

---

## 4. Architecture

### 4.1 High-level data & request flow

```
┌─────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  Raw Excel   │────▶│  Google Colab     │────▶│  Parquet datasets   │
│  (.xlsx)     │     │  ETL Pipeline     │     │  (partitioned by    │
│              │     │  (pandas)         │     │   month/dataset)    │
└─────────────┘     └──────────────────┘     └──────────┬─────────┘
                                                          │ git push
                                                          ▼
                                              ┌───────────────────────┐
                                              │  GitHub (processed/)  │
                                              └──────────┬────────────┘
                                                          │ pull on deploy/startup
                                                          ▼
                                       ┌─────────────────────────────────┐
                                       │  FastAPI backend (Render)        │
                                       │  - Auth (JWT)                    │
                                       │  - DuckDB query layer             │
                                       │  - Cached aggregation endpoints   │
                                       └─────────────────┬─────────────────┘
                                                          │ REST/JSON
                                                          ▼
                                       ┌─────────────────────────────────┐
                                       │  React SPA (Cloudflare Pages)    │
                                       │  Executive | DLPD | Suspect...   │
                                       └─────────────────────────────────┘
```

### 4.2 Clean Architecture layering (backend)

```
domain/        → pure business entities & rules (Suspect, DlpdCustomer, Reading) — no framework deps
application/    → use-cases ("GetSuspectSummary", "GetDetailTrend") — orchestrates repositories
infrastructure/ → DuckDB repository implementations, Parquet path resolvers, auth providers
interface/      → FastAPI routers, Pydantic request/response schemas
```
Dependencies point inward only (interface → application → domain; infrastructure implements domain-defined repository interfaces). This is what lets you add a new module (e.g. a future "Losses Analytics") by adding a new vertical slice without touching existing code — satisfies the brief's "no code changes for new months, modular for new modules" requirement.

### 4.3 Frontend module pattern

Each dashboard module (Executive, DLPD, Suspect Main/Summary/Detail) is a self-contained **feature folder**: its own API hooks, components, and page — never reaching into another feature's internals. Cross-page state (selected month, selected UNITUPI/UNITAP/UNITUP, selected suspect) lives in a small global **filter store** (Zustand) that any feature can read/write — this is what makes "select a suspect on Main Page → Detail Page opens on that month" work without prop-drilling.

---

## 5. Folder Structure

```
pln-analytics-platform/
│
├── backend/
│   ├── app/
│   │   ├── domain/
│   │   │   ├── entities/            # Suspect, DlpdRecord, InspectionRecord...
│   │   │   └── repositories/        # abstract interfaces (Protocol classes)
│   │   ├── application/
│   │   │   ├── use_cases/
│   │   │   │   ├── executive/
│   │   │   │   ├── dlpd/
│   │   │   │   └── suspect/
│   │   │   └── dto/                 # Pydantic schemas shared with interface layer
│   │   ├── infrastructure/
│   │   │   ├── duckdb/
│   │   │   │   ├── connection.py
│   │   │   │   └── repositories/    # concrete impls, one per dataset
│   │   │   ├── auth/                # JWT, password hashing
│   │   │   └── config/              # settings.py (env-driven)
│   │   ├── interface/
│   │   │   └── api/
│   │   │       ├── v1/
│   │   │       │   ├── executive.py
│   │   │       │   ├── dlpd.py
│   │   │       │   ├── suspect.py
│   │   │       │   └── auth.py
│   │   │       └── deps.py          # shared FastAPI dependencies
│   │   └── main.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── features/
│   │   │   ├── executive/
│   │   │   ├── dlpd-monitoring/
│   │   │   └── suspect-analytics/
│   │   │       ├── main/
│   │   │       ├── summary/
│   │   │       └── detail/
│   │   ├── shared/
│   │   │   ├── components/          # DataGrid wrapper, KpiCard, ChartCard...
│   │   │   ├── store/                # global filter store (Zustand)
│   │   │   ├── api/                  # typed API client
│   │   │   └── theme/                # dark mode tokens, PLN brand colors
│   │   ├── layouts/
│   │   ├── router/
│   │   └── App.tsx
│   ├── index.html
│   └── package.json
│
├── etl/
│   ├── notebooks/
│   │   └── monthly_etl.ipynb         # the Colab-run pipeline
│   ├── pipeline/
│   │   ├── discovery.py              # find & group files by month from filename
│   │   ├── readers/                  # one reader per source schema (DLPD prabayar/pascabayar, Pengecekan, ANEV)
│   │   ├── validators.py
│   │   ├── transformers/
│   │   └── writers/                  # Parquet writers, partitioning logic
│   └── config/
│       └── schema_registry.py        # expected columns per file type — validation source of truth
│
├── data/
│   ├── raw/                          # local staging only, NEVER committed/deployed
│   └── processed/                    # Parquet output, this is what ships to GitHub/backend
│
├── assets/                           # logo, brand assets
├── documentation/
├── config/                           # shared, non-secret config (env.example)
├── tests/
│   ├── backend/
│   ├── etl/
│   └── frontend/
└── deployment/
    ├── render.yaml
    ├── cloudflare-pages.toml
    └── github-actions/                # CI: lint, test, build on push
```

---

## 6. Dataset Design (from your provided schemas)

Mapping your four source schemas to platform modules:

| Source | Module(s) | Notes |
|---|---|---|
| **DLPD Pascabayar** (THBLREK, IDPEL, DLPD, DLPD_LM, DLPD_FKM, DLPD_KVARH, DLPD_3BLN...) | DLPD Monitoring | `THBLREK` drives month partitioning; `UNITAP`/`UNITUP` drive the org-hierarchy filters. |
| **DLPD Prabayar** (IDPEL, THBL, KRITERIA, BELI_TOKEN_AKHIR, STATUS_PERIKSA...) | DLPD Monitoring | Needs a union/reconciliation layer with Pascabayar since both feed "DLPD Monitoring" — recommend a unified `dlpd_customer` Parquet table with a `SEGMENT` (prepaid/postpaid) column produced in ETL. |
| **Pengecekan** (ID_P2TL, IDPEL, hasil pemeriksaan, banyak kolom teknis) | DLPD Monitoring (Customer Detail panel) | This is your "ground truth inspection result" table — joins to DLPD by IDPEL to populate the Customer Detail pane. |
| **17_ANEV_YYYYMMDD-YYYYMMDD.xlsx** (multi-file-per-month) | Suspect Analytics (Main/Summary/Detail) | Filename-derived month; the "SUSPECT_NAME", voltage/current/power-factor columns you listed for the Detail page map directly here — this is per-reading instant/timeseries data, the one needing DuckDB + Parquet partitioning most. |

**ETL month-detection rule** (from filename pattern `17_ANEV_YYYYMMDD-YYYYMMDD.xlsx` / the `17_ANNEV_...` variant seen in your file browser screenshot): extract the start-date's `YYYYMM` as the month key, group all files sharing that key, concatenate, dedupe on natural key (likely `IDPEL` + `READ_DATE`/timestamp), then write one partition per month. This handles the "one month = many files" requirement without any hardcoded month logic — new months just work.

---

## 7. Security

- JWT-based auth, no anonymous routes (all `/api/v1/*` behind `Depends(get_current_user)`).
- Backend only ever opens files under `data/processed/` — raw Excel never enters the backend container.
- Role field on user (e.g. `viewer`, `analyst`, `admin`) reserved now so row-level restriction (e.g. limit an analyst to their own UNITUPI) can be added later without a schema migration.
- Secrets (JWT signing key, any DB creds) via environment variables only, never committed — `config/env.example` documents required vars.

## 8. Performance

- DuckDB predicate pushdown on Parquet: month/unit filters happen inside the scan, not after loading into Python.
- Backend response caching (in-memory `functools.lru_cache` or `cachetools`, keyed by filter combination) for expensive aggregates (KPI cards, summary tables).
- AG Grid row virtualization on the frontend — DOM only holds visible rows regardless of dataset size.
- Server-side pagination for the Detail Page (never ship a 500k-row JSON payload to the browser).

---

## 9. Roadmap (incremental)

| Phase | Deliverable |
|---|---|
| **0 — done here** | Stack decision, architecture, folder scaffold, roadmap |
| **1** | Repo scaffold (empty but structured), ETL `discovery.py` + one reader (ANEV) proven against real files, Parquet output verified |
| **2** | FastAPI skeleton: auth, DuckDB connection layer, one working endpoint (Suspect Main page data) |
| **3** | React skeleton: routing, layout, dark theme tokens, login flow, first working page (Suspect Main) wired end-to-end |
| **4** | Suspect Analytics complete (Main → Summary → Detail, with trend charts, export) |
| **5** | DLPD Monitoring module (dashboard ULP + Customer Detail + Customer List, linked selection) |
| **6** | Executive Dashboard (KPI cards, all chart types, month-over-month trend) |
| **7** | Cross-cutting: global filter sync across all modules, caching, CSV/Excel export everywhere |
| **8** | Deployment: Render + Cloudflare Pages + GitHub Actions CI, smoke tests |
| **9+** | New modules added as vertical slices, following the same pattern |

---

## 10. What I'd need from you to start Phase 1

1. Confirm the stack above (or flag anything you want swapped).
2. Re-upload the three Excel files if you'd like me to validate the ETL reader against real data rather than the schemas alone.
3. Say which module you want built first — I'd suggest **Suspect Analytics** since it has the richest, most self-contained data (ANEV files) and proves the ETL month-merging logic earliest.
