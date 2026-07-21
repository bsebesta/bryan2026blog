# CLAUDE.md

Guidance for Claude Code when working in this repository.

**Read `PRODUCT.md` first.** It holds the content model, the pipeline contract,
and the decisions behind both. This file covers how to work here; that one
covers what is being built and why.

## What this is

The static site for **bryansebesta.net** — Bryan's personal hub for writing,
reading notes, a digital garden, designs, and learning. Explicitly *not* a
portfolio; `bryansebesta.com` is the product-design portfolio and is a separate
project. No decision here should be made to accommodate it.

Content is authored in Obsidian and exported here by a Python pipeline. **This
repo holds no original prose** — every file in `content/` is generated.

## Commands

Everything runs through `make`. Run `make` alone for the full list.

```bash
make setup          # create .venv, install pipeline dependencies
make export         # dry run — report what would publish, write nothing
make apply          # export for real, writing into content/
make serve          # apply, then run the Hugo dev server
make audit          # READ-ONLY schema check on book notes
make commit         # export, review the diff, prompt for a message, commit
```

Targets whose names end in `-apply` **write to the Obsidian vault**. Every one
has a dry-run twin; run that first, always.

```bash
make stamp / stamp-apply      # permanent ids into vault frontmatter
make norm  / norm-apply       # publish: "false" → publish: false
make books / books-apply      # one-time import of past book notes
make movies / movies-apply    # one-time import of past film notes
make dedupe / dedupe-apply    # merge duplicate book notes
make enrich / enrich-apply    # backfill covers and metadata
make rename / rename-apply    # normalise filenames, rewrite wikilinks
make reorder / reorder-apply  # canonical frontmatter order
make bodies / bodies-apply    # strip redundant embeds and headings
make prep                     # all vault preprocessing, with confirmation
```

**Terminal commands assume a fresh login.** Include the `cd`, and prefer
invocations needing no shell state — `make` targets call `.venv/bin/python`
directly, so nothing needs an activated venv.

## Two hard rules

**1. `export` never writes to the vault.** Not under any flag. Stamping,
normalising, and every other vault write is a separate command, because if
export both stamped and ran in CI, CI would write back into Dropbox.

**2. The publish gate fails closed.** Only `publish: true` (boolean) or
`publish: "true"` (string) publishes. This matters more than it sounds:
Obsidian's Properties UI writes booleans as strings, and the vault holds
hundreds of notes with `publish: "false"` — including unsent letters, health
notes, and work material. `if meta.get("publish"):` publishes every one of
them, because `"false"` is a non-empty string.

Three further tiers back this up (PRODUCT.md §7.4.3):

| Tier | Config | Behaviour |
|---|---|---|
| Excluded | `exclude_dirs` | Not indexed at all |
| Source | `source_dirs` | Indexed, never publishable, links substitute `url:` |
| Blocked | `never_publish_dirs` | Indexed and linkable, publish flag ignored |

`~ Attachments/` is Bryan's rule for **material he did not write** — clippings,
LLM analysis, course material, PDFs. Publishing anything there is structurally
impossible, which is a copyright guard rather than a privacy one.

## Architecture

Hugo v0.158.0 (+extended) → Netlify, from the `main` branch of
`github.com/bsebesta/bryan2026blog`.

```
Obsidian vault  →  [pipeline/]  →  content/  →  [Hugo]  →  public/
```

**The pipeline knows nothing about Hugo.** It emits plain markdown plus a link
graph, so swapping site generators is a template rewrite rather than a
migration. Keep it that way — nothing SSG-specific belongs in `pipeline/`.

### Directories

| Path | Role |
|---|---|
| `pipeline/` | Python export and vault-maintenance scripts |
| `pipeline/config.yaml` | Vault path, exclusion tiers, facet defaults, `extra_fields` |
| `pipeline/bookschema.py` | Canonical frontmatter order for books and films |
| `pipeline/state/` | Publish set, emitted manifest, slug history — **commit these** |
| `layouts/` | Hugo templates |
| `data/hues.yaml` | Hand-curated colour-name → hue map for the `uidesign` embed (§9.5); the two `*.json` beside it are pipeline-emitted |
| `tools/` | Shell scripts and AppleScript launchers |
| `content/` | **Generated. Never edit by hand.** |

### URLs

Canonical is `/<id>/` — an opaque 10-character id stamped into vault
frontmatter. Every slug a note has ever had becomes an alias redirecting to it,
so titles can change freely without breaking a link.

