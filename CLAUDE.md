# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start development server (with drafts visible)
hugo server --buildDrafts

# Build the site (output goes to ./public/)
hugo

# Create a new content file
hugo new content <section>/<filename>.md

# Create a new theme
hugo new theme <themename>
```

## Architecture

This is a [Hugo](https://gohugo.io/) static site generator project (v0.158.0).

**Key directories:**
- `content/` — Markdown source files; directory structure maps to URL paths
- `layouts/` — HTML templates that override theme templates
- `themes/` — Installed themes (set active theme via `theme` in `hugo.toml`)
- `static/` — Files copied as-is to the output root (images, fonts, etc.)
- `assets/` — Files processed by Hugo Pipes (SCSS, JS bundling/minification)
- `archetypes/` — Templates used when running `hugo new content`
- `data/` — Data files (JSON/YAML/TOML) accessible in templates via `.Site.Data`
- `i18n/` — Translation strings for multilingual sites
- `public/` — Build output (gitignored; regenerated on each `hugo` run)

**Configuration:** `hugo.toml` is the main config file. Key settings: `baseURL`, `title`, `theme`, `params`.

**Template lookup order:** Hugo looks for templates in `layouts/` before falling back to the active theme. Override any theme template by mirroring its path under `layouts/`.

**Content front matter:** Each content file starts with TOML/YAML/JSON front matter. `draft = true` hides content unless `--buildDrafts` is passed.
