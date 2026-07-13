# Installation de l'Application Etat des lieux (a executer par l'utilisateur).
$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot 'GB Etats des lieux'
$dst = Join-Path $env:LOCALAPPDATA 'GB Etats des lieux'
$donnees = Join-Path $env:LOCALAPPDATA 'GB Etats des lieux - donnees'

Write-Host ''
Write-Host '================================================='
Write-Host '   Installation : Application Etat des lieux'
Write-Host '================================================='
try {
    if (-not (Test-Path (Join-Path $src 'GB Etats des lieux.exe'))) {
        throw "Dossier 'GB Etats des lieux' introuvable a cote du script. Dezippez le pack COMPLET puis relancez."
    }

    Write-Host '1/5  Fermeture d''une eventuelle instance...'
    Stop-Process -Name 'GB Etats des lieux' -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3

    $sauve = $null
    if (Test-Path (Join-Path $dst '_internal\runtime')) {
        Write-Host '2/5  Ancienne version detectee : preservation des donnees...'
        $sauve = Join-Path $env:TEMP ('gb_sauve_' + (Get-Date -Format 'HHmmss'))
        New-Item -ItemType Directory -Force $sauve | Out-Null
        Copy-Item (Join-Path $dst '_internal\runtime') (Join-Path $sauve 'runtime') -Recurse -Force
        if (Test-Path (Join-Path $dst '_internal\.env')) { Copy-Item (Join-Path $dst '_internal\.env') (Join-Path $sauve '.env') -Force }
        if (Test-Path (Join-Path $dst '_internal\app\static\logo_client.png')) { Copy-Item (Join-Path $dst '_internal\app\static\logo_client.png') (Join-Path $sauve 'logo_client.png') -Force }
    } else {
        Write-Host '2/5  Nouvelle installation.'
    }

    Write-Host '3/5  Copie du programme (1 a 2 minutes)...'
    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
    Copy-Item $src $dst -Recurse -Force
    $n1 = (Get-ChildItem $src -Recurse -File | Measure-Object).Count
    $n2 = (Get-ChildItem $dst -Recurse -File | Measure-Object).Count
    if ($n2 -lt $n1) { throw "Copie incomplete ($n2/$n1 fichiers). Fermez toute instance et relancez." }

    if ($sauve) {
        if (Test-Path (Join-Path $sauve 'runtime')) { Copy-Item (Join-Path $sauve 'runtime') (Join-Path $dst '_internal\runtime') -Recurse -Force }
        if (Test-Path (Join-Path $sauve '.env')) { Copy-Item (Join-Path $sauve '.env') (Join-Path $dst '_internal\.env') -Force }
        if (Test-Path (Join-Path $sauve 'logo_client.png')) { Copy-Item (Join-Path $sauve 'logo_client.png') (Join-Path $dst '_internal\app\static\logo_client.png') -Force }
        Remove-Item $sauve -Recurse -Force
    }

    $envProg = Join-Path $dst '_internal\.env'
    $envDonnees = Join-Path $donnees '.env'
    if ((Test-Path $envProg) -or (Test-Path $envDonnees)) {
        Write-Host '4/5  Cle API deja en place : conservee.'
    } else {
        Write-Host ''
        Write-Host '4/5  --- Cle de lecture des devis PDF ---'
        Write-Host '     Collez la cle puis Entree. (Entree seul = passer, le logiciel'
        Write-Host '     marchera mais ne pourra pas lire de nouveaux devis.)'
        $cle = Read-Host '     Cle'
        if ($cle) {
            $contenu = "# Cle d'extraction - poste local.`r`nANTHROPIC_API_KEY=$cle`r`nGB_MODEL=claude-opus-4-8"
            Set-Content -Path $envProg -Value $contenu -Encoding ASCII
            Write-Host '     Cle enregistree.'
        }
    }

    Write-Host '5/5  Icone Bureau + menu Demarrer + demarrage automatique...'
    $exe = Join-Path $dst 'GB Etats des lieux.exe'
    $ws = New-Object -ComObject WScript.Shell
    foreach ($dossier in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
        $l = $ws.CreateShortcut((Join-Path $dossier 'Application Etat des lieux.lnk'))
        $l.TargetPath = $exe
        $l.WorkingDirectory = $dst
        $l.IconLocation = "$exe,0"
        $l.Description = 'Application Etat des lieux - GB Location'
        $l.Save()
    }
    $vbs = @'
Set sh = CreateObject("WScript.Shell")
sh.Environment("PROCESS")("GB_SERVEUR") = "1"
sh.Environment("PROCESS")("GB_PASSWORD") = ""
sh.Run """__EXE__""", 0, False
'@
    $vbs = $vbs.Replace('__EXE__', $exe)
    Set-Content -Path (Join-Path ([Environment]::GetFolderPath('Startup')) 'GB Etats des lieux (serveur).vbs') -Value $vbs -Encoding ASCII

    Write-Host ''
    Write-Host '================================================='
    Write-Host '   Installation TERMINEE - l''application s''ouvre'
    Write-Host '   Icone Bureau : "Application Etat des lieux"'
    Write-Host '================================================='
    Start-Process -FilePath $exe -WorkingDirectory $dst
}
catch {
    Write-Host ''
    Write-Host ('[ERREUR] ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Rien n''a ete perdu. Notez ce message et transmettez-le.'
}
Write-Host ''
Read-Host 'Appuyez sur Entree pour fermer cette fenetre'
