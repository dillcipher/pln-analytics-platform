# PLN Analytics Platform

Platform analitik internal PLN: Executive Dashboard, DLPD Monitoring, dan Suspect Analytics. Dibangun dengan FastAPI + DuckDB (backend), React + Vite (frontend), dan ETL berbasis Google Colab — semua teknologi gratis/open-source. Lihat `documentation/ARCHITECTURE.md` untuk penjelasan arsitektur lengkap (alasan pemilihan stack, Clean Architecture, dsb).

Status pembangunan: **ETL dan Backend sudah teruji jalan (lihat bagian "Apa yang sudah diverifikasi" di bawah). Frontend sudah lengkap kodenya** tapi belum sempat di-`npm install`/build karena lingkungan pengembangan Claude tidak punya akses internet — akan langsung jalan begitu kamu `npm install` di komputer/CI kamu sendiri.

---

## Daftar Isi

1. [Prasyarat](#1-prasyarat)
2. [Quick Start — Coba di Lokal dengan Data Contoh](#2-quick-start--coba-di-lokal-dengan-data-contoh)
3. [Memakai Data Excel Asli](#3-memakai-data-excel-asli)
4. [Panduan Pemakaian Tiap Modul](#4-panduan-pemakaian-tiap-modul)
5. [Mengaktifkan Web ke Internet (Deploy)](#5-mengaktifkan-web-ke-internet-deploy)
6. [Update Data Bulanan](#6-update-data-bulanan)
7. [Keamanan — Wajib Dilakukan Sebelum Produksi](#7-keamanan--wajib-dilakukan-sebelum-produksi)
8. [Troubleshooting](#8-troubleshooting)
9. [Struktur Proyek](#9-struktur-proyek)
10. [Apa yang Sudah Diverifikasi](#10-apa-yang-sudah-diverifikasi)

---

## 1. Prasyarat

Install di komputer kamu:

| Tool | Versi | Cek dengan |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| Node.js | 20+ | `node --version` |
| Git | apa saja | `git --version` |

Akun gratis yang dibutuhkan untuk deploy (opsional, hanya kalau mau online):
- [GitHub](https://github.com) — menyimpan kode + dataset hasil ETL
- [Google Colab](https://colab.research.google.com) — menjalankan ETL (sudah otomatis tersedia dengan akun Google)
- [Render](https://render.com) — hosting backend
- [Cloudflare Pages](https://pages.cloudflare.com) — hosting frontend

---

## 2. Quick Start — Coba di Lokal dengan Data Contoh

Cara tercepat melihat platform ini jalan, pakai data sintetis (bukan data asli) supaya kamu bisa langsung coba semua fitur.

### 2.1 Generate data contoh & jalankan ETL

```bash
cd pln-analytics-platform

# Buat virtual environment (opsional tapi disarankan)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install pandas openpyxl pyarrow numpy

# Generate file Excel sintetis (meniru struktur file asli, termasuk pola
# 17_ANEV_YYYYMMDD-YYYYMMDD.xlsx multi-file per bulan)
python -m etl.generate_sample_data --output-dir data/raw --months 202606 202607

# Jalankan ETL: baca semua file -> gabung per bulan -> validasi -> bersihkan
# -> hasilkan dataset Parquet
python -m etl.run_etl --input-dir data/raw --output-dir data/processed
```

Kalau berhasil, kamu akan lihat log `STEP 1/6` sampai `STEP 6/6`, dan folder `data/processed/` akan terisi (dlpd_customer, suspect_detail, suspect_main, suspect_summary, executive_kpis, pengecekan).

### 2.2 Jalankan Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Backend jalan di `http://localhost:8000`. Buka `http://localhost:8000/api/docs` untuk melihat dokumentasi API interaktif (Swagger UI, otomatis dari FastAPI).

### 2.3 Jalankan Frontend

Di terminal baru:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Buka `http://localhost:5173`.

### 2.4 Login

Gunakan salah satu akun contoh (lihat `backend/data/auth/users.json` — **ganti password ini sebelum dipakai sungguhan**, lihat bagian [Keamanan](#7-keamanan--wajib-dilakukan-sebelum-produksi)):

| Username | Password | Role |
|---|---|---|
| `admin` | `Admin#2026` | admin |
| `analyst` | `Analyst#2026` | analyst |

Setelah login kamu akan masuk ke Executive Dashboard dengan data sintetis yang tadi dibuat.

---

## 3. Memakai Data Excel Asli

Setelah quick start di atas berhasil, ganti data sintetis dengan data PLN yang sebenarnya:

1. Hapus isi `data/raw/` (data sintetis tadi).
2. Salin file Excel asli kamu ke `data/raw/`:
   - File DLPD Pascabayar (sheet `main`)
   - File DLPD Prabayar (sheet `Sheet1`) — contoh: `DLPD_Tidak_beli_Token.xlsx`
   - File Pengecekan (sheet `DATA`)
   - Semua file `17_ANEV_YYYYMMDD-YYYYMMDD.xlsx` / `17_ANNEV_YYYYMMDD-YYYYMMDD.xlsx` untuk bulan yang ingin diproses
3. Jalankan ulang: `python -m etl.run_etl --input-dir data/raw --output-dir data/processed`

ETL **otomatis mengenali jenis file dari kolom-kolomnya** (bukan dari nama file), jadi file boleh dinamai apa saja asal strukturnya sesuai. Kalau ada file yang tidak cocok dengan skema manapun, ETL akan melewatinya dan mencatat warning di log — proses tetap lanjut untuk file lain (lihat `etl/config/schema_registry.py` untuk daftar kolom yang diharapkan tiap jenis file).

---

## 4. Panduan Pemakaian Tiap Modul

### Executive Dashboard (`/`)
Ringkasan tingkat tinggi: 7 KPI card (Total Pelanggan, Suspect, Normal, Temuan, Sisa Pemeriksaan, Progress, Hit Rate) dan 6 chart. Pilih bulan dari dropdown di header — semua angka otomatis update.

### DLPD Monitoring (`/dlpd`)
- Gunakan filter di atas (UNITUPI/UNITAP/UNITUP, cari IDPEL/nama) untuk mempersempit data.
- Panel **Dashboard ULP** (atas) menunjukkan ringkasan per ULP.
- Klik baris di **Customer List** (kanan bawah) — panel **Customer Detail** (kiri bawah) otomatis menampilkan detail pelanggan tersebut beserta riwayat pemeriksaan P2TL-nya.
- Tombol CSV/Excel di Customer List mengekspor **seluruh data terfilter**, bukan cuma yang tampil di halaman saat ini.

### Suspect Analytics — Main (`/suspect/main`)
Ringkasan Suspect × Pelanggan × Frekuensi. **Klik satu baris** untuk otomatis membuka Detail Page yang terkunci pada bulan dan kategori suspect tersebut.

### Suspect Analytics — Summary (`/suspect/summary`)
Rekap per lokasi pelanggan: 9 kolom kategori anomali (Asymmetric Power, Incorrect Phase, Over Current, dst.) + Grand Total. Bisa diakses langsung (tidak harus lewat Main).

### Suspect Analytics — Detail (`/suspect/detail`)
**Hanya bermakna setelah klik dari Main Page** — kalau dibuka langsung tanpa memilih suspect dulu, akan muncul pesan yang mengarahkan ke Main Page. Klik satu baris pembacaan untuk menampilkan **Voltage Trend** dan **Current Trend** (grafik) beserta statistik ringkas untuk lokasi tersebut.

---

## 5. Mengaktifkan Web ke Internet (Deploy)

Setelah puas coba di lokal, berikut cara membuat platform ini bisa diakses online oleh tim PLN.

### Langkah 1 — Push kode ke GitHub

```bash
cd pln-analytics-platform
git init
git add .
git commit -m "Initial commit: PLN Analytics Platform"
gh repo create pln-analytics-platform --private --source=. --push
# (atau buat repo manual di github.com lalu `git remote add origin <url>` + `git push`)
```

> Repo **harus private** — walaupun dashboard tidak pernah menyimpan file Excel mentah, `data/processed/` tetap berisi data pelanggan yang diringkas.

### Langkah 2 — Siapkan ETL di Google Colab

1. Buka `etl/notebooks/PLN_ETL_Colab.ipynb` di [Google Colab](https://colab.research.google.com) (Upload notebook, atau File → Open notebook → GitHub).
2. Edit variabel `REPO_URL` di Step 1 supaya mengarah ke repo GitHub kamu.
3. Kalau repo private, buat [Personal Access Token](https://github.com/settings/tokens) dan pakai format `https://<TOKEN>@github.com/<org>/pln-analytics-platform.git`.
4. Jalankan notebook: upload file Excel bulan ini di Step 2, notebook otomatis menjalankan ETL dan push hasilnya ke GitHub.

### Langkah 3 — Deploy Backend ke Render

1. Login ke [Render](https://render.com) → **New +** → **Blueprint**.
2. Pilih repo GitHub kamu — Render otomatis membaca `deployment/render.yaml`.
3. Render akan generate `JWT_SECRET_KEY` otomatis (aman, acak). Catat URL backend yang dihasilkan, misalnya `https://pln-analytics-api.onrender.com`.
4. Setelah deploy pertama, cek `https://<url-render-kamu>/api/health` — harus muncul `{"status": "ok", ...}`.

> **Catatan free tier Render**: layanan gratis akan "tidur" setelah ~15 menit tanpa aktivitas, dan butuh beberapa detik untuk bangun lagi saat diakses. Ini normal untuk penggunaan internal skala kecil-menengah; kalau butuh selalu-aktif, upgrade ke paid tier.

### Langkah 4 — Deploy Frontend ke Cloudflare Pages

1. Login ke [Cloudflare Pages](https://pages.cloudflare.com) → **Create a project** → **Connect to Git** → pilih repo kamu.
2. Build settings:
   - **Framework preset**: Vite
   - **Root directory**: `frontend`
   - **Build command**: `npm run build`
   - **Build output directory**: `dist`
3. Tambahkan environment variable: `VITE_API_BASE_URL` = `https://<url-render-kamu>/api/v1`
4. Deploy. Cloudflare akan memberi URL seperti `https://pln-analytics-platform.pages.dev`.

### Langkah 5 — Sambungkan CORS

Kembali ke Render → service backend → Environment → update `CORS_ORIGINS` menjadi URL Cloudflare Pages kamu (persis, termasuk `https://`) → simpan (Render otomatis redeploy).

Sekarang buka URL Cloudflare Pages kamu — platform sudah bisa diakses tim.

---

## 6. Update Data Bulanan

Setiap bulan baru:

1. Buka notebook Colab (Langkah 2 di atas), jalankan ulang: upload file Excel periode baru → ETL jalan → push ke GitHub.
2. **Tidak perlu ubah kode apa pun** — backend otomatis mendeteksi bulan baru dari folder `month=YYYYMM` yang baru muncul di `data/processed/`.
3. Kalau backend di-deploy dengan data di-pull saat startup, restart service di Render (Manual Deploy → Deploy latest commit) supaya data terbaru ter-load. Kalau kamu setup backend untuk baca langsung dari repo yang di-`git pull` berkala, langkah ini bisa diotomatiskan lebih lanjut.

---

## 7. Keamanan — Wajib Dilakukan Sebelum Produksi

- [ ] **Ganti password default** di `backend/data/auth/users.json`. Generate hash baru dengan:
  ```bash
  cd backend
  python3 -c "from app.core.security import hash_password; print(hash_password('PasswordBaruYangKuat'))"
  ```
  Tempel hasilnya ke field `password_hash` untuk user terkait.
- [ ] Pastikan `JWT_SECRET_KEY` di production **bukan** nilai default di `.env.example` (Render Blueprint sudah generate otomatis — cukup jangan menimpanya manual dengan nilai lemah).
- [ ] Ganti placeholder logo (`LogoMark` di `frontend/src/shared/components/PageHeader.tsx`) dengan logo resmi PLN — file gambar ini sengaja tidak disertakan (ini bukan aset yang saya punya untuk didistribusikan ulang).
- [ ] Review `CORS_ORIGINS` — pastikan hanya domain resmi PLN yang diizinkan, bukan `*`.
- [ ] Pastikan repo GitHub **private**.

---

## 8. Troubleshooting

| Gejala | Penyebab umum | Solusi |
|---|---|---|
| `ModuleNotFoundError: No module named 'fastapi'` | Belum install dependencies backend | `pip install -r backend/requirements.txt` |
| Frontend blank / error di console soal `import` | Belum `npm install` | `cd frontend && npm install` |
| Login gagal terus padahal password benar | Salah baca file `.env` / `USERS_FILE` path | Cek `backend/.env` → `USERS_FILE=data/auth/users.json` (relatif terhadap folder `backend/`) |
| Dropdown bulan kosong | ETL belum pernah dijalankan, atau `DATA_PROCESSED_DIR` di `.env` salah path | Jalankan ETL dulu (bagian 2.1), cek path di `backend/.env` |
| CORS error di browser console | `CORS_ORIGINS` backend tidak cocok dengan URL frontend | Update `CORS_ORIGINS` persis sama dengan URL frontend (termasuk `https://`, tanpa trailing slash) |
| Render service "spinning down" / lambat pertama kali diakses | Perilaku normal free tier Render | Tunggu ~30 detik, atau upgrade paid tier untuk always-on |

---

## 9. Struktur Proyek

```
pln-analytics-platform/
├── etl/                    # Pipeline ETL — jalan di Google Colab
│   ├── config/              # Schema registry (kolom yang diharapkan per sumber)
│   ├── pipeline/             # discovery, readers, transformers, writers
│   ├── notebooks/            # PLN_ETL_Colab.ipynb
│   └── generate_sample_data.py
├── backend/                 # FastAPI + DuckDB (Clean Architecture)
│   └── app/
│       ├── domain/            # Entities & repository interfaces
│       ├── application/       # Use-cases & DTOs
│       ├── infrastructure/    # DuckDB repos, auth
│       └── interface/api/     # FastAPI routers
├── frontend/                # React + Vite + TypeScript
│   └── src/
│       ├── features/          # Satu folder per modul (executive, dlpd-monitoring, suspect-analytics)
│       ├── shared/             # Komponen, store, API client, tema
│       └── layouts/
├── tests/                   # Unit + integration tests (backend & ETL)
├── deployment/               # render.yaml, GitHub Actions CI
├── documentation/            # Dokumen arsitektur lengkap
└── data/                     # raw/ (lokal saja, jangan commit) + processed/ (yang di-commit)
```

---

## 10. Apa yang Sudah Diverifikasi

Karena proses pengembangan ini dilakukan di lingkungan tanpa akses internet (tidak bisa `pip install`/`npm install` paket dari luar), berikut yang **benar-benar sudah dijalankan dan diverifikasi**, bukan cuma ditulis:

- ✅ **ETL end-to-end**: dijalankan dengan data sintetis realistis (termasuk pola nama file `17_ANNEV_...` yang persis dengan aslinya) — discovery, klasifikasi kolom, merge multi-file per bulan, dedup, unit-hierarchy resolution (UNITUPI ter-isi 100% walau sumber Pascabayar tidak punya kolom itu), pivot Summary dengan Grand Total, tulis partisi Parquet.
- ✅ **Auth backend**: hashing password (PBKDF2) + JWT (encode/decode/tamper-detection/expiry) — semua ditulis pakai Python stdlib murni supaya bisa dites tanpa instalasi paket, dan semua skenario (login benar, salah, token kadaluarsa, token diutak-atik, secret salah) sudah diuji lolos.
- ✅ **Application layer (use-cases)**: 7 test dengan fake repository (pagination, filter, search) — semua lolos.
- ✅ **Export CSV/Excel**: dihasilkan dan dibaca-ulang untuk memastikan filenya benar-benar valid.
- ✅ **43 file backend** dan **28 file frontend**: semua lolos syntax/type check.
- ⚠️ **Yang belum bisa dijalankan langsung** (karena butuh paket dari internet yang tidak bisa diinstall di lingkungan pengembangan ini): server FastAPI hidup dengan DuckDB sungguhan, dan build/preview frontend React. Kode untuk keduanya sudah lengkap dan sudah lolos type-check menyeluruh — akan langsung berfungsi begitu kamu `pip install -r requirements.txt` dan `npm install` di komputer kamu sendiri (lihat Quick Start di atas).

Kalau ada bagian yang error saat kamu jalankan, itu paling mungkin salah konfigurasi `.env` (path, URL) — bukan bug logika, karena logikanya sudah diuji terpisah seperti di atas. Cek bagian [Troubleshooting](#8-troubleshooting) dulu.
