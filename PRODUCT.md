# PRODUCT.md — bryansebesta.net

> **Status:** Draft 2, 2026-07-20. **Purpose:** Product requirements and architectural decisions for Bryan's personal site. This is the document to re-read before making a structural choice. Companion to `CLAUDE.md` (which covers how to work in the repo, not what we're building).

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

### 3.1 Existing vault structure (as found, 2026-07-20)

```
Bryan's Notes/
  Notebook/          flat, title-addressed  → evergreen
  Logbook/           nested by year          → chronological
    1 Daily/         incl. voice-memo transcripts (private)
    2 Weekly/ 3 Monthly/ 4 Quarterly/ 5 Annual/
    Clippings/  Media/  People/
  Formation/         private (STRATEGY, RULE, NOW, OPERATIONS)
  ~ Attachments/
```

The `Notebook` / `Logbook` split already encodes the evergreen/chronological distinction the site needs. Preserve it.

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

### 7.4.2 Three link cases, not two

Wikilink resolution must handle:

1. **Target published** → rewrite to URL
2. **Target exists but unpublished** → render as plain text, no title
3. **Target does not exist anywhere in the vault** → render as plain text, no title

Case 3 is not theoretical: the sole published note links to `[[Friction creates a knowledge gap]]`, `[[Personal Kanban]]`, and `[[Embrace limits and constraints]]`, none of which exist in `Bryan's Notes`. Cases 2 and 3 render identically; only the reporting differs (case 3 should be surfaced as a dangling-link warning, since it likely indicates material still sitting in `Bryan's Past Writing`).

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

## 8. Third-party integration

**Micro.blog** — the pipeline pulls the JSON Feed at build time and **writes each post into the repo as a markdown `log` entry**. If Micro.blog disappears, every post is still owned. Rebuild via webhook.

**Claude interactives** — self-contained HTML, embedded via iframe within a page bundle for style and script isolation.

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

Escalation: (1) shared template + bundle CSS — covers most cases; (2) custom template `layouts/essay/<name>.html` when *markup* differs; (3) raw HTML in body, requiring `markup.goldmark.renderer.unsafe = true`.

Use plain CSS, not SCSS — `css.Sass` needs the extended Hugo binary and Dart Sass on Netlify, a rabbit hole not worth entering while styling is minimal.

**Scope page CSS now.** Emit a wrapper class from the slug (`<body class="essay-dartmoor">`) and scope every bespoke stylesheet under it. Trivial today, miserable to retrofit.

### 9.2 `source: repo`

The more art-directed a page is, the less it wants to round-trip through Obsidian — raw HTML and shortcodes render as garbage in the vault. Such pages are authored **in the repo**, with `source: repo`.

Without this flag the next export run either overwrites or orphans them. **This is a one-line rule today and a data-loss bug later.**

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

### Now

- [ ] Run `make stamp-apply` on the first note
- [ ] Confirm the `note_type` key name and its four values
- [ ] Hash-based asset idempotency (size comparison breaks once optimization lands)

### Next — pipeline v1

- [ ] Wikilink resolution, three cases (§7.4.2)
- [ ] `links.json`
- [ ] Backlinks, filtered by publish status (§7.4)
- [ ] Safety assertion against pipeline-generated surfaces
- [ ] Dangling-link report — likely points at material still in `Bryan's Past Writing`

### Then — site v1

- [ ] Remaining types (`essay`, `log`, `artifact`)
- [ ] Page-bundle CSS loading + slug-scoped wrapper class
- [ ] Image sizing / alt text (may require `goldmark.renderer.unsafe`)
- [ ] `domain` taxonomy, if tags prove insufficient

### Later

- [ ] Micro.blog ingest → repo markdown
- [ ] Pagefind index (unprominent)
- [ ] Obsidian templates standardizing frontmatter per type
- [ ] Backfill: standardize existing notes
- [ ] Hub notes / curated entry points
- [ ] Art direction begins — revisit Astro
