# Calls the venv's Python directly, so no target needs an activated shell.
PY := .venv/bin/python

.DEFAULT_GOAL := help
.PHONY: help setup export apply serve build clean stamp stamp-apply norm norm-apply prep commit

help:
	@echo "make setup        create .venv and install pipeline dependencies"
	@echo "make export       dry run — report what would be published, write nothing"
	@echo "make apply        export for real, writing into content/"
	@echo "make serve        apply, then run the Hugo dev server"
	@echo "make build        apply, then build the production site into public/"
	@echo "make clean        remove Hugo build output"
	@echo ""
	@echo "make stamp        dry run — show which notes would get permanent ids"
	@echo "make stamp-apply  WRITES TO THE VAULT. Stamps ids into frontmatter."
	@echo "make norm         dry run — show quoted publish values to fix"
	@echo "make norm-apply   WRITES TO THE VAULT. publish: \"false\" → publish: false"
	@echo "make prep         all vault preprocessing, with confirmation prompt"
	@echo "make commit       review changes, prompt for a message, commit"

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
stamp:
	$(PY) -m pipeline.stamp

stamp-apply:
	$(PY) -m pipeline.stamp --apply

# Idempotent — safe to re-run whenever Obsidian reintroduces quoted booleans.
norm:
	$(PY) -m pipeline.normalize

norm-apply:
	$(PY) -m pipeline.normalize --apply

# Interactive: shows every dry run, then asks before writing to the vault.
# Invoked via `bash` so the script needs no execute bit.
prep:
	@bash tools/prep.sh

commit:
	@bash tools/commit.sh
