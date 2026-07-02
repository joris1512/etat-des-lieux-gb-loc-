@echo off
REM Lancement en production (Windows) — sans rechargement auto, ecoute reseau.
setlocal
REM Resout le dossier racine du projet en chemin absolu propre (gere les espaces et le "..").
set "RACINE=%~dp0.."
for %%I in ("%RACINE%") do set "RACINE=%%~fI"
cd /d "%RACINE%"
REM Par defaut : ecoute LOCALE uniquement (RGPD art. 32 - donnees personnelles en base).
REM Pour ouvrir au LAN : set GB_HOST=0.0.0.0 explicitement, avec HTTPS (reverse proxy) devant.
if "%GB_HOST%"=="" set "GB_HOST=127.0.0.1"
if "%GB_PORT%"=="" set "GB_PORT=8000"
echo Demarrage sur http://%GB_HOST%:%GB_PORT%  (Ctrl+C pour arreter)
".venv\Scripts\python.exe" -m uvicorn app.main:app --host %GB_HOST% --port %GB_PORT%
endlocal
