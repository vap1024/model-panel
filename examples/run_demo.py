"""Generate a fully deterministic offline panel synthesis example."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from model_panel.config import PanelConfig, Route
from model_panel.fake_route import ANSWERS
from model_panel.runner import RouteResult, run_panel
from model_panel.synthesis import build_synthesis, render_synthesis


def main() -> int:
    """Write or print a synthesis with fixed measurements and date."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    args = parser.parse_args()
    routes = [Route(flavour, ["offline"], model=f"demo-{flavour}", kind="subscription") for flavour in ("alpha", "beta", "gamma")]
    routes.append(Route("dead", ["offline"], kind="subscription"))
    elapsed = {"alpha": 0.50, "beta": 0.70, "gamma": 0.90}
    def fake(route: Route, prompt: str) -> RouteResult:
        if route.name == "dead":
            return RouteResult(route.name, "failed", elapsed_s=0.0, error="synthetic unavailable", measured_at="2026-11-02T09:06:00+00:00")
        return RouteResult(route.name, "ok", ANSWERS[route.name], elapsed[route.name], exit_code=0, measured_at="2026-11-02T09:06:00+00:00")
    results = run_panel(PanelConfig(routes), "Compare the evidence.", runner_fn=fake)
    fingerprints = {route.name: route.fingerprint for route in routes if route.fingerprint}
    text = render_synthesis(build_synthesis(results, "My initial position: compare evidence before choosing.", "Retain the shared evidence and investigate the divergence.", now_iso="2026-11-02T09:06:00+00:00", fingerprints=fingerprints))
    if args.out:
        Path(args.out).write_bytes(text.encode("utf-8"))
    else:
        print(text, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
