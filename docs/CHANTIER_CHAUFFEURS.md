# Chantier « Espace chauffeurs » — plan technique (2026-07-17)

> **✅ LIVRÉ le 17/07/2026 en v2.4.0** (commit « Espace chauffeurs »). 128 tests verts,
> ruff clean, exe reconstruit et déployé dans `P:\Joris\APPLICATION FINALE - Etat des lieux`.
> Ce document reste comme référence de conception.

Demande utilisateur : (1) un espace chauffeur dédié où ils n'ont accès QU'AUX constats,
(2) signature électronique complète — y compris INSÉRÉE dans le document Excel,
(3) accès depuis leur téléphone (pratique, installable).

## 1. Rôle « chauffeur » (accès restreint)
- `db.creer_utilisateur` : accepter role « chauffeur » (en plus d'admin/utilisateur).
- `securite.exiger_auth` : après auth réussie, si role == « chauffeur », n'autoriser que les
  chemins : `/`, `/static`, `/etat`, `/parametres` (GET), `/constats`, `/terrain`,
  `/terrain-fichier`, `/telecharger`, `/ouvrir`, `/imprimer`, `/manifest.json` → sinon 403.
- Nouvel endpoint `GET /constats` : dossiers récents avec leurs fichiers xlsx
  (db.lister_constats(limit=30) : generations + fichiers + client/chantier).
- UI : si `/etat`.role == « chauffeur » → masquer TOUTE la nav, afficher une vue unique
  `view-chauffeur` (recherche + liste des dossiers → fichiers avec bouton « Constat » seul).
  Admin : option « chauffeur » dans le menu déroulant des rôles.

## 2. Signature insérée dans l'Excel
- `patch_xlsx.inserer_image(xlsx, feuille, cellule_ancre, png_bytes, largeur_po, hauteur_po)` :
  toutes nos feuilles ont déjà un drawing (logo/perspectives) → ajouter l'image dans
  `xl/media/signature_gb.png`, une Relationship dans `xl/drawings/_rels/drawingN.xml.rels`,
  un `<xdr:oneCellAnchor>` en fin de `drawingN.xml` (from = col/row de l'ancre, ext en EMU :
  1 pouce = 914400). Vérifier Default png dans [Content_Types].xml (ajouter si absent).
  Si re-signature : remplacer les octets de `signature_gb.png` si la rel existe déjà.
- Ancre : chercher via openpyxl la cellule contenant « Signature » (ligne « Date, Nom et
  Signature ») côté client (colonne E environ) ; sinon repli = pas d'insertion + note.
- Brancher dans `terrain.enregistrer_signature` (après écriture du PNG) sur le document.

## 3. Accès téléphone (LAN)
- Paramètre `acces_mobile` (table parametres, '1'/'0', défaut off) + toggle dans Administration
  avec avertissement « redémarrer l'application » + affichage de l'URL http://IP:8742 et d'un
  QR code (endpoint GET /mobile-qr → SVG, lib `qrcode` pure Python, admin seulement).
- `app_desktop._run_serveur` : host = '0.0.0.0' si db.lire_parametre('acces_mobile')=='1'
  sinon '127.0.0.1' (import tardif de app.db après config env).
- PWA : `GET /manifest.json` (name, icons logo.png, display standalone, theme_color #0E1A14)
  + `<link rel="manifest">` + `<meta name="theme-color">` + apple-touch-icon dans index.html
  → « Ajouter à l'écran d'accueil » sur téléphone = icône type appli.
- Les chauffeurs se connectent avec leur compte (rôle chauffeur) depuis le navigateur du
  téléphone (même Wi-Fi que le poste qui héberge l'app). Hors réseau : non couvert (v2).

## Livraison
pytest + ruff → commit → build local (--distpath %TEMP%\gb_dist, --icon app/static/app.ico,
--collect-all qrcode en plus) → robocopy vers `P:\Joris\APPLICATION FINALE - Etat des lieux`
(le _internal/.env y survit) → relance via `explorer.exe <exe>` (contexte utilisateur réel,
JAMAIS lancer l'exe directement depuis l'agent — voir mémoire logiciel-bureau-exe.md) →
sonde http://127.0.0.1:8742/etat (401 attendu).

## Tests à écrire
- role chauffeur : accès /terrain OK, /clients et /analyser → 403 ; /constats liste les xlsx.
- creer_utilisateur('x','X',hash,'chauffeur') accepté ; role invalide refusé.
- inserer_image : le xlsx généré contient xl/media/signature_gb.png + oneCellAnchor ;
  dessins d'origine intacts ; re-signature ne duplique pas.
- parametre acces_mobile lu/écrit ; /mobile-qr admin-only.
