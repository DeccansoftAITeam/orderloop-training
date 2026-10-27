# Legacy: nightly settlement job (Python 2)

`settle.py` (with `money.py` and `loader.py`) is the nightly settlement job for the marketplace merchants. It was written for Python 2.7 in 2014 and has run on one old server ever since. That server is being retired, so the job must run on Python 3.12 or later with **exactly the same output**.

Run it (on the old server, with Python 2.7):

```text
python2 settle.py 2030-03-01 data
```

It prints the report on standard output (UTF-8) and warnings on standard error.

| Path | What it is |
|---|---|
| `settle.py`, `money.py`, `loader.py` | The job. Python 2 only: it does not even parse on Python 3 |
| `data/` | A small synthetic data set: merchants, orders and refunds |
| `golden/` | The reports the job printed on the old server for two run dates. Treat them as the truth |
| `tests/` | Yours: characterization tests (Lab 15) |

All data is synthetic. Money is integer cents.
