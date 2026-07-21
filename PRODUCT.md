# PRODUCT.md — bryansebesta.net

> **Status:** Draft 3, 2026-07-20. **Purpose:** Product requirements and architectural decisions for Bryan's personal site. This is the document to re-read before making a structural choice. Companion to `CLAUDE.md` (which covers how to work in the repo, not what we're building).

## 1. What this is

A personal hub at **bryansebesta.net** for writing, reading notes, a digital garden, designs, and learning.

It is explicitly **not** a portfolio. `bryansebesta.com` is the product-design portfolio; `.net` is the site that travels with Bryan across career changes. The `.com` may link into `.net`, and some notes may eventually be cross-published — that is a separate, later workflow and **no architectural decision here should be made to accommodate it**.

**Current focus:** information architecture, the JAMstack content pipeline, and simple semantic HTML. Art direction, color, typography, and design tokens are deliberately deferred.

**Governing principle:** *own it.* Content lives in files Bryan controls, in formats that outlive any vendor. Any third-party service (Micro.blog, Netlify, GitHub) must be replaceable without content loss.

## 2. Inspiration

**Primary:** [Andy Matuschak's notes](https://notes.andymatuschak.org/) (evergreen notes, stacked panes, opaque permanent URLs) · [Maggie Appleton's garden](https://maggieappleton.com/) (multiple types under one garden, art-directed essays) · [Mandy Brown's A Working Library](https://aworkinglibrary.com/) (reading notes as practice, restraint).

**Secondary:** [Robin Rendle](https://robinrendle.com/) (bespoke pages as craft objects) · [Dave Rupert](https://daverupert.com/) · [Ben Crowder](https://bencrowder.net/) · [Tiantian Xu's 100 Days](https://medium.com/the-100-day-project/100-days-of-motion-design-463526af852f).

## 3. Sources

**`Bryan's Notes/` is the single export hub.** Everything published originates there.

`Bryan's Past Writing/` and `Bryan's Learning/` are **reference only**. Material from them is published by first bringing it into `Bryan's Notes/` — never exported directly. One hub, one pipeline, one place to reason about exposure.

### 3.1 Vault structure (2026-07-20)

```
Bryan's Notes/
  Notebook/            flat, title-addressed  → evergreen, type: note
  Logbook/             chronological          → dated, type: log
    Artifacts/                                → type: artifact
    Books/
    Movies/
    Journal/           1 Daily … 5 Annual
      Formation/       hard-blocked (STRATEGY, RULE, NOW, OPERATIONS)
  ~ Attachments/       material Bryan did NOT write → source, never publishable
    Artifacts/  Clippings/  Images/  LLM Analysis/  Gospel of Thomas/
  ~ Templates/         scaffolding → excluded from indexing entirely
```

Two rules carry almost all the weight:

- **`Notebook` / `Logbook`** encodes temporality. Top-level folder → `temporality`.
- **`~ Attachments` means "I didn't write this."** Anything there is source material: private, unpublishable, citable by URL (§7.4.2).

The Logbook subfolders are type-shaped, so `note_type` derives from folder too — leaving frontmatter to declare only exceptions, like an essay sitting in `Notebook` among ordinary notes.

**Keep `Notebook` flat.** Folders impose one hierarchy on things whose value is belonging to many contexts at once; that's what links and tags are for. `Journal` is the opposite case and correctly foldered, because there time genuinely *is* the hierarchy.

## 4. Content model

### 4.1 The core insight

Early thinking conflated three axes under the single word "type," which produces combinatorial explosion (is a rewritten, art-directed movie essay its own type?). Instead: **one content object with facets.**

| Facet | Values | Controls |
|---|---|---|
| `type` | `note`, `essay`, `log`, `artifact` | Base template, editorial contract |
| `temporality` | `evergreen`, `dated` | Date display, sort, index behavior |
| `domain` | `film`, `book`, `design`, `learning`, `faith`, … | Filtering, grouping, hub membership |
| `layout` | `default`, `wide`, `custom` | Presentation only |
| `growth` | `seedling`, `budding`, `evergreen` | Confidence signal to reader |
| `id` | opaque, immutable | Identity, permalinks |
| `source` | `vault`, `repo` | Whether the pipeline owns this file |

**Restraint is the design.** Andy has essentially one type; Mandy has two. New `type` values require justification; new `domain` values are cheap.

### 4.2 The four types

- **`note`** — the default and the bulk of the site. Evergreen: revised in place, title-addressed, densely interlinked. Simple markdown.
- **`essay`** — a crafted argument. May carry page-scoped CSS. Longer-lived, more finished, fewer.
- **`log`** — chronological and immutable. Microposts, doodles, designs, dailies, **films and books**. A stream, not a garden.
- **`artifact`** — a self-contained interactive (e.g. Claude-generated). Standalone page or embedded in a note.

**Decision (2026-07-20):** films and books are **chronological**, not evergreen. This removes the main case where temporality contradicted folder location.

### 4.3 Growth status

Gardens die when everything must be finished. `growth` is surfaced in the UI so unfinished work can be published honestly. Default for new notes is `seedling`.

## 5. Vault ↔ site contract

### 5.1 The rule

**The vault contains *facts about content*, never *instructions to a renderer*.**

`type: essay` is a fact — true whether rendered by Hugo, Astro, or nothing. `layout: wide` is a rendering instruction. Rendering instructions are added by the pipeline or authored in the repo, on the repo side of the §7.1 boundary.

Apply this and the vault never learns anything Hugo-specific.

### 5.2 Key mapping (vault → site)

| Vault key | Site key | Note |
|---|---|---|
| `note_type` | `type` | **Renamed.** `type` is already used in the vault (`type: "Voice Memo"`, written by the memo importer) *and* reserved by Hugo. Avoid both collisions. |
| `publish` | — | Gate only; never emitted |
| `domain` | `domain` | Becomes a **Hugo taxonomy**, not a plain param |
| `growth` | `growth` | Custom param |
| `id` | `id` / permalink | Immutable |
| *(folder)* | `temporality` | Derived; frontmatter overrides |
| `aliases` | — | Used for wikilink resolution |

### 5.3 What Obsidian must provide

Only three things:

1. **A distinction between stream and graph** — already handled by `Notebook` / `Logbook`
2. **A type marker** — `note_type` in frontmatter, standardized via Obsidian templates
3. **A stable `id`** — the one piece of metadata that cannot be inferred later

Everything else is the SSG's business.

### 5.4 Hugo mechanics

- `Kind` is **reserved and not user-settable** in Hugo (`home`, `page`, `section`, `taxonomy`, `term`). Never use `kind` as a param name.
- `type` and `layout` are reserved *and* settable; together they drive template lookup (`layouts/essay/wide.html` → `layouts/essay/single.html` → `layouts/_default/single.html`). Verify exact paths against 0.158 docs — Hugo reorganized `layouts/` around 0.146.
- `slug` is reserved and controls the URL. Desired.
- Evergreen content sorts and displays by `lastmod`; dated content by `date`.
- **Do not use `cascade`** for facet defaults. Put defaults in the pipeline so the logic lives in the portable layer.

## 6. Navigation

**Navigation is not the content model.** Nav is shallow and activity-shaped; facets do the filtering.

The spine from `Bryan's Notes/SITE.md`:

```
WRITING · READING · LEARNING
```

Verbs, not formats — which is why it survives adding a film log or a doodle series. Types appear as filters *within* sections, never as top-level nav.

**Ways in — browsing over searching (§10):** hub notes, curated entry points, domain/tag indexes, recently-updated, possibly a graph view.

## 7. The pipeline

### 7.1 The contract

```
Obsidian vault  →  [ export pipeline ]  →  clean markdown + links.json  →  [ SSG ]  →  static site
```

The pipeline knows nothing about the site generator. Its output is plain markdown with resolved links plus a JSON link graph. **Swapping SSGs is a template rewrite, not a migration.**

### 7.2 Stack

Python. The pipeline transforms markdown *into* markdown — the SSG does the parsing — so it needs no markdown library. Two dependencies: `python-frontmatter`, `PyYAML`. Nothing that rots.

```
pipeline/
  export.py     # entry, CLI, dry-run
  registry.py   # pass 1: scan & index
  transform.py  # wikilinks, transclusion
  assets.py
  emit.py       # markdown, links.json, _redirects
  config.yaml
```

**Pass 1 — scan and index.** Walk the *entire* vault, published or not, building `{id: {title, aliases, slug, publish, facets, path}}`. Indexing unpublished notes is required: you cannot safely handle a link to a private note unless you know it exists. Also catches title collisions, which Obsidian tolerates and the URL space will not.

**Pass 2 — transform and emit.** Rewrite wikilinks, expand transclusions, collect assets, normalize frontmatter, write markdown, accumulate graph edges. Then `links.json`, referenced assets only, redirects.

### 7.3 Commands

```
python -m pipeline.stamp --dry-run   # report notes needing an id
python -m pipeline.stamp --apply     # writes to vault — deliberate, local only
python -m pipeline.export            # read-only against the vault, always
```

**Stamping must never be part of export.** If export runs in CI and export stamps, CI writes back to the vault — a sync hazard and a way to lose IDs silently.

### 7.4 Publishing gate — a safety requirement

The vault contains faith-crisis notes, health data, career strategy, family history, and voice-memo transcripts of family conversations. This is exposure risk, not a feature.

- **Allowlist only.** `publish: true`. Never a denylist, never "publish folder X."
- **Normalize `publish` carefully.** Existing notes carry the *string* `"true"` / `"false"` from Obsidian's Properties UI. A `"false"` string is truthy in most languages — precisely the bug that publishes something you didn't mean to. Fail closed on anything not unambiguously true.
- **Unpublished links must not leak titles.** A published note linking to a private one renders as plain text *with no title* — a dead link exposes the title, which for this material can itself be the disclosure.
- **The publish filter applies to the backlink index, not just inline links.** A private note that links *to* a published note would otherwise surface its own title in that page's backlink panel. Backlinks must be filtered by publish status at emit time — links are directional, exposure is not.
- **Assert before writing:** no output file may contain the title of any unpublished note. Run the assertion against backlink output as well as body content.
- **Print a diff** of newly published / newly unpublished notes on every run.

### 7.4.1 Measured state of the vault (2026-07-20)

| | |
|---|---|
| Notes carrying a `publish` key | 133 |
| `publish: "false"` (string) | **132** |
| `publish: "true"` (string) | 1 |

The 132 include `Letter to Gerald (unsent)`, `Conversation with Ashley`, and numerous SelectHealth work notes. **A naive `if note.get("publish"):` publishes every one of them.** This is not a hypothetical hazard; it is the current state of the data.

Most Notebook notes have no frontmatter at all, so the default state of the vault is *unpublished*. The system fails closed before any code is written — but only if `publish` normalization is explicit.

### 7.4.2 Five link cases

Wikilink resolution must handle:

| Target | Renders as |
|---|---|
| Published note | Internal link |
| **Source note with `url:`** | **External link to the original** |
| Source note without `url:` | Plain text |
| Exists but unpublished | Plain text, no title |
| Does not exist in the vault | Plain text, no title |

The source case is the interesting one. `~ Attachments/` holds **material Bryan did not write** — clippings, LLM analysis, course material, PDF publications. Potentially copyrightable, always private. But a published note may legitimately cite one.

Rather than flattening that to a dead phrase, the pipeline substitutes the source's own `url:` and emits an external link. **A private reading note becomes a public citation.** Without a `url` there is nothing honest to point at, so it degrades to plain text — and export reports which sources are missing one, since that's a fixable gap.

The dangling case is not theoretical: the sole published note links to `[[Friction creates a knowledge gap]]`, `[[Personal Kanban]]`, and `[[Embrace limits and constraints]]`, none of which exist in `Bryan's Notes` — they're still in `Bryan's Past Writing`.

### 7.4.3 Three exclusion tiers

| Tier | Config | Behaviour |
|---|---|---|
| **Excluded** | `exclude_dirs` | Not indexed at all. Links resolve as "not in vault". `.obsidian`, `.trash`, `~ Attachments/Templates` |
| **Source** | `source_dirs` | Indexed, never publishable, links substitute `url:`. `~ Attachments` |
| **Blocked** | `never_publish_dirs` | Indexed and linkable, but the publish flag is not consulted. `Logbook/Journal/Formation` |

The distinction matters. Excluded material is invisible; source material is visible enough to cite; blocked material is visible and linkable but can never ship.

**Blocked and source guard against different failures than the publish gate.** The gate protects against *accident* — a stray `publish: true`. These protect against *intent*: publishing a clipping without realising a full-text capture is republication, or publishing a Formation doc without realising it's personal strategy.

### 7.5 Identity

**Decision: the pipeline stamps IDs; Obsidian templates optionally pre-stamp.**

Templates only cover notes created *through* a template. The vault demonstrably contains notes that bypass them — the voice-memo importer, clippings, mobile capture. Template-only generation is incomplete by construction.

Only **published** notes need IDs — a few dozen, not a few thousand. Stamping at publish time touches a small reviewable set and never modifies private material.

**Format:** random, ~10 chars, alphabet excluding `0/O` and `1/l/I`. Not timestamps — for an evergreen note, creation time is the least meaningful fact about it, and it invites reading significance into an identifier that should carry none.

Current Notebook filenames are full sentences (*"If we don't learn to mythologize our lives, inevitably we will pathologize them..md"* — note the stray double period). These will be rewritten, and they are currently the only handle on a note.

### 7.6 Known implementation hazards

1. **Wikilink regex vs. code blocks** — mask fenced and inline code before matching. Handle `[[Note]]`, `[[Note|Alias]]`, `[[Note#Heading]]`, `![[Note]]`, `![[img.png|400]]`.
2. **Transclusion cycles** — depth limit + visited set. Drop embeds of unpublished notes silently. Defer block refs (`![[note#^abc]]`).
3. **Slug history** — persist `slugs.json` (`id → [current, ...previous]`), emit Netlify `_redirects`.
4. **Dropbox cloud-only files** — undownloaded placeholders will error on walk. Detect and *report*; never skip silently.
5. **Idempotency** — content-hash outputs, skip unchanged, so commits show "three notes changed," not 800 touched files.

## 7.7 Media libraries — books and films

Both are `type: log`: chronological, dated, revised only by adding a new entry.
A rewatch or reread is a **new note**, not an edit to the old one.

### Field vocabulary

Canonical order lives in `pipeline/bookschema.py` — `BOOK_KEY_ORDER` and
`MOVIE_KEY_ORDER` — and every script that writes such a note imports it.

**The vocabulary is Bryan's existing one.** 500+ notes already used `authors`,
`publishers`, `pageCount`, `publishedYear`; renaming to a tidier scheme would
have been migration cost for no benefit. The templates were initially written
with different names (`author`, `published_year`) and had to be corrected —
worth remembering that a schema invented ahead of the data tends to lose.

| Concept | Books | Films |
|---|---|---|
| When Bryan encountered it | `date` | `date` |
| When the work appeared | `published` / `publishedYear` | `released` / `releasedYear` |
| Creator | `authors` | `director` |
| Secondary creators | `contributors` | `writer`, `actors` |
| Image | `cover` | `cover` |

`cover` is deliberately named the same for both, so one Bases column and one
`extra_fields` entry serves each.

### Three decisions worth keeping

**`cover` is a wikilink in the vault** (`"[[poster-x.jpg]]"`). Obsidian's Bases
cards view renders an image only for a link, URL, or hex colour — a bare
filename shows nothing. `emit.py` strips the brackets and repoints the value at
the copied filename on the way out, since assets are slugified when copied.

**`contributors` carries the role** — "Emily Wilson (Translator)". Open Library
records translators on the *edition* while the author often sits on the *work*
record; the lookup reads both. A translation is not interchangeable with any
other edition, so this is identity rather than trivia.

**`dateYear` was removed** from 426 notes. It existed only because Dataview
could not group by a computed value. Bases can — `groupBy: formula.read` over
`if(date, date.format("YYYY"))` — so it was pure duplication of `date`.

`publishedYear` was *kept* despite looking similar: `published` arrives as
either `2017` or `2011-12-27`, so the year field is a normalisation over
inconsistent input rather than a denormalisation of clean input.

### Provenance and its obligations

| Source | Used for | Obligation |
|---|---|---|
| Open Library | Book metadata, covers | Descriptive `User-Agent` or it returns 429 |
| Google Books | Fallback metadata | Anonymous quota is per-IP and exhausts fast |
| Amazon | Cover images by ISBN-10 | 979-prefix ISBNs have no ISBN-10 |
| TMDB | Film metadata, posters | **Attribution required site-wide** |

TMDB's terms require stating that the site uses their API but is not endorsed
by them. That line is in the site footer, alongside Open Library's credit.

**Images are downloaded, never hot-linked.** Remote URLs rot, and hot-linking
would make every visitor's browser call Amazon or TMDB. The old film notes
stored remote Amazon poster URLs; the migration downloaded them, upgrading
`_SX300` to `_SX900` on the way (~5× the resolution for the same image).

`imdbId` and `tmdbId` are both kept. IMDb's is the portable join key that every
other service carries; TMDB's is the tooling handle for direct re-fetches.
Neither requires an API key at render time — the URLs are static.

### Where the effort actually is

Books: 407 notes, near-complete metadata, **almost no reviews**. The migration
gave Bryan a browsable library, not a publishable one.

Films: 45 notes, **32 already carry reviews**. The opposite situation, and the
reason films will reach the site first.

No script writes a review. That is the whole remaining job.

## 8. Third-party integration

**Micro.blog** — the pipeline pulls the JSON Feed at build time and **writes each post into the repo as a markdown `log` entry**. If Micro.blog disappears, every post is still owned. Rebuild via webhook.

**Claude interactives** — self-contained HTML, embedded via iframe within a page bundle for style and script isolation. **Implemented** — the `artifact` fence and its pipeline are described in §9.3.

## 9. Presentation

### 9.1 Bespoke, art-directed pages

Rendle-style pages are design objects, not notes that look nice. Mechanism: **leaf bundles.**

```
content/essays/dartmoor/
  index.md
  style.css
  images/
```

```go
{{ with .Resources.GetMatch "style.css" }}
  {{ $css := . | resources.Minify | resources.Fingerprint }}
  <link rel="stylesheet" href="{{ $css.RelPermalink }}">
{{ end }}
```

Escalation: (1) shared template + bundle CSS — covers most cases; (2) custom template `layouts/essay/<name>.html` when *markup* differs (the hand-authored-HTML recipe is §9.4); (3) raw HTML in the body — now available, since `markup.goldmark.renderer.unsafe` is enabled site-wide for the artifact iframe (§9.3).

Use plain CSS, not SCSS — `css.Sass` needs the extended Hugo binary and Dart Sass on Netlify, a rabbit hole not worth entering while styling is minimal.

**Scope page CSS now.** Emit a wrapper class from the slug (`<body class="essay-dartmoor">`) and scope every bespoke stylesheet under it. Trivial today, miserable to retrofit.

### 9.2 `source: repo`

The more art-directed a page is, the less it wants to round-trip through Obsidian — raw HTML and shortcodes render as garbage in the vault. Such pages are authored **in the repo**, with `source: repo`.

Without this flag the next export run either overwrites or orphans them. **This is a one-line rule today and a data-loss bug later.**

### 9.3 Artifacts — Claude-generated interactives *(implemented 2026-07-20)*

An `artifact` is a self-contained HTML interactive (§4.2). It lives in
`Logbook/Artifacts/` and is referenced from its note by a fenced block, so the
note stays portable markdown — no raw HTML pins it to one renderer:

````text
```artifact
src: nibley-infrastructure-map.html
height: 720
```
````

The `.html` sits in `~ Attachments/Artifacts/`. On export, `emit.py`
(`resolve_artifacts`) copies it into the note's page bundle and rewrites the
fence into an `<iframe>` pointing at the copied file. The iframe gives the
interactive its own document scope — its styles and scripts can't reach the
page, nor the page's it. `layouts/artifact/single.html` renders it and adds a
fullscreen link. A missing `src:` is reported and the fence dropped, exactly
like a missing image embed.

Two Hugo settings in `hugo.toml` make this work:

- **`goldmark.renderer.unsafe = true`** — the emitted iframe is raw HTML, which
  goldmark otherwise drops. Safe here because every byte of content is
  generated by our own pipeline from the vault, never third-party input.
- **`contentTypes` narrowed to markdown** — see §12.2. Without it a bundled
  `.html` is parsed as a headless content *page* (no file URL, never
  published) instead of a static resource the iframe can load.

### 9.4 Hand-authored HTML pages

The bespoke-page escalation (§9.1) bottoms out in hand-written HTML. Because
`contentTypes` no longer treats `.html` as content (§12.2), that HTML must not
live in a `.html` content file — it lives in a **template**, fronted by a
markdown stub:

```
content/dartmoor/index.md              layouts/essay/dartmoor.html
---                                     {{ define "main" }}
title: Dartmoor                           …hand-authored HTML…
type: essay                             {{ end }}
layout: dartmoor
source: repo    # §9.2 — export never overwrites it
---
```

Hugo resolves `type` + `layout` to `layouts/essay/dartmoor.html`. The stub
carries identity (title, id, facets, `source: repo`) and joins the link graph;
the template carries the design. Same mechanism as the `artifact` layout, just
with the markup hand-written instead of iframed.

- For a **truly standalone** page — its own everything, no site chrome, not in
  the content model — drop the file in `static/`; it publishes verbatim at
  `/<name>.html`. Simpler, but it has no front matter, no bundle, and no place
  in the link graph.
- If you ever genuinely need `text/html` back in `contentTypes`, **do not
  re-widen the config** — that re-breaks artifacts (a bundled `.html` becomes a
  page again). Instead relocate artifact HTML out of content bundles into
  `assets/` and load it with `resources.Get` in the layout; Hugo's asset
  pipeline publishes it regardless of `contentTypes`. That costs a pipeline
  change (a Hugo-specific output path) but leaves both paths working.

## 10. Search — deliberately de-emphasized

**Search is a utility, not a front door.** A garden you can only search is a database. Entry points should encourage browsing: hub notes, curated sections, domain indexes, recently-updated, graph views.

Feasibility is not the issue — [Pagefind](https://pagefind.app/) builds a chunked static index, ships no server, loads only what a query needs, and is SSG-agnostic. Roughly an afternoon.

**Build the index, give it no prominent placement, ship it late.**

## 11. Stack

### 11.1 Current

Hugo 0.158.0 → Netlify. Repo is a bare scaffold: `hugo.toml` (placeholder `baseURL`), one `layouts/index.html`, `netlify.toml`, stock archetype. No content, no theme, **not yet a git repo**.

### 11.2 Hugo vs. Astro

| | Hugo | Astro |
|---|---|---|
| **For** | Single binary, no npm rot, instant builds, will run in ten years | Content collections express the facet model directly; MDX for art-directed essays; islands for interactives; `remark-wiki-link` |
| **Against** | No native wikilinks; Go templates fight components and art direction | Dependency treadmill; maintenance attention better spent writing |

**Decision: stay on Hugo.** Familiar, and the current focus is IA and pipelines, not presentation. Revisit when art direction becomes the main work — bespoke essays are the strongest argument for Astro.

### 11.3 Portability to Astro

| Ports cleanly | Does not |
|---|---|
| `type` → content collection | **Taxonomies** — Astro has no equivalent; every term/list page is hand-rolled via `getStaticPaths()`. Largest single Hugo-specific investment. |
| `domain`, `growth`, `temporality`, `id`, `slug` → Zod schema fields | `layout` — the *value* ports, Hugo's automatic lookup does not |
| `links.json` | Shortcodes → MDX components (another reason to use few) |
| Page bundles | `cascade` |

Porting costs template work and **zero content migration**. Markdown, frontmatter, link graph, and URLs survive intact.

**Set taxonomy URL structure explicitly in `hugo.toml`** rather than accepting defaults — URL structure is the only thing here genuinely expensive to change after you have readers.

### 11.4 Repo hygiene

- Not yet under version control. `git init`.
- **Git inside Dropbox is a hazard** — sync races corrupt `.git`. Move the repo outside Dropbox; the pipeline reads the vault in Dropbox and writes to the repo outside it.
- `baseURL` is still `https://example.org/`.

## 12. Open decisions

| # | Decision | Recommendation |
|---|---|---|
| 1 | Does the `id` appear in the URL? | **RESOLVED 2026-07-20 — yes.** See §12.1 |
| 2 | Final `type` list — is four right? | Start with four; add only under pressure |
| 3 | Is a Rendle-style bespoke page a new type, or `essay` + `source: repo`? | Lean `essay` + `source: repo` |
| 4 | Do evergreen-note *updates* belong in a feed? | Separate "recently updated" feed |
| 5 | Per-domain feeds, or one? | One main + opt-in per-domain later |
| 6 | Stacked panes (Andy-style)? | Defer — client-side, SSG-independent |
| 7 | Graph view as browsing entry point? | Cheap once `links.json` exists |
| 8 | Where does the repo live outside Dropbox? | Decide before `git init` |
| 9 | Artifacts: own folder under `Logbook`, or frontmatter-only in `1 Daily`? | **Own folder** — a folder of twelve is reviewable; three thousand daily notes are not |
| 10 | Taxonomy URL structure | Set explicitly, don't accept defaults |
| 11 | Is `.html` a content type? | **RESOLVED 2026-07-20 — no**, narrowed to markdown. See §12.2 |

### 12.1 Decision — the id appears in the URL

**Canonical URL is `/<id>/`. The slug is an alias that redirects to it.**

The reasoning is mechanical, not aesthetic. On a static host there is no
resolver: a URL either exists as a generated path or 404s. So `/<id>/<slug>/`
would *not* be permanent — change the title, change the slug, change the path,
break the link. **The ID only delivers permanence if the ID is the whole path.**

Hugo's `aliases` frontmatter generates the redirects:

```yaml
id: z5E5QawiXCMbt        # canonical → /z5e5qawixcmbt/
aliases:
  - /strategic-staircase-method-as-solution-to-knowledge-gap/
  - /older-slug-from-before-the-rename/          # from slugs.json history
```

Every slug a note has ever had keeps redirecting to the canonical ID URL.
Rename freely; nothing breaks, ever.

**The cost is that shared links are opaque** — this is the Andy Matuschak
tradeoff, made deliberately. If that proves unpleasant in practice, flipping
canonical and alias (pretty slug canonical, ID URL as an immortal permalink) is
a one-line change in `emit.py`. The ID exists either way; only which one is
canonical changes.

### 12.2 Decision — `.html` is not a content type

**`hugo.toml` narrows `contentTypes` to markdown alone. Resolved 2026-07-20.**

Hugo classifies `.html`, like `.md`, as a *content* format. An artifact's
`.html` sitting in its page bundle was therefore parsed as a headless content
page: no `RelPermalink`, never written to `public/`, so the iframe 404'd.
Narrowing `contentTypes` to markdown makes a bundled `.html` an ordinary file
resource — it publishes and gets a URL (§9.3).

This is safe because **all real content here is pipeline-generated markdown**;
nothing is authored as an `.html` content file. Hand-authored HTML pages live
in `layouts/`, not `content/` (§9.4), so they are unaffected.

The escape hatch, if `.html`-as-content is ever genuinely wanted: move
artifacts to `assets/` + `resources.Get` rather than re-widening the config
(§9.4).

## 13. TODO

### Done

- [x] **Decision #1** (id in URL) — resolved, §12.1
- [x] **Decision #8** (repo location) — `~/Sites/bryan2026blog-main`, outside Dropbox
- [x] `git init`, `.gitignore`, `baseURL`, flat permalinks, `tags` taxonomy
- [x] Scaffold `pipeline/` with dry-run by default
- [x] Pass 1: registry over the full vault; title-collision reporting
- [x] Publishing gate: allowlist, string-`publish` normalization, fail-closed
- [x] Diff report of newly published / withdrawn notes
- [x] Dropbox cloud-only file detection
- [x] Minimal Hugo templates — verified building on Hugo 0.158.0+extended
- [x] First note live end-to-end

- [x] Asset handling — page bundles, embed resolution, orphan pruning
- [x] `stamp` command, dry-run first, textual frontmatter insertion
- [x] Emit `id` as canonical URL + slug aliases (§12.1)
- [x] Slug history (`slugs.json`) feeding aliases
- [x] `Makefile` wrapping the venv

- [x] Books: migrated 515 → deduped → 407, covers on all but two
- [x] Films: migrated 45, posters downloaded, all covered
- [x] Canonical schema in `bookschema.py`, enforced by every writer
- [x] `make audit` — read-only schema check
- [x] QuickAdd macros for both media, key-free for books
- [x] Bases views: `§ Library.base`, `§ Films.base`
- [x] `layouts/log/single.html` — one template for books and films
- [x] `dateYear` removed; Bases groups by formula instead

- [x] `artifact` type end-to-end — the `artifact` fence (§9.3),
      `emit.resolve_artifacts` copies the `.html` and rewrites it to an
      `<iframe>`, `layouts/artifact/single.html`, first artifact live
- [x] `goldmark.renderer.unsafe` enabled; `contentTypes` narrowed to markdown
      so a bundled `.html` publishes as a file resource (§12.2)

### Now

- [ ] Confirm the `note_type` key name and its four values
- [ ] Hash-based asset idempotency (size comparison breaks once optimization lands)
- [ ] Sweep `~ Attachments/Images/Covers/` for orphans left by replaced covers
- [ ] Decide whether `imdbScore` / `metaScore` are worth keeping — they're
      frozen snapshots from whenever the OMDb import ran, and unlike an id
      they can't be refreshed without another API round
- [ ] **Write reviews.** 407 books with none; films are ahead at 32 of 45

### Next — pipeline v1

- [ ] Wikilink resolution, three cases (§7.4.2)
- [ ] `links.json`
- [ ] Backlinks, filtered by publish status (§7.4)
- [ ] Safety assertion against pipeline-generated surfaces
- [ ] Dangling-link report — likely points at material still in `Bryan's Past Writing`

### Then — site v1

- [ ] Remaining type: `essay` (the `log` and `artifact` templates exist)
- [ ] Page-bundle CSS loading + slug-scoped wrapper class
- [ ] Image sizing / alt text — `goldmark.renderer.unsafe` is now enabled
      (§9.3), so raw-HTML `<img>` width is unblocked when wanted
- [ ] `domain` taxonomy, if tags prove insufficient

### Later

- [ ] Micro.blog ingest → repo markdown
- [ ] Pagefind index (unprominent)
- [ ] Obsidian templates standardizing frontmatter per type
- [ ] Backfill: standardize existing notes
- [ ] Hub notes / curated entry points
- [ ] Art direction begins — revisit Astro
