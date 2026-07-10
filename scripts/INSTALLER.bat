@echo off
REM ================================================================
REM  INSTALLATION de GB - Etats des lieux sur CE poste.
REM  (fourni dans le pack de distribution - a lancer apres dezippage)
REM  Installe dans le dossier utilisateur local, cree l'icone Bureau
REM  et le demarrage automatique. Ne demande aucun droit administrateur.
REM ================================================================
setlocal
set "SRC=%~dp0GB Etats des lieux"
set "DST=%LOCALAPPDATA%\GB Etats des lieux"

if not exist "%SRC%\GB Etats des lieux.exe" (
  echo [ERREUR] Dossier "GB Etats des lieux" introuvable a cote de ce script.
  echo Dezippez le pack complet avant de lancer INSTALLER.bat
  pause & exit /b 1
)

echo Fermeture d'une eventuelle instance...
taskkill /im "GB Etats des lieux.exe" /f >nul 2>&1
timeout /t 3 /nobreak >nul

if exist "%DST%\_internal\runtime" (
  echo Mise a jour : donnees et cle existantes PRESERVEES.
  set "MAJ=1"
  if exist "%TEMP%\gb_install_sauve" rd /s /q "%TEMP%\gb_install_sauve"
  md "%TEMP%\gb_install_sauve"
  xcopy /e /i /q "%DST%\_internal\runtime" "%TEMP%\gb_install_sauve\runtime" >nul
  if exist "%DST%\_internal\.env" copy /y "%DST%\_internal\.env" "%TEMP%\gb_install_sauve\.env" >nul
  if exist "%DST%\_internal\app\static\logo_client.png" copy /y "%DST%\_internal\app\static\logo_client.png" "%TEMP%\gb_install_sauve\logo_client.png" >nul
)

echo Installation...
if exist "%DST%" rd /s /q "%DST%"
xcopy /e /i /q "%SRC%" "%DST%" >nul
if not exist "%DST%\GB Etats des lieux.exe" (
  echo [ERREUR] Copie incomplete - fermez toute instance et relancez ce script.
  pause & exit /b 1
)

if defined MAJ (
  if exist "%TEMP%\gb_install_sauve\runtime" xcopy /e /i /q "%TEMP%\gb_install_sauve\runtime" "%DST%\_internal\runtime" >nul
  if exist "%TEMP%\gb_install_sauve\.env" copy /y "%TEMP%\gb_install_sauve\.env" "%DST%\_internal\.env" >nul
  if exist "%TEMP%\gb_install_sauve\logo_client.png" copy /y "%TEMP%\gb_install_sauve\logo_client.png" "%DST%\_internal\app\static\logo_client.png" >nul
  rd /s /q "%TEMP%\gb_install_sauve" >nul 2>&1
)

if not exist "%DST%\_internal\.env" (
  echo.
  echo --- Cle d'extraction des devis PDF ---
  echo Sans cle, le logiciel fonctionne mais ne peut pas lire de nouveaux devis.
  set /p CLEAPI=Collez la cle API puis Entree (ou Entree pour passer) :
  if defined CLEAPI (
    > "%DST%\_internal\.env" echo # Cle d'extraction (poste local).
    >> "%DST%\_internal\.env" echo ANTHROPIC_API_KEY=%CLEAPI%
    >> "%DST%\_internal\.env" echo GB_MODEL=claude-opus-4-8
    echo Cle enregistree.
  )
)

echo Icone Bureau + demarrage automatique...
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$l = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Application Etat des lieux.lnk');" ^
  "$l.TargetPath = '%DST%\GB Etats des lieux.exe'; $l.WorkingDirectory = '%DST%'; $l.Save();" ^
  "$v = 'Set sh = CreateObject(\"WScript.Shell\")' + [Environment]::NewLine + 'sh.Environment(\"PROCESS\")(\"GB_SERVEUR\") = \"1\"' + [Environment]::NewLine + 'sh.Environment(\"PROCESS\")(\"GB_PASSWORD\") = \"\"' + [Environment]::NewLine + 'sh.Run \"\"\"%DST%\GB Etats des lieux.exe\"\"\", 0, False';" ^
  "Set-Content -Path ([Environment]::GetFolderPath('Startup') + '\GB Etats des lieux (serveur).vbs') -Value $v -Encoding ASCII"

echo.
echo ============================================================
echo  Installation terminee.
echo  Double-cliquez l'icone Bureau "GB Etats des lieux".
echo  Guide : GUIDE_UTILISATEUR.md (dans ce dossier)
echo ============================================================
start "" "%DST%\GB Etats des lieux.exe"
endlocal
