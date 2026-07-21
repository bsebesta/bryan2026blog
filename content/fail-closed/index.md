---
title: Fail Closed
slug: fail-closed
type: essay
temporality: evergreen
draft: false
tags:
- craft
- systems
id: p54ffpd6u8
url: /p54ffpd6u8/
aliases:
- /fail-closed/
lastmod: '2026-07-21T16:31:36.639640+00:00'
---

A publishing pipeline has to decide what happens when it isn't sure. Most of
them guess forward — publish the thing, render the page, ship the build — because
that's what makes a demo feel good. It's the wrong instinct, and the cost of
learning that is asymmetric.

When I built the export for this site, the vault held about 2,400 notes. A
hundred and thirty-three of them carried a `publish` property. One said `true`.
The other hundred and thirty-two said `"false"` — and here is the part worth
sitting with: in most programming languages, `"false"` is a non-empty string,
which is to say it is *true*. A single line of the most obvious code imaginable —

```
if note.get("publish"):
```

— would have published all hundred and thirty-three. Among them: an unsent
letter to someone I'd fallen out with, a folder of work notes belonging to my
employer, and several years of journal entries about my faith.

Nothing about that failure would have announced itself. The build would have
gone green. The site would have deployed. I'd have found out from a search
engine, or from someone I know, or not at all.

## The asymmetry is the whole argument

Publishing something private is not the same magnitude of error as failing to
publish something public. If a note doesn't appear, I notice within a day, and
I fix it in a minute. If a note appears that shouldn't have, it's been indexed,
cached, and possibly read before I know it exists. One is an inconvenience; the
other can't be taken back.

So the gate is an allowlist. Only `true` — the boolean, or the string, and
nothing else — publishes. Every other value, every typo, every absent property,
every malformed frontmatter block resolves to *no*. Roughly 2,300 notes in that
vault have no `publish` property at all, which means the default state of
everything I've ever written is: stays put.

## Where else this applies

The same shape shows up wherever a system touches something it can't undo.
Anything that writes to the vault runs a dry run first and prints what it would
do. Anything that deletes checks a manifest it wrote itself, and refuses to
touch a file it doesn't recognise. The backlink index is built from published
notes only, and the export *fails* — loudly, stopping everything — if the graph
ever names a note that isn't published.

That last one can't currently happen. It's checked anyway, on every run, because
a guarantee nobody verifies is a guarantee that quietly stopped being true at
some point and nobody noticed.

## What it costs

Friction, mostly. Publishing takes an explicit act. Vault-writing commands take
two runs instead of one. I've been mildly annoyed by my own dry runs more times
than I can count.

That's the trade, and it's not close. Systems that fail open are pleasant right
up until the moment they aren't, and then the damage is already distributed.
Systems that fail closed are slightly tedious forever, and the worst thing that
happens is you notice something is missing.
