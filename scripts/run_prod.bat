@echo off
REM Lancement en production (Windows) — sans rechargement auto, ecoute reseau.
setlocal
REM Resout le dossier racine du projet en chemin absolu propre (gere les espaces et le "..").
set "RACINE=%~dp0.."
for %%I in ("%RACINE%") do set "RACINE=%%~fI"
cd /d "%RACINE%"
if "%GB_HOST%"=="" set "GB_HOST=0.0.0.0"
if "%GB_PORT%"=="" set "GB_PORT=8000"
REM /!\ 0.0.0.0 expose l'appli sur TOUT le reseau : definissez GB_PASSWORD pour la proteger.
echo Demarrage sur http://%GB_HOST%:%GB_PORT%  (Ctrl+C pour arreter)
".venv\Scripts\python.exe" -m uvicorn app.main:app --host %GB_HOST% --port %GB_PORT%
endlocal
