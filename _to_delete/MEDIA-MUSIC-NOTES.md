# Media Catalog — Music (Artists, Albums, Tracks)

> [!abstract]
> **Last updated:** 2026-07-22. **Purpose:** Design record for music capture — three note types (artist, album, track), one note per capture, written by Obsidian templates. Companion to `MEDIA-BRIEF.md`.

## What this is

Three commands — **Album**, **Track**, **Artist** — so you can write a response to a record, a single song, or an artist's whole ouvre. Each creates **one note**; no side notes are auto-created. Source is MusicBrainz (no key, descriptive User-Agent, ~1 req/s), cover art from the Cover Art Archive. Notes live under `Logbook/Music/`, dated:

```
Logbook/Music/Artists/   Radiohead.md
Logbook/Music/Albums/    Radiohead - In Rainbows (2007).md
Logbook/Music/Tracks/    Radiohead - 15 Step.md
```

The script mirrors your `tmdb-movie.js` / `book-search.js` pattern exactly: it fetches, downloads the cover, and hands variables to a QuickAdd **Template** step that writes the note. The script writes no notes itself — so the note skeletons live in Obsidian templates you can edit.

## Files

| File | Where | Role |
|---|---|---|
| `musicbrainz.js` | `~ Attachments/Scripts/` | Shared logic — exports `album`, `track`, `artist`. Not pointed at by a command directly. |
| `music-album.js` | `~ Attachments/Scripts/` | Single-function wrapper → the Album command points here (no picker) |
| `music-track.js` | `~ Attachments/Scripts/` | Single-function wrapper → the Track command points here |
| `music-artist.js` | `~ Attachments/Scripts/` | Single-function wrapper → the Artist command points here |
| `Album (QuickAdd).md` | `~ Templates/` | Album note skeleton |
| `Track (QuickAdd).md` | `~ Templates/` | Track note skeleton |
| `Artist (QuickAdd).md` | `~ Templates/` | Artist note skeleton |
| `§ Music.base` | `Logbook/Music/` | Bases views — Albums, Tracks, Artists, All music, Needs a rating |

## The three schemas

Field order follows the book/film convention. Full field lists are in the template files; the shapes:

**Artist** — `title` (name), `artistType`, `country`, `activeYears`, `genres[]`, `cover` (blank), `date`, `rating`, `artistMbid`, `tags[artist]`

**Album** — `title`, `artist[[[wikilink]]]`, `released`, `releasedYear`, `label[]`, `trackCount`, `releaseFormat`, `genres[]`, `cover`, `date`, `rating`, `relisten`, `releaseMbid`, `releaseGroupMbid`, `tags[album]`

**Track** — `title`, `artist[[[wikilink]]]`, `album[[[wikilink]]]`, `trackNumber`, `length`, `released`, `releasedYear`, `cover`, `date`, `rating`, `relisten`, `recordingMbid`, `tags[track]`

## Decisions worth recording

**One note per capture, no side notes.** Capturing an album does not create an artist note, and capturing a track does not create an album note. If you want those, make them yourself with the matching command.

**`artist` (and a track's `album`) are wikilinks, not plain text** — but nothing is auto-created. They sit as unresolved links until you choose to make the target note; the moment you do (via the Artist or Album command, which use the same filename format), every existing note connects to it automatically. Zero cost, keeps the graph optional. Switch to plain text if you'd rather.

**Templates live in Obsidian.** The script only sets `QuickAdd.variables` and downloads the cover; the Template step writes the note. Edit a note's frontmatter layout or the `## Response` heading in the template file, never in JavaScript.

**A track is reached through its album, never by free-text recording search.** A recording search for a song title returns a flood of live bootlegs before the studio take (verified 2026-07-22). So Track mode asks for the album, pulls its tracklist, and lets you pick — yielding the canonical recording MBID, length, and number, plus the album wikilink and cover.

**Cover download follows the redirect by hand.** The Cover Art Archive's `front-500` returns a **307 to archive.org**, and Obsidian's `requestUrl` does not auto-follow that cross-host redirect — so the earlier version silently produced empty covers. The script now follows redirects manually (verified against a non-following client). Covers try the release first, then the release-group.

**Known rough edge — representative release.** Among editions sharing the earliest official release date, the tiebreak is arbitrary, so `releaseFormat` and `trackNumber` reflect whichever won (e.g. a cassette's "A1" rather than a CD's "1"). MusicBrainz's release list carries no format data, so ranking by it would cost an extra fetch per edition — not paid. Values are accurate to the chosen edition; fix by hand if an album picks an odd one.

## QuickAdd setup (three commands)

QuickAdd macros are configured in Obsidian's UI. Create **three** commands, each a Macro with two steps:

1. **User Script** → point at the matching **wrapper**: `music-album.js`, `music-track.js`, or `music-artist.js`. Because each wrapper exports a single function, QuickAdd runs it directly — **no "which function?" dropdown**. (Don't point a command at `musicbrainz.js` itself; that's the shared library, and pointing at it is exactly what causes the runtime function-picker.)
2. **Template** → select the matching template file, set the folder (`Logbook/Music/Albums`, `/Tracks`, or `/Artists`), and set the file-name format to `{{VALUE:fileName}}`. Here you also choose how the note opens (new tab, split, focus) — the reason for using a Template step.

Bind each to a hotkey. No API key. If you re-capture something you already have, QuickAdd's template step handles the existing file per its own "if file exists" setting — there's no MBID de-duplication in the script (kept simple by request).

**Why wrappers:** a single script that exports `album`/`track`/`artist` makes QuickAdd prompt you to pick the function every run — friction, and a chance to mis-click Track on an album. Each wrapper is a one-line file that calls the matching function in `musicbrainz.js`, so QuickAdd sees exactly one function and skips the prompt, while all logic stays in one shared file. (Desktop only: wrappers use `require` and the vault file path.)

## Deferred

**Site publishing** — not wired in; every note is `publish: false`. When wanted, in `pipeline/config.yaml`: add `"Logbook/Music": "log"` to `type_by_folder` (covers all three subfolders) and add the fields you want public to `extra_fields` (`artist`, `album`, `released`, `releaseMbid`, `recordingMbid`; `releasedYear` and `cover` are already there).

**Artist images** — not in the Cover Art Archive; `cover` is left blank on artist notes. Add one by hand, or wire up Wikidata/fanart.tv later.

**Classical decomposition** — a classical album/track captures fine if you search by composer (the credit "Beethoven; Wiener Philharmoniker, Simon Rattle" lands whole in `artist`). Splitting that into `composer` / `conductor` / `ensemble` / `catalogueNo` fields needs MusicBrainz's typed relationships — the `releaseGroupMbid` / `recordingMbid` hooks are in place for it.
