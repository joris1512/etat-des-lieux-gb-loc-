# Reprise sur une autre machine (Mac → Windows)

Guide pour transférer le projet et **reprendre exactement où on s'est arrêté** avec Claude Code.

## Ce qui est inclus dans le transfert
- Tout le code (`app/`, `scripts/`, `config/`, `templates/`, `fixtures/`, `tests/`), les docs
  (`README.md`, `CLAUDE.md`, `HANDOFF.md`, `DEPLOIEMENT_WINDOWS.md`, `INTEGRATION_MISTRAL.md`)
  et l'historique git (`.git/`).
- **NON inclus** (volontairement) : `.venv/` (à recréer), `runtime/` (base + sorties, recréées),
  `.env` (secret — à recréer avec votre clé).

## Méthode A — Clé USB / cloud (la plus simple)
1. Sur le Mac, un fichier **`gb-etats-des-lieux.zip`** a été créé sur le Bureau.
2. Copiez-le sur une clé USB ou un cloud (iCloud / Google Drive / OneDrive).
3. Sur Windows, décompressez-le où vous voulez, par ex. `C:\GB\gb-etats-des-lieux`.

## Méthode B — GitHub (recommandée pour travailler à long terme)
1. Créez un dépôt **privé** sur github.com (sans README).
2. Sur le Mac, dans le dossier projet :
   ```bash
   git remote add origin https://github.com/VOTRE-COMPTE/gb-etats-des-lieux.git
   git push -u origin main
   ```
3. Sur Windows : `git clone https://github.com/VOTRE-COMPTE/gb-etats-des-lieux.git`

## Sur Windows — remettre en route (une fois)
```bat
cd C:\GB\gb-etats-des-lieux
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt

copy .env.example .env
notepad .env            REM coller ANTHROPIC_API_KEY (idéalement RÉGÉNÉRÉE) + GB_PASSWORD si voulu

.venv\Scripts\python.exe scripts\make_placeholder_templates.py   REM tant que les vrais .xlsx ne sont pas là
.venv\Scripts\python.exe scripts\seed_demo.py                    REM crée le dossier client EIFFAGE de démo
```
Lancer : `scripts\run_prod.bat` puis ouvrir `http://localhost:8000`.
Vérifier : `.venv\Scripts\python.exe -m pytest -q` et `.venv\Scripts\ruff check app scripts tests`.

## Reprendre avec Claude Code (Windows)
1. Ouvrez Claude Code **dans le dossier du projet** (il lit `CLAUDE.md` automatiquement → tout le contexte).
2. Dites-lui par ex. : *« Reprends le projet GB états des lieux : on en était à la sécurité renforcée
   (faite). Prochaine brique = auto-cocher la fonction du bungalow, en attente des vrais modèles. »*
3. Le détail de l'état d'avancement et du reste à faire est dans **`CLAUDE.md` → ÉTAT D'AVANCEMENT**.

## ⚠️ Sécurité
La clé API Anthropic a transité en clair pendant le développement : **régénérez-la** sur
console.anthropic.com et mettez la nouvelle dans le `.env` Windows. Ne commitez jamais `.env`.
