#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Nightly settlement for Kestrel Outfitters' marketplace merchants.

Usage:  python2 settle.py YYYY-MM-DD DATA_DIR

Reads merchants.csv, orders.csv and refunds.csv from DATA_DIR and prints the settlement
report on standard output (UTF-8, one report per run date). Warnings go to standard error.
Only rows dated on or before the run date count.
"""

import os
import string
import sys

import loader
import money


class Line:
    """One merchant's settlement line."""

    def __init__(self, merchant):
        self.merchant = merchant
        self.orders = 0
        self.gross = 0
        self.refunds = 0
        self.fee = 0
        self.partner = 0

    def net(self):
        return self.gross - self.refunds - self.fee

    def __cmp__(self, other):
        # Report order: unrated merchants (tier None) first, then by tier,
        # then higher net first, then by merchant id.
        return (cmp(self.merchant['tier'], other.merchant['tier'])
                or cmp(other.net(), self.net())
                or cmp(self.merchant['id'], other.merchant['id']))


def settle(run_date, data_dir):
    merchants = loader.load_merchants(os.path.join(data_dir, 'merchants.csv'))
    orders, bad_orders = loader.load_orders(os.path.join(data_dir, 'orders.csv'))
    refunds, bad_refunds = loader.load_refunds(os.path.join(data_dir, 'refunds.csv'))

    lines = {}
    for mid, merchant in merchants.iteritems():
        lines[mid] = Line(merchant)

    paid = {}
    future = 0
    cancelled = 0
    unknown_merchant = 0
    smallest = sys.maxint
    for o in orders:
        if o['date'] > run_date:
            future += 1
            continue
        if o['status'] == 'CANCELLED':
            cancelled += 1
            continue
        if not merchants.has_key(o['merchant_id']):
            unknown_merchant += 1
            continue
        line = lines[o['merchant_id']]
        line.orders += 1
        line.gross += o['amount']
        line.fee += money.fee_for_order(o['amount'], line.merchant['fee_bps'])
        paid[o['id']] = o
        if o['amount'] < smallest:
            smallest = o['amount']

    orphans = []
    for r in refunds:
        if r['date'] > run_date:
            continue
        if not paid.has_key(r['order_id']):
            orphans.append(r)
            continue
        lines[paid[r['order_id']]['merchant_id']].refunds += r['amount']

    for line in lines.itervalues():
        line.partner = money.split_fee(line.fee)

    ordered = lines.values()
    ordered.sort()

    print 'Nightly settlement for ' + run_date
    print '=' * 78
    print u'%-16s %4s %6s %12s %10s %9s %12s %6s' % (
        u'Merchant', u'Tier', u'Orders', u'Gross', u'Refunds', u'Fee', u'Net', u'Units')
    for line in ordered:
        tier = line.merchant['tier']
        if tier is None:
            tier_text = '-'
        else:
            tier_text = `tier`
        row = u'%-16s %4s %6d %12s %10s %9s %12s %6d' % (
            line.merchant['name'][:16], tier_text, line.orders,
            money.fmt_money(line.gross), money.fmt_money(line.refunds),
            money.fmt_money(line.fee), money.fmt_money(line.net()),
            money.whole_units(line.net()))
        print row.encode('utf-8')
    print '-' * 78

    total_orders = reduce(lambda a, b: a + b, map(lambda l: l.orders, ordered), 0)
    total_gross = reduce(lambda a, b: a + b, map(lambda l: l.gross, ordered), 0)
    total_refunds = sum(map(lambda l: l.refunds, ordered))
    total_fee = sum(map(lambda l: l.fee, ordered))
    total_partner = sum(map(lambda l: l.partner, ordered))
    total_net = total_gross - total_refunds - total_fee

    print 'Totals: orders=%d gross=%s refunds=%s fee=%s net=%s' % (
        total_orders, money.fmt_money(total_gross), money.fmt_money(total_refunds),
        money.fmt_money(total_fee), money.fmt_money(total_net))
    print 'Partner share of fees: ' + money.fmt_money(total_partner)
    ratio = total_refunds * 1000 / total_gross
    print 'Refund ratio: %d.%d%%' % (ratio / 10, ratio % 10)
    print 'Average order (cents):', total_gross / total_orders
    print 'Smallest order: ' + money.fmt_money(smallest)
    print 'First line:', map(lambda l: l.merchant['id'], ordered)[0]
    print 'Merchants we pay: %d' % len(filter(lambda l: l.net() > 0, ordered))
    print 'Merchants who owe us: %d' % len(filter(lambda l: l.net() < 0, ordered))
    print 'Ignored:',
    print 'future=%d' % future,
    print 'cancelled=%d' % cancelled,
    print 'unknown_merchant=%d' % unknown_merchant
    print 'Rows skipped:',
    print 'orders=%d' % len(bad_orders),
    print 'refunds=%d' % len(bad_refunds)
    if orphans:
        ids = map(lambda r: r['id'], orphans)
        ids.sort()
        print 'Orphan refunds: ' + string.join(ids, ' ')
    else:
        print 'Orphan refunds: none'


def main(argv):
    if len(argv) <> 3:
        print >>sys.stderr, 'usage: settle.py YYYY-MM-DD DATA_DIR'
        return 2
    try:
        if len(argv[1]) <> 10:
            raise ValueError, 'run date must look like 2030-03-01'
        settle(argv[1], argv[2])
    except ValueError, e:
        print >>sys.stderr, 'settle: %s' % e
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
