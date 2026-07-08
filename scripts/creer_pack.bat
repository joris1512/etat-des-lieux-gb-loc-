@echo off
REM ================================================================
REM  Cree le PACK DE DISTRIBUTION : un zip a donner a n'importe quel
REM  poste Windows (dezipper -> INSTALLER.bat -> pret).
REM  Le pack ne contient NI donnees clients, NI cle API, NI logo
REM  personnalise (chaque poste renseigne sa cle a l'installation).
REM  Prerequis : avoir construit le logiciel avec build_exe.bat
REM ================================================================
setlocal
set "SRC=%~dp0..\dist\GB Etats des lieux"
set "PACK=%~dp0..\dist\pack"
set "ZIP=%~dp0..\dist\GB-Etats-des-lieux-installation.zip"

if not exist "%SRC%\GB Etats des lieux.exe" (
  echo [ERREUR] Construisez d'abord le logiciel avec build_exe.bat
  pause & exit /b 1
)

echo Preparation du pack (copie propre, sans donnees ni cle)...
if exist "%PACK%" rd /s /q "%PACK%"
md "%PACK%"
xcopy /e /i /q "%SRC%" "%PACK%\GB Etats des lieux" >nul
del /q "%PACK%\GB Etats des lieux\_internal\.env" 2>nul
del /q "%PACK%\GB Etats des lieux\_internal\app\static\logo_client.png" 2>nul
if exist "%PACK%\GB Etats des lieux\_internal\runtime" rd /s /q "%PACK%\GB Etats des lieux\_internal\runtime"
del /q "%PACK%\GB Etats des lieux\gb_erreur.log" 2>nul

copy /y "%~dp0INSTALLER.bat" "%PACK%\INSTALLER.bat" >nul
copy /y "%~dp0..\docs\GUIDE_UTILISATEUR.md" "%PACK%\GUIDE_UTILISATEUR.md" >nul

echo Compression...
if exist "%ZIP%" del /q "%ZIP%"
powershell -NoProfile -Command "Compress-Archive -Path '%PACK%\*' -DestinationPath '%ZIP%' -CompressionLevel Optimal"
rd /s /q "%PACK%"

echo.
echo ============================================================
echo  Pack pret :  %ZIP%
echo  A remettre au poste cible : dezipper, puis INSTALLER.bat
echo ============================================================
pause
endlocal
