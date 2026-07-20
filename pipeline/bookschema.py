"""Canonical frontmatter order for book and film notes.

`dateYear` was removed on 2026-07-20. It existed only because Dataview could
not group by a computed value; Obsidian Bases can (`groupBy: formula.read`),
which made it pure duplication of `date`.

One definition, imported by every script that writes a book note, so migration,
dedupe, enrichment, and the Obsidian templates can't drift apart.

The vocabulary is Bryan's existing one — `authors`, `publishers`, `pageCount`,
`publishedYear` — because 515 notes already use it. Renaming to a tidier scheme
would be migration cost for no benefit.

Ordering rationale, roughly most-to-least useful when the note is open:
identity, then the book's own facts, then Bryan's reading of it, then the
long tail nobody reads inline.
"""

from __future__ import annotations

import re

BOOK_KEY_ORDER = [
    # gate
    "publish",
    # identity
    "title",
    "subtitle",
    "authors",
    # Translators, editors, illustrators — role kept alongside the name, e.g.
    # "Emily Wilson (Translator)". A translation is not interchangeable with
    # any other edition of the same work, so this is identity, not trivia.
    "contributors",
    "publishers",
    # the book's facts
    "published",
    "publishedYear",
    "isbn",
    "pageCount",
    # display
    "cover",
    "coverGoogle",
    # Bryan's reading
    "date",        # when he read it — also the Hugo sort date
    "rating",
    "highlights",  # wikilink to the highlights note
    "shelves",
    "tags",
    # long tail
    "description",
]

# Films run parallel to books, using the vocabulary already in the 45 migrated
# notes rather than a tidier scheme invented here.
#
# The parallel that matters: `date` is when BRYAN watched it (same as books),
# `released` is when the film came out (same role as `published`). `cover` is
# named to match books so one Base column and one extra_fields entry serves
# both media.
MOVIE_KEY_ORDER = [
    # gate
    "publish",
    # identity
    "title",
    "director",
    "writer",
    "actors",
    # the film's facts
    "released",
    "releasedYear",
    "runtime",
    "genre",
    "mpaaRating",
    # display
    "cover",
    # Bryan's watching
    "date",
    "rating",
    "rewatch",
    # his own taxonomy, carried over from the old notes
    "criterion",
    "animated",
    "color",
    "aspectRatio",
    # external ids
    "imdbId",
    "imdbScore",
    "metaScore",
    "tmdbId",
    "tags",
    # long tail
    "plot",
]


def order_frontmatter(meta: dict, key_order: list[str] | None = None) -> dict:
    """Return meta reordered. Unknown keys keep their relative order at the end,
    so a field added by hand is never silently dropped."""
    key_order = key_order or BOOK_KEY_ORDER
    ordered = {k: meta[k] for k in key_order if k in meta}
    ordered.update({k: v for k, v in meta.items() if k not in ordered})
    return ordered


def tidy_yaml(front: str) -> str:
    """PyYAML writes None as 'null', which Obsidian displays literally. An empty
    value reads as a slot waiting to be filled, which is what it is."""
    return re.sub(r"^(\w+): null$", r"\1:", front, flags=re.MULTILINE)
