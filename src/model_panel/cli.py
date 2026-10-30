"""Command line interface for route probes and panel runs."""
from __future__ import annotations
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from .config import load_config
from .runner import ping_route, run_panel
from .report import render_panel_report


def main(argv: list[str] | None = None) -> int:
    """Run the requested operation and return a process exit status."""
    parser = argparse.ArgumentParser(prog="model-panel")
    subs = parser.add_subparsers(dest="action", required=True)
    ping = subs.add_parser("ping")
    ping.add_argument("--config", required=True)
    run = subs.add_parser("run")
    run.add_argument("--config", required=True)
    run.add_argument("--prompt-file", required=True)
    run.add_argument("--opinion", default="")
    run.add_argument("--out")
    run.add_argument("--verdict", default="")
    run.add_argument("--stale", default="")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        prompt = Path(args.prompt_file).read_text(encoding="utf-8") if args.action == "run" else ""
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.action == "ping":
        results = [ping_route(route) for route in config.routes]
        for result in results:
            print(f"{result.route}: {result.status}")
    else:
        pings = [ping_route(route) for route in config.routes]
        live = [route for route, ping in zip(config.routes, pings) if ping.status == "ok"]
        dropped = [type(ping)(ping.route, "dropped after ping: " + ping.status) for ping in pings if ping.status != "ok"]
        from .config import PanelConfig
        results = run_panel(PanelConfig(live), prompt) + dropped
        fingerprints = {route.name: route.fingerprint for route in config.routes if route.fingerprint}
        report = render_panel_report(results, Path(args.prompt_file).name, datetime.now(timezone.utc).isoformat(), args.opinion, fingerprints, args.verdict, tuple(x for x in args.stale.split(",") if x))
        if args.out:
            Path(args.out).write_text(report, encoding="utf-8")
        else:
            print(report)
    return 0 if any(result.status == "ok" for result in results) else 1

if __name__ == "__main__":
    raise SystemExit(main())
