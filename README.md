# Motor OP Studio V1.4 — import automatique Excel / MOP

Application locale Streamlit pour tracer sur **un même graphique** le courant, le couple, la puissance et le rendement d'un moteur électrique, avec quatre axes Y indépendants. La V1.4 remplace les imports cachés dans des menus par **une seule zone visible de dépôt**.

## Lancer l'application

1. **Windows** : extraire le ZIP dans un dossier, puis double-cliquer sur `lancer_windows.bat`. La première fois, l'application installe ses dépendances (Python 3.10+ et connexion Internet nécessaires). La page s'ouvre sur `http://localhost:8501`.
2. Autres systèmes : `python -m pip install -r requirements.txt` puis `python -m streamlit run app.py`.
3. **Déposer le fichier directement dans la zone de dépôt en haut de page**, ou cliquer dessus pour choisir un fichier. Il n'y a **aucun bouton « Ouvrir »**.

Formats acceptés par le même sélecteur :

- **`.xlsx` / `.xlsm`** : import du classeur Excel complet, sélection automatique de la feuille `Characteristics Nom OP`. Affichage dès l'import.
- **`.mop`** : ouverture du projet sauvegardé, récupération du classeur Excel embarqué, des annotations, des courbes affichées, du titre et des réglages.

La zone de dépôt **reste visible après l'ouverture** : pour changer de fichier, déposer un nouvel Excel ou `.mop` au même endroit. Si un import échoue, le projet précédent n'est pas effacé. Le bouton **Fermer le fichier** réinitialise l'écran et le sélecteur.

## Colonnes Excel

| Colonne | Grandeur |
|---|---|
| B (2) | Phase current [Arms] |
| C (3) | Torque [Nm] |
| D (4) | Power [kW] |
| E (5) | Speed [RPM] |
| F (6) | Efficiency |

Lecture **à partir de la ligne 3** et arrêt à la **première cellule vide de B**. La courbe de rendement est automatiquement convertie en pourcentage si elle est stockée entre 0 et 1. Les fichiers Excel doivent avoir des valeurs calculées pour les cellules avec formules. Le format historique `.xls` n'est pas pris en charge ; enregistrer en `.xlsx` au préalable.

## Commandes à portée de main

- **Titre** : repris par défaut du nom Excel, sans l'extension, modifiable en haut de page.
- **Masquer / afficher** : quatre cases cochées par défaut (courant, couple, puissance, rendement).
- **Télécharger PNG** : export graphique haute résolution avec échelles, titre et annotations.
- **Sauver .mop** : téléchargement d'un projet autonome permettant de reprendre plus tard le travail.
- **Réglages** : ouvre une fenêtre flottante pour modifier thème, épaisseur, rendement et hauteur du graphique.
- **Annotations** : choisir la grandeur dans la colonne droite. En mode Point ou Segment, sélectionner les points du graphique ; la saisie de coordonnées libres reste accessible par « Annotation manuelle ». Les boutons Modifier et Supprimer sont en accès direct.

Le graphique est réglé sur 440 px de hauteur par défaut pour réduire le défilement sur une fenêtre d'ordinateur. La hauteur se règle entre 330 et 750 px selon la taille de l'écran. Il n'y a qu'une page et aucun changement d'onglet requis pour les opérations essentielles.

## Personnaliser automatiquement le titre

Au début du fichier `app.py`, modifier ces deux constantes :

```python
TITLE_REMOVE_FIRST = 0  # nombre de caractères supprimés au début
TITLE_REMOVE_LAST = 0   # nombre de caractères supprimés à la fin
```

Exemple : `XXX_MOTEUR_2026.xlsx` devient `MOTEUR` avec `4` et `5`. Un `.mop` **conserve le titre personnalisé** sauvé dans le projet, au lieu de le recalculer.

## Détails techniques

- Un seul uploader Streamlit persistant, reconnaissance par extension et chargement automatique au changement de contenu.
- Les boutons PNG et MOP n'exécutent pas de rechargement de la page au clic.
- Les formulaires secondaires s'ouvrent en fenêtres dialog ; pas de panneaux d'import à rouvrir.
- Ancien format `.mop` V1 / V1.1 / V1.2 / V1.3 compatible.
- Les fichiers sont traités **localement** par Streamlit sur ton poste. Il n'y a aucun serveur d'upload distant dans le code.
- La limite Streamlit d'upload est configurée à 512 Mo dans `.streamlit/config.toml`. Pour de très gros fichiers, la RAM disponible sur le poste reste déterminante.

### Tests

```bash
python -m unittest -v test_app_core
```

Les tests couvrent Excel multi-feuilles, titres, projet MOP aller-retour, MOP ancien format, graphique Plotly et export PNG. **Le rendu interactif du navigateur doit être vérifié sur la machine cible**.

### En cas d'interface blanche ou de boutons inactifs

Ouvrir `http://localhost:8501` dans un navigateur récent, attendre que le graphique se charge, puis regarder les erreurs dans la fenêtre noire qui a lancé Streamlit. On peut aussi lancer manuellement `python -m streamlit run app.py` pour conserver le journal visible.
