"""Golden-master tests: the job must print exactly what the old server printed."""

import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
DATES = ["2030-02-15", "2030-03-01"]


def run(date: str) -> str:
    done = subprocess.run([sys.executable, str(HERE / "settle.py"), date, str(HERE / "data")],
                          capture_output=True, timeout=60)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    return done.stdout.replace(b"\r\n", b"\n").decode("utf-8")


@pytest.mark.parametrize("date", DATES)
def test_report_equals_golden(date):
    golden = (HERE / "golden" / f"settlement_{date}.txt").read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
    assert run(date) == golden


def test_unrated_merchant_sorts_first():
    # Python 2 sorted None before every number.
    assert "First line: M04" in run("2030-03-01").splitlines()


def test_negative_net_uses_floor_for_units():
    row = next(ln for ln in run("2030-03-01").splitlines() if ln.startswith("Nordic Trail Co"))
    assert row.split()[-2:] == ["-2.25", "-3"]


def test_non_ascii_names_are_padded_by_characters():
    out = run("2030-03-01")
    assert "Łódź Camping    " in out and "Café Müller     " in out


def test_bad_rows_future_rows_and_orphans_are_reported():
    lines = run("2030-03-01").splitlines()
    assert "Rows skipped: orders=1 refunds=1" in lines
    assert "Ignored: future=2 cancelled=1 unknown_merchant=1" in lines
    assert "Orphan refunds: R2005 R2006" in lines
