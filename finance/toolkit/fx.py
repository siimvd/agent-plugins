#!/usr/bin/env python3
"""Convert amounts and stored bar series into EUR using stored FX bars.

The reference currency is EUR because the portfolio this toolkit serves is
EUR-based. FX pairs live in the bar store like any other instrument, under a
provider-native key:

* ``ibkr/IDEALPRO_EURUSD`` — the IDEALPRO ``EUR.USD`` cash pair
* ``yfinance/EURUSD=X``    — the same pair from Yahoo

In both, the close is the **quote currency per EUR** (an ``EURUSD`` close of
1.10 means one EUR buys 1.10 USD), so converting an amount denominated in the
quote currency into EUR *divides*::

    amount_eur = amount / rate

Rate selection is deliberately backward-looking: the bar on the requested
session, else the nearest bar **before** it. Never a later bar — using
tomorrow's rate to value today would be a look-ahead, and a series converted
that way would show correlations that were not observable at the time. When
no bar precedes the date at all, that is an error rather than an
extrapolation.

Note that IDEALPRO stamps its daily FX bars at 21:15Z; ``store.session_date``
maps that to the UTC calendar date, so an FX bar lines up with the same-day
equity bar. See the note in ``store.py``.

Usage as a library::

    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    import fx
    rate, used_date, key = fx.rate("USD", "2026-01-05")

Usage as a CLI::

    python3 fx.py convert AMOUNT CCY [--date YYYY-MM-DD]
    python3 fx.py series KEY --to EUR
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import store  # noqa: E402

#: The one currency everything converts to.
BASE_CURRENCY = "EUR"

#: Store key templates tried in order for the ``EUR<CCY>`` pair. IBKR first:
#: it is the venue the portfolio actually trades on.
PAIR_KEY_TEMPLATES = ("IDEALPRO_EUR%s", "EUR%s=X")

#: Interval preferred when a pair is stored at more than one resolution.
PREFERRED_INTERVAL = "1d"

#: Sidecar fields carried across from the source entry to the derived one.
CARRIED_META_FIELDS = (
    "symbol",
    "exchange",
    "contract_id",
    "isin",
    "adjusted",
    "delayed_sec",
    "price_source",
)

#: Price fields converted bar by bar. ``volume`` is a share count, not money.
PRICE_FIELDS = ("open", "high", "low", "close")

KEY_FORM_HELP = "store key, either KEY or source/KEY (e.g. yfinance/VWCE.DE)"


class FxError(Exception):
    """Raised when a rate cannot be established for a currency and date."""


# --------------------------------------------------------------------------
# Rates
# --------------------------------------------------------------------------

def find_pair(ccy):
    """Return the ``(source, key, interval)`` of the ``EUR<CCY>`` entry."""
    upper = ccy.upper()
    candidates = [template % upper for template in PAIR_KEY_TEMPLATES]
    for candidate in candidates:
        matches = store.find_entries(candidate)
        if matches:
            daily = [match for match in matches if match[2] == PREFERRED_INTERVAL]
            return (daily or matches)[0]
    raise FxError(
        "no FX entry for EUR%s in the store; expected one of the keys %s"
        % (upper, " or ".join(candidates))
    )


def load_pair(ccy):
    """Return ``(rows, fx_key)`` for the ``EUR<CCY>`` entry, read once.

    Callers converting many dates should hold onto the rows and feed them to
    :func:`rate_from` rather than calling :func:`rate` per date, which would
    re-list the store and re-parse the whole CSV every time.
    """
    source, key_, interval = find_pair(ccy)
    rows, _ = store.read_bars(source, key_, interval)
    if not rows:
        raise FxError("FX entry %s/%s_%s has no bars" % (source, key_, interval))
    return rows, "%s/%s" % (source, key_)


def rate_from(rows, ccy, date=None):
    """Pick the ``ccy``-per-EUR rate for ``date`` out of already-loaded rows.

    Returns ``(rate, used_date)``: the bar on that session, else the nearest
    one before it. Never a later bar — pricing today with tomorrow's rate is a
    look-ahead, and a series converted that way would show relationships that
    were not observable at the time.
    """
    chosen = None
    for row in rows:  # store rows are ascending by date
        if date is None or row["date"] <= date:
            chosen = row
        else:
            break
    if chosen is None:
        raise FxError(
            "no EUR%s bar on or before %s; the earliest stored bar is %s"
            % (ccy.upper(), date, rows[0]["date"])
        )
    if chosen["close"] is None or chosen["close"] <= 0:
        raise FxError(
            "EUR%s bar on %s has a non-positive close" % (ccy.upper(), chosen["date"])
        )
    return chosen["close"], chosen["date"]


def rate(ccy, date=None):
    """Return ``(rate, used_date, fx_key)`` for converting ``ccy`` into EUR.

    ``rate`` is quote currency per EUR. ``date`` selects the bar on that
    session or the nearest prior one; omit it for the latest stored bar.
    ``ccy`` of ``EUR`` short-circuits to ``1.0`` with no store access, so a
    EUR-denominated caller never needs an FX entry at all.

    This reads the pair from disk on every call. Converting a whole series
    goes through :func:`load_pair` plus :func:`rate_from` instead.
    """
    if ccy and ccy.upper() == BASE_CURRENCY:
        return 1.0, date, None

    rows, fx_key = load_pair(ccy)
    value, used_date = rate_from(rows, ccy, date)
    return value, used_date, fx_key


def to_eur(amount, ccy, date=None):
    """Convert ``amount`` of ``ccy`` into EUR; returns the same triple plus it."""
    value, used_date, fx_key = rate(ccy, date)
    return amount / value, value, used_date, fx_key


# --------------------------------------------------------------------------
# Store access
# --------------------------------------------------------------------------

def resolve_entry(spec, source=None, interval=None):
    """Resolve ``KEY`` or ``source/KEY`` to one ``(source, key, interval)``."""
    if "/" in spec:
        spec_source, _, key_ = spec.partition("/")
        source = spec_source
    else:
        key_ = spec
    matches = store.find_entries(key_, source, interval)
    if not matches:
        raise ValueError("no store entry for key %s" % spec)
    if len(matches) > 1:
        lines = ["ambiguous key %s; qualify it as source/KEY or pass "
                 "--source/--interval. Matches:" % spec]
        lines += ["  %s %s %s" % match for match in matches]
        raise ValueError("\n".join(lines))
    return matches[0]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _kv(field, value):
    print("%-14s %s" % (field, "null" if value is None else value))


def _cmd_convert(args):
    amount_eur, value, used_date, fx_key = to_eur(args.amount, args.ccy, args.date)
    payload = {
        "amount": args.amount,
        "currency": args.ccy.upper(),
        "rate": value,
        "rate_date": used_date,
        "fx_key": fx_key,
        "amount_eur": amount_eur,
        "quote": "%s per EUR" % args.ccy.upper(),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    _kv("amount", "%.4f" % args.amount)
    _kv("currency", payload["currency"])
    _kv("rate", "%.6f (%s)" % (value, payload["quote"]))
    _kv("rate_date", used_date)
    _kv("fx_key", fx_key)
    _kv("amount_eur", "%.4f" % amount_eur)
    return 0


def _cmd_series(args):
    if args.to.upper() != BASE_CURRENCY:
        raise ValueError(
            "--to %s is not supported; this toolkit converts to %s only"
            % (args.to, BASE_CURRENCY)
        )
    source, key_, interval = resolve_entry(args.key, args.source, args.interval)
    rows, meta = store.read_bars(source, key_, interval)
    ccy = meta.get("currency")
    if not ccy:
        raise ValueError(
            "%s/%s_%s has no currency in its sidecar; re-ingest it with the "
            "venue currency before converting" % (source, key_, interval)
        )
    if ccy.upper() == BASE_CURRENCY:
        raise ValueError(
            "%s/%s_%s is already denominated in EUR; nothing to convert"
            % (source, key_, interval)
        )

    # The pair is read once for the whole series; calling rate() per bar would
    # re-list the store and re-parse the FX CSV on every iteration.
    fx_rows, fx_key = load_pair(ccy)
    converted = []
    for row in rows:
        value, _ = rate_from(fx_rows, ccy, row["date"])
        new_row = {"date": row["date"], "volume": row.get("volume")}
        for field in PRICE_FIELDS:
            new_row[field] = row[field] / value
        converted.append(new_row)

    derived_key = "%s_%s" % (key_, BASE_CURRENCY)
    derived_from = "%s/%s_%s" % (source, key_, interval)
    new_meta = dict((field, meta.get(field)) for field in CARRIED_META_FIELDS)
    new_meta["currency"] = BASE_CURRENCY
    new_meta["derived_from"] = derived_from
    new_meta["fx_key"] = fx_key
    sidecar = store.write_bars(source, derived_key, interval, converted, new_meta)

    payload = {
        "key": derived_key,
        "source": source,
        "interval": interval,
        "from_currency": ccy.upper(),
        "to_currency": BASE_CURRENCY,
        "fx_key": fx_key,
        "derived_from": derived_from,
        "bar_count": sidecar["bar_count"],
        "start": sidecar["start"],
        "end": sidecar["end"],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    for field in ("key", "source", "interval", "from_currency", "to_currency",
                  "fx_key", "derived_from", "bar_count", "start", "end"):
        _kv(field, payload[field])
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="fx.py",
        description=(
            "Convert amounts and stored series into EUR using stored FX bars. "
            "Rates are quote currency per EUR and are taken from the requested "
            "session or the nearest prior one, never a later one."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    convert = sub.add_parser("convert", help="convert one amount into EUR")
    convert.add_argument("amount", type=float, metavar="AMOUNT")
    convert.add_argument("ccy", metavar="CCY", help="source currency, e.g. USD")
    convert.add_argument(
        "--date", help="session to price at (default: the latest stored bar)"
    )
    convert.add_argument("--json", action="store_true", help="machine-readable output")
    convert.set_defaults(func=_cmd_convert)

    series = sub.add_parser(
        "series", help="write a EUR-converted copy of a stored bar entry"
    )
    series.add_argument("key", metavar="KEY", help=KEY_FORM_HELP)
    series.add_argument(
        "--to", default=BASE_CURRENCY, help="target currency (EUR only)"
    )
    series.add_argument("--source", help="restrict to one source, e.g. yfinance")
    series.add_argument("--interval", help="restrict to one interval, e.g. 1d")
    series.add_argument("--json", action="store_true", help="machine-readable output")
    series.set_defaults(func=_cmd_series)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return 1
    try:
        return args.func(args)
    except (store.StoreError, FxError, ValueError) as exc:
        sys.stderr.write("%s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
