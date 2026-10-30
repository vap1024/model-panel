"""Full markdown report wrapper for panel runs."""
from .runner import RouteResult
from .synthesis import build_synthesis, render_synthesis


def render_panel_report(results: list[RouteResult], prompt_title: str, now_iso: str, own_opinion: str = "(not recorded)", fingerprints: dict[str, str] | None = None, verdict: str = "", stale_routes: tuple[str, ...] = ()) -> str:
    """Render a titled dated panel report using the common synthesis format."""
    syn = build_synthesis(results, own_opinion=own_opinion, now_iso=now_iso, fingerprints=fingerprints, verdict=verdict, stale_routes=stale_routes)
    return f"# Panel run: {prompt_title}\n\n" + render_synthesis(syn)
