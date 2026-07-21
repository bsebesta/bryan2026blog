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
| `presentation` | `wide`, `custom` | Optional. Portable intent, not a template name (§5.1) |
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

**Sharpened, 2026-07-21.** "Is it presentation?" turned out to be the wrong test — some presentational intent belongs in the vault. Two better questions:

**1. Is it portable?** `layout: wide` is Hugo's template-lookup mechanism: a filename. `presentation: wide` is an abstract statement that *this piece needs room*, which Astro, Eleventy, or a print stylesheet could each honour differently. The first is a directive to one renderer; the second is a fact about the work.

**2. Is the vault authoritative?** Does the vault *know* this, or is it asserting something about somewhere else?

| Candidate | Portable | Vault knows | |
|---|---|---|---|
| `presentation: wide` | yes | yes — authorial intent | **allowed** |
| `presentation: custom` | yes | yes — you decided the published form is hand-built | **allowed** |
| `presentation: custom-css` | yes | **no** — only the repo knows whether CSS exists | rejected |
| `layout: wide` | no — a Hugo filename | — | rejected |

The second test is the one that catches subtler mistakes. A field the vault can *claim* but not *guarantee* isn't a fact; it's a wish, and it will drift silently. Whether custom CSS exists is the repo's business, discovered by the pipeline finding `presentation/<id>/style.css` — never declared.

`presentation` is therefore a **two-value enum**, both optional. Absence is the default. The pipeline emits it as a page param; Hugo renders `presentation-wide` as a body class. Another generator would read the same field and decide for itself.

`presentation: custom` also does non-visual work: it tells you, in Obsidian, that the note's body is a *draft* rather than what ships (§9.3.1). Export reports any note claiming `custom` without a presentation bundle behind it.

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
| **Source** | `source_dirs` | Indexed, never publishable, links substitute `url:`. Material whose canonical home is elsewhere: `~ Attachments`, `Logbook/Microposts` |
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

## 7.8 How Bryan runs it — the dock

The whole pipeline is `make` targets, but Bryan does not live in a terminal.
The day-to-day interface is **four compiled AppleScript droplets in the macOS
dock** (`tools/*.applescript` → `~/Applications/bryansebesta.net/`), each
opening a terminal and running one `make` target. This is not a convenience
bolted on after the fact; it is *the* interface, and the pipeline's ergonomics
are designed around it. A step that can't be a labelled button Bryan clicks is
a step he won't run reliably.

The droplets are numbered in workflow order — Download the newest microposts,
Prep the vault, Serve to preview, Commit to publish:

| Dock droplet | Target | What it does | Cadence |
|---|---|---|---|
| **1 Download Microposts** | `make micro-download` | Pull new microposts from the Micro.blog API into the vault. Dry-run, then confirm. Does *not* export. | When there are new microposts |
| **2 Prep Notes** | `make prep` | Vault hygiene: seed → normalize → stamp → export. Dry-run, then confirm. | Before publishing |
| **3 Serve** | `make serve` | Export, then the Hugo dev server for local preview. | While working |
| **4 Commit** | `make commit` | Export, review the diff, prompt for a message, commit and push. | To publish |

Three design rules the droplets encode:

**Every vault-writing droplet shows a dry run and waits for confirmation.** A
double-clickable icon that silently rewrote thousands of notes would undo the
entire point of the dry-run design. This is why they run through a real
terminal — Automator and Shortcuts cannot prompt.

**Download is first, and separate from Prep.** The obvious instinct is to fold
micropost download into the routine Prep step. It is deliberately its own button
because it is *occasional* (run only when there are new posts) — running it on
every Prep would hit the API needlessly. Prep is hygiene on what Bryan wrote;
Download brings in what Micro.blog holds. Different cadence, different trigger.

**Download stops at the vault; it does not export.** Its scope is "pull posts
into Obsidian." Every droplet that follows it (Prep, Serve, Commit) runs export,
so regenerating `content/` and the homepage micropost list is their job — a
Download that also exported would be redundant work in the common
Download → Prep → Commit sequence.

## 8. Third-party integration

