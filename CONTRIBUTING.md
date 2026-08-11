# Contributing to Confluence MD

Thanks for helping out! This is a small project with a few firm conventions —
following them keeps the history clean and the tool predictable.

## Workflow: one logical change per PR

`main` moves only through squash-merged pull requests, one **logical change** per PR —
a fix, a dependency bump, a doc edit each get their own. This keeps every change
independently reviewable, bisectable, and revertable.

```bash
git checkout main && git pull
git checkout -b <type>/<short-name>       # e.g. fix/nested-list-rendering
# ...make exactly one change, test it...
git commit -am "Short imperative title"
git push -u origin <type>/<short-name>
gh pr create --base main
```

### Commit / PR message style

- Title: `<type>: short imperative summary`, lowercase after the colon —
  `feat: convert info panels to blockquotes`, `fix: escaped pipes in table
  cells`. Types in use: `feat`, `fix`, `perf`, `refactor`, `docs`, `test`,
  `build`, `chore`.
- Release commits are the exception: `Release x.y.z`, matching the tag.
- Body (when the change needs explaining): plain prose, *what* and *why*, wrapped
  at ~72 columns. The problem first, then the change.

## CI gates

Every PR must pass CI (run the same checks locally before pushing):

```bash
pip install -r src/requirements.txt pytest ruff
ruff check src tests
ruff format --check src tests
python -m pytest tests/
```

Changes to a conversion pipeline need a test in [tests/](tests/) — round-trip
tests live in `tests/test_round_trip.py`. For changes to the subcommands
themselves, also exercise the one you touched against a real Confluence page
(a personal space works well as a sandbox).

## Project rules

1. **Conversion is symmetric.** Every element the Markdown → storage pipeline
   (`md_to_confluence_storage`) learns to produce, the storage → Markdown
   pipeline (`confluence_storage_to_md`) must learn to parse, and vice versa.
   A page should survive a download → upload round trip without losing
   structure.
2. **Document every equivalence.** New conversions get a row or section in
   [docs/conversion.md](docs/conversion.md); anything that cannot round-trip
   goes under its *Known limitations* heading.
3. **Errors exit through `api()`.** Subcommands stay free of try/except
   boilerplate; wrap fallible calls in the `api()` helper so failures print
   one readable `ERROR:` line and exit non-zero.
4. **No new dependencies without discussion.** The four in
   [src/requirements.txt](src/requirements.txt) are the budget; open an issue
   first if a change seems to need a fifth.
