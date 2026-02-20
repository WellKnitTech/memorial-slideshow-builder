# Project Review: Areas for Improvement

## Executive Summary

This repository has a clear goal (build memorial slideshow videos) and useful shell wrappers, but it is currently in an early/incomplete state.

The highest-impact issue is that the core implementation file (`build_slideshow_kb.py`) is empty, so the documented workflow cannot run yet.

## Priority Findings

### 1) Core functionality is missing (Critical)
- `build_slideshow_kb.py` exists but has no implementation.
- `make.sh` and `sample_run.sh` both depend on CLI arguments that are not currently implemented.
- README feature claims cannot be validated from code.

**Recommendation**
- Implement an MVP CLI first:
  - argument parsing and validation
  - image discovery from `--photos`
  - deterministic ordering
  - simple fixed-duration slideshow render using ffmpeg
  - output path creation and exit codes
- Add one integration test that runs against a tiny fixture set.

### 2) Documentation is incomplete/inconsistent (High)
- README ends in the middle of the installation block and has no usage examples, no expected directory layout, and no troubleshooting.
- No statement of supported Python versions/platforms.

**Recommendation**
- Expand README to include:
  - complete installation instructions
  - required external binaries (`ffmpeg`)
  - minimal “quick start” and example command
  - expected file/folder structure (`photos/`, `audio/`, `out/`)
  - known limitations and roadmap

### 3) Dependency and environment management (High)
- `requirements.txt` only includes Pillow, while advertised features require more (e.g., EXIF handling, hashing logic, media processing integration).
- No lock file, no virtualenv guidance, no reproducibility strategy.

**Recommendation**
- Pin a tested dependency set (or use `pyproject.toml` with exact ranges).
- Add optional dev dependencies for formatting/lint/test.
- Document environment setup (`python -m venv .venv`).

### 4) Testing and quality gates (High)
- No automated tests or CI workflow.
- No static analysis or formatting policy.

**Recommendation**
- Add:
  - unit tests for argument parsing, sorting, dedup logic
  - integration smoke test for rendering a tiny slideshow
  - CI workflow (lint + tests)
  - pre-commit hooks (`ruff`, `black`, `pytest`)

### 5) Error handling and user experience (Medium)
- Expected runtime failures are currently unhandled (missing ffmpeg, unreadable files, invalid audio path).
- No clear logging, progress reporting, or final run summary.

**Recommendation**
- Standardize errors with actionable messages.
- Add structured logging with verbosity levels.
- Print run summary: input count, dedup drops, output duration/path.

### 6) Product-level robustness (Medium)
- Feature set mentions EXIF ordering and near-duplicate removal, which can be edge-case heavy.
- No fallback behavior for missing EXIF or corrupt images is documented.

**Recommendation**
- Define deterministic fallback rules:
  - missing EXIF -> filename/mtime ordering
  - corrupt files -> skip with warning + report
  - unsupported formats -> skip with reason

### 7) Release/readiness gaps (Medium)
- No versioning strategy, changelog, or release notes.
- No license file.

**Recommendation**
- Add `LICENSE`, semantic versioning, and `CHANGELOG.md`.
- Create release checklist (tests pass, sample output verified).

## Suggested 2-Week Execution Plan

### Week 1 (Foundation)
1. Implement CLI MVP and ffmpeg slideshow generation.
2. Complete README with runnable quick start.
3. Add unit tests for CLI and file ordering.

### Week 2 (Quality + features)
1. Implement exact and near-duplicate filtering.
2. Add EXIF-aware ordering with fallback logic.
3. Add CI + lint/format checks.
4. Add integration test and sample fixtures.

## “Definition of Done” for MVP

- Command in `make.sh` runs successfully on a sample folder.
- Produces a 1080p MP4 with per-slide duration + fade.
- Non-zero exit codes on invalid inputs.
- README quick-start works from a clean machine.
- CI passes tests on every push.