**Micro.blog** — Micro.blog authors short-form posts; `micro.py` (`make
micro-api` / the **Download Microposts** dock droplet) **ingests them into the
vault as markdown** Source-tier notes, and the site shows them as links out to
their Micro.blog home rather than hosting copies. If Micro.blog disappears, every
post is still owned. See §12.3 for the full decision and the as-built mechanics,
and §7.8 for how it's run.

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

### 9.1.1 Raw HTML in a note — the blank-line rule

**A raw HTML block in a vault note must contain no blank lines.**

CommonMark ends an HTML block at the first blank line. Everything after it is
re-parsed as Markdown, and any line indented four or more spaces becomes an
indented code block — so a hand-built `<div>` renders partially, then dumps its
own source onto the page as code.

```html
<div style="…">
                          ← block ends HERE
  <div>…</div>            ← parsed as a new HTML block (still renders)

    <!-- STEP 1 -->       ← 4-space indent after a blank line = CODE BLOCK
```

Obsidian's Reading view is more forgiving and renders it correctly, so **the
note looks fine in the vault and breaks only on the site**. That asymmetry is
what makes this worth writing down.

Requires `markup.goldmark.renderer.unsafe = true` in `hugo.toml`, which is set.

### 9.1.2 Mermaid

Hugo has no Mermaid support; a ```mermaid fence renders as a plain code block.
Two pieces make it work:

- `layouts/_default/_markup/render-codeblock-mermaid.html` turns the fence into
  `<div class="mermaid">` and sets a `hasMermaid` flag on the page
- `baseof.html` loads Mermaid from a CDN **only when that flag is set** — the
  library is ~2MB and most pages have no diagram

`securityLevel: "strict"` blocks click handlers and inline HTML in diagram
labels, so a diagram can't inject script into the page.

### 9.3 Stories — art-directed pages

A **story** is a page whose layout carries part of the argument. Rendle's
essays are the reference. Four ways to build one, escalating in isolation:

| | Authored in | Isolation | Keeps |
|---|---|---|---|
| Bundle + scoped CSS | Vault | Layers over base styles | Everything |
| **Bundle + `layout: story`** | **Repo** | **Own document, no site chrome** | **Everything** |
| Standalone HTML in `static/` | Repo | Total | Nothing — outside the graph |
| Iframed artifact | Either | Total, both directions | Page wrapper only |

### 9.3.1 Presentation overrides — the default route

**Decision (2026-07-21): every piece of writing lives in the vault.** The
archive principle outranks avoiding duplication. A page whose published form is
hand-built still keeps its draft in Obsidian, where it can be written, linked,
searched, and kept.

A repo directory keyed by the note's **permanent id** supplies presentation:

```
presentation/<id>/style.css     design only  → vault body, repo styling
presentation/<id>/index.md      body too     → repo body, repo styling
```

Keyed by id rather than slug, so renaming a note never orphans its design.

**Nothing about rendering enters the vault.** The note carries no `layout`, no
`source`, no CSS reference — the pipeline infers all of it from the directory's
existence. The vault stays facts-only (§5.1), and the note stays a note.

**The vault always owns metadata**: title, id, tags, dates, links, backlinks.
Only the *body* can diverge, and only for pages built out of markup rather than
written as prose. That divergence is the feature — the draft is archived, the
published arrangement is designed.

A warning callout in the vault note records that its body isn't what ships.

**Link graph, when the body is overridden.** Both sets of links count: the
draft's wikilinks (real links in the vault's own graph) and the published
body's `relref`s (what a reader can actually follow). Backlinks describe the
site, so the published body's links must be parsed too.

Worked example: `Notebook/What a Page Can Be.md` + `presentation/4f3c43y3ke/`.

### 9.3.2 `source: repo` — the exception

For a page with **no vault original at all** — a hand-built index, a one-off
experiment, something that isn't writing. `layouts/_default/story.html` emits
its own `<html>`, and `source: repo` in the frontmatter stops the pruner
deleting it.

Rare by design. If there are words worth keeping, they belong in the vault, and
§9.3.1 is the route.

**Cascade layers make this painless.** The site's base styles live in
`@layer base`; a page's own stylesheet is unlayered. **Unlayered CSS always
beats layered CSS regardless of specificity**, so a story's design wins with no
`!important` and no need to know what the defaults are.

**Links use `relref`, not hardcoded URLs.** Resolved at build time against the
content graph, so a retitled or moved note is followed automatically — and a
missing target **fails the build** rather than shipping a dead link.

**Reach for this rarely.** A story is authored in the repo rather than Obsidian,
needs its own CSS, and can't be revised casually. That price is worth paying
when the layout does argumentative work, and not otherwise. The default should
stay boring; exceptions earn their keep by being rare.

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
| 12 | How do Micro.blog microposts reach the site? | **Ingest into the vault**, then export normally. See §12.3 |
| 13 | Micro.blog custom domain — subdomain or apex? | **RESOLVED 2026-07-21 — `micro.bryansebesta.net`**, existing handle kept. See §12.3 |

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

### 12.3 Decision — microposts live in the vault and publish as links, not pages

**Resolved and implemented 2026-07-21** (`pipeline/micro.py`, `make micro` /
`micro-api` / `micro-download`, homepage list in `export.py`). One external
question remains open (see Unverified). This supersedes the build-time feed pull
described in earlier drafts of §8.

Micro.blog is the natural home for short-form posts written from a phone. The
posting ergonomics are the entire product; they cannot be replicated by a
pipeline, which is why pushing *to* Micro.blog from the vault was rejected —
it costs $5/month for a syndication endpoint Mastodon gives away, and requires
opening a laptop to write a sentence.

**Micro.blog authors and hosts. The vault archives. The site links.**

```
Micro.blog  ──micro-apply──▶  Logbook/Microposts/  ──▶  data/microposts.json
   (canonical)                  (source tier)              (latest N links)
