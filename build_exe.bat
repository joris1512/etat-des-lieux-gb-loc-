@echo off
REM ================================================================
REM  Construit le LOGICIEL AUTONOME (.exe) de GB - Etats des lieux.
REM  Resultat : dist\GB Etats des lieux\  (dossier a copier tel quel
REM  sur n'importe quel PC Windows ; double-clic sur le .exe).
REM ================================================================
cd /d "%~dp0"
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --onedir --windowed --name "GB Etats des lieux" ^
 --add-data "templates;templates" ^
 --add-data "config;config" ^
 --add-data "fixtures;fixtures" ^
 --add-data "correspondances.csv;." ^
 --add-data "app\templates_html;app\templates_html" ^
 --add-data "app\static;app\static" ^
 --collect-all uvicorn ^
 --collect-all anthropic ^
 --hidden-import app.main ^
 "app_desktop.py"
echo.
echo ============================================================
echo  Termine. Logiciel dans :  dist\GB Etats des lieux\
echo  Double-cliquez sur  "GB Etats des lieux.exe"
echo ============================================================
pause
