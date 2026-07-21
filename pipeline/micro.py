"""Ingest Micro.blog posts into the vault as microposts.

    .venv/bin/python -m pipeline.micro            # dry run
    .venv/bin/python -m pipeline.micro --apply    # writes to the vault

WRITES TO THE VAULT. Like `stamp` and `norm`, this is a separate command kept
out of `export` by design — `export` never writes to the vault (PRODUCT.md
§7.1). Ingest is the one thing that puts *generated* content in the vault, so it
is deliberately its own step with a dry-run twin.

What it does
------------
Reads a Micro.blog markdown export (Mac app → File → Export → Markdown) and
writes each post into `Logbook/Microposts/` as a `log` note, copying any photos
into `Logbook/Microposts/_media/`. The posts are Source-tier (PRODUCT.md
§7.4.3): indexed and linkable, but never published as pages. The site shows
*links* to them at their Micro.blog home, never a hosted copy — so the vault
copy exists for search and for keeping Bryan's writing in one place, not to
feed `bryansebesta.net`. See PRODUCT.md §12.3 for the full decision.

Why the vault copy is never hand-edited
----------------------------------------
Micro.blog is authoritative. This command is an idempotent overwrite keyed on
each post's URL path, so re-running re-syncs rather than duplicating. Edit a
post on Micro.blog and re-run; never edit the vault copy, or the next run
silently reverts it.

Decisions baked in (PRODUCT.md §12.3)
-------------------------------------
- **Filename** is the post's UTC timestamp, `YYYY-MM-DD-HHMMSS.md`. Stable
  because it derives from `date_published`, which never changes — unlike a
  title-derived slug, which would turn a re-sync into a rename-and-migrate.
  Note this is UTC, so it will *not* match the local time in the Micro.blog URL
  (a 2:13pm post is `.../141306.html` but ingests as `...-201306.md`); the
  authoritative link is the `url:` field, not the filename.
- **`url:`** is the absolute Micro.blog URL. The export stores it *relative*
  (`/2024/08/09/foo.html`), so we prepend the custom domain here. Because the
  export URL carries no domain, this path can never freeze a stale
  `bsebesta.micro.blog` — that risk only ever applied to the live feed.
- **`source: microblog`** is stamped as a loop guard: it marks these as
  ingested so no future syndication step can push them back to their origin.
- **Photos** are copied out of the export (not fetched from Micro.blog's CDN)
  and embedded as markdown images so the descriptive `alt` text survives.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Same frontmatter regex the other vault-writers use (enrich_books, migrate_*).
FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)

# Micro.blog's export emits raw <img> tags with absolute CDN URLs, e.g.
#   <img src="https://bsebesta.micro.blog/uploads/2024/abc.jpg" ... alt="...">
# The input is our own export, not arbitrary HTML, so a tolerant regex is safe
# here — we are not parsing the web.
IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
SRC_RE = re.compile(r"""\bsrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
ALT_RE = re.compile(r"""\balt\s*=\s*["']([^"']*)["']""", re.IGNORECASE)

# Defaults; overridable in config.yaml under a `micro:` block.
DEFAULTS = {
    "export_dir": "_MICRO",              # relative to vault_root
    "dest_dir": "Logbook/Microposts",    # relative to vault_root
    "media_subdir": "_media",            # under dest_dir
    "domain": "https://micro.bryansebesta.net",
}

