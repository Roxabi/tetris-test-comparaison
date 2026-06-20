# Tetris-Test-Comparaison

Showcase bilingue (FR/EN) comparant trois agents IA sur le même brief Tetris HTML :

| Agent | Modèle / réglage | Durée | Livrable |
|-------|------------------|-------|----------|
| Grok | Composer 2.5 | ~2 min | `grok-composer/index.html` |
| Claude | Sonnet · effort medium | ~2 min 10 | `claude-sonnet/index.html` |
| Claude | Opus · ultra + subagents | 35 min+ | `claude-opus/index.html` + tests |

## Site live

[tetris.roxabi.dev](https://tetris.roxabi.dev)

## Brief

Voir [`DEMANDE.md`](DEMANDE.md) — identique pour les trois tests.

## Structure

```
├── index.html              # Page showcase
├── mentions-legales.html   # Mentions légales
├── DEMANDE.md              # Brief du test
├── grok-composer/          # Livrable Grok (brut)
├── claude-sonnet/          # Livrable Claude Sonnet (brut)
└── claude-opus/            # Livrable Claude Opus (brut) + tests Playwright
```

Les fichiers Tetris générés par les agents ne sont **pas modifiés** — ils sont conservés tels quels.

## Licence

AGPL-3.0 — © 2026 [Roxabi](https://roxabi.dev)