```

Three consequences, all simplifying:

- **No micropost is ever emitted as a page.** There is exactly one URL for a
  micropost, and Micro.blog owns it. No ids stamped, no `/<id>/`, no
  duplicate-content question, no `rel=canonical` work.
- **§12.1 is untouched.** The permanence contract governs pages; microposts
  aren't pages.
- **The vault copy exists for search and for one-place-ness**, not to feed the
  site. If ingest broke tomorrow, nothing on `bryansebesta.net` would change
  except the link list going stale.

#### The Source tier is the mechanism, and it already exists

§7.4.3 defines it as *indexed, never publishable, links substitute `url:`*.
That is exactly the required behaviour: a wikilink to a micropost from any
published note renders as a link to its Micro.blog URL. **Add
`Logbook/Microposts` to `source_dirs`.**

This required correcting the tier's description. `~ Attachments/` was its only
member, so the tier had been glossed as "material Bryan did not write" — a
copyright guard. That is the *occupant*, not the rule. The rule is **material
whose canonical home is elsewhere**, and microposts are the second instance:
Bryan's own writing, living authoritatively on Micro.blog. §7.4.3 updated
accordingly.

#### Filenames — timestamp, from `date_published`

**`2024-08-09-141306.md`.** Seconds included; five posts landed on the morning
of 2024-08-09 and the collision question is worth retiring outright.

Rejected: first-words slugs (`2024-08-09-currently-reading-the.md`), readable
excerpts, and the id itself.

The readability case for a content-derived name is weaker than it looks.
Obsidian search is full-text, so finding a micropost never consults the
filename; a `log` folder is browsed chronologically rather than by name, and
every candidate sorted correctly; and wikilinking *to* a micropost is rare by
construction — §4.2 defines a log as stream, not garden.

**The deciding argument is stability.** Ingest is an idempotent overwrite
keyed on the post's URL path. A content-derived filename changes when a post
is edited upstream, turning that overwrite into a rename-and-migrate and
forcing `state/microblog.json` to track filename history to avoid orphans.
`date_published` never changes. The overwrite stays an overwrite, forever.

The observed corpus also shows derivation failing on its own terms:
Micro.blog's own slugs truncate mid-phrase (`currently-reading-the`), and
photo-only posts have no words to derive from at all — Micro.blog falls back
to a bare timestamp (`141306.html`). A first-words scheme is therefore two
schemes and a branch.

Opacity is mitigated without touching stability: `url:` in frontmatter points
at the origin post, and Obsidian's frontmatter title supplies a readable
display name in search and graph view while the filename stays put.

#### Microposts do not absorb books and films

The archived corpus is dominated by 📚 and 🎥 — but `Logbook/Books/` and
`Logbook/Movies/` already exist with a real schema (§7.7). **Microposts remain
their own category.** A micropost about a film is a micropost. Books and films
are the garden's business; the micropost stream is not a second front door to
them.

#### Mechanics — as built (`pipeline/micro.py`, 2026-07-21)

- **Backfill source:** Micro.blog for macOS, File → Export → Markdown. Yields
  clean markdown with `title` / `date` / `url` frontmatter plus a mirrored
  `uploads/` photo tree, all local. `micro.py` reads this folder; photos are
  **copied from it**, never fetched from Micro.blog's CDN — exact bytes, offline.
- **Incremental (implemented 2026-07-21):** `--from-api` pulls live from
  Micropub `q=source` with an app token — no Mac app, no manual export. Verified
  against the live API: `content` comes back as **markdown** with any photo as an
  inline `<img>`, exactly the export's shape, so the same parser handles both.
  **Not `feed.json`** — its `content_html` would mean a lossy HTML→markdown
  round-trip. The token lives only in `$MICROBLOG_TOKEN`, never the repo. The
  two modes differ in just two spots: where the post list comes from, and
  whether an image is copied from disk (export) or downloaded (API).
- **`url:` keeps the path, owns the domain.** Ingest takes only the URL *path*
  and prepends the configured domain (`micro.bryansebesta.net`). This is not
  belt-and-suspenders — both sources hand back an untrustworthy domain. The
  export stores the URL relative (no domain at all); the **API returns
  `bsebesta.micro.blog` for any post created before the custom domain was set**
  (verified 2026-07-21 — the test post came back on the new domain, a 2024 post
  on the old). Trusting either verbatim would freeze a stale domain into the
  vault. Owning the domain here makes that impossible, and honours §5.1's second
  test: take the path Micro.blog gives, assert only the domain configured.
- **Filename:** the post's **UTC** timestamp, `YYYY-MM-DD-HHMMSS.md`, from the
  immutable `date`. UTC by choice: DST-proof, no timezone dependency. Cost,
  accepted: it won't match the local-time slug in the URL — a 2:13pm post is
  `.../141306.html` but ingests as `…-201306.md`, and a late-evening local post
  can land on the next UTC day. The authoritative link is `url:`, not the
  filename.
- **Photos → markdown images with alt preserved.** The export's raw
  `<img src=… alt=…>` becomes `![alt](_media/<stem>.ext)`, copied into
  `Logbook/Microposts/_media/`. Markdown (not a wikilink embed) so the
  descriptive alt survives — some of it is real writing.
- **State:** `pipeline/state/microblog.json`, keyed on the **URL path**
  (`/2024/08/09/foo.html`). The Mac export has *no* `guid` (an earlier draft
  assumed one); the URL path is the stable key common to both the export and the
  API. Idempotent — re-running re-syncs rather than duplicating.
- **Date is normalised to ISO-8601 UTC** (`…T…+00:00`) whichever source it came
  from — the export gives `… +0000`, the API gives `…T…+00:00`. Storing one
  canonical form stops the two from sorting against each other after a mode
  switch.
- **Homepage list is export-derived, not ingest-emitted.** `export.py` collects
  the Source-tier microposts from the vault scan and writes
  `data/microposts.json` (all of them, newest first) right beside
  `data/links.json`; `layouts/index.html` renders the first five as links out to
  Micro.blog. Deriving in `export` rather than in `micro.py` keeps the vault the
  single source of truth — the list refreshes on every export, and `micro.py`
  stays a pure vault-writer. A photo-only post falls back to its alt text as the
  excerpt. Hugo does **no** build-time remote fetching (protects §11.3).
- **Commands, dry-run twin per §7.3:** `make micro` / `micro-apply` (export
  mode) and `make micro-api` / `micro-api-apply` (API mode); the interactive
  `make micro-download` behind the dock droplet (§7.8) uses the API path. All
  write to the vault, so they sit with `stamp` and `norm`, never inside
  `export`.

**Vault copies are never hand-edited.** Edit on Micro.blog, re-ingest. The
alternative is two masters and real conflict handling, bought for nothing.

**`source: microblog` is a loop guard, not decoration.** Stamp it at ingest so
no future syndication step can push ingested posts back to their origin. Cheap
now; the fix after the fact is a duplicate-flooded timeline.

**The vault gains generated content for the first time.** Everything in it
today is hand-authored. A real new category, accepted deliberately rather than
stumbled into, bounded by one clearly-named folder in the Source tier.

#### Order of operations — the domain must be set first

Archived posts currently resolve at `bsebesta.micro.blog`. Once
`micro.bryansebesta.net` points at the blog, the feed serves the new domain —
but anything ingested beforehand has the old domain frozen into `url:`, and
recovering costs a rewrite pass over a mixed corpus.

**Set custom domain → verify the feed's *item* URLs show it → then backfill.**
The gate is the URLs *inside* the feed, not merely that the domain resolves:
observed 2026-07-21, the feed answered at `micro.bryansebesta.net` for minutes
while every item `url` still read `bsebesta.micro.blog`.

The DNS procedure, the CNAME, and the registrar gotchas are in `RUNBOOK.md` §3.

#### Unverified

1. ~~**Does the export actually yield clean markdown?**~~ **RESOLVED
   2026-07-21 — yes, clean.** The 21-post export was inspected directly. The
   `<input type="checkbox">` seen on the live site was Hugo *rendering* a
   literal `[X]` redaction placeholder Bryan typed; the stored source is intact
   (`* He thinks religion would disappear overnight by [X] happening`). And
   because microposts are Source-tier and never re-rendered by this Hugo, the
   ambiguity is moot regardless.
2. **Does the old subdomain redirect after a custom-domain change?**
   Micro.blog promises URL durability when *migrating away* from the platform,
   which is not the same claim. Ask before relying on it.

#### Decision 13 — the subdomain and the fediverse handle **(RESOLVED 2026-07-21)**

**Resolved: `micro.bryansebesta.net`, existing handle kept.**

A custom subdomain makes the fediverse identity
`@bryan@micro.bryansebesta.net`. The clean `@bryan@bryansebesta.net` is
unavailable because the apex is served by Netlify, and ActivityPub at one's own
domain requires the hosted blog to hold it. Whether WebFinger delegation from
the apex could recover the short handle was never resolved — plausible,
undocumented, and moot given the decision below.

The `bsebesta.micro.blog` account already carries an assigned fediverse handle
and a follower graph. Chasing a prettier handle would reset that identity —
per Micro.blog's own docs, changing the domain forces a fediverse-username
reset that "deletes" the profile from Mastodon servers and requires every
follower to re-follow. Not worth it. Keep the handle; map the subdomain purely
for the blog's web address.

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

- [x] **Decision #12** (Micro.blog ingest path) — resolved, §12.3: ingest to
      vault, publish as Source-tier links, not pages
- [x] **Decision #13** (subdomain / fediverse handle) — resolved 2026-07-21,
      §12.3: `micro.bryansebesta.net`, existing handle kept
- [x] **Micro.blog ingest → vault markdown** — implemented 2026-07-21.
      `pipeline/micro.py` with two modes: `make micro` (Mac export) and
      `make micro-api` (live Micropub API, `$MICROBLOG_TOKEN`); the **Download
      Microposts** dock droplet (`make micro-download`) uses the API path.
      Homepage micropost list derived in `export.py` (`data/microposts.json`).
      API verified end-to-end 2026-07-21 (dry run returns all 22 posts).
      *Remaining:* run `micro-download` to apply; optional scheduled pull
- [ ] Pagefind index (unprominent)
- [ ] Obsidian templates standardizing frontmatter per type
- [ ] Backfill: standardize existing notes
- [ ] Hub notes / curated entry points
- [ ] Art direction begins — revisit Astro
- [ ] Micro.blog visual parity — shared CSS tokens into the theme's Custom CSS
      slot, theme as a cloneable repo, do *not* port templates. Gated on art
      direction above. See `DESIGN.md` § Micro.blog visual parity
