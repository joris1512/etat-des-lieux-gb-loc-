@echo off
REM ================================================================
REM  Installe / met a jour le logiciel GB - Etats des lieux en LOCAL
REM  (dossier utilisateur, hors partage reseau - conforme audit RGPD).
REM  1. Construire d'abord :  build_exe.bat
REM  2. Puis double-cliquer ce script.
REM  Vos donnees (base clients) et votre cle API sont PRESERVEES.
REM ================================================================
setlocal
set "SRC=%~dp0..\dist\GB Etats des lieux"
set "DST=%LOCALAPPDATA%\GB Etats des lieux"
set "SAUVE=%TEMP%\gb_maj_sauvegarde"

if not exist "%SRC%\GB Etats des lieux.exe" (
  echo [ERREUR] Construisez d'abord le logiciel avec build_exe.bat
  pause & exit /b 1
)

echo Fermeture de l'application si ouverte...
taskkill /im "GB Etats des lieux.exe" /f >nul 2>&1

echo Preservation des donnees et de la cle...
if exist "%SAUVE%" rd /s /q "%SAUVE%"
md "%SAUVE%"
if exist "%DST%\_internal\runtime" xcopy /e /i /q "%DST%\_internal\runtime" "%SAUVE%\runtime" >nul
if exist "%DST%\_internal\.env" copy /y "%DST%\_internal\.env" "%SAUVE%\.env" >nul

echo Installation de la nouvelle version...
if exist "%DST%" rd /s /q "%DST%"
xcopy /e /i /q "%SRC%" "%DST%" >nul

echo Restauration des donnees et de la cle...
if exist "%SAUVE%\runtime" xcopy /e /i /q "%SAUVE%\runtime" "%DST%\_internal\runtime" >nul
if exist "%SAUVE%\.env" copy /y "%SAUVE%\.env" "%DST%\_internal\.env" >nul
rd /s /q "%SAUVE%" >nul 2>&1

echo Raccourci Bureau + demarrage automatique...
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$l = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\GB Etats des lieux.lnk');" ^
  "$l.TargetPath = '%DST%\GB Etats des lieux.exe'; $l.WorkingDirectory = '%DST%'; $l.Save();" ^
  "$v = 'Set sh = CreateObject(\"WScript.Shell\")' + [Environment]::NewLine + 'sh.Environment(\"PROCESS\")(\"GB_SERVEUR\") = \"1\"' + [Environment]::NewLine + 'sh.Environment(\"PROCESS\")(\"GB_PASSWORD\") = \"\"' + [Environment]::NewLine + 'sh.Run \"\"\"%DST%\GB Etats des lieux.exe\"\"\", 0, False';" ^
  "Set-Content -Path ([Environment]::GetFolderPath('Startup') + '\GB Etats des lieux (serveur).vbs') -Value $v -Encoding ASCII"

echo.
echo ============================================================
echo  Mise a jour terminee : %DST%
echo  Double-cliquez l'icone Bureau "GB Etats des lieux".
echo ============================================================
start "" "%DST%\GB Etats des lieux.exe"
endlocal
