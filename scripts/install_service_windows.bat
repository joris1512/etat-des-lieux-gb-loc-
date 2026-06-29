@echo off
REM ============================================================================
REM  Installe l'appli comme SERVICE Windows (redemarrage auto au boot / crash).
REM  Prerequis :
REM    1) NSSM installe et accessible (https://nssm.cc) — nssm.exe dans le PATH.
REM    2) Environnement prepare : .venv cree + pip install -r requirements.txt
REM    3) .env renseigne (ANTHROPIC_API_KEY, GB_PASSWORD, GB_HOST, GB_PORT...).
REM  Lancer ce script dans une invite "Administrateur".
REM ============================================================================
setlocal
REM Resout le dossier racine en chemin absolu propre (gere les espaces et le "..").
set "RACINE=%~dp0.."
for %%I in ("%RACINE%") do set "RACINE=%%~fI"
set "PYTHON=%RACINE%\.venv\Scripts\python.exe"
set "NOM=GBEtatsDesLieux"
if "%GB_HOST%"=="" set "GB_HOST=0.0.0.0"
if "%GB_PORT%"=="" set "GB_PORT=8000"
REM /!\ 0.0.0.0 expose l'appli sur tout le reseau : definissez GB_PASSWORD dans .env.

if not exist "%PYTHON%" (
  echo [ERREUR] Environnement introuvable : %PYTHON%
  echo Creez-le d'abord :  py -3.12 -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)

REM Programme et parametres separes (idiome NSSM correct).
nssm install %NOM% "%PYTHON%"
nssm set %NOM% AppParameters "-m uvicorn app.main:app --host %GB_HOST% --port %GB_PORT%"
nssm set %NOM% AppDirectory "%RACINE%"
nssm set %NOM% AppStdout "%RACINE%\runtime\service.log"
nssm set %NOM% AppStderr "%RACINE%\runtime\service.log"
nssm set %NOM% Start SERVICE_AUTO_START
nssm start %NOM%

echo.
echo Service "%NOM%" installe et demarre sur http://%GB_HOST%:%GB_PORT%
echo   - Etat    : nssm status %NOM%
echo   - Arret   : nssm stop %NOM%
echo   - Retrait : nssm remove %NOM% confirm
endlocal
