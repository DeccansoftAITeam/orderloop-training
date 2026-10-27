# Migration note: nightly settlement, Python 2 to Python 3

## Risk tier

Tier: high
Why: the job moves money out to merchants; a one-cent difference is a wrong payout, and nobody on the team has read the code since 2014.

## Steps taken

1. Tagged the last Python 2 version as `settle-py2-last`.
2. Wrote characterization tests from the golden reports and the Python 2 rules (they failed: the job did not parse).
3. Migrated `money.py`, then `loader.py`, then `settle.py`, one commit each, running the tests after each.

## Python 2 behaviour that had to be kept on purpose

- `/` on integers was floor division (`//`), also for negative amounts.
- `round()` rounded halves away from zero; the partner share uses decimal `ROUND_HALF_UP`.
- `None` sorted before numbers; the sort key now says so.
- Names are padded and cut by characters, and the report is written as UTF-8 with `\n` line ends.

## Evidence

Both golden reports (2030-02-15 and 2030-03-01) are reproduced byte for byte, and a third run date (2030-02-28) matches an independent calculation of the rows and totals. Next step before go-live: run both versions side by side on one real night of data and diff the output.

## Rollback

If the Python 3 job prints a different number, stop it and run the tagged version on the old server: `git checkout settle-py2-last -- legacy`. Keep the old server until two clean nights have passed.
