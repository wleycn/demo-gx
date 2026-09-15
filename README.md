# Pipeline Project

A Pandas-based single-machine lakehouse reference implementation. It processes JSON event data through a three-layer pipeline: Bronze (raw archive), Silver (cleaned detail), Gold (curated star schema).

## Prerequisites

Python 3.10 or later, and `make` (Linux/macOS). Every step has a `make` target; manual equivalents are listed for environments without `make`.

## Quick Start

| Step | Command | What it does |
|---|---|---|
| 1 | `make setup` | First run only: create `.venv` and install the package in editable mode |
| 2 | `make data` | Generate `data/{env}/input/sample_data.json` (107 records with injected anomalies) |
| 3 | `make run` | Run the pipeline (default env `dev`; override with `ENV=test make run`) |
| 4 | `make test` | Run the pytest suite |
| 5 | `make lint` | Check lint, formatting and type annotations (ruff + mypy) |
| 6 | `make clean` | Remove all run artifacts for a clean re-run |
| 7 | `make check-data` | reads what a run produced and compares it with the table contracts in `docs/tables/` |
| 8 | `make show-data` | prints the rows themselves, LAYER=gold TABLE=fact_daily_events DATE=2026-09-01 |

Manual equivalents (no `make`):

```bash
# 1. Setup (first run only). Dependencies are declared in pyproject.toml.
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"

# 2. Generate data
.venv/bin/python scripts/generate_sample_data.py

# 3. Run the pipeline
.venv/bin/python -m demo_gx.cli --env dev

# 4. Run tests
.venv/bin/python -m pytest tests/

# 5. Lint, format check and type check. All three read pyproject.toml.
.venv/bin/python -m ruff check src scripts tests
.venv/bin/python -m ruff format --check src scripts tests
.venv/bin/python -m mypy
```

`pip install -e .` is what makes `python -m demo_gx.cli` work from any directory.
If you would rather not install, `PYTHONPATH=src .venv/bin/python -m demo_gx.cli ...`
runs the same entry point, and `pytest` needs no install at all because
`pyproject.toml` already puts `src` on the test path.

## Repository Layout

```text
demo-gx/
├── src/demo_gx/              # Installable package (per-package __init__.py)
│   ├── cli.py                # Entry point: orchestrates read -> Bronze -> validate -> clean -> dedup -> Silver -> Gold
│   ├── ingestion/reader.py   # read_input() + write_bronze()
│   ├── validation/schema_validator.py   # SchemaValidator (strict contract validation)
│   ├── validation/error_envelope.py     # Quarantine envelope build + write
│   ├── transformation/cleaner.py        # DataCleaner
│   ├── transformation/deduplicator.py   # Deduplicator
│   ├── curation/builder.py              # GoldBuilder (fact / dims / wide)
│   └── common/               # config.py, logger.py, mask.py, metrics.py, time_utils.py
├── config/                   # Configuration, split by purpose
│   ├── env/                  # dev.yaml / test.yaml / prod.yaml (runtime parameters per environment)
│   └── contract/             # schema.yaml (the data contract: types, required, enums, patterns)
├── data/                     # Per-env storage: {env}/input committed, {env}/output ignored
├── docs/
│   ├── business/             # Project, data, module, interface, glossary, changelog, known issues
│   ├── tables/               # Per-table contracts (one file per table)
│   ├── changes/              # Per-module change logs
│   ├── rules/                # Engineering rules (structure / coding / flow / acceptance)
│   └── archive/              # Superseded documents and the original assessment prompt
├── tests/                    # pytest suite (88 tests)
├── scripts/generate_sample_data.py
├── scripts/check_data.py     # Read-only artefact verifier behind `make check-data`
├── scripts/show_data.py      # Read-only viewer behind `make show-data`
├── scripts/hooks/pre-commit  # Pre-commit gate hook (copy into .git/hooks)
├── scripts/hooks/commit-msg  # Commit-message provenance hook (same install step)
├── Makefile                  # setup / data / run / test / lint / check-data / show-data / clean
├── pyproject.toml            # Single entry for dependencies, packaging and pytest config
├── .gitlab-ci.yml            # CI skeleton: test + lint -> data-quality -> manual promote
├── .gitattributes            # Line-ending policy (md=CRLF, code=LF)
├── .gitignore                # Ignores the virtualenv, run artefacts and caches
├── AGENTS.md                 # AI coding constraints (red lines and conduct)
└── README.md
```

Each environment writes under `data/{env}/`. What you feed in goes to `input/`, which is
committed so a fresh clone runs out of the box. Everything the pipeline writes goes to
`output/`, which is git-ignored and rebuildable: `make clean` then `make run`.


## Pre-commit Gate

The gate script lives in the shared toolchain, so the hook is installed once per clone:

```bash
mkdir -p .git/hooks \
  && cp scripts/hooks/pre-commit .git/hooks/pre-commit \
  && cp scripts/hooks/commit-msg .git/hooks/commit-msg \
  && chmod +x .git/hooks/pre-commit .git/hooks/commit-msg
```

The gate blocks a commit when any of these checks fails:

- credential scan
- forbidden file paths
- oversized files
- test suite
- `AGENTS.md` structure check
- commit-message provenance: an agent-session commit must carry the `[AI]` marker

The test command uses the project venv (`.venv/bin/python -m pytest -q`), so no external interpreter is required.
The hook sources live in `scripts/hooks/`, which keeps them reviewable and reproducible. The
commit-message hook runs `pre_commit_gate.py --commit-msg`; it asks nothing of a human commit.

## Documentation

For architecture, data design, module interfaces, CLI contract, glossary, changelog, and known issues, see the seven business documents:

- [docs/business/PROJECT.md](docs/business/PROJECT.md) - Project overview, technology stack, directory layout, contract summary
- [docs/business/DATA-DESIGN.md](docs/business/DATA-DESIGN.md) - End-to-end data flow, layer schemas, partitioning, reprocessing
- [docs/business/MODULE-DESIGN.md](docs/business/MODULE-DESIGN.md) - Module responsibilities, interface contracts, dependencies
- [docs/business/INTERFACE-DESIGN.md](docs/business/INTERFACE-DESIGN.md) - CLI parameters, input formats, output paths, error envelope, metrics
- [docs/business/DOMAIN-LANGUAGE.md](docs/business/DOMAIN-LANGUAGE.md) - Project glossary
- [docs/business/CHANGELOG.md](docs/business/CHANGELOG.md) - Version-level changes
- [docs/business/KNOWN-ISSUE.md](docs/business/KNOWN-ISSUE.md) - Known pitfalls, design decisions, and rejected alternatives

## Credits

Built by **Rocky** and **Cheese** in collaboration. Rocky owns the requirements,
the design decisions and the review. Cheese is the AI operator responsible for
the implementation, the tests and the documentation.
