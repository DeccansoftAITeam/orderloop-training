"""Characterization tests for money.py: what the Python 2 version did, written before the migration.

Expected values come from the golden reports and from Python 2 rules (floor division,
round() half away from zero), not from running the new code.
"""

import pytest

import money


@pytest.mark.parametrize("amount, bps, expected", [
    (12999, 250, 324),   # 324.975 rounds down
    (4550, 250, 113),    # 113.75 rounds down
    (23999, 250, 599),
    (1, 250, 0),
])
def test_fee_is_rounded_down_per_order(amount, bps, expected):
    assert money.fee_for_order(amount, bps) == expected


@pytest.mark.parametrize("fee, expected", [(25, 13), (24, 12), (7, 4), (1, 1), (0, 0)])
def test_partner_gets_the_extra_cent(fee, expected):
    # Python 2 round(12.5 / ...) went away from zero: 25 cents splits 13 / 12.
    assert money.split_fee(fee) == expected


@pytest.mark.parametrize("cents, expected", [(225, 2), (99, 0), (-200, -2), (-225, -3), (-1, -1)])
def test_whole_units_round_toward_minus_infinity(cents, expected):
    assert money.whole_units(cents) == expected


@pytest.mark.parametrize("cents, text", [
    (0, "0.00"), (5, "0.05"), (-5, "-0.05"), (-213, "-2.13"),
    (100000, "1,000.00"), (123456789, "1,234,567.89"),
])
def test_money_format(cents, text):
    assert money.fmt_money(cents) == text
