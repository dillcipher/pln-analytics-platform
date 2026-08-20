# PLN Analytics Platform — Final Fix

## What is fixed

### DLPD Monitoring
- Dropdown periode di pojok kanan dihapus.
- **Prabayar:** filter **Bulan** berada di filter bar.
- **Pascabayar:** filter **Perulangan** berada di filter bar dan dihitung berdasarkan **distinct month occurrence** dalam 6 periode analisis.
- Periode analisis tetap ditampilkan sebagai konteks.
- Detail pelanggan mengembalikan field dengan kontrak frontend yang benar (lower-case), bukan raw uppercase DuckDB columns.
- Detail menampilkan IDPEL, identitas, unit, status pemeriksaan, hasil, tarif, daya, repeat, kategori, kendala, alamat, petugas, regu, waktu, catatan, dan riwayat pemeriksaan.
- Peta melakukan validasi koordinat Lampung, menangani X/Y terbalik, dan juga menormalisasi koordinat inspection yang tertukar.
- Batas peta frontend disamakan dengan backend: latitude -6.6..-3.7 dan longitude 103.0..106.5.

### Executive Dashboard
- Ditambahkan **Decision Cockpit**:
  - Inspection Gap
  - Finding Rate
  - Top ULP
  - Top Classification
  - Repeat Risk
- Ditambahkan Action Priorities yang menerjemahkan signal analytics menjadi tindakan operasional.

### Data Management
- Tidak lagi `Coming Soon`.
- Dataset Registry: jumlah dataset, rows, storage, status.
- ETL / Upload History.
- Refresh metadata.

### Settings
- Health/service status.
- Application dan environment.
- API base.
- Refresh Warehouse.
- Standar analytics: WGS84/EPSG:4326, UID Lampung, distinct-month repeat, latest inspection per IDPEL.

---

# INSTALL WINDOWS / POWERSHELL

## 1. Stop aplikasi lama

Tutup terminal Vite/Uvicorn yang sedang berjalan.

## 2. Backup source lama

```powershell
cd C:\Users\fadil\Documents

$backup = "C:\Users\fadil\Documents\pln-analytics-platform-before-final"
New-Item -ItemType Directory -Force $backup | Out-Null

robocopy `
  ".\pln-analytics-platform" `
  $backup `
  /E `
  /XD node_modules .venv data .git
```

## 3. Extract ZIP

Misalnya ZIP disimpan di Downloads:

```powershell
cd C:\Users\fadil\Documents

Remove-Item .\_final_revision -Recurse -Force -ErrorAction SilentlyContinue

Expand-Archive `
  "$HOME\Downloads\PLN_Analytics_FINAL_FIXED.zip" `
  -DestinationPath .\_final_revision `
  -Force
```

## 4. Copy revision

```powershell
robocopy `
  ".\_final_revision\pln-analytics-platform" `
  ".\pln-analytics-platform" `
  /E `
  /XD data .venv node_modules .git dist
```

**Jangan hapus `data`, `.venv`, atau `node_modules` project lama.** ZIP final memang tidak membawa ketiga folder tersebut.

---

# BACKEND

## 5. Aktifkan virtual environment lama

```powershell
cd C:\Users\fadil\Documents\pln-analytics-platform
.\.venv\Scripts\Activate.ps1
```

Jika environment ada di `backend\.venv`, gunakan:

```powershell
cd C:\Users\fadil\Documents\pln-analytics-platform\backend
.\.venv\Scripts\Activate.ps1
```

## 6. Pastikan dependency tersedia

```powershell
pip install -r requirements.txt
```

Jika requirements berada di backend:

```powershell
pip install -r .\backend\requirements.txt
```

## 7. Compile check

```powershell
python -m compileall .\backend\app
```

Harus selesai tanpa `SyntaxError`.

## 8. Jalankan FastAPI

```powershell
cd .\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Jangan tutup terminal ini.

---

# FRONTEND

## 9. Install dependency

Buka PowerShell baru:

```powershell
cd C:\Users\fadil\Documents\pln-analytics-platform\frontend
npm install
```

## 10. TypeScript check

```powershell
npx tsc --noEmit
```

Harus tidak ada error TypeScript.

## 11. Production build

```powershell
npm run build
```

Harus menghasilkan folder `dist`.

## 12. Jalankan frontend

```powershell
npm run dev
```

Buka:

```text
http://127.0.0.1:5173
```

---

# VERIFIKASI WAJIB

## API

```powershell
curl.exe "http://127.0.0.1:8000/health"
```

Kemudian:

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/dlpd/dashboard?customer_type=prabayar&month=202606"
```

**Jangan paste JSON hasil curl kembali ke PowerShell sebagai command.**

## DLPD

1. Pilih **Prabayar**.
2. Gunakan dropdown **Bulan** di filter bar.
3. Pastikan tidak ada dropdown bulan di pojok kanan.
4. Pilih pelanggan pada tabel.
5. Detail harus terisi, bukan `-` semua.
6. Pilih **Pascabayar**.
7. Pastikan filter **Perulangan** muncul.
8. Pilih nilai repeat dan pastikan tabel/KPI berubah.
9. Cek peta: titik harus berada di area Lampung, bukan di laut/negara lain.

## Data Management

Buka:

```text
/data-management
```

Harus menampilkan registry dataset dan history, bukan `Coming Soon`.

## Settings

Buka:

```text
/settings
```

Harus menampilkan service status dan analytics standard.

## Executive

Buka:

```text
/executive
```

Harus ada:

- KPI executive
- Decision Cockpit
- Action Priorities
- ANEV analytics
- Prabayar analytics
- Pascabayar repeat analytics
- Historical / operational analytics

---

# CATATAN KOORDINAT

Standar final:

```text
Coordinate system : WGS84 / EPSG:4326
Latitude          : -6.6 .. -3.7
Longitude         : 103.0 .. 106.5
```

Jika source Excel koordinat masih mentah / packed / X-Y terbalik, **jalankan ETL ulang setelah memasang revision ini** supaya transformer koordinat terbaru diterapkan ke dataset processed.

Urutannya:

```text
Upload source
   ↓
ETL / Process
   ↓
Warehouse refresh
   ↓
Buka DLPD
```

Jangan hanya mengganti frontend jika processed dataset masih berasal dari transformasi lama.

---

# BACKUP / ROLLBACK

Jika ada masalah:

```powershell
cd C:\Users\fadil\Documents

robocopy `
  ".\pln-analytics-platform-before-final" `
  ".\pln-analytics-platform" `
  /E
```

Backup dibuat sebelum revision final dicopy.
