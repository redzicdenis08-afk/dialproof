# Contributing to dialproof

Thanks for considering a contribution. This project aims to stay small, readable, and dependency-free at its core.

## Development setup

```bash
git clone https://github.com/redzicdenis08-afk/dialproof
cd dialproof
pip install -e ".[dev]"
```

## Running tests

```bash
python -m pytest tests/ -q
```

The suite is pure pytest with no fixtures beyond `tmp_path`; every check has at least one firing test and one passing test.

## Guidelines

- **Keep the core dependency-free.** Standard library only. Optional integrations belong behind extras.
- **Every finding needs a receipt.** If you add a check, it must cite the transcript turns that triggered it via `receipt_for`. The `Finding` constructor will reject you otherwise — that is intentional.
- **Be conservative.** A false "your agent is broken" costs more trust than a miss. Prefer a check that under-fires to one that over-fires, and add a negative test proving it stays quiet on clean calls.
- Run `ruff check .` before opening a PR.
- One focused change per PR, with the before/after behavior described.

## Adding a new check

1. Write a function `(transcript, config) -> list[Finding]` in `dialproof/checks.py` (or your own module) and decorate it with `@register_check("name", "description")`.
2. Cite evidence with `receipt_for(transcript, [indices], note=...)`.
3. Add at least two tests in `tests/test_checks.py`: one where it fires (asserting the receipt indices) and one where it stays quiet.
4. If it needs a knob, add a field to `AuditConfig` with a sensible default.

## Adding a transcript format

1. Add a `parse_<provider>` function in `dialproof/parser.py` returning a `Transcript`.
2. Wire it into `parse_transcript`, and extend auto-detection only if the format is unambiguous.
3. Drop a synthetic sample under `examples/` (fictional businesses, `+1-555` numbers, `example.com` emails only) and add a parser test.
