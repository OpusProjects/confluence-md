<!--
One logical change per PR (see CONTRIBUTING.md). Describe the problem first,
then the change. Delete sections that don't apply.
-->

## Problem

What's wrong or missing today?

## Change

What this PR does, and why this approach.

## Compatibility

Any behavior change for the CLI or the conversion output? Note breaking
changes here (and add a CHANGELOG entry under `Unreleased`).

## Checklist

- [ ] `ruff check src tests`, `ruff format --check src tests`, `python -m pytest tests/` pass locally
- [ ] Tests added or updated for the change
- [ ] Docs updated (`README.md` or `docs/`) if behavior changed
- [ ] `docs/conversion.md` updated if a conversion equivalence changed
- [ ] `CHANGELOG.md` updated under `Unreleased` if user-facing
