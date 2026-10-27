#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""CSV loading for the nightly settlement. Input files are UTF-8."""

import csv
import string
import sys


def to_text(value):
    """Return unicode text for a str (UTF-8 bytes) or unicode value."""
    if isinstance(value, basestring):
        if isinstance(value, unicode):
            return value
        return value.decode('utf-8')
    return unicode(value)


def load_merchants(path):
    """Return {merchant id: merchant dict}. A blank tier means 'not rated yet' and becomes None."""
    merchants = {}
    f = open(path, 'rb')
    try:
        for row in csv.DictReader(f):
            tier = row['tier']
            if tier == '':
                tier = None
            else:
                tier = int(tier)
            merchants[row['id']] = {
                'id': row['id'],
                'name': to_text(row['name']),
                'tier': tier,
                'fee_bps': int(row['fee_bps']),
            }
    finally:
        f.close()
    return merchants


def load_orders(path):
    """Return (orders, bad_lines). A row with a bad amount is skipped and its line number is kept."""
    orders = []
    bad = []
    f = open(path, 'rb')
    reader = csv.DictReader(f)
    for row in reader:
        try:
            orders.append({
                'id': row['order_id'],
                'merchant_id': row['merchant_id'],
                'date': row['date'],
                'amount': int(row['amount_cents']),
                'status': string.upper(row['status']),
            })
        except ValueError, e:
            bad.append(reader.line_num)
            print >>sys.stderr, 'skipped orders line %d: %s' % (reader.line_num, e)
    f.close()
    return orders, bad


def load_refunds(path):
    """Return (refunds, bad_lines), like load_orders."""
    refunds = []
    bad = []
    f = open(path, 'rb')
    reader = csv.DictReader(f)
    for row in reader:
        try:
            refunds.append({
                'id': row['refund_id'],
                'order_id': row['order_id'],
                'amount': int(row['amount_cents']),
                'date': row['date'],
            })
        except ValueError, e:
            bad.append(reader.line_num)
            print >>sys.stderr, 'skipped refunds line %d: %s' % (reader.line_num, e)
    f.close()
    return refunds, bad
