"""Backfill covers and metadata for book notes.

    .venv/bin/python -m pipeline.enrich_books            # dry run
    .venv/bin/python -m pipeline.enrich_books --apply    # writes to the vault
    .venv/bin/python -m pipeline.enrich_books --apply --low-confidence

WRITES TO THE VAULT. Only fills EMPTY fields — existing metadata is never
overwritten, because the vault is more trustworthy than a search result.

Matching confidence
-------------------
Automated title matching gets things wrong, so matches are tiered:

  EXACT   ISBN lookup. Unambiguous — applied automatically.
  HIGH    Title search where the returned title matches after normalisation.
          Applied automatically.
  LOW     Title search with a partial match. REPORTED BUT NOT APPLIED unless
          you pass --low-confidence, because the failure mode is a book note
          quietly wearing the wrong cover.

Sources
-------
Open Library first: no API key, no published rate limit, and its -L covers are
far larger than Google's ~128px thumbnails. Google Books is the fallback for
title search, where its ranking is better.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

from .bookschema import order_frontmatter, tidy_yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

BOOKS_DIR = "Logbook/Books"
COVERS_DIR = "~ Attachments/Images/Covers"

OPENLIB = "https://openlibrary.org"
OPENLIB_COVER = "https://covers.openlibrary.org/b/isbn"
GOOGLE = "https://www.googleapis.com/books/v1/volumes"

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)
UA = {"User-Agent": "bryansebesta.net book enrichment (personal vault)"}

# Fields the API may fill when the note is silent. Never overwritten.
FILLABLE = ("title", "subtitle", "authors", "publishers", "published",
            "publishedYear", "isbn", "pageCount")

DELAY = 0.4  # polite pause between requests; Google rate-limits aggressively


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    return config


# Last transport error, so --debug can tell "no results" apart from "refused".
LAST_ERROR: str | None = None


def get_json(url: str) -> dict | None:
    global LAST_ERROR
    LAST_ERROR = None
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as exc:
        LAST_ERROR = f"{type(exc).__name__}: {exc}"
        return None


def get_bytes(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.read()
    except Exception:
        return None


def split_frontmatter(text: str) -> tuple[dict, str]:
    match = FM_RE.match(text)
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}, text
    return (meta if isinstance(meta, dict) else {}), match.group(2)


def clean_filename(stem: str) -> tuple[str, str | None]:
    """'Dopamine Nation (book by Anna Lembke)' → ('Dopamine Nation', 'Anna Lembke').

    These stubs were made by hand, and the parenthetical is the only metadata
    they carry.
    """
    author = None
    m = re.search(r"\((?:book\s+)?by ([^)]+)\)\s*$", stem, re.IGNORECASE)
    if m:
        author = m.group(1).strip()
        stem = stem[: m.start()].strip()
    stem = re.sub(r"\s*\((?:book|novel|audiobook)\)\s*$", "", stem, flags=re.IGNORECASE)
    return stem.strip(), author


def normalise(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
    return " ".join(text.split())


def slug_filename(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (title or "book").lower()).strip("-")
    return f"cover-{s[:70]}.jpg"


GB_ID_RE = re.compile(r"(?:/edition/[^/]+/|[?&]id=)([A-Za-z0-9_-]{8,})")


def google_volume_id(value: str) -> str | None:
    """Accept a bare volume id or any Google Books URL containing one."""
    value = value.strip()
    match = GB_ID_RE.search(value)
    if match:
        return match.group(1)
    return value if re.fullmatch(r"[A-Za-z0-9_-]{8,}", value) else None


def cover_from_google_id(volume_id: str, zooms: tuple[str, ...] = ("2", "1", "0")) -> bytes | None:
    """Fetch a cover straight from a Google Books volume id.

    Bypasses the API entirely — books.google.com/books/content is a plain image
    endpoint with no quota.

    Order matters. `zoom=0` is the largest rendition, but on volumes with full
    preview enabled it sometimes returns an interior page instead of the front
    cover. `zoom=2` is reliably the cover and usually big enough, so it leads;
    pass --zoom to override when a particular book wants something else.
    """
    for zoom in zooms:
        data = get_bytes(
            "https://books.google.com/books/content"
            f"?id={volume_id}&printsec=frontcover&img=1&zoom={zoom}&source=gbs_api"
        )
        if data and len(data) > 3000:
            return data
    return None


def isbn13_to_10(isbn13: str) -> str | None:
    """978-prefixed ISBN-13 → ISBN-10. Amazon's image URLs are keyed on ISBN-10."""
    digits = re.sub(r"[^0-9]", "", isbn13)
    if len(digits) == 10:
        return isbn13.upper()
    if len(digits) != 13 or not digits.startswith("978"):
        return None
    core = digits[3:12]
    total = sum((10 - i) * int(d) for i, d in enumerate(core))
    check = (11 - (total % 11)) % 11
    return core + ("X" if check == 10 else str(check))


