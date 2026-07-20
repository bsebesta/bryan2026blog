"""Permanent note identifiers.

An id is a promise about a URL: once stamped it must never change, because
`/<id>/` is the canonical address of the note forever (PRODUCT.md §12.1).

Format is deliberately meaningless. Timestamps were rejected — for an evergreen
note, creation time is the least interesting fact about it, and encoding it
invites reading significance into an identifier that should carry none.
"""

from __future__ import annotations

import re
import secrets

# 32 characters. Excludes 0, 1, and l — the pairs that get misread or
# mistyped when someone copies an id off a screen. All lowercase, so ids are
# never mangled by case-insensitive filesystems or URL normalization.
ALPHABET = "23456789abcdefghijkmnpqrstuvwxyz"
ID_LENGTH = 10

# 32^10 ≈ 1.1e15. Collisions are not a practical concern, but generation
# checks anyway — the cost is one set lookup and the failure mode is a
# permanently wrong URL.
ID_RE = re.compile(rf"^[{ALPHABET}]{{{ID_LENGTH}}}$")


def generate(existing: set[str]) -> str:
    while True:
        candidate = "".join(secrets.choice(ALPHABET) for _ in range(ID_LENGTH))
        if candidate not in existing:
            return candidate


def is_valid(value: object) -> bool:
    return isinstance(value, str) and bool(ID_RE.match(value.strip()))
