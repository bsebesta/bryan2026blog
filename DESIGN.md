---
version: alpha
name: bryansebesta.net
description: >
  A deliberately small token set for a personal writing hub. Documents what
  exists today; real art direction is deferred (PRODUCT.md §1).
colors:
  primary: "#1a1a1a"
  secondary: "#6b6b6b"
  tertiary: "#8b3a2f"
  neutral: "#ffffff"
  outline: "#e4e4e4"
  surface: "#f6f6f6"
typography:
  body:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Georgia, serif
    fontSize: 1rem
    lineHeight: 1.65
  heading:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Georgia, serif
    fontSize: 2rem
    lineHeight: 1.25
  meta:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Georgia, serif
    fontSize: 0.85rem
  label-caps:
    fontFamily: ui-sans-serif, system-ui, sans-serif
    fontSize: 0.75rem
    letterSpacing: 0.02em
  code:
    fontFamily: ui-monospace, SFMono-Regular, Menlo, monospace
    fontSize: 0.9em
rounded:
  sm: 2px
  md: 6px
spacing:
  gap: 1.4rem
  measure: 36rem
  measure-wide: 58rem
components:
  link:
    textColor: "{colors.primary}"
  link-hover:
    textColor: "{colors.tertiary}"
  facet:
    textColor: "{colors.primary}"
    backgroundColor: "{colors.neutral}"
    typography: "{typography.label-caps}"
    rounded: "{rounded.sm}"
    padding: 0.1rem 0.45rem
  meta:
    textColor: "{colors.secondary}"
    backgroundColor: "{colors.neutral}"
    typography: "{typography.meta}"
  blockquote:
    textColor: "{colors.secondary}"
    backgroundColor: "{colors.neutral}"
  code-block:
    textColor: "{colors.primary}"
    backgroundColor: "{colors.surface}"
    typography: "{typography.code}"
    padding: 1rem
  artifact-frame:
    backgroundColor: "#ffffff"
    rounded: "{rounded.md}"
---

## Overview

This is a reading surface, not an interface. Nearly every page is one column of
prose, and the design's job is to be legible and then get out of the way. The
default look is intentionally plain — closer to a manuscript than a product —
because the interesting visual work is meant to happen on individual pages that
opt out of the defaults, not in the defaults themselves.

**The token set is small on purpose.** Twelve CSS custom properties, listed
below. Enough that a single page can be re-themed by overriding a handful of
values instead of rewriting rules, which is the entire point of tokens at this
stage. It is not enough to be a design system, and it should not be extended
into one speculatively. Expand it when a real page needs something it can't
express — not before.

### Where the tokens live

All of them are declared in `:root` inside `layouts/_default/baseof.html`,
wrapped in `@layer base`. That layer wrapping is the load-bearing decision:

> **Unlayered CSS always beats layered CSS, regardless of specificity.**

So an art-directed page's own stylesheet wins automatically — no `!important`,
no specificity arms race, and no need for the page author to know what the
defaults are. See PRODUCT.md §9.3.

### Two ways a page departs from the defaults

| Case | Mechanism | When |
|:--|:--|:--|
| Light — same page, different mood | `presentation/<id>/style.css` overriding only token values | Recolouring, a different measure, a display face |
| Heavy — a different thing entirely | `layout: story`, which emits its own `<head>` and never loads this CSS | Bespoke structure, custom grid, scroll behaviour |

Per Rupert, the heavy cases age better as **full ejections** than as partial
overrides. A page that fights the base stylesheet for three years is worse off
than one that never loaded it. If a `style.css` is restructuring rather than
recolouring, that's the signal to promote it to `layout: story`.

### Token name mapping

The frontmatter above uses DESIGN.md's canonical names so that linters and
`export` work. The CSS uses Bryan's names, which are shorter and read better in
a stylesheet. They are the same values:

| CSS variable | DESIGN.md token |
|:--|:--|
| `--ink` | `colors.primary` |
| `--quiet` | `colors.secondary` |
| `--accent` | `colors.tertiary` |
| `--bg` | `colors.neutral` |
| `--rule` | `colors.outline` |
| `--wash` | `colors.surface` |
| `--font-body` | `typography.body.fontFamily` |
| `--font-ui` | `typography.label-caps.fontFamily` |
| `--font-mono` | `typography.code.fontFamily` |
| `--gap` | `spacing.gap` |
| `--measure` | `spacing.measure` |

## Colors

Six values. Four neutrals, one accent, one background — a palette sized for
text and nothing else.

- **Primary (`#1a1a1a`, `--ink`)** — body text and headings. Not pure black;
  `#000` on `#fff` is harsher than paper ever is. 17.4:1 against the
  background.
- **Secondary (`#6b6b6b`, `--quiet`)** — metadata, captions, dates, blockquote
  text. Everything that is *about* the writing rather than the writing.
  5.3:1 — clears WCAG AA for body text, which matters because some of it is set
  at 0.85rem.
- **Tertiary (`#8b3a2f`, `--accent`)** — the only chromatic value in the
  system. Links, hover states, emphasis. 7.6:1. One accent is a constraint
  worth keeping: it means every coloured thing on a page is the same kind of
  thing.
- **Neutral (`#ffffff`, `--bg`)** — page background. Plain white for now;
  a warmer paper tone is a likely early change and is exactly the sort of thing
  a single token override should be able to do.