STATE_FILE = REPO_ROOT / "pipeline/state/microblog.json"


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    micro = dict(DEFAULTS)
    micro.update(config.get("micro") or {})
    config["micro"] = micro
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


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def parse_export_date(value) -> tuple[str, str] | None:
    """('2024-08-09 20:13:06 +0000') → ('2024-08-09-201306', original string).

    The stem is UTC by decision (§12.3): DST-proof and derived from an
    immutable field. Returns None if the date can't be read, so the caller can
    skip rather than mint a garbage filename.
    """
    raw = str(value or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", raw)
    if not m:
        return None
    y, mo, d, h, mi, s = m.groups()
    return f"{y}-{mo}-{d}-{h}{mi}{s}", raw


def find_uploads_root(source: Path) -> Path | None:
    """Locate the export's single `uploads/` tree, wherever it sits.

    The Mac export nests posts and uploads under a 'Micro.blog export'
    subfolder, but that name is Micro.blog's to change — so we find the uploads
    directory by name rather than assuming the path.
    """
    for path in source.rglob("uploads"):
        if path.is_dir():
            return path
    return None


def resolve_image(src: str, uploads_root: Path | None) -> Path | None:
    """'https://.../uploads/2024/abc.jpg' → <uploads_root>/2024/abc.jpg."""
    if uploads_root is None:
        return None
    m = re.search(r"/uploads/(.+)$", src)
    if not m:
        return None
    candidate = uploads_root / m.group(1)
    return candidate if candidate.exists() else None


def sanitize_alt(alt: str) -> str:
    """Flatten an alt string for a markdown image: no newlines, no stray ]."""
    alt = " ".join((alt or "").split())
    return alt.replace("]", ")")


def process_body(
    body: str, stem: str, uploads_root: Path | None
) -> tuple[str, list[tuple[Path, str]]]:
    """Rewrite <img> tags to markdown images; return (new_body, [(src, dest_name)]).

    Photos are renamed with the post stem prefixed, so an image is traceable to
    its post and two posts can't collide on a bare CDN hash. Multiple images in
    one post get an index suffix.
    """
    copies: list[tuple[Path, str]] = []
    counter = {"n": 0}

    def replace(match: re.Match) -> str:
        tag = match.group(0)
        src_m = SRC_RE.search(tag)
        if not src_m:
            return tag  # malformed; leave it rather than lose content
        src = src_m.group(1)
        alt_m = ALT_RE.search(tag)
        alt = sanitize_alt(alt_m.group(1) if alt_m else "")

        source_file = resolve_image(src, uploads_root)
        if source_file is None:
            # Image not found on disk. Leave the original tag so nothing is
            # silently dropped — the dry run will flag it in the summary.
            return tag

        counter["n"] += 1
        suffix = f"-{counter['n']}" if counter["n"] > 1 else ""
        dest_name = f"{stem}{suffix}{source_file.suffix.lower()}"
        copies.append((source_file, dest_name))
        return f"![{alt}](_media/{dest_name})"

    new_body = IMG_RE.sub(replace, body)
    return new_body, copies


def build_note(meta: dict, body: str, url_abs: str, microblog_id: str) -> str:
    """Assemble the vault micropost. Titleless by construction; type derives
    from the folder (Logbook/Microposts → log), so it isn't declared here."""
    front = {
        "date": meta.get("date"),
        "url": url_abs,
        "source": "microblog",
        "microblog_id": microblog_id,
    }
    dumped = yaml.safe_dump(
        front, sort_keys=False, allow_unicode=True,
        default_flow_style=False, width=10000,
    )
    return "---\n" + dumped + "---\n\n" + body.lstrip("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest a Micro.blog export into the vault as microposts.")
    parser.add_argument("--apply", action="store_true", help="Write to the vault.")
    parser.add_argument("--source", metavar="DIR",
                        help="Export directory. Default: vault_root/<micro.export_dir>.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Process at most N posts (for a trial run).")
    args = parser.parse_args()

    config = load_config()
    vault = Path(config["vault_root"])
    micro = config["micro"]

    source = Path(args.source) if args.source else vault / micro["export_dir"]
    dest = vault / micro["dest_dir"]
    media = dest / micro["media_subdir"]
    domain = micro["domain"].rstrip("/")

    if not source.exists():
        print(f"Export directory not found: {source}", file=sys.stderr)
        return 2

    uploads_root = find_uploads_root(source)

    # Collect post files: every .md under the export except anything inside an
    # uploads/ tree (there are none, but be defensive).
    posts = sorted(
        p for p in source.rglob("*.md")
        if "uploads" not in p.parts
    )
    if args.limit:
        posts = posts[: args.limit]

    state = load_state()

    print(f"\n{'─' * 72}")
    print(f"MICRO INGEST — {len(posts)} post(s) in {source}")
    print(f"  → {dest}")
    print(f"{'─' * 72}\n")

    planned = []          # (stem, url_path, url_abs, microblog_id, note_text, copies)
    skipped_no_date = []
    missing_images = []

    for path in posts:
        meta, body = split_frontmatter(
            path.read_text(encoding="utf-8", errors="replace"))
        parsed = parse_export_date(meta.get("date"))
        if not parsed:
            skipped_no_date.append(path)
            continue
        stem, _ = parsed

        rel_url = str(meta.get("url") or "").strip()
        if not rel_url:
            # No URL means no stable key and no link target — skip loudly.
            skipped_no_date.append(path)
            continue
        url_path = rel_url if rel_url.startswith("/") else "/" + rel_url
        url_abs = domain + url_path
        microblog_id = path.stem  # Micro.blog's internal post id (the filename)

        new_body, copies = process_body(body, stem, uploads_root)
        if IMG_RE.search(new_body):
            missing_images.append((path, url_path))

        note_text = build_note(meta, new_body, url_abs, microblog_id)
        planned.append((stem, url_path, url_abs, microblog_id, note_text, copies))

    # Report
    new_count = sum(1 for p in planned if p[1] not in state)
    update_count = len(planned) - new_count
    image_count = sum(len(p[5]) for p in planned)

    for stem, url_path, url_abs, mbid, _, copies in planned:
        flag = "new " if url_path not in state else "sync"
        imgs = f"  [{len(copies)} img]" if copies else ""
        print(f"  {flag}  {stem}.md   ← {url_path}{imgs}")

    print(f"\n{'─' * 72}")
    print("SUMMARY")
    print(f"  posts:      {len(planned)}  ({new_count} new, {update_count} re-sync)")
    print(f"  photos:     {image_count}")
    if skipped_no_date:
        print(f"  skipped:    {len(skipped_no_date)} (no readable date or url)")
    if missing_images:
        print(f"  ⚠ images not found on disk in {len(missing_images)} post(s):")
        for path, url_path in missing_images:
            print(f"      {url_path}  ({path.name})")

    print(f"\n{'─' * 72}")
    if not args.apply:
        print("DRY RUN — vault untouched. Re-run with --apply.")
        return 0

    # Apply
    dest.mkdir(parents=True, exist_ok=True)
    if image_count:
        media.mkdir(parents=True, exist_ok=True)

    written = 0
    copied = 0
    for stem, url_path, url_abs, microblog_id, note_text, copies in planned:
        for source_file, dest_name in copies:
            target = media / dest_name
            if not target.exists():
                shutil.copy2(source_file, target)
                copied += 1

        note_path = dest / f"{stem}.md"
        tmp = note_path.with_suffix(".md.micro-tmp")
        tmp.write_text(note_text, encoding="utf-8")
        os.replace(tmp, note_path)
        written += 1

        state[url_path] = {
            "file": f"{micro['dest_dir']}/{stem}.md",
            "microblog_id": microblog_id,
            "url": url_abs,
        }

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE {written} micropost(s), copied {copied} photo(s).")
    print(f"State: {STATE_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