def cover_from_amazon(isbn: str) -> bytes | None:
    """Amazon's ISBN-keyed cover images. No API, no key, wide coverage.

    This is the pattern Bryan's own Readwise exports already used, so it's a
    known-good source for this library specifically. Amazon returns a 1x1 GIF
    rather than a 404 when it has nothing, hence the size check.
    """
    isbn10 = isbn13_to_10(str(isbn))
    if not isbn10:
        return None
    for pattern in (
        "https://images-na.ssl-images-amazon.com/images/P/{}.01._SCLZZZZZZZ_.jpg",
        "https://images-na.ssl-images-amazon.com/images/P/{}.01.LZZZZZZZ.jpg",
    ):
        data = get_bytes(pattern.format(isbn10))
        if data and len(data) > 3000:
            return data
    return None


def cover_from_isbn(isbn: str) -> bytes | None:
    clean = re.sub(r"[^0-9Xx]", "", str(isbn))
    if not clean:
        return None
    data = get_bytes(f"{OPENLIB_COVER}/{clean}-L.jpg?default=false")
    # Open Library serves a tiny placeholder rather than 404 in some cases.
    if data and len(data) > 3000:
        return data
    return None


def search_openlibrary(title: str, author: str | None) -> dict | None:
    """Primary title search.

    Preferred over Google Books: no API key, no aggressive rate limiting, and
    search.json returns a `cover_i` id that resolves straight to a large cover
    image without a second ISBN round-trip.
    """
    params = {
        "title": title,
        "limit": "5",
        "fields": "title,author_name,first_publish_year,publisher,isbn,"
                  "number_of_pages_median,cover_i",
    }
    if author:
        params["author"] = author
    url = f"{OPENLIB}/search.json?{urllib.parse.urlencode(params)}"
    data = get_json(url)

    if (not data or not data.get("docs")) and author:
        # Author names in the vault are often partial or misspelled; title
        # alone usually still finds the right book.
        params.pop("author")
        data = get_json(f"{OPENLIB}/search.json?{urllib.parse.urlencode(params)}")

    if not data or not data.get("docs"):
        return None

    # Prefer a doc that actually has a cover.
    docs = data["docs"]
    doc = next((d for d in docs if d.get("cover_i")), docs[0])

    return {
        "title": doc.get("title", ""),
        "subtitle": "",
        "authors": doc.get("author_name") or [],
        "publishers": (doc.get("publisher") or [])[:1],
        "published": str(doc.get("first_publish_year") or ""),
        "publishedYear": str(doc.get("first_publish_year") or ""),
        "isbn": (doc.get("isbn") or [""])[0],
        "pageCount": doc.get("number_of_pages_median"),
        "cover_id": doc.get("cover_i"),
        "thumbnail": "",
    }


def lookup_by_isbn(isbn: str) -> dict | None:
    """Full record for a known ISBN. Open Library first, Google as backup."""
    clean = re.sub(r"[^0-9Xx]", "", isbn)
    data = get_json(f"{OPENLIB}/isbn/{clean}.json")
    if data:
        authors = []
        for a in (data.get("authors") or [])[:3]:
            info = get_json(f"{OPENLIB}{a['key']}.json")
            if info and info.get("name"):
                authors.append(info["name"])
        record = {
            "title": data.get("title", ""),
            "subtitle": data.get("subtitle", ""),
            "authors": authors,
            "publishers": data.get("publishers") or [],
            "published": data.get("publish_date", ""),
            "publishedYear": re.sub(r"\D", "", str(data.get("publish_date", "")))[-4:],
            "isbn": clean,
            "pageCount": data.get("number_of_pages"),
            "cover_id": (data.get("covers") or [None])[0],
            "thumbnail": "",
        }
        if not record["authors"] or not record["publishers"]:
            google = search_google_raw(f"isbn:{clean}")
            if google:
                for key in ("authors", "publishers", "published", "publishedYear",
                            "pageCount", "subtitle", "thumbnail"):
                    if not record.get(key) and google.get(key):
                        record[key] = google[key]
        return record
    return search_google_raw(f"isbn:{clean}")


