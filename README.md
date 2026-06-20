# Tetris-Test-Comparaison

Showcase bilingue (FR/EN) : même brief Tetris HTML, mais **deux agents au départ** (Grok Composer 2.5 vs Claude Opus ultracode), puis Sonnet ajouté quand Opus bloque.

| Agent | Modèle / réglage | Durée | Livrable |
|-------|------------------|-------|----------|
| Grok | Composer 2.5 | ~2 min | `grok-composer/index.html` |
| Claude | Opus · ultra + subagents | ~50 min | `claude-opus/index.html` + tests |
| Claude | Sonnet · effort medium | ~2 min 10 | `claude-sonnet/index.html` *(lancé après blocage Opus)* |

## Site live

[tetris.roxabi.dev](https://tetris.roxabi.dev) — récap vidéo ~59 s intégré (`out/tetris-comparison.mp4`).

```bash
# .env : CLOUDFLARE_API_TOKEN=…
make deploy
```

Push sur `main` déclenche aussi le workflow GitHub Actions si le secret `CLOUDFLARE_API_TOKEN` est configuré sur le dépôt.

## Brief

Voir [`DEMANDE.md`](DEMANDE.md) — même consigne pour tous ; ordre de lancement différent (Grok+Opus d'abord).

## Structure

```
├── index.html              # Page showcase
├── video-plan.html         # Plan / script du montage
├── out/                    # Récap vidéo HQ + compat
├── video/                  # Pipeline FFmpeg + HyperFrames
├── mentions-legales.html   # Mentions légales
├── DEMANDE.md              # Brief du test
├── grok-composer/          # Livrable Grok (brut)
├── claude-sonnet/          # Livrable Claude Sonnet (brut)
└── claude-opus/            # Livrable Claude Opus (brut) + tests Playwright
```

Les fichiers Tetris générés par les agents ne sont **pas modifiés** — ils sont conservés tels quels.

## Licence

AGPL-3.0 — © 2026 [Roxabi](https://roxabi.dev)