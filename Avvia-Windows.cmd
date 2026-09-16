@echo off
cd /d "%~dp0"
py -3 app.py 2>nul || python app.py
pause
