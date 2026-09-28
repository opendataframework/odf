# CONTRIBUTING

## Development setup

```bash
poetry install
pipx install pre-commit
pre-commit install
pre-commit run --all-files  # run all hooks on demand, without committing
```

## Commit messages

Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
prefixed with a [gitmoji](https://gitmoji.dev/):

```
<gitmoji> <type>[(scope)][!]: <description>

[optional body — the *why*, not the *what*]
```

Common types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `build`.
Append `!` after the type/scope for a breaking change. Keep the
description short and in the imperative mood ("add", not "added").

Commit messages must not mention AI tools or models (no "Generated with
…" lines, no `Co-Authored-By` trailers for them) and must not contain
external links.

Example:

```
:bug: fix(deps): mark docs dependency group optional

A plain `poetry install`/`poetry sync` was pulling in the whole `docs`
group (mkdocs-material, requests, watchdog, ...) by default since
nothing marked it non-default, contradicting the zero-runtime-deps
guarantee and the documented `poetry install --with docs` opt-in.
```
