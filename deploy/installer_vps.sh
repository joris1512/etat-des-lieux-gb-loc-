#!/usr/bin/env bash
# ============================================================================
#  Installation de « GB États des lieux » sur un VPS Debian 12 / Ubuntu 22+.
#  À lancer en root, DEPUIS le dossier du projet copié sur le serveur :
#      sudo bash deploy/installer_vps.sh app.gb-location.fr
#  Guide complet : docs/DEPLOIEMENT_VPS.md
# ============================================================================
set -euo pipefail

DOMAINE="${1:-}"
[ -z "$DOMAINE" ] && { echo "Usage : sudo bash deploy/installer_vps.sh <domaine>"; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "Lancez ce script avec sudo/root."; exit 1; }

CIBLE=/opt/gb-etats
SRC="$(cd "$(dirname "$0")/.." && pwd)"

echo "== 1/7 Paquets système (python, caddy) =="
apt-get update -qq
apt-get install -y -qq python3 python3-venv sqlite3 curl rsync gnupg debian-keyring debian-archive-keyring apt-transport-https
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq && apt-get install -y -qq caddy
fi

echo "== 2/7 Compte de service + copie de l'application =="
id gbapp >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin gbapp
mkdir -p "$CIBLE"
# runtime/ (base + documents) et .env (clé API) ne sont JAMAIS touchés par une (ré)installation.
rsync -a --delete \
  --exclude '.venv' --exclude '.git' --exclude 'dist' --exclude 'build' \
  --exclude 'runtime' --exclude '.env' \
  --filter 'protect runtime/***' --filter 'protect .env' \
  "$SRC/" "$CIBLE/"

echo "== 3/7 Environnement Python =="
python3 -m venv "$CIBLE/.venv"
"$CIBLE/.venv/bin/pip" install --quiet --upgrade pip
"$CIBLE/.venv/bin/pip" install --quiet -r "$CIBLE/requirements.txt"

echo "== 4/7 Fichier .env =="
if [ ! -f "$CIBLE/.env" ]; then
  cat > "$CIBLE/.env" <<'ENV'
# --- À COMPLÉTER ---
ANTHROPIC_API_KEY=
# Derrière Caddy : lire l'IP réelle des clients (anti-force-brute, journal)
GB_PROXY_CONFIANCE=1
GB_HOST=127.0.0.1
GB_PORT=8000
ENV
  echo "  >>> Éditez $CIBLE/.env pour renseigner ANTHROPIC_API_KEY <<<"
fi
chown -R gbapp:gbapp "$CIBLE"
chmod 600 "$CIBLE/.env"

echo "== 5/7 Compte administrateur (JAMAIS d'accès public sans authentification) =="
# L'app est OUVERTE tant qu'aucun compte n'existe : on impose un admin AVANT de la publier.
if sudo -u gbapp "$CIBLE/.venv/bin/python" "$CIBLE/scripts/creer_admin.py" --verifier; then
  echo "  Un compte administrateur existe déjà (base migrée) — étape ignorée."
else
  echo "  Aucun compte : créons le compte administrateur maintenant."
  read -rp "  Identifiant administrateur : " ADMIN_ID
  read -rsp "  Mot de passe (8 caractères min.) : " ADMIN_PW; echo
  sudo -u gbapp "$CIBLE/.venv/bin/python" "$CIBLE/scripts/creer_admin.py" "$ADMIN_ID" "$ADMIN_PW"
fi

echo "== 6/7 Services (application + HTTPS) =="
cp "$CIBLE/deploy/gb-etats.service" /etc/systemd/system/gb-etats.service
sed "s/app\.gb-location\.fr/$DOMAINE/" "$CIBLE/deploy/Caddyfile" > /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable gb-etats
systemctl restart gb-etats          # restart (pas start) : applique bien le nouveau code en cas de MAJ
systemctl reload caddy || systemctl restart caddy

echo "== 7/7 Sauvegarde quotidienne externe =="
cp "$CIBLE/deploy/sauvegarde.sh" /usr/local/bin/gb-sauvegarde
chmod +x /usr/local/bin/gb-sauvegarde
cat > /etc/cron.d/gb-etats <<'CRON'
# Sauvegarde quotidienne de la base + des documents (03h15, conservation 30 jours)
15 3 * * * root /usr/local/bin/gb-sauvegarde >> /var/log/gb-sauvegarde.log 2>&1
CRON

echo
echo "============================================================"
echo " Terminé. Vérifications :"
echo "   systemctl status gb-etats --no-pager | head -5"
echo "   curl -s http://127.0.0.1:8000/etat"
echo "   puis ouvrez  https://$DOMAINE  (HTTPS automatique)"
echo " N'oubliez pas :"
echo "   1. renseigner ANTHROPIC_API_KEY dans $CIBLE/.env puis: systemctl restart gb-etats"
echo "   2. copier les données du poste bureau (voir guide, section Migration)"
echo "============================================================"
