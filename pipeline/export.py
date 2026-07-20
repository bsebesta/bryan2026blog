"""Export entry point.

    python -m pipeline.export              # dry run — reports, writes nothing
    python -m pipeline.export --apply      # writes markdown into content/

This command NEVER writes to the vault, under any flag. Stamping IDs is a
separate command by design (PRODUCT.md §7.3): if export both stamped and ran
in CI, CI would write back to the vault.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from .emit import emit
from .registry import scan, scan_assets

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    with open(Path(__file__).parent / "config.yaml", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    # Allows running against a different mount without editing config.yaml.
    override = os.environ.get("PIPELINE_VAULT_ROOT")
    if override:
        config["vault_root"] = override
    return config


def load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {"slugs": [], "emitted": []}
    return json.loads(state_path.read_text(encoding="utf-8"))


def rule(label: str = "") -> None:
    print(f"\n{'─' * 72}")
    if label:
        print(label)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Obsidian notes to Hugo content.")
    parser.add_argument("--apply", action="store_true",
                        help="Write files. Without this flag nothing is written.")
    args = parser.parse_args()

    config = load_config()
    vault = Path(config["vault_root"])
    if not vault.exists():
        print(f"ERROR: vault not found at {vault}", file=sys.stderr)
        return 2

    registry = scan(
        vault,
        config.get("exclude_dirs", []),
        config.get("temporality_by_folder", {}),
        config.get("default_temporality", "evergreen"),
    )
    scan_assets(registry, vault, config.get("asset_exclude_dirs", []))

    # ---- scan summary --------------------------------------------------
    total = len(registry.notes)
    has_key = [n for n in registry.notes if n.publish_raw is not None]
    published = registry.published

    rule("VAULT SCAN")
    print(f"  notes indexed          {total:>6,}")
    print(f"  unreadable             {len(registry.unreadable):>6,}")
    print(f"  carrying `publish`     {len(has_key):>6,}")
    print(f"    → published          {len(published):>6,}")
    print(f"    → withheld           {len(has_key) - len(published):>6,}")
    print(f"  no publish key         {total - len(has_key):>6,}   (fails closed)")
    print(f"  assets indexed         {len(registry.assets):>6,}")

    if registry.unreadable:
        rule("UNREADABLE — likely Dropbox online-only placeholders")
        for rel, err in registry.unreadable[:10]:
            print(f"  {rel}\n    {err}")
        if len(registry.unreadable) > 10:
            print(f"  … and {len(registry.unreadable) - 10} more")

    ambiguous = [n for n in registry.notes if n.ambiguous_publish]
    if ambiguous:
        rule("AMBIGUOUS `publish` VALUES — withheld, but check for typos")
        for n in ambiguous:
            print(f"  {n.rel}\n    publish: {n.publish_raw!r}")

    broken_yaml = [n for n in registry.notes if n.yaml_error]
    if broken_yaml:
        rule("MALFORMED FRONTMATTER — withheld")
        for n in broken_yaml[:10]:
            print(f"  {n.rel}")

    # ---- collisions ----------------------------------------------------
    collisions = registry.collisions()
    published_collisions = {
        k: v for k, v in collisions.items() if any(n.published for n in v)
    }
    if published_collisions:
        rule("TITLE COLLISIONS INVOLVING PUBLISHED NOTES — must resolve")
        for key, notes in published_collisions.items():
            print(f"  {key!r}")
            for n in notes:
                print(f"    {'[pub]' if n.published else '     '} {n.rel}")
    elif collisions:
        print(f"\n  ({len(collisions):,} title collisions elsewhere in the vault; "
              f"none involve published notes)")

    # ---- publish set + diff --------------------------------------------
    state_path = REPO_ROOT / config["state_file"]
    state = load_state(state_path)
    previous = set(state.get("slugs", []))
    current = {n.slug for n in published}

    rule(f"PUBLISH SET ({len(published)})")
    for n in sorted(published, key=lambda n: n.slug):
        marker = "NEW" if n.slug not in previous else "   "
        print(f"  {marker}  {n.slug}")
        print(f"       {n.title}")

    removed = previous - current
    if removed:
        rule("WITHDRAWN SINCE LAST RUN")
        for slug in sorted(removed):
            print(f"  −  {slug}")

    # ---- emit ----------------------------------------------------------
    result = emit(registry, config, REPO_ROOT, apply=args.apply,
                  previous_manifest=state.get("emitted", []))

    if result.skipped:
        rule("SKIPPED")
        for rel, why in result.skipped:
            print(f"  {rel}\n    {why}")

    # ---- link report ---------------------------------------------------
    if result.links:
        by_status: dict[str, list] = {}
        for ref in result.links:
            by_status.setdefault(ref.status, []).append(ref)

        rule("WIKILINKS IN PUBLISHED BODIES  (v0 flattens all to plain text)")
        for status in ("published", "unpublished", "dangling"):
            refs = by_status.get(status, [])
            print(f"  {status:<12} {len(refs):>4}")
            for ref in refs:
                print(f"       {ref.target}")

    if result.assets:
        copied = [a for a in result.assets if a.status == "copied"]
        missing = [a for a in result.assets if a.status == "missing"]
        rule("ASSETS")
        print(f"  copied into bundles    {len(copied):>4}")
        for ref in copied:
            print(f"       {ref.target}  →  {ref.source}/{ref.dest}")
        if missing:
            print(f"  MISSING FROM VAULT     {len(missing):>4}   (embed dropped)")
            for ref in missing:
                print(f"       {ref.target}   in {ref.source}")

    if registry.asset_collisions:
        rule("DUPLICATE ASSET FILENAMES — first match wins")
        for name, paths in list(registry.asset_collisions.items())[:10]:
            print(f"  {name}")
            for p in paths:
                print(f"       {p}")

    if result.pruned:
        rule("PRUNED — output no longer published")
        print("  Withdrawing a note removes its page. Only files this pipeline")
        print("  generated are eligible; repo-authored pages are never touched.\n")
        for rel in result.pruned:
            print(f"  −  {rel}")

        leaking = by_status.get("unpublished", [])
        if leaking:
            rule("WARNING — published bodies name unpublished notes")
            print("  These are author-written words, not pipeline-generated, so they")
            print("  are not blocked. But each one names a note you chose not to")
            print("  publish. Review before going live.\n")
            for ref in leaking:
                print(f"  {ref.source} → {ref.target!r}")

    # ---- finish --------------------------------------------------------
    rule()
    if args.apply:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"slugs": sorted(current), "emitted": sorted(result.manifest)}, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"WROTE {len(result.written)} file(s) to {config['content_dir']}/")
        for rel in result.written:
            print(f"  {rel}")
    else:
        print(f"DRY RUN — nothing written. {len(result.written)} file(s) would be "
              f"created in {config['content_dir']}/.")
        print("Re-run with --apply to write.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
