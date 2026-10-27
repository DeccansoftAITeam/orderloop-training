#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Money helpers for the nightly settlement. All amounts are integer cents.

Written for Python 2.7 in 2014. Do not run on Python 3 (see legacy/README.md).
"""

import string

FEE_DENOMINATOR = 10000L


def fee_for_order(amount_cents, fee_bps):
    """Fee on one order in whole cents, rounded down. fee_bps = basis points (250 = 2.5%)."""
    return int(amount_cents * fee_bps / FEE_DENOMINATOR)


def split_fee(fee_cents):
    """The partner's half of a fee. With an odd number of cents the partner gets the extra cent."""
    return int(round(fee_cents / 2.0))


def whole_units(cents):
    """Whole currency units, rounded down (toward minus infinity), also for negative amounts."""
    return cents / 100


def fmt_money(cents):
    """Format cents as 1,234.56 (a leading minus for negative amounts)."""
    sign = ''
    if cents < 0:
        sign = '-'
        cents = -cents
    units = cents / 100
    rest = cents % 100
    digits = `units`
    groups = []
    while len(digits) > 3:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    groups.insert(0, digits)
    return sign + string.join(groups, ',') + '.' + '%02d' % rest
