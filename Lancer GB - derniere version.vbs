' Lance la DERNIERE version de GB - Etats des lieux (v2.7.2+) depuis le code source,
' SANS exe a compiler (Trend Micro ne bloque que les .exe). Donnees PARTAGEES sur le serveur.
' Fenetre masquee = lancement propre, comme l'application normale.
Set sh = CreateObject("WScript.Shell")
sh.Environment("PROCESS")("GB_DONNEES_DIR") = "P:\Joris\GB Etats des lieux\GB Etats des lieux - donnees"
sh.CurrentDirectory = "P:\Joris\GB Etats des lieux\gb-etats-des-lieux"
sh.Run """P:\Joris\GB Etats des lieux\gb-etats-des-lieux\.venv\Scripts\pythonw.exe"" ""P:\Joris\GB Etats des lieux\gb-etats-des-lieux\app_desktop.py""", 0, False
