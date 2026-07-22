---
title: Media Catalog Expansion — Music, Video Games, Board Games
purpose: Handoff spec for the Cowork agent building QuickAdd macros + templates
status: draft proposal
owner: Bryan
date: 2026-07-21
---

# Media Catalog Expansion Spec

## Context

Bryan already runs a working media-cataloging pipeline in Obsidian:

- **QuickAdd** macro → **user script** hits an API → **capture/template** writes a markdown note into a media folder (e.g. `Movies/The Odyssey (2026).md`, `Books/Harry Potter and the Sorcerer's Stone (2000).md`).
- The note is pre-filled with API metadata as YAML frontmatter; Bryan fills in review, rating, tags by hand.
- A **cover/poster image** is pulled so the collection renders as a visual grid (Dataview / Bases / cards).
- Current sources: **TMDB** (movies), **Open Library** (books).

This spec extends that same pattern to three new media types, with sources chosen to match the existing "free API, stable ID, cover art available" profile.

| Media | Source API | Backbone ID | Auth | Cover source |
|---|---|---|---|---|
| Movies *(existing)* | TMDB | `tmdb_id` | API key | TMDB image CDN |
| Books *(existing)* | Open Library | `olid` / `isbn` | none | Open Library Covers |
| **Music (albums)** | **MusicBrainz** | `release_mbid` | none* | Cover Art Archive |
| **Video games** | **IGDB** | `igdb_id` | Twitch OAuth | IGDB image CDN |
| **Board games** | **BoardGameGeek** | `bgg_id` | none | BGG `<image>` field |

\* MusicBrainz requires no key but **does** require a descriptive `User-Agent` header and enforces ~1 request/second.

---

## Design principle: separate the *work* from the *instance*

The one idea worth building around. In every medium there's an abstract creative work and a specific thing you actually consumed:

- Book: the *work* (the story) vs the *edition* (the printing you read) — Open Library already models this as work vs edition.
- Movie: mostly collapses to one record (TMDB movie).
- **Music: this split is unavoidable.** A *recording/release* (the album you listened to) is a performance of an underlying *work* (the composition). For pop this barely matters; for **classical it's the whole game** — one work (Beethoven's Symphony No. 5) has thousands of recordings.

Recommendation: for the everyday catalog, key each note to the **specific instance** (the release you listened to, the edition you read) as the primary record, and store the **abstract-work ID as a secondary field** when the source provides one. That keeps the common case simple while leaving a hook for classical and for future "all versions of X" queries.

---

## Unified core schema

Every media note — regardless of type — shares this core so a single Dataview/Bases query can render the whole collection in one grid.

```yaml
---
type:            # movie | book | album | game | boardgame
title:           # display title
year:            # release/publication year (number)
cover:           # full image URL (see cover patterns below)
creators:        # list — director / author / artist / developer / designer
status:          # backlog | active | done   (watched/read/played/listened)
rating:          # my rating (number, e.g. 1–10 or 1–5 — pick one scale globally)
tags:            # list — my own tags
date_added:      # ISO date the note was created
date_done:       # ISO date I finished it
source:          # tmdb | openlibrary | musicbrainz | igdb | bgg
source_id:       # the backbone ID for that source
---

<!-- body: my review / notes -->
```

Design notes:
- **`creators` is deliberately generic** (a list) so the grid can show "who made this" for any type. Type-specific role fields (director vs conductor vs designer) live in the extensions below.
- **`source` + `source_id`** together are the stable "ISBN-equivalent." Keep them even when you also store friendlier IDs, so a note can always be re-fetched/reconciled.
- Pick **one global rating scale** across all media or cross-type sorting breaks.
- `status` uses three neutral values that read correctly for every verb (watch/read/play/listen).

---

## Type-specific extensions

Added *alongside* the core fields.

### Movies *(existing — shown for parity)*
```yaml
tmdb_id:
imdb_id:
runtime:      # minutes
genres:       # list
```

### Books *(existing — shown for parity)*
```yaml
olid:
isbn:
page_count:
```

### Albums (MusicBrainz)
```yaml
artist:              # primary album artist
release_mbid:        # the specific release (backbone id → source_id)
release_group_mbid:  # groups editions of the same album ("the album" abstractly)
label:
track_count:
release_format:      # CD | Vinyl | Digital | etc.
# --- optional classical block (only when relevant) ---
composer:            # underlying work's composer
work_mbid:           # abstract composition
conductor:
ensemble:            # orchestra / performing group
catalogue_no:        # Köchel / BWV / Op. / RV etc.
```
> **Classical caveat:** MusicBrainz models composer/conductor/ensemble/movements as *typed relationships*, and richness is editor-dependent — famous recordings are well-annotated, obscure ones may not link tracks to works. The classical block is intentionally optional; populate it only when the release is classical and the data exists. See the classical appendix.

### Video games (IGDB)
```yaml
igdb_id:
developer:           # list
publisher:           # list
platforms:           # list
genres:              # list
first_release_year:
```
> IGDB IDs power Twitch's game data and are the de-facto standard. Auth is a one-time Twitch dev app (client id + secret → bearer token); the script refreshes the token as needed.

