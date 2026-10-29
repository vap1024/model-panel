"""Subprocess route execution with bounded retries and parallel fan-out."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .config import PanelConfig, Route, collect_secrets, expand_env, redact


@dataclass
class RouteResult:
    """Observed outcome and available measurement metadata for one route."""
    route: str
    status: str
    answer: str = ""
    elapsed_s: float = 0.0
    exit_code: int | None = None
    error: str | None = None
    attempts: int = 1
    tokens_in: int | None = None
    tokens_out: int | None = None
    finish_reason: str | None = None
    measured_at: str = ""


RunnerFn = Callable[[Route, str], RouteResult]


def run_route(route: Route, prompt: str, runner_fn: RunnerFn | None = None) -> RouteResult:
    """Run one route, retrying empty output once; injection supports offline tests."""
    if runner_fn is not None:
        return runner_fn(route, prompt)
    started = time.monotonic()
    stamp = datetime.now(timezone.utc).isoformat()
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write(prompt)
            prompt_path = handle.name
        try:
            command = expand_env(route.command)
            command = [item.replace("{python}", sys.executable).replace("{model}", route.model or "").replace("{prompt_file}", prompt_path) for item in command]
            for attempt in (1, 2):
                try:
                    proc = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=route.timeout_s, check=False)
                except subprocess.TimeoutExpired:
                    return RouteResult(route.name, "timeout", elapsed_s=time.monotonic()-started, error="route timed out", attempts=attempt, measured_at=stamp)
                elapsed = time.monotonic() - started
                if proc.returncode:
                    return RouteResult(route.name, "failed", elapsed_s=elapsed, exit_code=proc.returncode, error=redact(proc.stderr[-1000:].strip() or "command failed", collect_secrets()), attempts=attempt, measured_at=stamp)
                output = proc.stdout.rstrip()
                meta = {}
                parts = output.splitlines()
                if parts and parts[-1].startswith("PANEL_META "):
                    try:
                        parsed = json.loads(parts[-1][11:])
                        if isinstance(parsed, dict):
                            meta = parsed
                            parts.pop()
                    except (json.JSONDecodeError, TypeError):
                        pass
                answer = "\n".join(parts).strip()
                if answer:
                    return RouteResult(route.name, "ok", redact(answer, collect_secrets()), elapsed, proc.returncode, attempts=attempt, tokens_in=meta.get("tokens_in"), tokens_out=meta.get("tokens_out"), finish_reason=meta.get("finish_reason"), measured_at=stamp)
                if attempt == 2:
                    return RouteResult(route.name, "empty", elapsed_s=elapsed, exit_code=proc.returncode, error="empty stdout after retry", attempts=2, measured_at=stamp)
        finally:
            Path(prompt_path).unlink(missing_ok=True)
    except (OSError, ValueError) as exc:
        return RouteResult(route.name, "failed", elapsed_s=time.monotonic()-started, error=redact(str(exc), collect_secrets()), measured_at=stamp)
    return RouteResult(route.name, "failed", error="unexpected runner state", measured_at=stamp)


def run_panel(config: PanelConfig, prompt: str, max_workers: int | None = None, runner_fn: RunnerFn | None = None) -> list[RouteResult]:
    """Fan the same prompt to all routes concurrently and retain config order."""
    with ThreadPoolExecutor(max_workers=max_workers or max(1, len(config.routes))) as pool:
        futures = [pool.submit(run_route, route, prompt, runner_fn) for route in config.routes]
        return [future.result() for future in futures]


def ping_route(route: Route, prompt: str = "ping: reply with the single word ok") -> RouteResult:
    """Probe a route using the ordinary execution path."""
    return run_route(route, prompt)

