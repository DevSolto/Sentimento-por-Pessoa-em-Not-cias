from __future__ import annotations

import unicodedata
from typing import List, Tuple


def _normalize(text: str) -> str:
    # Lowercase + remove diacritics + collapse spaces
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = " ".join(t.lower().split())
    return t


class NameFilter:
    def __init__(self, names: List[str] | None = None):
        self.original: List[str] = [n for n in (names or []) if n.strip()]
        self.normalized: List[str] = [_normalize(n) for n in self.original]

    def enabled(self) -> bool:
        return len(self.normalized) > 0

    def match(self, text: str) -> Tuple[bool, List[str]]:
        if not self.enabled():
            return True, []
        nt = _normalize(text or "")
        matched: List[str] = []
        for orig, nn in zip(self.original, self.normalized):
            if nn and nn in nt:
                matched.append(orig)
        return (len(matched) > 0), matched

