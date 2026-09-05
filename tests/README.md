# Tests

## Run all tests

```bash
poetry run pytest
```

## Run a single test file

```bash
poetry run pytest tests/test_cli.py
```

## Run a single test

```bash
poetry run pytest tests/test_cli.py::test_run_imports_app_module_and_loads_config
```

## Verbose output

```bash
poetry run pytest -v
```
