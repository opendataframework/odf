# 03 — Data Science

The project shape `odf init --template data-science` scaffolds: `data/raw/`
holds source data exactly as it arrived, `data/processed/` holds anything
derived from it, and `notebooks/` is where that derivation happens
interactively — outside the running app entirely.

`main.py` does the one thing that needs a `Server`: loading
`data/raw/readings.csv` into the `Readings` repository via normal DI.
`notebooks/explore.ipynb` picks up from there and reads `app.db` directly,
without a `Server`. `@Repository` (an `opendataframework` decorator)
returns the class unchanged, so nothing stops you from instantiating it by
hand with its dependencies built yourself, which is exactly what a
notebook kernel needs.

## Structure

```
03-data-science/
├── config.toml            # SQLite path
├── main.py                 # entry point — loads data/raw/readings.csv into app.db
├── app/
│   ├── __init__.py         # imports all modules so decorators register at startup
│   ├── entities.py         # Reading — @Entity @dataclass
│   ├── storages.py          # SQLite — @Storage @Component
│   └── repositories.py     # Readings — @Storage @Repository(Reading)
├── data/
│   ├── raw/readings.csv    # source data, never edited in place
│   └── processed/          # written by the notebook, not checked in
└── notebooks/
    └── explore.ipynb       # standalone Readings access; writes data/processed/summary.csv
```

## Run it

```bash
cd examples/03-data-science
python main.py
```

```
loaded 5 reading(s) from data/raw/readings.csv into app.db
Now open notebooks/explore.ipynb to explore app.db standalone.
```

Then open the notebook (requires Jupyter — install with the `examples`
extra, `pip install odf[examples]`, or `poetry install` in this repo,
which pulls it in via the `dev` dependency group) from inside this
directory:

```bash
jupyter notebook notebooks/explore.ipynb
```

It reads `app.db` through `Readings`, built standalone rather than through
`server.context.get(...)`, and writes `data/processed/summary.csv` with the
average `celsius` per `sensor`.

Or start the dev UI to browse `Readings` directly — there's no Task to
execute here, just a repository to inspect:

```bash
odf run
```
