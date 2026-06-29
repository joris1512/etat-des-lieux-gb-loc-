@echo off
REM ================================================================
REM  Demarrage AUTOMATIQUE du logiciel au demarrage du serveur.
REM  Utilise une tache planifiee Windows native (aucun outil a installer).
REM  Clic droit  >  "Executer en tant qu'administrateur".
REM ================================================================
setlocal
set "RACINE=%~dp0.."
for %%I in ("%RACINE%") do set "RACINE=%%~fI"
set "NOM=GB Etats des Lieux"

schtasks /Create /TN "%NOM%" /TR "\"%RACINE%\scripts\run_prod.bat\"" /SC ONSTART /RU SYSTEM /RL HIGHEST /F
if errorlevel 1 (
  echo [ERREUR] Echec de la creation de la tache.
  echo Relancez ce script en tant qu'Administrateur.
  pause
  exit /b 1
)

echo.
echo Tache "%NOM%" creee : le logiciel demarrera a chaque demarrage du serveur.
echo   - Demarrer maintenant sans reboot : schtasks /Run /TN "%NOM%"
echo   - Voir l'etat                     : schtasks /Query /TN "%NOM%"
echo   - Arreter l'execution             : schtasks /End  /TN "%NOM%"
echo   - Supprimer la tache              : schtasks /Delete /TN "%NOM%" /F
echo.
pause
endlocal