def search_google_raw(query: str) -> dict | None:
    """Run a literal Google Books query, e.g. 'isbn:9780310162247'."""
    data = get_json(f"{GOOGLE}?q={urllib.parse.quote(query)}&maxResults=3")
    return _first_google(data)


def search_google(title: str, author: str | None) -> dict | None:
    query = f'intitle:"{title}"'
    if author:
        query += f' inauthor:"{author}"'
    url = f"{GOOGLE}?q={urllib.parse.quote(query)}&maxResults=5"
    data = get_json(url)
    if not data or not data.get("items"):
        # Retry unquoted — Google's exact-phrase search is brittle on
        # subtitles and punctuation.
        url = f"{GOOGLE}?q={urllib.parse.quote(title + (' ' + author if author else ''))}&maxResults=5"
        data = get_json(url)
    return _first_google(data)


def _first_google(data: dict | None) -> dict | None:
    if not data or not data.get("items"):
        return None

    for item in data["items"]:
        v = item.get("volumeInfo", {})
        ids = v.get("industryIdentifiers") or []
        find = lambda t: next((i["identifier"] for i in ids if i["type"] == t), "")
        return {
            "title": v.get("title", ""),
            "subtitle": v.get("subtitle", ""),
            "authors": v.get("authors") or [],
            "publishers": [v["publisher"]] if v.get("publisher") else [],
            "published": v.get("publishedDate", ""),
            "publishedYear": (v.get("publishedDate") or "")[:4],
            "isbn": find("ISBN_13") or find("ISBN_10"),
            "pageCount": v.get("pageCount"),
            "thumbnail": (v.get("imageLinks") or {}).get("thumbnail", "")
            .replace("http://", "https://")
            .replace("zoom=1", "zoom=0"),
        }
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill book covers and metadata.")
    parser.add_argument("--apply", action="store_true", help="Write to the vault.")
    parser.add_argument("--low-confidence", action="store_true",
                        help="Also apply partial title matches.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Process at most N notes (useful for a trial run).")
    parser.add_argument("--only", metavar="TEXT",
                        help="Only notes whose filename contains TEXT. "
                             "Also lifts the 'already has a cover' skip, so it "
                             "can repair a note that matched the wrong book.")
    parser.add_argument("--isbn", metavar="ISBN",
                        help="Force this ISBN. Requires --only to match exactly "
                             "one note. Implies --force.")
    parser.add_argument("--gbid", metavar="ID_OR_URL",
                        help="Google Books volume id, or any Google Books URL "
                             "containing one. Fetches the cover directly, "
                             "bypassing the API. Requires --only.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing fields rather than only "
                             "filling empty ones. Use with --only.")
    parser.add_argument("--zoom", metavar="N",
                        help="Google Books image size for --gbid: 0 largest, "
                             "1 smallest, 2 usually best. Default tries 2,1,0.")
    parser.add_argument("--debug", action="store_true",
                        help="Report what each cover source returned.")
    args = parser.parse_args()
    if args.isbn:
        args.force = True
    if args.gbid and not args.only:
        print("--gbid requires --only to pick a single note.", file=sys.stderr)
        return 2

    config = load_config()
    vault = Path(config["vault_root"])
    books = vault / BOOKS_DIR
    covers = vault / COVERS_DIR
    covers.mkdir(parents=True, exist_ok=True)
    existing = {p.name for p in covers.glob("*")}

    todo = []
    for path in sorted(books.glob("*.md")):
        if args.only and args.only.lower() not in path.stem.lower():
            continue
        meta, body = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        cover = str(meta.get("cover") or "").strip().strip("[]")
        # --only means "work on this note regardless" — the whole point is
        # repairing a note that already has the wrong cover.
        if not args.only and cover and cover in existing:
            continue
        todo.append((path, meta, body))

    if (args.isbn or args.gbid) and len(todo) != 1:
        flag = "--isbn" if args.isbn else "--gbid"
        print(f"{flag} needs exactly one note; --only matched {len(todo)}.",
              file=sys.stderr)
        for path, _, _ in todo[:10]:
            print(f"    {path.stem}", file=sys.stderr)
        return 2

    if args.limit:
        todo = todo[: args.limit]

    print(f"\n{'─' * 72}")
    print(f"ENRICH BOOKS — {len(todo)} notes lack a usable cover")
    print(f"{'─' * 72}\n")

    results = []
    for i, (path, meta, body) in enumerate(todo, 1):
        title = meta.get("title")
        authors = meta.get("authors")
        author = authors[0] if isinstance(authors, list) and authors else authors

        if not title:
            title, parsed_author = clean_filename(path.stem)
            author = author or parsed_author

        found, confidence, image = None, None, None

        if args.gbid:
            volume_id = google_volume_id(args.gbid)
            if not volume_id:
                print(f"  Could not read a volume id from {args.gbid!r}", file=sys.stderr)
                return 2
            zooms = (args.zoom,) if args.zoom else ("2", "1", "0")
            image = cover_from_google_id(volume_id, zooms)
            found = search_google_raw(f"id:{volume_id}") if args.force else None
            confidence = "FORCED"
            results.append((path, meta, body, title, found, confidence, image))
            size = f"{len(image) // 1024}KB" if image else "no image"
            print(f"  FORCED  {path.stem[:44]:<44} volume {volume_id}  {size}")
            continue

        if args.isbn:
            # Explicit ISBN: trust it completely and rebuild from it.
            found = lookup_by_isbn(args.isbn)
            image = cover_from_isbn(args.isbn)
            if not image and found and found.get("cover_id"):
                image = get_bytes(
                    f"https://covers.openlibrary.org/b/id/{found['cover_id']}-L.jpg"
                )
            if not image and found and found.get("thumbnail"):
                image = get_bytes(found["thumbnail"])
            if not image:
                image = cover_from_amazon(args.isbn)
            if found:
                found["isbn"] = args.isbn
                confidence = "FORCED"
            results.append((path, meta, body, title, found, confidence, image))
            shown = found["title"] if found else "— not found"
            print(f"  FORCED  {path.stem[:40]:<40} → {shown[:36]}")
            continue

        if meta.get("isbn"):
            image = cover_from_isbn(meta["isbn"])
            if image:
                confidence = "EXACT"
            time.sleep(DELAY)

        if not image:
            found = search_openlibrary(title, author)
            time.sleep(DELAY)
            if not found:
                # Google ranks better on obscure titles, but rate-limits hard.
                found = search_google(title, author)
                time.sleep(DELAY)
            if found:
                if found.get("cover_id"):
                    image = get_bytes(
                        f"https://covers.openlibrary.org/b/id/{found['cover_id']}-L.jpg"
                    )
                if not image and found.get("isbn"):
                    image = cover_from_isbn(found["isbn"])
                    time.sleep(DELAY)
                if not image and found.get("thumbnail"):
                    image = get_bytes(found["thumbnail"])

                # Open Library frequently HAS the record but no artwork. Falling
                # back to Google only when OL returns nothing missed all of
                # those — so try Google for the cover specifically, using the
                # ISBN we now know, which is a far stronger query than a title.
                if not image:
                    gq = f"isbn:{found['isbn']}" if found.get("isbn") else None
                    google = (search_google_raw(gq) if gq else None) or \
                        search_google(title, author)
                    time.sleep(DELAY)
                    if google and google.get("thumbnail"):
                        image = get_bytes(google["thumbnail"])
                        if args.debug:
                            print(f"        google thumbnail → "
                                  f"{len(image) if image else 'failed'}")
                    elif args.debug:
                        why = "no imageLinks" if google else (LAST_ERROR or "no results")
                        print(f"        google → {why}")
                    if google:
                        for key in FILLABLE:
                            if not found.get(key) and google.get(key):
                                found[key] = google[key]

                # Last resort: Amazon's ISBN-keyed images. No API, no key, and
                # it covers plenty that Open Library and Google both miss.
                if not image and found.get("isbn"):
                    image = cover_from_amazon(found["isbn"])
                    if args.debug:
                        print(f"        amazon → "
                              f"{len(image) if image else 'nothing'}")

                if image and len(image) < 3000:
                    image = None  # placeholder, not a real cover
                if normalise(found["title"]) == normalise(title):
                    confidence = "HIGH"
                elif normalise(title) in normalise(found["title"]) or \
                        normalise(found["title"]) in normalise(title):
                    confidence = "LOW"
                else:
                    confidence = "LOW"

        results.append((path, meta, body, title, found, confidence, image))

        label = confidence or "NONE"
        shown = found["title"] if found else "—"
        by = ", ".join(found["authors"][:2]) if found and found.get("authors") else ""
        size = f"{len(image) // 1024}KB" if image else "no image"
        print(f"  [{i:>3}/{len(todo)}] {label:<5} {path.stem[:38]:<38} → {shown[:32]:<32} {by[:22]:<22} {size}")

    tally = {}
    for *_, confidence, image in results:
        key = (confidence or "NONE", bool(image))
        tally[key] = tally.get(key, 0) + 1

    print(f"\n{'─' * 72}")
    print("SUMMARY")
    for (conf, has_img), count in sorted(tally.items()):
        print(f"  {conf:<6} {'with cover' if has_img else 'no cover  '}  {count:>4}")

    # A FORCED match applies even without an image: you supplied the ISBN, so
    # correcting the metadata is worth doing whether or not artwork exists.
    # A FORCED match applies when it has either an image or a record: you
    # supplied the identifier, so whichever half succeeded is worth keeping.
    applicable = [
        r for r in results
        if (r[5] == "FORCED" and (r[4] or r[6]))
        or (r[6] and (r[5] in ("EXACT", "HIGH") or args.low_confidence))
    ]
    print(f"\n  applicable now: {len(applicable)}")
    if not args.low_confidence:
        low = [r for r in results if r[6] and r[5] == "LOW"]
        if low:
            print(f"  held back (LOW confidence): {len(low)} — review the list above,")
            print("  then re-run with --low-confidence to accept them.")

    print(f"\n{'─' * 72}")
    if not args.apply:
        print("DRY RUN — vault untouched. Re-run with --apply.")
        return 0

    written = 0
    for path, meta, body, title, found, confidence, image in applicable:
        filename = slug_filename(found["title"] if found else title) if image else None
        if image:
            (covers / filename).write_bytes(image)

        updated = dict(meta)
        # Fill only what's empty. The vault is more trustworthy than a search.
        if found:
            for key in FILLABLE:
                empty = updated.get(key) in (None, "", [])
                if (empty or args.force) and found.get(key):
                    updated[key] = found[key]
        old_cover = str(meta.get("cover") or "").strip().strip("[]")

        if filename:
            updated["cover"] = f"[[{filename}]]"
        elif confidence == "FORCED":
            # You corrected this note to a different book and no artwork was
            # found. Keeping the old cover would leave it wearing another
            # book's jacket, which is worse than having none.
            updated.pop("cover", None)
        updated.setdefault("publish", False)
        tags = updated.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        if "book" not in tags:
            tags.insert(0, "book")
        updated["tags"] = tags

        front = yaml.safe_dump(order_frontmatter(updated), sort_keys=False, allow_unicode=True,
                               default_flow_style=False, width=10000)
        front = tidy_yaml(front)

        new_body = body
        # Drop the previous cover embed when it's being replaced or removed,
        # so the note never shows two covers or a stale one.
        if old_cover and old_cover != filename:
            new_body = re.sub(
                r"^!\[\[" + re.escape(old_cover) + r"\]\]\s*$\n?",
                "", new_body, flags=re.MULTILINE,
            )
        if filename and f"![[{filename}]]" not in new_body:
            new_body = f"\n![[{filename}]]\n" + new_body.lstrip("\n")

        tmp = path.with_suffix(".md.enrich-tmp")
        tmp.write_text("---\n" + front + "---\n" + new_body, encoding="utf-8")
        os.replace(tmp, path)
        written += 1

    print(f"UPDATED {written} note(s) and saved {written} cover(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
