---
title: What a Page Can Be
slug: what-a-page-can-be
type: essay
temporality: evergreen
draft: false
tags:
- design
- meta
id: 4f3c43y3ke
url: /4f3c43y3ke/
aliases:
- /what-a-page-can-be/
lastmod: '2026-07-21T16:31:36.640756+00:00'
layout: story
---

<!--
  PUBLISHED BODY for the note "What a Page Can Be" (id 4f3c43y3ke).

  The vault note holds the draft and owns every piece of metadata — title, id,
  tags, dates, links, backlinks. This file supplies only the arrangement of
  words that ships, for a page whose layout is part of the argument.

  Frontmatter here is ignored; the pipeline strips it. Put metadata in the
  vault note, where it belongs.
-->

<header class="masthead">
  <p class="kicker">A worked example</p>
  <h1>What a page<br>can be</h1>
  <p class="standfirst">Most of this site is notes. A note wants to get out of the way. Sometimes a page should be the point.</p>
</header>

There are two kinds of thing on this site, and they want opposite treatment.

A **note** is a unit of thinking. It should look like every other note, because
the interesting variation is in the links between them, not the typography. When
I write about the [strategic staircase]({{< relref "strategic-staircase-method-as-solution-to-knowledge-gap" >}}),
the page's job is to disappear.

A **story** is different. The form carries part of the argument. Robin Rendle's
essays do this — the layout isn't decoration on top of the writing, it *is* some
of the writing.

<aside class="pull">
  The question isn't whether a page can be art-directed. It's what you give up
  to do it.
</aside>

## What this page gives up: nothing

This is the part worth noticing. This page has its own document, its own
stylesheet, its own typography — no site chrome reached it. And it is still a
normal member of the garden:

<div class="proof">
  <div class="proof-item">
    <span class="proof-label">Real URL</span>
    <span class="proof-value">Stamped, permanent, aliased</span>
  </div>
  <div class="proof-item">
    <span class="proof-label">Tagged</span>
    <span class="proof-value">design, meta — see the footer</span>
  </div>
  <div class="proof-item">
    <span class="proof-label">Linkable</span>
    <span class="proof-value">Both directions, like any note</span>
  </div>
</div>

Those links above aren't hardcoded. They're `relref`, resolved at build time
against the content graph — so if a note's title changes, or its slug moves,
this page follows. And if a target disappears, **the build fails** rather than
shipping a dead link.

Proof it works in both directions: here's a book I read —
[Wintering]({{< relref "wintering" >}}) — and a film,
[The Boy and the Heron]({{< relref "the-boy-and-the-heron-how-will-you-live" >}}).
Different types, different templates, same graph.

## The one rule that still applies

Raw HTML blocks in markdown **cannot contain blank lines**. CommonMark ends the
block at the first gap and reparses the rest as markdown, which is how a
hand-built `<div>` ends up dumping its own source onto the page as code.

Look at the source of this file: every HTML block above is blank-line-free. Not
a style preference — a hard requirement.

## When to reach for this

Rarely. A story costs more than a note: it's authored in the repo rather than
Obsidian, it needs its own CSS, and it can't be revised as casually. That price
is worth paying when the layout is doing argumentative work, and not otherwise.

The default should stay boring. This is the exception, and exceptions earn their
keep by being rare.
