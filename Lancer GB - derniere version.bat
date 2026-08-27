@echo off
REM ============================================================================
REM  Lance la DERNIERE version de l'application GB - Etats des lieux (v2.7.2+)
REM  DIRECTEMENT depuis le code source, SANS exe a compiler.
REM  -> l'antivirus Trend Micro ne bloque QUE les .exe : ici, rien a bloquer.
REM  Les donnees restent PARTAGEES sur le serveur (memes comptes / clients).
REM ============================================================================
set "GB_DONNEES_DIR=P:\Joris\GB Etats des lieux\GB Etats des lieux - donnees"
cd /d "P:\Joris\GB Etats des lieux\gb-etats-des-lieux"
start "" "P:\Joris\GB Etats des lieux\gb-etats-des-lieux\.venv\Scripts\pythonw.exe" "P:\Joris\GB Etats des lieux\gb-etats-des-lieux\app_desktop.py"
