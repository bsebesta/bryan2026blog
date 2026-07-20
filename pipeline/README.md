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

| File | Role |
|---|---|
| `config.yaml` | Vault path, output dir, facet defaults, folder→temporality map |
| `registry.py` | Pass 1 — scan the whole vault, index every note, apply the gate |
| `emit.py` | Pass 2 — neutralize wikilinks, build frontmatter, write markdown |
| `export.py` | CLI and reporting |
| `state/published.json` | Previous publish set, for the run-over-run diff |

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
