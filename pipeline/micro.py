"""Ingest Micro.blog posts into the vault as microposts.

    .venv/bin/python -m pipeline.micro                 # dry run, from the export
    .venv/bin/python -m pipeline.micro --apply         # writes to the vault
    .venv/bin/python -m pipeline.micro --from-api       # dry run, from the API
    .venv/bin/python -m pipeline.micro --from-api --apply

WRITES TO THE VAULT. Like `stamp` and `norm`, this is a separate command kept
out of `export` by design — `export` never writes to the vault (PRODUCT.md
§7.1). Ingest is the one thing that puts *generated* content in the vault, so it
is deliberately its own step with a dry-run twin.

Two sources, one writer
-----------------------
The posts can come from either place; everything downstream is identical.

  EXPORT  Micro.blog for macOS → File → Export → Markdown, unpacked into
          `_MICRO/`. Photos sit on disk in an `uploads/` tree and are copied.

  API     `GET /micropub?q=source` with an app token. The same clean markdown,
          returned live — no Mac app, no manual export. Photos are CDN URLs and
          are downloaded. This is the incremental path (PRODUCT.md §12.3); it
          can run on a schedule.

Both return each post's `content` as markdown with any photo as an inline
`<img>` tag — verified 2026-07-21 against the live API — so the body parser is
shared. The only per-source differences are *where the list of posts comes
from* and *where an image's bytes come from*.

Why the vault copy is never hand-edited
----------------------------------------
Micro.blog is authoritative. This command is an idempotent overwrite keyed on
each post's URL path, so re-running re-syncs rather than duplicating. Edit a
post on Micro.blog and re-run; never edit the vault copy.

Decisions baked in (PRODUCT.md §12.3)
-------------------------------------
- **Filename** is the post's UTC timestamp, `YYYY-MM-DD-HHMMSS.md`, from the
  immutable publish time. UTC by decision: DST-proof. It will not match the
  local time in the URL; the authoritative link is `url:`, not the filename.
- **`url:`** keeps the post's *path* and prepends the configured domain. Both
  sources hand back an unreliable domain — the export's URL is relative, and the
  API returns `bsebesta.micro.blog` for posts predating the custom domain — so
  the path is the only trustworthy part. Owning the domain here means a stale
  `bsebesta.micro.blog` can never freeze into the vault.
- **`date:`** is normalised to ISO-8601 UTC (`…T…+00:00`) regardless of source,
  so the two formats never sort against each other.
- **`source: microblog`** is a loop guard: it marks these as ingested so no
  future syndication step pushes them back to their origin.
- **Photos** are stored in the vault (`_media/`), never hot-linked, and embedded
  as markdown images so the descriptive `alt` text survives.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)

# Micro.blog returns a post's photo as an inline <img> in `content`, absolute
# CDN URL and alt text included. The input is our own account's data, not
# arbitrary HTML, so a tolerant regex is safe here.
IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
SRC_RE = re.compile(r"""\bsrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
ALT_RE = re.compile(r"""\balt\s*=\s*["']([^"']*)["']""", re.IGNORECASE)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# Defaults; overridable in config.yaml under a `micro:` block.
DEFAULTS = {
    "export_dir": "_MICRO",                     # relative to vault_root
    "dest_dir": "Logbook/Microposts",           # relative to vault_root
    "media_subdir": "_media",                   # under dest_dir
    "domain": "https://micro.bryansebesta.net",  # prepended to each post's path
    "micropub_url": "https://micro.blog/micropub",
    "token_env": "MICROBLOG_TOKEN",             # env var holding the app token
    "mp_destination": "",                       # only needed with multiple blogs
}

STATE_FILE = REPO_ROOT / "pipeline/state/microblog.json"
UA = {"User-Agent": "bryansebesta.net micropost ingest (personal)"}


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


# --------------------------------------------------------------------------
# A source-independent post record
# --------------------------------------------------------------------------


