@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo PLN Analytics Platform - Local Runner
echo ===============================================

if not exist "backend\.venv\Scripts\python.exe" (
  echo Backend virtualenv not found.
  echo Create it with:
  echo   python -m venv backend\.venv
  echo   backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
  pause
  exit /b 1
)

if not exist "frontend\node_modules" (
  echo Installing frontend dependencies...
  pushd frontend
  call npm install
  if errorlevel 1 (
    popd
    echo Frontend dependency installation failed.
    pause
    exit /b 1
  )
  popd
)

start "PLN Backend" /D "%~dp0backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
timeout /t 2 /nobreak >nul
start "PLN Frontend" /D "%~dp0frontend" cmd /k "npm run dev"
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:5173/

echo Backend : http://127.0.0.1:8000
 echo Frontend: http://127.0.0.1:5173
 echo.
echo Keep the two terminal windows open.
endlocal
