# model-panel

A small Python package for comparing independent model routes on one identical task and turning their answers into a decision-grade report. It keeps route metadata visible, detects duplicate voices, and treats failed measurement as missing evidence rather than a weak answer.

## Method

1. Record your own opinion before reading any panel answer.
2. Ping every route; each ping is a real call per route and roughly doubles the number of route calls in a run; drop dead routes and note the drop.
3. Send an identical prompt to every live route in parallel, with standard input closed.
4. Collect each answer, elapsed time, token counts, finish reason, and error when available.
5. Retry an empty answer once. Empty output, timeout, and billing failure are not measured, never weak.
6. Treat labels with the same fingerprint as one independent voice.
7. Synthesize with your opinion first, then route answers, agreement, divergence, unique contributions, verdict, and a dated cost report. Earlier verdicts become stale within hours; unpinged routes are labelled not remeasured.

## Quick start

Python 3.11 or newer is required. Runtime code uses only the standard library.

```sh
python3 -m pip install .
```

For a source checkout, use the `PYTHONPATH` variant below. `requirements.txt` lists test dependencies only.

```sh
PYTHONPATH=src python3 -m model_panel.cli run --config examples/routes.example.json --prompt-file task.txt --opinion 'My initial position'
```

Routes are command templates; configure secrets through environment-variable placeholders rather than putting credentials in the file. A route example:

```json
{"name":"sample","command":["{python}","-m","model_panel.fake_route","--flavour","alpha","--prompt-file","{prompt_file}"],"model":"offline","kind":"subscription","timeout_s":10}
```

The runner expands `${VAR}` and `${VAR:-default}`, substitutes `{python}`, `{model}`, and `{prompt_file}`, and closes child standard input. Keep facts separate from prior conclusions; label conclusions as positions to audit.

## Honest failure log

- A panel given the lead's conclusions as facts optimized strategy inside that frame and missed that the frame itself was wrong. Facts and prior conclusions are now shipped separately, with conclusions marked as positions to audit.
- Reasoning routes burned a small token budget on hidden reasoning and returned empty; they were logged as silent or weak. Empty output with length is a retry signal, not a verdict.
- A route catalogue listed many labels that probes later showed were one backend under many names. Counting them as independent voices inflated confidence. Fingerprint dedup is mandatory.
- Stale route verdicts were repeated for days as if current. A route not pinged in the current round is reported as not remeasured.
- A panel run through a gateway died on billing mid-round; missing answers were first summarized as disagreement. Not measured is not disagreement.

## Limitations

The package cannot establish that routes are truly independent; fingerprints only detect identical normalized answers. Token and finish metadata depend on the configured command's output and may be unavailable. It does not estimate prices or repair a biased prompt.

## Project layout

`src/model_panel` contains configuration, execution, deduplication, synthesis, reporting, and the offline fake route. `examples` contains a JSON configuration and deterministic demo. `tests` contains the acceptance suite.

## Testing

```sh
PYTHONPATH=src python3 -m pytest -q
python3 examples/run_demo.py
```
