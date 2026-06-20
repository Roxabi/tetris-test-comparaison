# Demande — Tetris en page HTML

## Objectif

Réaliser un jeu **Tetris** entièrement fonctionnel, jouable dans un navigateur web.

## Livrable

- **Un seul fichier `index.html`** autonome.
- Tout le code (HTML + CSS + JavaScript) est **inline** dans ce fichier.
- **Aucune dépendance externe** : pas de CDN, pas de framework, pas d'étape de build, pas de fichier annexe.
- Le jeu doit fonctionner en ouvrant simplement `index.html` dans un navigateur récent (Chrome / Firefox), hors-ligne.
- Pas d'images externes : tout est dessiné en CSS ou via `<canvas>`.

## Règles du jeu (Tetris standard)

- Grille de jeu de **10 colonnes × 20 lignes**.
- Les **7 tétrominos** classiques : `I`, `O`, `T`, `S`, `Z`, `J`, `L`, chacun avec sa **couleur standard** (I=cyan, O=jaune, T=violet, S=vert, Z=rouge, J=bleu, L=orange).
- Génération des pièces aléatoire, de préférence par **sac de 7** (7-bag : chaque pièce apparaît une fois par cycle de 7).
- Les pièces tombent automatiquement, à une cadence qui **accélère avec le niveau**.
- **Rotation** des pièces (sens horaire au minimum ; gestion des collisions contre murs/blocs).
- **Suppression des lignes** complètes, avec décalage des blocs au-dessus.
- **Détection de game over** quand une nouvelle pièce ne peut plus apparaître.

## Contrôles (clavier)

Le jeu se joue aux **flèches directionnelles**, avec un mapping équivalent en **WASD** (clavier QWERTY) **et** **ZQSD** (clavier AZERTY) — les deux schémas de lettres sont actifs en même temps, pas besoin de détecter ou choisir la disposition.

| Action | Flèches | QWERTY (WASD) | AZERTY (ZQSD) |
|---|---|---|---|
| Déplacer à gauche | ← | A | Q |
| Déplacer à droite | → | D | D |
| Rotation | ↑ et ↓ | W et S | Z et S |
| Faire tomber la pièce | Espace **ou** Entrée | Espace **ou** Entrée | Espace **ou** Entrée |

- Les flèches **haut et bas** gèrent toutes deux la **rotation** (ex. ↑ = sens horaire, ↓ = sens anti-horaire) — idem `W`/`S` et `Z`/`S`.
- **Espace** ou **Entrée** font **tomber la pièce** (hard drop).

### Touches système

| Touche | Action |
|---|---|
| **F2** | Recommencer / Reset de la partie |
| **F4** | Pause / Reprendre |

> Les touches `F2` / `F4` doivent annuler le comportement par défaut du navigateur (`preventDefault`).

## Interface

- Affichage du **score**, du **niveau** et du **nombre de lignes** supprimées.
- Aperçu de la **pièce suivante** (Next).
- Écran / message de **Game Over** avec possibilité de relancer.
- Indication visuelle quand le jeu est **en pause**.

## Thème clair / sombre

- Proposer un **thème clair (light)** et un **thème sombre (dark)**.
- Un **bouton / interrupteur** visible permet de basculer entre les deux à tout moment.
- Toute l'interface (grille, blocs, panneaux, texte) reste **lisible et contrastée** dans les deux thèmes.
- Bonus : se baser sur la préférence système (`prefers-color-scheme`) au premier chargement.

## Scoring & progression

- Points attribués selon le nombre de lignes supprimées d'un coup (1/2/3/4 lignes → score croissant, le Tetris à 4 lignes rapporte le plus).
- Le **niveau augmente** tous les ~10 lignes, et la vitesse de chute augmente avec le niveau.

## Bonus (optionnel, si le temps le permet)

- **Ghost piece** : projection de la position d'atterrissage de la pièce courante.
- **Hold** : mettre une pièce de côté (touche C ou Shift).
- Design soigné : grille nette, contraste lisible, mise en page responsive et centrée.
- Petit effet visuel lors de la suppression de lignes.

## Critères de réussite

1. Le jeu est **jouable du début à la fin** sans bug bloquant.
2. Les 7 pièces apparaissent, tournent et se posent correctement.
3. Les lignes complètes se suppriment et le score se met à jour.
4. La difficulté augmente avec le temps.
5. Le game over et le redémarrage fonctionnent.
6. Code **propre et lisible**.
