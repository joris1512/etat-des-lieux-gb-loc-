@echo off
title Creation du raccourci Bureau
set "GBAPP=%~dp0"
if "%GBAPP:~-1%"=="\\" set "GBAPP=%GBAPP:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$dossier = $env:GBAPP;" ^
  "$exe = Join-Path $dossier 'GB Etats des lieux.exe';" ^
  "if (-not (Test-Path $exe)) { Write-Host '[ERREUR] exe introuvable a cote de ce script.'; exit 1 };" ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$l = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Application Etat des lieux.lnk');" ^
  "$l.TargetPath = $exe; $l.WorkingDirectory = $dossier; $l.IconLocation = ($exe + ',0');" ^
  "$l.Description = 'Application Etat des lieux - GB Location'; $l.Save();" ^
  "Write-Host 'Raccourci cree sur le Bureau : Application Etat des lieux (logo GB)'"
pause
