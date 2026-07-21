# Calls the venv's Python directly, so no target needs an activated shell.
PY := .venv/bin/python

.DEFAULT_GOAL := help
.PHONY: help setup export apply serve build clean stamp stamp-apply seed seed-apply norm norm-apply books books-apply movies movies-apply dedupe dedupe-apply enrich enrich-apply reorder reorder-apply rename rename-apply audit bodies bodies-apply micro micro-apply micro-import prep commit

help:
	@echo "make setup        create .venv and install pipeline dependencies"
	@echo "make export       dry run — report what would be published, write nothing"
	@echo "make apply        export for real, writing into content/"
	@echo "make serve        apply, then run the Hugo dev server"
	@echo "make build        apply, then build the production site into public/"
	@echo "make clean        remove Hugo build output"
	@echo ""
	@echo "make seed         dry run — find notes with no frontmatter"
	@echo "make seed-apply   WRITES TO THE VAULT. Adds publish: false."
	@echo "make stamp        dry run — show which notes would get permanent ids"
	@echo "make stamp-apply  WRITES TO THE VAULT. Stamps ids into frontmatter."
	@echo "make norm         dry run — show quoted publish values to fix"
	@echo "make norm-apply   WRITES TO THE VAULT. publish: \"false\" → publish: false"
	@echo "make books        dry run — preview the past-books migration"
	@echo "make books-apply  WRITES TO THE VAULT. Imports past book notes."
	@echo "make movies       dry run — preview the past-films migration"
	@echo "make movies-apply WRITES TO THE VAULT. Imports past film notes."
	@echo "make dedupe       dry run — preview merging duplicate book notes"
	@echo "make dedupe-apply WRITES TO THE VAULT. Merges duplicates."
	@echo "make enrich       dry run — preview cover + metadata backfill"
	@echo "make enrich-apply WRITES TO THE VAULT. Fetches covers and metadata."
	@echo "make reorder      dry run — preview frontmatter reordering"
	@echo "make reorder-apply WRITES TO THE VAULT. Canonical field order."
	@echo "make rename       dry run — preview filename normalisation"
	@echo "make rename-apply WRITES TO THE VAULT. Renames + rewrites links."
	@echo "make audit        READ-ONLY. Check book notes against the schema."
	@echo "make bodies       dry run — strip cover embeds + empty Review headings"
	@echo "make bodies-apply WRITES TO THE VAULT. Strips them."
	@echo "make micro        dry run — preview Micro.blog export ingest"
	@echo "make micro-apply  WRITES TO THE VAULT. Ingests microposts + photos."
	@echo ""
	@echo "make prep         all vault preprocessing, with confirmation prompt"
	@echo "make micro-import interactive micropost import, then re-export"
	@echo "make commit       export, review changes, prompt for a message, commit"

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

# The only commands that write to the vault. Kept separate from export by
# design — see pipeline/stamp.py.
seed:
	$(PY) -m pipeline.seed

seed-apply:
	$(PY) -m pipeline.seed --apply

stamp:
	$(PY) -m pipeline.stamp

stamp-apply:
	$(PY) -m pipeline.stamp --apply

# Idempotent — safe to re-run whenever Obsidian reintroduces quoted booleans.
norm:
	$(PY) -m pipeline.normalize

norm-apply:
	$(PY) -m pipeline.normalize --apply

# One-time migration of past book notes. Copies by default; --move deletes
# the originals, which is a separate decision.
books:
	$(PY) -m pipeline.migrate_books

movies:
	$(PY) -m pipeline.migrate_movies

movies-apply:
	$(PY) -m pipeline.migrate_movies --apply

dedupe:
	$(PY) -m pipeline.dedupe_books

dedupe-apply:
	$(PY) -m pipeline.dedupe_books --apply

enrich:
	$(PY) -m pipeline.enrich_books

reorder:
	$(PY) -m pipeline.reorder

reorder-apply:
	$(PY) -m pipeline.reorder --apply

bodies:
	$(PY) -m pipeline.clean_bodies

bodies-apply:
	$(PY) -m pipeline.clean_bodies --apply

# Ingests a Micro.blog markdown export into Logbook/Microposts/. Idempotent —
# keyed on each post's URL path, so re-running re-syncs rather than duplicating.
micro:
	$(PY) -m pipeline.micro

micro-apply:
	$(PY) -m pipeline.micro --apply

audit:
	$(PY) -m pipeline.audit_books

rename:
	$(PY) -m pipeline.rename_books

rename-apply:
	$(PY) -m pipeline.rename_books --apply

enrich-apply:
	$(PY) -m pipeline.enrich_books --apply

books-apply:
	$(PY) -m pipeline.migrate_books --apply

# Interactive: shows every dry run, then asks before writing to the vault.
# Invoked via `bash` so the script needs no execute bit.
prep:
	@bash tools/prep.sh

# Interactive micropost import (the "Import Microposts" dock droplet): dry run,
# confirm, write to the vault, then re-export. Occasional, not part of prep.
micro-import:
	@bash tools/micro-import.sh

commit:
	@bash tools/commit.sh
