@echo off
taskkill /FI "WINDOWTITLE eq PLN Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq PLN Frontend*" /T /F >nul 2>&1
echo PLN Analytics processes stopped.
pause