### Board games (BGG)
```yaml
bgg_id:
designers:           # list
publishers:          # list
min_players:
max_players:
playtime:            # minutes
weight:              # BGG complexity rating 1–5 (float)
```
> BGG's API returns **XML, not JSON**, and occasionally returns a `202 queued` response the script must retry after a short delay. Otherwise no auth.

---

## Cover art URL patterns (the visual-grid requirement)

Each source exposes covers differently. Store the **final resolved URL** in the `cover` field so the grid needs no per-type logic.

| Source | Pattern | Notes |
|---|---|---|
| TMDB *(existing)* | `https://image.tmdb.org/t/p/w500{poster_path}` | `poster_path` from movie response |
| Open Library *(existing)* | `https://covers.openlibrary.org/b/id/{cover_id}-L.jpg` | or `/b/isbn/{isbn}-L.jpg` |
| **MusicBrainz** | `https://coverartarchive.org/release/{release_mbid}/front-500` | Art lives in the **Cover Art Archive**, keyed by release MBID — MusicBrainz itself doesn't host it. May 404 if no art uploaded; fall back to `release-group/{release_group_mbid}/front-500`. |
| **IGDB** | `https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg` | IGDB returns a cover `image_id`; build the URL. `t_cover_big` or `t_720p` for larger. |
| **BGG** | value of the `<image>` element | Returned directly in the item XML; also a `<thumbnail>` for grids. |

Practical: have each script **verify the cover resolves (HTTP 200)** and write a local placeholder path if not, so the grid never shows broken images.

---

## File naming & folder conventions

Keep Bryan's existing `Title (Year).md` convention, extended per type to avoid collisions:

```
Movies/The Odyssey (2026).md                          # existing
Books/Harry Potter and the Sorcerer's Stone (2000).md # existing
Music/Radiohead - In Rainbows (2007).md               # Artist - Album (Year)
Games/Hollow Knight (2017).md
Board Games/Ark Nova (2021).md
```

- **Music** benefits from an `Artist - ` prefix — album titles collide far more than film titles, and it makes the file list scannable.
- **Classical** is the hard case: `Composer - Work (Performer, Year)` is more useful than album title, e.g. `Beethoven - Symphony No. 5 (Kleiber, 1975).md`. Flag as an open question — Bryan may prefer to file classical under performer or under composer.
- Sanitize `:` `/` `?` from titles (common in album/game names) before writing the filename.

---

## QuickAdd macro flow (per type)

Same shape as the existing movie/book macros:

1. **Macro choice** (hotkey / command palette) → prompts Bryan for a search term.
2. **User script** (`/scripts/<type>.js`):
   - calls the source API (search → pick result → fetch details),
   - for IGDB, obtains/refreshes the Twitch bearer token first,
   - for MusicBrainz, sets the `User-Agent` header and throttles to ≤1 req/s,
   - for BGG, parses XML and retries on `202`,
   - resolves the cover URL and validates it,
   - returns native JS types (arrays for list fields) so QuickAdd writes real Obsidian List properties — not stringified YAML.
3. **Template/Capture** writes the note into the type's folder using the core + extension frontmatter, leaving the body empty for Bryan's review.

Reuse note: the four scripts differ mainly in *fetch + field-mapping*; the cover-resolution step, filename sanitizer, and frontmatter writer can be shared helpers.

---

## Appendix: classical music handling

Why classical needs special care and how this schema accommodates it:

- MusicBrainz separates the **Work** (composition) from the **Recording** (performance) and supports **parent/child work hierarchies** (a symphony as a parent work containing its movements as child works). This is its real strength — most consumer services (Spotify et al.) can't reconstruct movement structure.
- Roles (composer, conductor, orchestra, chorus, soloist, arranger) are **typed relationships**, not flat fields — so the optional classical block maps them explicitly.
- Catalogue numbers (Köchel/K, BWV, Hoboken, Deutsch/D, RV, Op.) are supported via work attributes and a catalogue "series" system; capture the human-readable one in `catalogue_no`.
- **Reality check:** completeness is uneven and a lot of nuance lives inside formatted title strings governed by MusicBrainz's Classical Style Guidelines. The script should degrade gracefully: if work/movement links are absent, still create the note from release-level data and leave the classical block empty.

Secondary source worth considering for classical + physical editions: **Discogs API** (excellent on pressings/box sets; weaker on abstract work modeling). Could be a reconciliation layer later, not needed for v1.

---

## Open questions for Bryan

1. **Rating scale** — unify on 1–10 or 1–5 across all media? (Needed for cross-type sorting.)
2. **Music granularity** — catalog at the **album** level only, or also individual **tracks**? (Albums recommended for v1; tracks explode the note count.)
3. **Classical filing** — file classical notes by album title, by composer, or by performer? Affects naming convention and folder split (`Music/` vs a separate `Classical/`).
4. **Video games scope** — games you've *played/finished*, or also a *backlog/wishlist*? (`status: backlog` supports both if wanted.)
5. **Board games** — worth the XML-parsing overhead of BGG, or is this a lower priority than music/games?
6. **One folder or several** — keep per-type folders (recommended for your naming pattern) vs one `Media/` folder distinguished by the `type` field.
