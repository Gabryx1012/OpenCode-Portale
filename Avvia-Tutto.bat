@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap-windows.ps1"
if errorlevel 1 (
  echo.
  echo Avvio non riuscito. Leggi l'errore qui sopra e premi un tasto per chiudere.
  pause >nul
  exit /b 1
)
endlocal
