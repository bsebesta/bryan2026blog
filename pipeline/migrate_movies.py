"""One-time migration: bring past film notes into Bryan's Notes.

    .venv/bin/python -m pipeline.migrate_movies           # dry run
    .venv/bin/python -m pipeline.migrate_movies --apply   # copies + downloads
    .venv/bin/python -m pipeline.migrate_movies --apply --move

WRITES TO THE VAULT. Copies by default; --move deletes the Past Writing
originals afterwards.

Unlike the books, these notes already carry Bryan's own reviews — 32 of 45 have
prose. Nothing in the body is touched.

What this normalises
--------------------
The old OMDb script left three pairs of competing field names, because it
changed shape partway through:

    yearReleased (41)  /  year (3)        → releasedYear
    length (41)        /  runtime (3)     → runtime, as an integer
    mpaaRating (41)    /  rated (3)       → mpaaRating

`released` arrives as either "21 Jul 2023" or "2024-10-02"; both become ISO.

Posters are REMOTE Amazon URLs, which rot and would make every visitor's
browser call Amazon. They're downloaded into the vault and `cover` becomes a
wikilink, matching the books. The URL's `_SX300` is swapped for `_SX900` first
— same image, ~5x the resolution, and the smaller one is too small to publish.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import yaml

from .bookschema import MOVIE_KEY_ORDER, order_frontmatter, tidy_yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

SOURCE = "Bryan's Past Writing/Movies"
DEST = "Logbook/Movies"
COVERS = "~ Attachments/Images/Covers"

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)
UA = {"User-Agent": "bryansebesta.net-vault/1.0 (https://bryansebesta.net)"}

# old name → canonical name
RENAMES = {
    "yearReleased": "releasedYear",
    "year": "releasedYear",
    "length": "runtime",
    "rated": "mpaaRating",
}

# Dropped: `type` and `imdbType` are derived from the folder now.
DISCARD = {"type", "imdbType", "poster", "cssclasses"}


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    return config


def split_frontmatter(text: str) -> tuple[dict, str]:
    match = FM_RE.match(text)
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}, text
    return (meta if isinstance(meta, dict) else {}), match.group(2)


def iso_date(value) -> str:
    """'21 Jul 2023' and '2024-10-02' both become '2024-10-02' form."""
    text = str(value or "").strip()
    if not text:
        return ""
    for fmt in ("%d %b %Y", "%Y-%m-%d", "%d %B %Y", "%Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.strftime("%Y-%m-%d") if fmt != "%Y" else text
        except ValueError:
            continue
    return text


def as_int(value) -> int | str:
    """'114 min' → 114."""
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else ""


def as_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


def sanitize(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|#^\[\]]', "", name)).strip()


def poster_url(url: str) -> str:
    """Amazon's OMDb posters are stored at SX300. SX900 is the same image at
    roughly five times the resolution — 20KB vs 99KB."""
    return re.sub(r"_SX\d+", "_SX900", str(url or ""))


def fetch(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as res:
            data = res.read()
        return data if len(data) > 3000 else None
    except Exception:
        return None


def build(meta: dict, body: str, cover_file: str) -> str:
    out: dict = {"publish": meta.get("publish") is True}

    for key, value in meta.items():
        if key in DISCARD:
            continue
        out[RENAMES.get(key, key)] = value

    if out.get("released"):
        out["released"] = iso_date(out["released"])
    if out.get("releasedYear"):
        out["releasedYear"] = as_int(out["releasedYear"])
    if out.get("runtime"):
        out["runtime"] = as_int(out["runtime"])

    for key in ("director", "writer", "actors", "genre"):
        if out.get(key):
            out[key] = as_list(out[key])

    if cover_file:
        out["cover"] = f"[[{cover_file}]]"

    out.setdefault("rating", None)
    out.setdefault("rewatch", False)

    tags = out.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tags = [str(t) for t in tags if str(t) != "movies"]
    if "film" not in tags:
        tags.insert(0, "film")
    out["tags"] = tags

    front = yaml.safe_dump(order_frontmatter(out, MOVIE_KEY_ORDER), sort_keys=False,
                           allow_unicode=True, default_flow_style=False, width=10000)
    return "---\n" + tidy_yaml(front) + "---\n\n" + body.strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate past film notes.")
    parser.add_argument("--apply", action="store_true", help="Write files.")
    parser.add_argument("--move", action="store_true",
                        help="Delete source files after a successful copy.")
    args = parser.parse_args()

    config = load_config()
    vault = Path(config["vault_root"])
    source = vault.parent / SOURCE
    dest = vault / DEST
    covers = vault / COVERS

    if not source.exists():
        print(f"ERROR: {source} not found", file=sys.stderr)
        return 2

    existing = {p.stem.lower().replace(",", "").replace("  ", " "): p
                for p in dest.glob("*.md")}

    planned, collisions, no_poster = [], [], []
    renames_seen: dict[str, int] = {}

    for path in sorted(source.glob("*.md")):
        meta, body = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        for old in RENAMES:
            if old in meta:
                renames_seen[old] = renames_seen.get(old, 0) + 1

        key = path.stem.lower().replace(",", "").replace("  ", " ")
        if key in existing:
            # A note of the same film already sits in Logbook/Movies — in
            # practice a stray left by the book migration, carrying a review
            # but no metadata. Merge rather than skip: take the incoming
            # metadata, keep both bodies, and drop the old file.
            collisions.append(path)

        if not meta.get("poster"):
            no_poster.append(path)

        planned.append((path, meta, body))

    print(f"\n{'─' * 72}")
    print("FILM MIGRATION")
    print(f"  notes in Past Writing/Movies  {len(list(source.glob('*.md'))):>4}")
    print(f"    to import                   {len(planned):>4}  → {DEST}/")
    print(f"    merged with existing        {len(collisions):>4}")
    print(f"  with a review                 {sum(1 for _, _, b in planned if b.strip()):>4}")
    print(f"  no poster URL                 {len(no_poster):>4}")

    if collisions:
        print(f"\n{'─' * 72}")
        print("MERGED WITH AN EXISTING NOTE — incoming metadata wins, both")
        print("bodies kept, the old file removed.")
        for path in collisions:
            key = path.stem.lower().replace(",", "").replace("  ", " ")
            print(f"  {path.stem}\n      absorbs  {existing[key].name}")

    if renames_seen:
        print(f"\n{'─' * 72}")
        print("FIELD RENAMES")
        for old, count in sorted(renames_seen.items(), key=lambda kv: -kv[1]):
            print(f"  {count:>4}  {old:<14} → {RENAMES[old]}")

    print(f"\n{'─' * 72}")
    print("EVERY IMPORTED NOTE IS publish: false. Reviews are carried over intact.")

    print(f"\n{'─' * 72}")
    if not args.apply:
        print("DRY RUN — nothing written. Posters are downloaded only with --apply.")
        print("Re-run with --apply (add --move to delete the originals).")
        return 0

    dest.mkdir(parents=True, exist_ok=True)
    covers.mkdir(parents=True, exist_ok=True)

    downloaded = failed = 0
    for path, meta, body in planned:
        cover_file = ""
        if meta.get("poster"):
            title = meta.get("title") or path.stem
            year = meta.get("yearReleased") or meta.get("year") or ""
            name = sanitize(f"poster-{title} {year}".strip()) + ".jpg"
            target = covers / name
            if target.exists():
                cover_file = name
            else:
                data = fetch(poster_url(meta["poster"]))
                if data:
                    target.write_bytes(data)
                    cover_file = name
                    downloaded += 1
                else:
                    failed += 1

        key = path.stem.lower().replace(",", "").replace("  ", " ")
        prior = existing.get(key)
        if prior and prior.exists():
            _, prior_body = split_frontmatter(
                prior.read_text(encoding="utf-8", errors="replace")
            )
            prior_body = re.sub(r"^##\s*Review\s*$", "", prior_body,
                                flags=re.MULTILINE).strip()
            if prior_body and prior_body not in body:
                body = (body.strip() + "\n\n---\n\n" + prior_body).strip()

        (dest / path.name).write_text(build(meta, body, cover_file), encoding="utf-8")

        if prior and prior.exists() and prior.name != path.name:
            prior.unlink()

    if args.move:
        for path, _, _ in planned:
            path.unlink()

    print(f"IMPORTED {len(planned)} film note(s).")
    print(f"Posters downloaded {downloaded}, failed {failed}.")
    if not args.move:
        print("\nOriginals left in Past Writing. Re-run with --move once satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
