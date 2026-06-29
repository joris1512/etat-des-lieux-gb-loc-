# Modèles Excel des états des lieux

Déposez ici les **vrais** modèles `.xlsx` GB Location. Les noms de fichiers doivent
correspondre à la colonne `modele` de `../correspondances.csv` et à `modele_assemble`
dans `../config/cellules.yaml`.

Attendus pour le devis EIFFAGE (starter — à compléter avec les ~25 modèles officiels) :

| Fichier                      | Usage                                   |
|------------------------------|-----------------------------------------|
| `bungalow_15m2.xlsx`         | Bungalow 15m2 individuel                |
| `bungalow_assemble.xlsx`     | État « assemblé » (regroupe N modules)  |
| `sanitaire_2wc_2d_2u.xlsx`   | Sanitaire 2 WC / 2 douches / 2 urinoirs |
| `sanitaire_2wc_pmr.xlsx`     | Sanitaire 2 WC dont 1 PMR               |

En attendant les vrais fichiers, des **modèles factices** sont générés par :

```
python scripts/make_placeholder_templates.py
```

➡️ Lundi : remplacez ces fichiers par les vrais modèles (mêmes noms) puis ajustez les
coordonnées de cellules dans `../config/cellules.yaml`. Aucune autre modification de code
n'est nécessaire.
