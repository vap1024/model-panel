"""Deterministic evidence summary for measured and unmeasured routes."""
from __future__ import annotations
import re
from collections import Counter
from dataclasses import dataclass, field
from .runner import RouteResult

_STOP = set("about after again against all also and are because been before being between both but can could did does each few for from had has have her here him his how into its itself just more most not now off once only other our out over own same she should some such than that the their them then there these they this those through too under until very was were what when where which while who will with would you your".split())


def _tokens(answer: str) -> set[str]:
    """Return distinct content words of at least four characters."""
    return {word for word in re.findall(r"[a-zA-Z0-9]+", answer.lower()) if len(word) >= 4 and word not in _STOP}


@dataclass
class Synthesis:
    """Computed route comparisons and caller-supplied report context."""
    results: list[RouteResult]
    own_opinion: str
    verdict: str = ""
    stale_routes: tuple[str, ...] = ()
    now_iso: str = ""
    common_tokens: list[str] = field(default_factory=list)
    unique_tokens: dict[str, list[str]] = field(default_factory=dict)
    agreement_score: float | None = None
    not_measured: list[tuple[str, str]] = field(default_factory=list)
    duplicate_groups: list[list[str]] = field(default_factory=list)
    independent_voices: int = 0


def build_synthesis(results: list[RouteResult], own_opinion: str, verdict: str = "", stale_routes: tuple[str, ...] = (), now_iso: str = "", fingerprints: dict[str, str] | None = None) -> Synthesis:
    """Compare lexical overlap while keeping failed routes out of answer judgments."""
    ok = [r for r in results if r.status == "ok"]
    groups: dict[str, list[RouteResult]] = {}
    from .dedup import fingerprint_of
    for result in ok:
        groups.setdefault((fingerprints or {}).get(result.route) or fingerprint_of(result.answer), []).append(result)
    representatives = [items[0] for items in groups.values()]
    token_sets = {r.route: _tokens(r.answer) for r in representatives}
    counts = Counter(token for tokens in token_sets.values() for token in tokens)
    common = sorted(token for token, count in counts.items() if len(representatives) >= 2 and count > len(representatives) / 2)
    unique = {route: sorted(token for token in tokens if counts[token] == 1) for route, tokens in token_sets.items()}
    pairs = [(token_sets[left.route], token_sets[right.route]) for i, left in enumerate(representatives) for right in representatives[i+1:]]
    scores = []
    for (left_tokens, right_tokens), (left, right) in zip(pairs, [(representatives[i], representatives[j]) for i in range(len(representatives)) for j in range(i + 1, len(representatives))]):
        if not left_tokens and not right_tokens:
            scores.append(1.0 if re.sub(r"\s+", " ", left.answer.lower()).strip() == re.sub(r"\s+", " ", right.answer.lower()).strip() else 0.0)
        elif not left_tokens or not right_tokens:
            scores.append(0.0)
        else:
            scores.append(len(left_tokens & right_tokens) / len(left_tokens | right_tokens))
    missing = [(r.route, r.status) for r in results if r.status != "ok"]
    score = sum(scores) / len(scores) if len(representatives) >= 2 and scores else None
    return Synthesis(results, own_opinion, verdict, tuple(stale_routes), now_iso, common, unique, score, missing, [ [r.route for r in g] for g in groups.values() if len(g)>1 ], len(representatives))


def render_synthesis(syn: Synthesis) -> str:
    """Render fixed-order markdown with no implicit wall-clock timestamps."""
    lines = ["# Panel synthesis", "", "## Own opinion (recorded first)", "", syn.own_opinion or "(none recorded)", "", "## Per-route answers", ""]
    first_for = {name: group[0] for group in syn.duplicate_groups for name in group}
    for r in syn.results:
        if r.status == "ok":
            suffix = f" (duplicate voice of {first_for[r.route]})" if r.route in first_for and first_for[r.route] != r.route else ""
            lines.append(f"- **{r.route}**{suffix}: {r.answer}")
    agreement = f"Agreement score: {syn.agreement_score:.2f}" if syn.agreement_score is not None else "Agreement score: n/a (single independent voice)"
    lines += ["", "## Agreement", "", agreement, f"Independent voices: {syn.independent_voices} of {sum(r.status == 'ok' for r in syn.results)} measured", "Common tokens: " + (", ".join(syn.common_tokens) or "none"), "", "## Divergence", "", "Lexical overlap is a lightweight signal; review the full answers above.", "", "## Unique contributions", ""]
    for route, tokens in syn.unique_tokens.items():
        lines.append(f"- **{route}**: {', '.join(tokens) if tokens else 'none'}")
    lines += ["", "## Not measured / not remeasured", ""]
    for route, status in syn.not_measured:
        lines.append(f"- **{route}**: not measured ({status})")
    for route in syn.stale_routes:
        lines.append(f"- **{route}**: not remeasured")
    if not syn.not_measured and not syn.stale_routes:
        lines.append("- None")
    lines += ["", "## Verdict", "", syn.verdict or "(no verdict supplied)", "", "## Cost report", "", f"Date: {syn.now_iso or 'not supplied'}", ""]
    for r in syn.results:
        lines.append(f"- **{r.route}**: elapsed {r.elapsed_s:.2f}s; attempts {r.attempts}; status {r.status}; tokens in {r.tokens_in if r.tokens_in is not None else 'unknown'}; tokens out {r.tokens_out if r.tokens_out is not None else 'unknown'}; finish {r.finish_reason or 'unknown'}")
    lines += ["", "Token counts are shown when a route supplies them via PANEL_META; otherwise they are reported as unknown.", ""]
    return "\n".join(lines)

