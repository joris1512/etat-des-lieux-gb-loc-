@echo off
REM ================================================================
REM  Installateur GB - Etats des Lieux (serveur Windows).
REM  Clic droit  >  "Executer en tant qu'administrateur"
REM  (l'admin permet d'ouvrir le pare-feu pour l'acces reseau).
REM ================================================================
setlocal
set "RACINE=%~dp0.."
for %%I in ("%RACINE%") do set "RACINE=%%~fI"
cd /d "%RACINE%"

echo ============================================
echo   Installation GB - Etats des Lieux
echo   Dossier : %RACINE%
echo ============================================
echo.

REM --- 1. Python present ? ---
where py >nul 2>&1 || where python >nul 2>&1
if errorlevel 1 (
  echo [ERREUR] Python introuvable.
  echo Installez Python 3.12 ou plus : https://www.python.org/downloads/windows/
  echo Pendant l'installation, COCHEZ "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

REM --- 2. Environnement virtuel + dependances ---
if not exist ".venv\Scripts\python.exe" (
  echo Creation de l'environnement Python...
  py -3.12 -m venv .venv 2>nul || py -m venv .venv 2>nul || python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo [ERREUR] Impossible de creer l'environnement .venv
  pause
  exit /b 1
)
echo Installation des dependances...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt

REM --- 3. Fichier .env ---
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo Un fichier .env a ete cree. Renseignez ANTHROPIC_API_KEY et GB_PASSWORD,
  echo puis enregistrez et fermez le bloc-notes pour continuer.
  pause
  notepad ".env"
)

REM --- 4. Modeles factices si templates vide ---
dir /b "templates\*.xlsx" >nul 2>&1
if errorlevel 1 (
  echo Generation de modeles factices provisoires...
  ".venv\Scripts\python.exe" scripts\make_placeholder_templates.py
)

REM --- 5. Pare-feu (necessite admin) ---
if "%GB_PORT%"=="" set "GB_PORT=8000"
netsh advfirewall firewall add rule name="GB Etats des Lieux" dir=in action=allow protocol=TCP localport=%GB_PORT% >nul 2>&1
if errorlevel 1 (
  echo [INFO] Regle de pare-feu non ajoutee. Relancez en Administrateur pour autoriser
  echo        l'acces depuis les autres postes du reseau sur le port %GB_PORT%.
) else (
  echo Pare-feu : port %GB_PORT% autorise.
)

REM --- 6. Diagnostic ---
echo.
".venv\Scripts\python.exe" scripts\diagnostic.py

echo.
echo ============================================
echo  Installation terminee.
echo   - Demarrer maintenant    : scripts\run_prod.bat
echo   - Demarrage auto au boot : scripts\demarrer_au_demarrage.bat  (Administrateur)
echo   - Adresse locale         : http://localhost:%GB_PORT%
echo ============================================
pause
endlocal
