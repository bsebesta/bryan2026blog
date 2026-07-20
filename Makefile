# Calls the venv's Python directly, so no target needs an activated shell.
PY := .venv/bin/python

.DEFAULT_GOAL := help
.PHONY: help setup export apply serve build clean

help:
	@echo "make setup    create .venv and install pipeline dependencies"
	@echo "make export   dry run — report what would be published, write nothing"
	@echo "make apply    export for real, writing into content/"
	@echo "make serve    apply, then run the Hugo dev server"
	@echo "make build    apply, then build the production site into public/"
	@echo "make clean    remove Hugo build output"

setup:
	python3 -m venv .venv
	.venv/bin/pip install --quiet --upgrade pip
	.venv/bin/pip install --quiet -r pipeline/requirements.txt
	@echo "Ready. Run 'make export' for a dry run."

export:
	$(PY) -m pipeline.export

apply:
	$(PY) -m pipeline.export --apply

# `apply` runs first so content/ exists before the server starts watching.
# Hugo only watches directories present at boot — creating content/ afterward
# leaves the server blind to it.
serve: apply
	hugo server

build: apply
	hugo --minify

clean:
	rm -rf public resources .hugo_build.lock
