@echo off
REM Ouvre GB - Etats des lieux en fenetre application (sans navigateur).
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" "app_desktop.py"
