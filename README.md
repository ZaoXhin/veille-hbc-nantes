# H Actu — veille automatisée HBC Nantes

Petit site statique (HTML/CSS/JavaScript) alimenté par `data.json`. Un workflow GitHub Actions récupère des flux RSS, élimine les titres en doublon, applique des règles thématiques/pertinence et commit le nouveau fichier. Aucun serveur ni service payant n'est requis : GitHub Pages et GitHub Actions sont configurés pour un dépôt public.

## Contenu

- `index.html` : interface adaptée du dashboard fourni (filtres thématiques, pertinence, recherche, cartes d'articles, idées de tweets, tâches sauvegardées localement et calendrier).
- `data.json` : instantané de veille initial.
- `scripts/update.py` : collecte, dédoublonnage, classement et génération des données.
- `.github/workflows/update.yml` : actualisation deux fois par jour, avec exécution manuelle possible.

Le script consulte Google Actualités RSS pour « HBC Nantes » et une recherche HandNews, ainsi que le flux public `https://handnews.fr/feed/`. Il ne scrappe pas directement Ouest-France (accès refusé observé) ni le site du HBC (échec TLS observé) : des articles de ces éditeurs peuvent néanmoins apparaître via Google Actualités. Les liens d'articles Google News sont utilisés comme fournis dans leur flux.

## Déploiement pas à pas (gratuit)

1. Connectez-vous à GitHub et créez un nouveau dépôt **public**, par exemple `veille-hbc-nantes`.
2. Décompressez l'archive et poussez **le contenu du dossier** à la racine du dépôt (pas le dossier parent). Depuis un terminal :
   ```bash
   git init
   git add .
   git commit -m "Initialiser la veille HBC Nantes"
   git branch -M main
   git remote add origin https://github.com/VOTRE-NOM/veille-hbc-nantes.git
   git push -u origin main
   ```
3. Dans le dépôt GitHub, ouvrez **Settings → Actions → General → Workflow permissions**, sélectionnez **Read and write permissions**, puis sauvegardez. Le workflow demande déjà `contents: write`; cette permission permet au job de pousser `data.json`.
4. Ouvrez **Settings → Pages**. Dans **Build and deployment**, choisissez **Deploy from a branch**, branche `main`, dossier `/(root)`, puis **Save**. Attendez la fin du premier déploiement Pages.
5. Dans **Actions**, ouvrez « Actualiser la veille HBC Nantes » et lancez **Run workflow** pour tester immédiatement. Le schedule s'exécute ensuite à 09h00 et 17h00, heure de Paris.
6. Votre site sera publié à `https://VOTRE-NOM.github.io/veille-hbc-nantes/` (pour un dépôt de site utilisateur, l'adresse GitHub Pages suit les règles GitHub).

## Horaire et heure d'été

Les expressions cron GitHub sont en UTC, sans règle de fuseau Europe/Paris. Le workflow déclenche à 07h, 08h, 15h et 16h UTC. `scripts/update.py --if-due` vérifie ensuite l'heure locale avec `zoneinfo` et n'écrit que si l'heure à Paris est 09h ou 17h. En heure d'été, les exécutions utiles sont 07h/15h UTC; en hiver, 08h/16h UTC. Les deux autres déclenchements quotidiens sortent sans modifier les données. GitHub peut décaler ou retarder les tâches planifiées, en particulier aux heures de forte charge; ce n'est pas un service temps réel garanti.

Pour une mise à jour locale immédiate (sans filtre d'heure) :

```bash
python3 scripts/update.py
```

Pour tester la condition de l'horaire :

```bash
python3 scripts/update.py --if-due
```

## Règles éditoriales et limites

- Les thèmes sont attribués par mots-clés (`Résultats`, `Coupes`, `Calendrier`, `Effectif`, `Club/Polémique`); la pertinence est un score heuristique 3–5 fondé sur le thème et l'âge de l'article. Ce n'est ni une vérification factuelle ni une classification parfaite.
- Les textes d'idées de tweets sont générés automatiquement à partir du titre, indiquent qu'il faut consulter la source et marquent les sujets d'effectif/polémique comme risqués. Toujours ouvrir les liens et vérifier avant publication.
- La date du flux sert à classer l'article; si le RSS n'a pas de date exploitable, le script utilise l'heure d'exécution.
- Le calendrier et les tâches initiales proviennent du dashboard transmis et restent statiques dans `scripts/seed.json`; coche/ajout de tâche sont enregistrés dans le `localStorage` du navigateur, et ne sont pas synchronisés entre appareils.
- Si les flux ne répondent pas, le script conserve le dernier `data.json` non vide. Au tout premier lancement hors ligne, il retombe sur les 9 articles du dashboard statique daté du 3 novembre 2026 et le note dans `provenance`. Cette sauvegarde ne vaut pas nouvelle vérification des faits.
- L'exécution automatique est hébergée par GitHub après déploiement. Elle ne peut pas tourner périodiquement dans le sandbox de création lui-même.

## Vérification locale

Le collecteur n'utilise que la bibliothèque standard Python 3. `data.json` est du JSON UTF-8. Pour afficher l'interface, lancer un petit serveur HTTP à la racine du projet (ne pas ouvrir directement `file://`, car `fetch()` est soumis aux restrictions du navigateur) :

```bash
python3 -m http.server 8000
```

Puis ouvrir `http://localhost:8000/`. Les tâches s'enregistrent dans le stockage local de ce navigateur.
