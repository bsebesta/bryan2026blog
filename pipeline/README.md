# pipeline

Exports published notes from the Obsidian vault into `content/`.

See `PRODUCT.md` §7 for the design. The short version: this pipeline knows
nothing about Hugo. It emits plain markdown, so swapping site generators is a
template rewrite rather than a migration.

## Setup

```bash
make setup
```

Creates `.venv` and installs dependencies. macOS ships `python3` with no bare
`python`, and Homebrew's Python refuses `pip install` outside a virtualenv —
the venv sidesteps both.

## Use

```bash
make export    # dry run — reports, writes nothing
make apply     # writes markdown into content/
make serve     # apply, then run the Hugo dev server
```

Every target calls `.venv/bin/python` directly, so nothing needs an activated
shell and it works from any new terminal tab.

`make serve` applies before starting Hugo deliberately: Hugo only watches
directories that exist when it boots, so a `content/` created afterward is
invisible to the server until restart.

To run the module by hand instead:

```bash
.venv/bin/python -m pipeline.export --apply
```

`PIPELINE_VAULT_ROOT` overrides the vault path from `config.yaml`.

`PIPELINE_VAULT_ROOT` overrides the vault path from `config.yaml` without
editing it.

## Stamping ids

```bash
make stamp        # dry run — shows exact planned changes
make stamp-apply  # WRITES TO THE VAULT
```

This is the only command that writes to the vault. It adds a permanent `id`
to published notes that lack one.

**Why ids exist.** On a static host there is no resolver — a URL either exists
as a generated path or 404s. So `/<id>/<slug>/` would *not* be permanent:
change the title, change the slug, change the path, break the link. The id only
delivers permanence if the id is the whole path. Canonical is therefore
`/<id>/`, and every slug the note has ever had becomes an alias redirecting to
it (PRODUCT.md §12.1).

Rename a note as often as you like. Nothing breaks, ever.

**Only published notes are stamped.** An id is a promise about a URL, and
private notes have no URLs. This keeps the command touching a few dozen files
rather than a few thousand.

**Insertion is textual, not a YAML round-trip.** Re-serializing frontmatter
would reorder keys, rewrite `publish: "true"` as `publish: 'true'`, and
collapse list styles — rewriting files Obsidian owns and producing noisy
Dropbox diffs. Only a single `id:` line is inserted. Writes are atomic
(temp file, then rename), so an interrupted run can't truncate a note.

`state/slugs.json` holds the id → slug history that generates the aliases.
**Losing that file loses the redirects**, so it is committed to the repo.

## Normalizing `publish`

```bash
make norm        # dry run
make norm-apply  # WRITES TO THE VAULT
```

Obsidian's Properties UI stores booleans as strings, so the vault accumulates
`publish: "false"` instead of `publish: false`. The gate handles both, but the
quoted form is a standing hazard: `"false"` is truthy in most languages, so any
future tool reading this frontmatter without knowing the history publishes
everything.

Normalized once on 2026-07-20 (133 notes). The command is idempotent and worth
re-running whenever properties get edited through the Obsidian UI.

## Two invariants

**1. Export never writes to the vault.** Not under any flag. ID stamping will
be a separate command for exactly this reason — if export both stamped and ran
in CI, CI would write back into Dropbox.

**2. The publish gate fails closed.** Only `publish: true` (boolean) or
`publish: "true"` (string) publishes. Everything else is withheld and, if
unrecognizable, reported.

This matters more than it sounds. Obsidian's Properties UI writes booleans as
strings, and the vault currently holds 132 notes with `publish: "false"` —
including unsent letters and work notes. `if meta.get("publish"):` publishes
every one of them, because `"false"` is a non-empty string. The gate exists to
make that impossible rather than unlikely.

## Output shape

Every published note becomes a Hugo leaf bundle:

```
content/<slug>/index.md
content/<slug>/diagram.png
```

Bundles are uniform, even for text-only notes — the URL is the same either
way, and uniformity avoids a stale-file bug when a note later gains an image.

## Pruning

Withdrawing a note (`publish: false`) must remove its page, not merely stop
updating it. The pipeline records every file it generates in
`state/published.json` and deletes anything from the previous manifest that
this run didn't produce.

Only files the pipeline generated are eligible. Pages authored directly in the
repo (`source: repo`, PRODUCT.md §9.2) never appear in the manifest and are
never touched.

## What v0 does not do

- **No wikilink resolution.** Every `[[link]]` is flattened to plain text.
- **No backlinks / `links.json`.**
- **No IDs.** Slugs derive from titles and remain provisional until `stamp`
  exists. Decision #1 is settled — the id becomes the canonical URL and slugs
  become aliases (PRODUCT.md §12.1) — but nothing is stamped yet.
- **No image sizing.** Obsidian's `![[img.png|400]]` width is dropped; alt text
  is preserved. Expressing width needs raw HTML, which needs
  `goldmark.renderer.unsafe`.

## Layout

**Export** — the only path that produces the site. Read-only against the vault.

| File | Role |
|---|---|
| `config.yaml` | Vault path, exclusion tiers, facet defaults, `extra_fields` |
| `registry.py` | Pass 1 — scan the whole vault, index every note, apply the gate |
| `emit.py` | Pass 2 — resolve links and assets, build frontmatter, write markdown |
| `export.py` | CLI and reporting |
| `bookschema.py` | Canonical frontmatter order for books and films |
| `state/` | Publish set, emitted manifest, slug history — **commit these** |

**Vault maintenance** — each writes to the vault and has a dry run.

| File | Role |
|---|---|
| `stamp.py` | Permanent ids into frontmatter |
| `normalize.py` | Quoted booleans → real booleans |
| `reorder.py` | Canonical field order |
| `strip_field.py` | Remove a field that's reproducible from another |
| `clean_bodies.py` | Strip redundant cover embeds and empty headings |

**One-time migrations** — kept in the repo as a record of what happened.

| File | Role |
|---|---|
| `migrate_books.py` | Past Writing/Books → Logbook/Books + ~ Attachments/Readwise |
| `migrate_movies.py` | Past Writing/Movies → Logbook/Movies, posters downloaded |
| `dedupe_books.py` | Merge duplicates by ISBN and normalised title |
| `enrich_books.py` | Backfill covers and metadata from Open Library / Google / Amazon |
| `rename_books.py` | Normalise filenames, rewriting inbound wikilinks |
| `audit_books.py` | **Read-only** schema check |

Pass 1 indexes the entire vault, not just published notes. That is a
requirement: you cannot decide how to render a link to a private note unless
you know the note exists.

## On the leak rule

An earlier formulation — "no unpublished title may appear in any output" — is
too broad to enforce, since an author may legitimately write a private note's
title in their own prose. The workable distinction:

- **Author-written body text.** You wrote `[[Personal Kanban]]` in a note you
  chose to publish. Rendering those words is your call. The pipeline must not
  *link* it, and it warns so you can reconsider.
- **Pipeline-generated surfaces** — backlinks, indexes, graph views. These
  introduce titles you never chose to put on that page. Here the rule is
  absolute and asserted.

v0 produces only the first kind, so it warns. The assertion arrives in v1
alongside the backlink index.