- **Outline (`#e4e4e4`, `--rule`)** — hairlines. `hr`, list separators, facet
  borders, the backlinks divider, cover-image borders.
- **Surface (`#f6f6f6`, `--wash`)** — inset panels. In practice, code blocks.

**Links do not use the accent as their text colour.** They inherit `--ink` and
take the accent on the *underline* (`text-decoration-color`) and on hover. In a
page that is largely prose with links threaded through it, colouring every link
turns the paragraph into confetti. The underline already says "link."

## Typography

The stack is a system stack, which is a placeholder rather than a choice. No
webfont is loaded, nothing blocks render, and there is no licensing to carry —
all of which are the right defaults until there's a reason to pay the costs.

Three families:

- **`--font-body`** — everything that is read. Falls back through the platform
  UI faces to Georgia. (Worth noting: `-apple-system` resolves to a sans, so
  the serif fallback only fires off-Apple. This is a known inconsistency and a
  candidate for the first real type decision.)
- **`--font-ui`** — small labels only: facets, the "Backlinks" heading. A
  different face at small sizes reads as a different *register* — chrome, not
  content — more cheaply than any other signal.
- **`--font-mono`** — code, inline and block.

Body copy is `1rem / 1.65`. Headings are `1.25` line-height with `2.5rem` of
space above and none above an `h1`. There is no modular scale, because there
aren't yet enough distinct text sizes to need one.

### SVG titles

A page bundle containing `title.svg` gets it rendered in place of the `h1`
(`layouts/partials/title.html`). The SVG is themed by the same tokens: paths
using `fill="currentColor"` inherit `--ink` through `.svg-title`, so a
re-themed page gets a re-themed title for free.

**Non-negotiable:** the SVG must render the title *text*, not a different
phrase or a decorative mark. `role="img"` plus `aria-label` carries the real
title to screen readers. This is what keeps hand-lettered titles from being an
accessibility regression wearing a craft costume.

## Layout

One column, centred, `--measure` wide. That's the whole system.

- **`--measure: 36rem`** — roughly 65–75 characters at body size. The
  well-established comfortable range for continuous reading.
- **`--measure-wide: 58rem`** — applied by `.presentation-wide .wrap`.
- **`--gap: 1.4rem`** — the rhythm between blocks; paragraph bottom margin.

### `presentation: wide`

Set in Obsidian frontmatter. It is an **abstract request for room**, not a
template name — which is the whole separation rule from PRODUCT.md §5.1:

> `layout: wide` is Hugo's template-lookup mechanism: a filename.
> `presentation: wide` is a statement that *this piece needs room.*

A different site generator could honour it a different way, and the vault would
still be right. That's the test for whether something belongs in frontmatter at
all: is it portable, and does the vault actually know it?

Page padding is `2rem 1.25rem 6rem`. The deep bottom padding is so the last
paragraph doesn't sit flush against the viewport edge on mobile.

## Shapes

Barely a scale. `2px` on facet pills, `6px` on the artifact iframe. Nothing
else is rounded, because nothing else is a box.

## Components

Small, and all of them are text decoration rather than interface.

- **Facet** — the lowercase pill carrying `type`, a year, a publisher, a
  runtime. Bordered, not filled; the label is metadata and shouldn't outweigh
  the title above it.
- **Meta line** — secondary colour, `0.85rem`, pulled up with a negative top
  margin so it reads as attached to the heading rather than as its own block.
- **Blockquote** — a 2px left rule and secondary text. No quotation marks, no
  indent on both sides.
- **Code block** — surface background, `1rem` padding, horizontal scroll rather
  than wrap.
- **Backlinks** — a top rule, then a `0.8rem` uppercase UI-face heading. Sized
  to be findable and ignorable at once. Suppressed on essays: an essay is a
  finished argument, not a node in a graph.
- **Artifact frame** — a bordered, rounded iframe, min-height 600px. Isolated
  so a Claude-generated interactive can't leak styles into the page or inherit
  them from it.

## Do's and Don'ts

**Do** override tokens from `presentation/<id>/style.css` when a page wants a
different mood. That path is unlayered and wins by construction.

**Do** eject to `layout: story` when a page wants a different *structure*.
Partial overrides of a base stylesheet accumulate debt; full ejections don't.

**Do** use `currentColor` in SVGs so they follow the theme.

**Don't** add tokens speculatively. The set is small because a small set is
honest about how much design has actually been decided. Every token added
before a page needs it is a guess that later has to be maintained or unwound.

**Don't** reach for `!important` in a page stylesheet. If layering isn't
winning, something is unlayered that shouldn't be — fix that instead.

**Don't** treat this file as aspirational. It documents the twelve variables
that exist in `baseof.html` today. When those change, this changes with them,
or it becomes a lie that an agent will act on.

---

### About this format

DESIGN.md is a format from Google Labs (open-sourced 23 April 2026,
Apache-2.0): machine-readable tokens in YAML frontmatter, human-readable
rationale in markdown prose. Tokens give an agent exact values; prose tells it
why they exist and how to apply them.

The spec is at version **alpha** and is expected to change.

- Spec and CLI — <https://github.com/google-labs-code/design.md>
- Validate — `npx @google/design.md lint DESIGN.md`
- Export DTCG tokens — `npx @google/design.md export --format dtcg DESIGN.md`
