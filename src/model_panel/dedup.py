"""Detect identical normalized answers and count independent voices.

These helpers operate on answer fingerprints only. Synthesis also honours
caller-declared fingerprints, which can group distinct answer text.
"""
from __future__ import annotations
import hashlib
import re
from collections import defaultdict
from .runner import RouteResult


def fingerprint_of(answer: str) -> str:
    """Return a stable 12-character digest of a normalized answer."""
    normalized = re.sub(r"\s+", " ", answer.lower()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def group_duplicates(results: list[RouteResult]) -> list[list[str]]:
    """Return groups of successful route names with shared answer fingerprints."""
    groups: dict[str, list[str]] = defaultdict(list)
    for result in results:
        if result.status == "ok":
            groups[fingerprint_of(result.answer)].append(result.route)
    return [names for names in groups.values() if len(names) > 1]


def independent_count(results: list[RouteResult]) -> int:
    """Count successful routes after removing repeated voices."""
    ok = [result for result in results if result.status == "ok"]
    return len(ok) - sum(len(group) - 1 for group in group_duplicates(ok))
