# Contributing to Corpus

Thank you for your interest in contributing!

## Development setup

```bash
git clone https://github.com/your-org/corpus.git
cd corpus
pip install -e ".[dev]"
```

## Running tests

```bash
pytest                         # all tests
pytest tests/gravity/          # single module
pytest -k test_block           # by keyword
pytest --tb=short -q           # compact output
```

All 369+ tests must pass before a PR is merged.

## Code style

```bash
ruff check .        # lint
ruff format .       # format
mypy corpus/        # type check
```

We use:
- `ruff` for linting and formatting (line length: 100)
- `mypy --strict` for type checking
- `pytest-asyncio` for async tests

## Architecture principles

1. **No business logic in routes** — routes delegate to services/engines.
2. **PolicyEngine is final authority** — GuardianEngine checks policy before acting.
3. **Integration adapters are isolated** — they import only `corpus_sdk`, never `corpus.*`.
4. **All decisions are auditable** — every gravity computation, policy evaluation, and guardian intervention is logged.
5. **Local-first** — no external dependencies at runtime (Ollama is optional).

## Pull request process

1. Fork the repository and create a feature branch.
2. Write tests for new behaviour.
3. Ensure `pytest` and `ruff check .` both pass.
4. Open a PR with a clear description of the change and motivation.
5. A maintainer will review within 5 business days.

## Reporting bugs

Open an issue with:
- Corpus version (`corpus --version`)
- Python version
- Minimal reproduction steps
- Expected vs. actual behaviour

## Questions

Open a Discussion on GitHub.