@dataclass
class Post:
    date_raw: str       # publish time, either "… +0000" (export) or ISO (API)
    url_path: str       # /2024/08/09/foo.html — domain stripped
    content: str        # markdown body, may hold an inline <img>
    microblog_id: str   # Micro.blog's numeric post id


def parse_post_date(value) -> tuple[str, str] | None:
    """Publish time → (filename stem, canonical ISO), both UTC.

    Accepts either the export's '2024-08-09 20:13:06 +0000' or the API's
    '2024-08-09T20:13:06+00:00' and returns a single canonical form, so the two
    sources never produce differently-formatted `date:` values that would sort
    against each other. None if unparseable — the caller skips rather than mint
    a garbage filename.
    """
    raw = str(value or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", raw)
    if not m:
        return None
    y, mo, d, h, mi, s = m.groups()
    stem = f"{y}-{mo}-{d}-{h}{mi}{s}"
    canonical = f"{y}-{mo}-{d}T{h}:{mi}:{s}+00:00"
    return stem, canonical


def url_to_path(url: str) -> str:
    """Absolute or relative URL → path only. '/2024/08/09/foo.html'."""
    url = str(url or "").strip()
    if not url:
        return ""
    if url.startswith("/"):
        return url
    return urllib.parse.urlparse(url).path or ""


def image_ext(src: str) -> str:
    """Extension for a stored photo, defaulting to .jpg for odd CDN URLs."""
    ext = Path(urllib.parse.urlparse(src).path).suffix.lower()
    return ext if ext in IMAGE_EXTS else ".jpg"


def sanitize_alt(alt: str) -> str:
    """Flatten an alt string for a markdown image: no newlines, no stray ]."""
    alt = " ".join((alt or "").split())
    return alt.replace("]", ")")


def process_body(body: str, stem: str) -> tuple[str, list[tuple[str, str]]]:
    """Rewrite <img> tags to markdown images.

    Returns (new_body, [(src_url, dest_name)]). Photos are renamed with the post
    stem prefixed, so an image is traceable to its post and two posts can't
    collide on a bare CDN hash. Multiple images in one post get an index suffix.

    The (src, dest) pairs are resolved to bytes later, by the caller, because
    that step differs by source: copy from disk (export) or download (API).
    """
    refs: list[tuple[str, str]] = []
    counter = {"n": 0}

    def replace(match: re.Match) -> str:
        tag = match.group(0)
        src_m = SRC_RE.search(tag)
        if not src_m:
            return tag  # malformed; leave it rather than lose content
        src = src_m.group(1)
        alt_m = ALT_RE.search(tag)
        alt = sanitize_alt(alt_m.group(1) if alt_m else "")

        counter["n"] += 1
        suffix = f"-{counter['n']}" if counter["n"] > 1 else ""
        dest_name = f"{stem}{suffix}{image_ext(src)}"
        refs.append((src, dest_name))
        return f"![{alt}](_media/{dest_name})"

    return IMG_RE.sub(replace, body), refs


def build_note(date_iso: str, url_abs: str, microblog_id: str, body: str) -> str:
    """Assemble the vault micropost. Titleless by construction; type derives
    from the folder (Logbook/Microposts → log), so it isn't declared here."""
    front = {
        "date": date_iso,
        "url": url_abs,
        "source": "microblog",
        "microblog_id": microblog_id,
    }
    dumped = yaml.safe_dump(
        front, sort_keys=False, allow_unicode=True,
        default_flow_style=False, width=10000,
    )
    return "---\n" + dumped + "---\n\n" + body.lstrip("\n")


# --------------------------------------------------------------------------
# Source: the Mac markdown export
# --------------------------------------------------------------------------


def find_uploads_root(source: Path) -> Path | None:
    """Locate the export's single `uploads/` tree, wherever it sits."""
    for path in source.rglob("uploads"):
        if path.is_dir():
            return path
    return None


def local_image(src: str, uploads_root: Path | None) -> Path | None:
    """'https://.../uploads/2024/abc.jpg' → <uploads_root>/2024/abc.jpg."""
    if uploads_root is None:
        return None
    m = re.search(r"/uploads/(.+)$", src)
    if not m:
        return None
    candidate = uploads_root / m.group(1)
    return candidate if candidate.exists() else None


def posts_from_export(source: Path) -> list[Post]:
    out: list[Post] = []
    for path in sorted(source.rglob("*.md")):
        if "uploads" in path.parts:
            continue
        meta, body = split_frontmatter(
            path.read_text(encoding="utf-8", errors="replace"))
        out.append(Post(
            date_raw=str(meta.get("date") or ""),
            url_path=url_to_path(meta.get("url") or ""),
            content=body,
            microblog_id=path.stem,  # the export names files by post id
        ))
    return out


# --------------------------------------------------------------------------
# Source: the Micropub q=source API
# --------------------------------------------------------------------------


def api_get(micropub_url: str, token: str, params: dict) -> dict:
    url = micropub_url + "?" + urllib.parse.urlencode(params)
    headers = {"Authorization": f"Bearer {token}", **UA}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8"))


def posts_from_api(micro: dict, token: str, cap: int = 0) -> list[Post]:
    """Page through /micropub?q=source, published posts only, newest first.

    Micro.blog returns items newest-first; we page on `offset` until a short
    page arrives. Drafts (`post-status: draft`) are skipped — they have no
    stable public URL yet.
    """
    out: list[Post] = []
    seen: set = set()
    page = 100
    offset = 0
    while True:
        params = {"q": "source", "limit": page, "offset": offset}
        if micro.get("mp_destination"):
            params["mp-destination"] = micro["mp_destination"]
        data = api_get(micro["micropub_url"], token, params)
        items = data.get("items") or []
        if not items:
            break
        for it in items:
            props = it.get("properties") or {}
            status = (props.get("post-status") or ["published"])[0]
            if status == "draft":
                continue
            uid = (props.get("uid") or [None])[0]
            if uid in seen:
                continue
            seen.add(uid)
            content = (props.get("content") or [""])[0]
            # Defensive: some Micropub servers wrap HTML content in a dict.
            # Micro.blog returns a plain markdown string (verified), but coerce
            # rather than crash if that ever changes.
            if isinstance(content, dict):
                content = content.get("html") or content.get("value") or ""
            out.append(Post(
                date_raw=(props.get("published") or [""])[0],
                url_path=url_to_path((props.get("url") or [""])[0]),
                content=content,
                microblog_id=str(uid) if uid is not None else "",
            ))
        if len(items) < page:
            break
        offset += page
        if cap and len(out) >= cap:
            break
    return out[:cap] if cap else out


def download_image(src: str) -> bytes | None:
    """Fetch a photo from its CDN URL. No auth — uploads are public."""
    try:
        req = urllib.request.Request(src, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as res:
            data = res.read()
        return data if data and len(data) > 500 else None
    except Exception:
        return None


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest Micro.blog posts into the vault as microposts.")
    parser.add_argument("--apply", action="store_true", help="Write to the vault.")
    parser.add_argument("--from-api", action="store_true",
                        help="Pull live from the Micropub API instead of the "
                             "Mac export. Needs the app token in the environment.")
    parser.add_argument("--source", metavar="DIR",
                        help="Export directory (export mode). "
                             "Default: vault_root/<micro.export_dir>.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Process at most N posts (for a trial run).")
    args = parser.parse_args()

    config = load_config()
    vault = Path(config["vault_root"])
    micro = config["micro"]
    dest = vault / micro["dest_dir"]
    media = dest / micro["media_subdir"]
    domain = micro["domain"].rstrip("/")

    # ---- gather posts from the chosen source ---------------------------
    mode = "api" if args.from_api else "export"
    uploads_root = None

    if mode == "api":
        token = os.environ.get(micro["token_env"], "").strip()
        if not token:
            print(f"No app token. Set ${micro['token_env']} to a Micro.blog "
                  f"app token (Account → App tokens).", file=sys.stderr)
            return 2
        try:
            posts = posts_from_api(micro, token, cap=args.limit)
        except Exception as exc:
            print(f"API request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        origin = micro["micropub_url"] + "?q=source"
    else:
        source = Path(args.source) if args.source else vault / micro["export_dir"]
        if not source.exists():
            print(f"Export directory not found: {source}", file=sys.stderr)
            return 2
        uploads_root = find_uploads_root(source)
        posts = posts_from_export(source)
        if args.limit:
            posts = posts[: args.limit]
        origin = str(source)

    state = load_state()

    print(f"\n{'─' * 72}")
    print(f"MICRO INGEST ({mode}) — {len(posts)} post(s) from {origin}")
    print(f"  → {dest}")
    print(f"{'─' * 72}\n")

    # ---- plan ----------------------------------------------------------
    planned = []          # (stem, url_path, url_abs, mbid, note_text, refs)
    skipped = []
    for post in posts:
        parsed = parse_post_date(post.date_raw)
        if not parsed or not post.url_path:
            skipped.append(post)
            continue
        stem, date_iso = parsed
        url_abs = domain + post.url_path
        new_body, refs = process_body(post.content, stem)
        note_text = build_note(date_iso, url_abs, post.microblog_id, new_body)
        planned.append((stem, post.url_path, url_abs, post.microblog_id, note_text, refs))

    planned.sort(key=lambda p: p[0], reverse=True)

    new_count = sum(1 for p in planned if p[1] not in state)
    image_count = sum(len(p[5]) for p in planned)

    for stem, url_path, _, _, _, refs in planned:
        flag = "new " if url_path not in state else "sync"
        imgs = f"  [{len(refs)} img]" if refs else ""
        print(f"  {flag}  {stem}.md   ← {url_path}{imgs}")

    # In export mode we can cheaply confirm each photo exists on disk now.
    missing_local = []
    if mode == "export":
        for stem, url_path, _, _, _, refs in planned:
            for src, _ in refs:
                if local_image(src, uploads_root) is None:
                    missing_local.append((url_path, src))

    print(f"\n{'─' * 72}")
    print("SUMMARY")
    print(f"  posts:      {len(planned)}  ({new_count} new, {len(planned) - new_count} re-sync)")
    print(f"  photos:     {image_count}   ({'download' if mode == 'api' else 'copy from disk'})")
    if skipped:
        print(f"  skipped:    {len(skipped)} (no readable date or url)")
    if missing_local:
        print(f"  ⚠ {len(missing_local)} photo(s) not found in the export:")
        for url_path, src in missing_local:
            print(f"      {url_path}  {src}")

    print(f"\n{'─' * 72}")
    if not args.apply:
        print("DRY RUN — vault untouched. Re-run with --apply.")
        return 0

    # ---- apply ---------------------------------------------------------
    dest.mkdir(parents=True, exist_ok=True)
    if image_count:
        media.mkdir(parents=True, exist_ok=True)

    written = saved = failed = 0
    fetch_failures = []
    for stem, url_path, url_abs, microblog_id, note_text, refs in planned:
        for src, dest_name in refs:
            target = media / dest_name
            if target.exists():
                continue
            if mode == "api":
                data = download_image(src)
                if data is None:
                    fetch_failures.append((url_path, src))
                    failed += 1
                    continue
                target.write_bytes(data)
            else:
                local = local_image(src, uploads_root)
                if local is None:
                    fetch_failures.append((url_path, src))
                    failed += 1
                    continue
                shutil.copy2(local, target)
            saved += 1

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

    print(f"WROTE {written} micropost(s), saved {saved} photo(s).")
    if failed:
        print(f"⚠ {failed} photo(s) could not be fetched:")
        for url_path, src in fetch_failures:
            print(f"      {url_path}  {src}")
    print(f"State: {STATE_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
