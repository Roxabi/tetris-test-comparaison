# Playbook — Recap OBS → site Roxabi (~60 s)

> Dernière mise à jour : 2026-06-20  
> Référence implémentée : [Tetris-Test-Comparaison](https://github.com/Roxabi/tetris-test-comparaison)  
> Complète le [mode d'emploi stack vidéo](https://github.com/Roxabi/roxabi-production/blob/main/docs/mode-emploi-stack-video.md) (quel outil choisir — ici le **how-to** FFmpeg + HyperFrames + Pages).

---

## Quand utiliser ce playbook

| Cas | Outil |
|-----|-------|
| Enregistrement OBS long → recap court + page showcase | **Ce playbook** |
| Motion brandée avec kits React Lyra / VoiceCLI | roxabi-production |
| Promo HTML/GSAP from scratch sans montage OBS | HyperFrames seul |
| Brief → research → assets IA → compose lourd | OpenMontage |

**Règle** : un runtime par livrable. Ici = **FFmpeg** (découpe/accélération/overlays/audio) + **HyperFrames** (intro/outro/badges) + **site statique** sur Cloudflare Pages.

---

## Squelette repo (J1 — copier Tetris)

```
projet/
├── index.html                 # showcase bilingue + <video>
├── video-plan.html            # script validé (optionnel mais utile)
├── docs/recap-obs-playbook.md # ce fichier
├── video/
│   ├── video-config.json      # ★ source de vérité segments
│   ├── build-montage.py       # pipeline FFmpeg + HF
│   ├── source/                # OBS brut → Git LFS
│   ├── intro-hyperframes/
│   ├── outro-hyperframes/
│   └── overlay-hyperframes/speed-badge/
├── out/
│   ├── tetris-comparison.mp4        # HQ yuv444p
│   └── tetris-comparison-compat.mp4 # Safari yuv420p
├── Makefile                   # deploy staging
├── .wranglerignore            # exclure video/source/
├── .github/workflows/deploy.yml
└── .gitignore                 # video/source/ (deploy), .env
```

**Cloudflare dès le premier commit** (pas après coup) :

1. Projet Pages + domaine custom (`*.roxabi.dev`)
2. Token API limité **Pages Read/Write** sur le compte Roxabi
3. Secret GitHub `CLOUDFLARE_API_TOKEN` sur le dépôt
4. Workflow deploy avec **rsync staging** (voir § Deploy)

> Ne jamais utiliser la Global API Key en CI. Ne jamais la coller dans un chat.

---

## Phase 1 — Repérage source OBS (~30 min)

1. Une passe linéaire de l'enregistrement — noter **timestamp source** + **événement** + **panneau actif**.
2. Distinguer **qui démarre quand** (ex. Grok+Opus d'abord, Sonnet après blocage — pas « 3 IA d'emblée »).
3. Repères type Tetris (à adapter) :

| Source ~ | Événement |
|----------|-----------|
| 0:00 | Brief / prompt |
| ~3:10 | Agent A terminé |
| ~3:40 | Agent B bloqué → lancement C |
| ~11:50 | Agent C terminé |
| ~50:30 | Agent B terminé (long) |
| ~59:00 | Showcase résultats |

4. Renseigner `video-plan.html` ou un tableau dans l'issue — validation humaine **avant** le premier build complet.

---

## Phase 2 — `video-config.json`

Chaque segment source :

```json
{
  "id": "grok_done",
  "ss": 183,
  "t": 10,
  "out": 3.5,
  "layout": "grok_md_opus",
  "overlay": "success",
  "overlay_delay": 1.3,
  "timer": "2:00",
  "panel": "grok",
  "caption": "Grok termine en 2 min"
}
```

| Champ | Rôle |
|-------|------|
| `ss` / `t` | Fenêtre dans l'OBS (secondes source) |
| `out` | Durée dans le rendu final |
| `layout` | Position overlays (`grok_md_opus`, `grok_opus_sonnet`, …) |
| `speed` | Accélération (`t/out`) + badge HF |
| `overlay` | `success` \| `fail` \| `reset` |
| `overlay_delay` | Secondes avant panneau dark OK (laisser le terminal finir) |
| `caption_panel` | Caption centrée sur un panneau, **au-dessus** de STALL |
| `type: speed_ramp` | Paliers Opus accélérés |
| `type: generated` | Intro / outro HyperFrames |
| `no_grade: true` | Exclure du color grade moody_dark |

**Audio** (`audio.sfx`) — synchroniser sur `overlay_delay` pour les chimes :

```json
{ "segment": "grok_done", "offset": 1.4, "sound": "chime", "volume": 0.55 }
```

---

## Phase 3 — Build montage

```bash
python3 video/build-montage.py
# → out/tetris-comparison.mp4 + compat (~7 min full rebuild)
```

### Checklist post-build (obligatoire)

| Test | Commande / critère |
|------|-------------------|
| Durée cible | `ffprobe` ≈ 55–65 s |
| Audio présent | stream `aac` ; `volumedetect` mean > **-55 dB** |
| Badge vitesse | Frame avec x55 : **pas** d'écran noir |
| Succès | Terminal visible **avant** overlay dark |
| Safari | `tetris-comparison-compat.mp4` joue (yuv420p) |

### Pièges connus (Tetris 2026-06-20)

| Symptôme | Cause | Fix |
|----------|-------|-----|
| Écran noir + badge coin | Webm HF plein écran opaque | `colorkey=0x000000` avant overlay |
| Pas de son | `amix` normalise (÷ N pistes) | `normalize=0` + `alimiter` + volumes |
| Overlay succès trop tôt | Overlay dès t=0 | `overlay_delay` 1.3–1.8 s |
| Coupure noire 0,5 s | Bumper plein écran | Supprimer ; whoosh sur segment suivant |
| `/out/*.mp4` → HTML | Source 531 Mo non déployée ou 404 | Deploy staging sans `video/source/` |

### Rebuild partiel (gain de temps)

Re-extraire un seul segment + `concat` + `mix_audio` — voir fonctions dans `build-montage.py` (`process_segment`, `build_timeline`).

### HyperFrames overlays

```bash
npx hyperframes render video/intro-hyperframes -o /tmp/intro.mp4 -f 30
```

Badges vitesse : format **webm** + variables `{"label":"x55"}`. Toujours valider une frame composée avant build complet.

---

## Phase 4 — Site showcase

Mettre à jour **dans le même PR** que la vidéo :

| Fichier | Contenu |
|---------|---------|
| `index.html` | Lead (vraie chronologie), stats durées, findings, player vidéo |
| `mentions-legales.html` | Hébergement Pages + vidéo auto-hébergée |
| `README.md` | Table agents + lien live |

Player (HQ avec fallback compat) :

```javascript
recap.src = supportsHq
  ? '/out/tetris-comparison.mp4'
  : '/out/tetris-comparison-compat.mp4';
```

**Alignement narratif** : le texte du site = les captions de la vidéo (pas de « même prompt 3 IA » si Sonnet arrive plus tard).

---

## Phase 5 — Deploy Cloudflare Pages

### Prérequis

- Projet : `tetris` → `tetris-8og.pages.dev` + `tetris.roxabi.dev`
- Secret : `CLOUDFLARE_API_TOKEN` (Pages only)
- **Limite** : 25 Mo/fichier — `video/source/*.mp4` **exclu** du bundle

### Manuel

```bash
echo 'CLOUDFLARE_API_TOKEN=…' >> .env   # gitignoré
make deploy
```

### Auto (push `main`)

`.github/workflows/deploy.yml` — rsync → `/tmp/…-pages-deploy` → `wrangler pages deploy`.

### Vérification live

```bash
curl -sI https://tetris.roxabi.dev/out/tetris-comparison-compat.mp4 | grep content-type
# → content-type: video/mp4
curl -s https://tetris.roxabi.dev/ | grep -o 'ultracode\|trois agents' | head -1
# → texte attendu selon narrative
```

> Intégration Git native Cloudflare (dashboard → Connect Git) = alternative au workflow GitHub ; une seule méthode active suffit.

---

## Checklist « premier coup » (ordre)

- [ ] Fork / copier ce repo comme template
- [ ] Pages + domaine + token + secret GitHub **avant** le montage
- [ ] Repères OBS validés → `video-config.json`
- [ ] Narration correcte (qui démarre quand)
- [ ] `overlay_delay` sur tous les `success`
- [ ] Test badge (colorkey) sur 1 frame
- [ ] Build complet + checklist audio/visuel
- [ ] `index.html` synchronisé
- [ ] `git push main` → deploy vert
- [ ] `content-type: video/mp4` sur le live

---

## Commandes rapides

```bash
# Build
python3 video/build-montage.py

# Preview local site
make open   # http://localhost:8765

# Deploy
make deploy

# Durée + audio
ffprobe -v error -show_entries format=duration -of csv=p=0 out/tetris-comparison.mp4
ffmpeg -i out/tetris-comparison.mp4 -af volumedetect -f null - 2>&1 | grep mean_volume
```

---

## Références

| Ressource | Chemin |
|-----------|--------|
| Implémentation | `video/build-montage.py`, `video/video-config.json` |
| Script détaillé Tetris | `video-plan.html` |
| Tokens design HF | `video/hyperframes-shared.css`, `video/assets/fonts/` |
| Stack vidéo (decision) | `roxabi-production/docs/mode-emploi-stack-video.md` |
| Site live | https://tetris.roxabi.dev |

---

## Prochain projet

1. Dupliquer le repo (ou branche `template/recap-obs`).
2. Remplacer `video/source/`, réécrire `video-config.json` + textes site.
3. Garder le pipeline tel quel — ajuster layouts dans `LAYOUTS` si nombre de panneaux différent.
4. Pousser `main` — le reste suit ce playbook.