The id must be the *whole* path. On a static host there is no resolver, so
`/<id>/<slug>/` would break on rename — see PRODUCT.md §12.1.

`pipeline/state/slugs.json` holds the id → slug history that generates those
aliases. **Losing that file loses the redirects.**

### Content model

One object with facets, not a taxonomy of types (PRODUCT.md §4).

- `type` — `note` / `essay` / `log` / `artifact`, derived from folder
- `temporality` — `evergreen` / `dated`, derived from top-level folder
- Vault key is `note_type`, not `type`: `type` is reserved by Hugo *and*
  already used by the vault's voice-memo importer.

`Notebook/` is evergreen and flat; `Logbook/` is dated and foldered by kind.
Keep Notebook flat — folders impose one hierarchy on things whose value is
belonging to many contexts at once.

### Note embeds — fences

Two fenced blocks in a vault note resolve at export into a page-bundle embed,
each copying its asset in and rewriting the fence (PRODUCT.md §9.3, §9.5). Both
read as plain code blocks in Obsidian, so the note stays portable:

- ` ```artifact ` → an `<iframe>` around a self-contained `.html` interactive.
- ` ```uidesign ` → a `{{< device >}}` shortcode framing a UI mockup image in a
  minimal iPhone bezel. The frame's markup and CSS live once in
  `layouts/partials/device-frame.html` (repeated component markup is always a
  partial); `hue` accepts a number or a name from `data/hues.yaml`.

Unlike the artifact iframe, the `uidesign` fence emits a Hugo shortcode rather
than plain HTML — a deliberate, narrow SSG coupling noted in `emit.py`, taken so
the frame isn't duplicated between the pipeline and `layouts/`.

### Books and films

`pipeline/bookschema.py` defines `BOOK_KEY_ORDER` and `MOVIE_KEY_ORDER`. Every
script that writes such a note imports from there, so nothing drifts.

The vocabulary is **Bryan's existing one** — `authors`, `publishers`,
`pageCount`, `publishedYear` — because hundreds of notes already use it.
Renaming to something tidier is migration cost for no benefit.

- `date` is when *Bryan* read or watched it, and doubles as Hugo's sort date.
  `published` / `released` is when the work appeared.
- `cover` is a **wikilink** in the vault (`"[[poster-x.jpg]]"`), because
  Obsidian's Bases cards view renders nothing otherwise. `emit.py` strips the
  brackets and repoints it at the copied filename on the way out.
- `contributors` holds translators and editors with the role attached —
  "Emily Wilson (Translator)". A translation is not interchangeable with any
  other edition, so this is identity, not trivia.
- `dateYear` was removed. It existed only because Dataview could not group by
  a computed value; Bases can (`groupBy: formula.read`).

**Publication is an allowlist.** `extra_fields` in `config.yaml` names the only
frontmatter keys that reach the site. Getting a name wrong fails *silently* —
the field simply never appears — so check against a real note.

### Obsidian-side pieces

These live in the vault, not this repo, but the pipeline depends on them:

| Path | Purpose |
|---|---|
| `~ Templates/` | Note templates. Field order matches `bookschema.py`. |
| `~ Attachments/Scripts/` | QuickAdd scripts: `book-search.js`, `tmdb-movie.js` |
| `Logbook/Books/§ Library.base` | Bases views over the book library |
| `Logbook/Movies/§ Films.base` | Bases views over the film library |

QuickAdd gotchas, each of which cost a debugging round:

- `fetch()` is blocked by CORS in Obsidian's renderer. Use `requestUrl`.
- `require("obsidian")` fails — QuickAdd resolves `require` against vault
  files. The module arrives as **`params.obsidian`**.
- Open Library throttles requests that don't identify themselves; send a
  descriptive `User-Agent` or expect 429s.
- Book covers: Open Library cover id → OL by ISBN → Amazon by ISBN-10 →
  Google. A 979-prefix ISBN has no ISBN-10, so the Amazon path can't work.

## Working here

- **Dry-run first.** Every vault-writing command has one. Read its report.
- **Don't hand-edit `content/`.** It's regenerated, and stale files are pruned.
- **Secrets stay out of the repo.** The TMDB key belongs in QuickAdd's script
  settings, inside the vault's `.obsidian/`.
- **Git lives outside Dropbox** (`~/Sites/bryan2026blog-main`). Sync races
  corrupt `.git`.
- **Check `PRODUCT.md` §12 before a structural decision** — several are already
  settled, with reasons.
