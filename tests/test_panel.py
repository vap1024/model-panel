"""Acceptance tests for configuration, execution, synthesis, and examples."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
import pytest
from model_panel.config import PanelConfig, Route, collect_secrets, expand_env, load_config, redact, validate_config
from model_panel.dedup import fingerprint_of, group_duplicates, independent_count
from model_panel.runner import RouteResult, run_panel, run_route
from model_panel.synthesis import build_synthesis, render_synthesis


def test_load_config(tmp_path):
    p = tmp_path / "routes.json"
    p.write_text(json.dumps({"routes": [{"name": "one", "command": ["echo"]}]}))
    assert load_config(p).routes[0].name == "one"

def test_validation_errors():
    cases = [
        ([Route("x", ["a"]), Route("x", ["b"])], "duplicate route name"),
        ([Route("x", [])], "command must not be empty"),
        ([Route("x", ["a"], timeout_s=0)], "timeout_s must be positive"),
        ([Route("", ["a"])], "name must not be empty"),
    ]
    for routes, message in cases:
        with pytest.raises(ValueError, match=message):
            validate_config(PanelConfig(routes))


def test_expand_env_value():
    assert expand_env(["${A}"], {"A": "value"}) == ["value"]

def test_expand_env_default():
    assert expand_env(["${A:-fallback}"], {}) == ["fallback"]
    assert expand_env(["${A:-fallback}"], {"A": ""}) == ["fallback"]

def test_expand_env_missing():
    with pytest.raises(ValueError, match="missing environment variable"):
        expand_env(["${A}"], {})

def test_redact():
    assert redact("value leaked", ["leaked"]) == "value ***"

def test_collect_secrets():
    assert collect_secrets({"API_KEY": "abcd", "TOKEN": "abc", "NAME": "abcd"}) == ["abcd"]

def test_real_runner_ok():
    route = Route("a", [sys.executable, "-m", "model_panel.fake_route", "--flavour", "alpha", "--prompt-file", "{prompt_file}"])
    assert run_route(route, "task").status == "ok"

def test_empty_retry():
    route = Route("e", [sys.executable, "-m", "model_panel.fake_route", "--flavour", "empty", "--prompt-file", "{prompt_file}"])
    result = run_route(route, "task")
    assert (result.status, result.attempts) == ("empty", 2)

def test_timeout():
    route = Route("slow", [sys.executable, "-c", "import time; time.sleep(2)"], timeout_s=0.05)
    assert run_route(route, "task").status == "timeout"

def test_failed():
    route = Route("bad", [sys.executable, "-m", "model_panel.fake_route", "--flavour", "fail"])
    result = run_route(route, "task")
    assert result.status == "failed" and "synthetic" in result.error

def test_parallel_order():
    routes = [Route(str(i), ["unused"]) for i in range(3)]
    def fake(route, prompt):
        time.sleep((2-int(route.name)) * .01)
        return RouteResult(route.name, "ok", prompt)
    assert [r.route for r in run_panel(PanelConfig(routes), "same", runner_fn=fake)] == ["0", "1", "2"]

def test_fingerprint_normalization():
    assert fingerprint_of("A  B\n") == fingerprint_of("a b")

def test_group_duplicates():
    results = [RouteResult("a", "ok", "same"), RouteResult("b", "ok", " same "), RouteResult("c", "ok", "other")]
    assert group_duplicates(results) == [["a", "b"]]

def test_independent_count():
    results = [RouteResult("a", "ok", "same"), RouteResult("b", "ok", "same"), RouteResult("c", "failed")]
    assert independent_count(results) == 1

def test_synthesis_section_order():
    text = render_synthesis(build_synthesis([], "prior"))
    assert text.index("## Own opinion") < text.index("## Per-route answers")

def test_not_measured():
    text = render_synthesis(build_synthesis([RouteResult("x", "timeout")], "prior"))
    assert "x**: not measured (timeout)" in text

def test_stale():
    assert "not remeasured" in render_synthesis(build_synthesis([], "", stale_routes=("old",)))

def test_agreement_unique_tokens():
    syn = build_synthesis([RouteResult("a", "ok", "shared common uniquea"), RouteResult("b", "ok", "shared common uniqueb")], "")
    assert "shared" in syn.common_tokens and "uniquea" in syn.unique_tokens["a"]

def test_cost_report():
    text = render_synthesis(build_synthesis([RouteResult("a", "ok", "x", elapsed_s=.5)], "", now_iso="date"))
    assert "Date: date" in text and "elapsed 0.50s" in text and "PANEL_META" in text

def test_synthesis_dedup():
    syn = build_synthesis([RouteResult("a", "ok", "same answer"), RouteResult("b", "ok", "same answer")], "")
    assert syn.independent_voices == 1 and "duplicate voice of a" in render_synthesis(syn)

def test_agreement_empty_token_sets():
    syn = build_synthesis([RouteResult("a", "ok", "yes"), RouteResult("b", "ok", "no")], "")
    assert syn.agreement_score == 0.0

def test_single_voice_agreement_is_na():
    syn = build_synthesis([RouteResult("a", "ok", "same"), RouteResult("b", "ok", " SAME ")], "")
    assert syn.independent_voices == 1
    assert "Agreement score: n/a" in render_synthesis(syn)

def test_declared_fingerprint_dedup():
    syn = build_synthesis([RouteResult("a", "ok", "answer one"), RouteResult("b", "ok", "different answer")], "", fingerprints={"a": "fp1", "b": "fp1"})
    text = render_synthesis(syn)
    assert syn.independent_voices == 1 and "b** (duplicate voice of a)" in text

def test_concurrency():
    routes = [Route(str(i), ["unused"]) for i in range(3)]
    def slow(route, prompt):
        time.sleep(.3)
        return RouteResult(route.name, "ok", "done")
    start = time.monotonic()
    run_panel(PanelConfig(routes), "", runner_fn=slow)
    assert time.monotonic() - start < .8

def test_stdin_closed():
    route = Route("stdin", [sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"])
    assert run_route(route, "secret input").answer == "0"

def test_redaction_subprocess(monkeypatch):
    secret = "synthetic-secret-value-1234"
    monkeypatch.setenv("DEMO_API_TOKEN", secret)
    route = Route("leak", [sys.executable, "-c", "import os,sys; print(os.environ['DEMO_API_TOKEN'], file=sys.stderr); sys.exit(1)"])
    result = run_route(route, "")
    assert secret not in result.error and "***" in result.error

def test_panel_meta():
    route = Route("meta", [sys.executable, "-m", "model_panel.fake_route", "--flavour", "meta"])
    result = run_route(route, "")
    assert result.answer == "metadata answer" and (result.tokens_in, result.tokens_out, result.finish_reason) == (12, 34, "stop")

def test_report_content():
    from model_panel.report import render_panel_report
    text = render_panel_report([RouteResult("a", "ok", "answer")], "title", "date")
    assert "# Panel run: title" in text and "## Agreement" in text and "## Cost report" in text

def test_ping_route_ok():
    from model_panel.runner import ping_route
    route = Route("p", [sys.executable, "-m", "model_panel.fake_route", "--flavour", "alpha"])
    assert ping_route(route).status == "ok"

def test_cli_options_and_bad_config(tmp_path):
    env = dict(os.environ, PYTHONPATH="src")
    config = tmp_path / "routes.json"
    config.write_text(json.dumps({"routes": [{"name":"r", "command":[sys.executable,"-m","model_panel.fake_route","--flavour","alpha"], "fingerprint":"shared"}]}))
    prompt = tmp_path / "prompt"; prompt.write_text("go")
    report = tmp_path / "report"
    result = subprocess.run([sys.executable,"-m","model_panel.cli","run","--config",str(config),"--prompt-file",str(prompt),"--verdict","DECISION","--stale","old","--out",str(report)],env=env,capture_output=True,text=True)
    assert result.returncode == 0 and "DECISION" in report.read_text() and "old**: not remeasured" in report.read_text()
    bad = subprocess.run([sys.executable,"-m","model_panel.cli","ping","--config",str(tmp_path / "missing")],env=env,capture_output=True,text=True)
    assert bad.returncode == 2 and "Traceback" not in bad.stderr and bad.stderr.startswith("error:")

def test_cli_ping_and_run(tmp_path):
    config = Path("examples/routes.example.json")
    env = dict(os.environ, PYTHONPATH="src")
    ping = subprocess.run([sys.executable, "-m", "model_panel.cli", "ping", "--config", str(config)], env=env, capture_output=True)
    prompt = tmp_path / "task.txt"
    prompt.write_text("task")
    out = tmp_path / "report.md"
    run = subprocess.run([sys.executable, "-m", "model_panel.cli", "run", "--config", str(config), "--prompt-file", str(prompt), "--out", str(out)], env=env, capture_output=True)
    assert ping.returncode == 0 and run.returncode == 0 and out.exists()

def test_demo_determinism(tmp_path):
    env = dict(os.environ, PYTHONPATH="src")
    paths = [tmp_path / "a.md", tmp_path / "b.md"]
    for path in paths:
        subprocess.run([sys.executable, "examples/run_demo.py", "--out", str(path)], env=env, check=True)
    assert paths[0].read_bytes() == paths[1].read_bytes()
