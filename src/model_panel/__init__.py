"""Public interface for the model-panel package."""
from .config import PanelConfig, Route, collect_secrets, expand_env, load_config, redact, validate_config
from .dedup import fingerprint_of, group_duplicates, independent_count
from .report import render_panel_report
from .runner import RouteResult, ping_route, run_panel, run_route
from .synthesis import Synthesis, build_synthesis, render_synthesis

__version__ = "0.1.0"

__all__ = ["PanelConfig", "Route", "RouteResult", "Synthesis", "build_synthesis", "collect_secrets", "expand_env", "fingerprint_of", "group_duplicates", "independent_count", "load_config", "ping_route", "redact", "render_panel_report", "render_synthesis", "run_panel", "run_route", "validate_config"]
