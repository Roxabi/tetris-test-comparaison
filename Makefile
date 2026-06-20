# Tetris showcase — Cloudflare Pages (tetris.roxabi.dev)
PROJECT_NAME ?= tetris
CF_ACCOUNT   ?= b5e90be971920ce406f7b679c4f1cd33

-include .env
export CLOUDFLARE_ACCOUNT_ID := $(CF_ACCOUNT)

.PHONY: deploy open help

help:
	@echo "  make deploy   Publish to Cloudflare Pages ($(PROJECT_NAME))"
	@echo "  make open     Open local preview (python http.server)"

deploy:
	@test -n "$$CLOUDFLARE_API_TOKEN" || (echo "Set CLOUDFLARE_API_TOKEN in .env or env"; exit 1)
	@echo "▸ Deploying to Cloudflare Pages ($(PROJECT_NAME))…"
	npx wrangler pages deploy . --project-name=$(PROJECT_NAME) --branch=main --commit-dirty=true

open:
	python3 -m http.server 8765