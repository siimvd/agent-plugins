#!/usr/bin/env python3
"""Fetch Yahoo Finance data into the store, via yfinance.

This is the only toolkit script with third-party dependencies, and it is meant
to run under uv rather than the system Python::

    uv run --python 3.12 --with yfinance --with pandas python fetch_yf.py \\
        bars VWCE.DE --period 1y
    uv run --python 3.12 --with yfinance --with pandas python fetch_yf.py \\
        info MSFT

``yfinance`` and ``pandas`` are imported inside the methods that need them, so
``import fetch_yf`` still works on the system Python 3.9 where neither is
installed. That is what lets the tests exercise every code path with a fake
downloader and no network.

Two subcommands:

``bars``
    Daily or intraday OHLCV written through :mod:`store` with ``adjusted:
    true``. Bars come back from ``history(..., auto_adjust=True)``, so closes
    are split- and dividend-adjusted; the sidecar says so, which is what keeps
    a yfinance series from being silently correlated against an unadjusted
    IBKR one.

``info``
    A fixed whitelist of ``Ticker.info`` fields written to
    ``fundamentals/<TICKER>.json``. Yahoo has no fundamentals for UCITS ETFs
    and answers with a 404, which is a normal outcome here, not a failure: the
    file records that and the command exits 0.

Dates
-----
yfinance stamps daily bars at exchange-local midnight in a tz-aware index, so
an Amsterdam session on 2026-09-04 arrives as ``2026-09-04 00:00+02:00``, which
is 2026-09-03T22:00Z. Converting that to a UTC date would file the bar under
the wrong session, so for daily and coarser intervals the date column is the
calendar date of the index. Intraday bars keep their full UTC timestamp
through :func:`store.session_date`, where the resolution matters more than the
session label.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import registry  # noqa: E402
import store  # noqa: E402

SOURCE = "yfinance"

#: yfinance interval name -> store interval name, where the two differ. Any
#: other value is passed through unchanged.
STORE_INTERVALS = {"1wk": "1w", "60m": "1h"}

#: ``Ticker.info`` keys worth keeping. The full dict runs to hundreds of keys
#: including a business summary and an officer roster, which is exactly the
#: kind of payload this plugin exists to keep out of the transcript.
INFO_FIELDS = (
    "shortName",
    "longName",
    "sector",
    "industry",
    "marketCap",
    "currency",
    "trailingPE",
    "forwardPE",
    "dividendYield",
    "fiftyTwoWeekHigh",
    "fiftyTwoWeekLow",
    "sharesOutstanding",
    "quoteType",
    "exchange",
)

NO_FUNDAMENTALS = "no fundamentals data"

FUNDAMENTALS_DIR = "fundamentals"

PRICE_FIELDS = ("open", "high", "low", "close")


class FetchError(Exception):
    """Raised when Yahoo returns nothing usable for a ticker."""


def _utc_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_nan(value):
    """True for a float NaN. NaN is the only value not equal to itself."""
    return isinstance(value, float) and value != value


def _clean(value):
    """Return a float, or None for a missing or NaN cell."""
    if value is None or _is_nan(value):
        return None
    return float(value)


class YahooDownloader:
    """Thin wrapper over ``yfinance.Ticker``, flattening pandas out of the way.

    Every method returns plain Python containers so the rest of the module,
    and the tests, never touch pandas. yfinance is imported per call rather
    than at module scope to keep this file importable without it.
    """

    def history(self, ticker, period, interval):
        """Return the price history as a list of plain row dicts.

        Each row carries ``local_date`` (the exchange-local calendar date of
        the index) and ``epoch`` (the same instant in seconds since the epoch)
        so the caller can pick the right one for the interval.
        """
        import yfinance

        frame = yfinance.Ticker(ticker).history(
            period=period, interval=interval, auto_adjust=True
        )
        if frame is None or len(frame) == 0:
            return []
        rows = []
        for stamp, values in frame.iterrows():
            row = {
                "local_date": stamp.strftime("%Y-%m-%d"),
                "epoch": stamp.timestamp(),
            }
            for name, column in (
                ("open", "Open"),
                ("high", "High"),
                ("low", "Low"),
                ("close", "Close"),
                ("volume", "Volume"),
            ):
                row[name] = values[column] if column in values else None
            rows.append(row)
        return rows

    def fast_info(self, ticker):
        """Return the venue facts we record: currency and exchange."""
        import yfinance

        fast = yfinance.Ticker(ticker).fast_info
        out = {}
        for name in ("currency", "exchange"):
            value = None
            try:
                value = fast[name]
            except Exception:  # noqa: BLE001 - FastInfo raises assorted types
                value = getattr(fast, name, None)
            if value is not None:
                out[name] = value
        return out

    def info(self, ticker):
        """Return the raw ``Ticker.info`` dict."""
        import yfinance

        return yfinance.Ticker(ticker).info or {}


def _default_downloader(downloader):
    return YahooDownloader() if downloader is None else downloader


def store_interval(interval):
    """Map a yfinance interval name onto the store's interval vocabulary."""
    return STORE_INTERVALS.get(interval, interval)


def _bar_rows(raw_rows, interval):
    """Turn downloader rows into store rows, dropping the unusable ones.

    A row with a NaN or missing price is skipped rather than repaired: Yahoo
    emits them for halted sessions and for the current, still-forming bar, and
    an interpolated price would be indistinguishable from a real one later.
    A NaN volume is kept as None, because FX and index series carry no volume
    at all and that is not a reason to lose the bar.
    """
    is_daily = interval in store.DATE_INTERVALS
    rows = []
    for raw in raw_rows:
        prices = dict((name, _clean(raw.get(name))) for name in PRICE_FIELDS)
        if any(prices[name] is None for name in PRICE_FIELDS):
            continue
        if is_daily:
            date = raw["local_date"]
        else:
            date = store.session_date(raw["epoch"], interval)
        row = {"date": date, "volume": _clean(raw.get("volume"))}
        row.update(prices)
        rows.append(row)
    return rows


def normalise_currency(raw):
    """Return ``(iso_code, price_scale)`` for a Yahoo currency label.

    Yahoo quotes most London lines in pence and says so with a case-sensitive
    ``GBp`` (older payloads use ``GBX``). Upper-casing that to ``GBP`` would
    record pounds for prices that are pence, off by a factor of 100 and
    undetectable downstream. So pence is converted at ingest: prices are
    scaled and the store keeps an ISO code, which is what the pair lookups in
    ``fx.py`` expect. The raw label and the factor go into the sidecar as
    ``source_currency`` and ``price_scale``, so the original quote is
    recoverable.
    """
    if not raw:
        return None, 1
    if raw in ("GBp", "GBX"):
        return "GBP", 0.01
    return str(raw).upper(), 1


def _isin_for(ticker):
    """Return the registry's ISIN for this ticker, or None when unknown.

    A miss is normal: store keys are provider-native so that a fetch never
    waits on registry state.
    """
    try:
        return registry.resolve_yahoo(ticker)
    except registry.RegistryError:
        return None


def fetch_bars(ticker, period="1y", interval="1d", downloader=None):
    """Fetch one ticker's bars into the store; return the sidecar written."""
    if not ticker:
        raise FetchError("a ticker is required")
    source = _default_downloader(downloader)

    raw_rows = source.history(ticker, period, interval)
    if not raw_rows:
        raise FetchError(
            "Yahoo returned no bars for %s over period %s at interval %s; "
            "check the ticker and its venue suffix" % (ticker, period, interval)
        )

    resolved = store_interval(interval)
    rows = _bar_rows(raw_rows, resolved)
    if not rows:
        raise FetchError(
            "Yahoo returned %d bars for %s but none carried a usable price"
            % (len(raw_rows), ticker)
        )

    fast = source.fast_info(ticker) or {}
    raw_currency = fast.get("currency")
    exchange = fast.get("exchange")
    currency, scale = normalise_currency(raw_currency)
    if scale != 1:
        for row in rows:
            for field in PRICE_FIELDS:
                row[field] = row[field] * scale
    meta = {
        "symbol": ticker,
        "exchange": str(exchange) if exchange else None,
        "contract_id": None,
        "currency": currency,
        "source_currency": raw_currency if raw_currency is None else str(raw_currency),
        "price_scale": scale,
        "adjusted": True,
        "delayed_sec": 0,
        "price_source": "Close",
        "isin": _isin_for(ticker),
    }
    return store.write_bars(SOURCE, store.key(SOURCE, None, ticker), resolved, rows, meta)


def fundamentals_path(ticker):
    """Return the path of one ticker's fundamentals file in the store."""
    return os.path.join(store.root(), FUNDAMENTALS_DIR, "%s.json" % ticker)


def _write_fundamentals(ticker, payload):
    directory = os.path.join(store.root(), FUNDAMENTALS_DIR)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    with open(fundamentals_path(ticker), "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return payload


def fetch_info(ticker, downloader=None):
    """Fetch and store one ticker's fundamentals; return what was written.

    Yahoo has no fundamentals for UCITS ETFs: ``Ticker.info`` raises a 404
    ("No fundamentals data found") for VWCE.DE and friends, and for some other
    instruments it answers with a dict that carries none of the whitelisted
    keys. Both are recorded as a note rather than raised, because the caller
    asked a reasonable question and the honest answer is that Yahoo has
    nothing.
    """
    if not ticker:
        raise FetchError("a ticker is required")
    source = _default_downloader(downloader)

    try:
        info = source.info(ticker) or {}
    except Exception as exc:  # noqa: BLE001 - yfinance raises assorted types
        return _write_fundamentals(
            ticker,
            {
                "ticker": ticker,
                "fetched_at": _utc_now_iso(),
                "note": NO_FUNDAMENTALS,
                "detail": str(exc)[:200],
            },
        )

    payload = {}
    for field in INFO_FIELDS:
        value = info.get(field)
        if value is not None:
            payload[field] = value
    if not payload:
        return _write_fundamentals(
            ticker,
            {
                "ticker": ticker,
                "fetched_at": _utc_now_iso(),
                "note": NO_FUNDAMENTALS,
            },
        )
    payload["ticker"] = ticker
    payload["fetched_at"] = _utc_now_iso()
    return _write_fundamentals(ticker, payload)


def _print_summary(sidecar):
    fields = (
        ("key", sidecar.get("key")),
        ("interval", sidecar.get("interval")),
        ("bars", sidecar.get("bar_count")),
        ("range", "%s -> %s" % (sidecar.get("start"), sidecar.get("end"))),
        ("currency", sidecar.get("currency")),
        ("adjusted", sidecar.get("adjusted")),
        ("price_source", sidecar.get("price_source")),
        ("isin", sidecar.get("isin")),
    )
    for name, value in fields:
        print("%-14s %s" % (name, "null" if value is None else value))


def _cmd_bars(args, downloader):
    sidecar = fetch_bars(
        args.ticker,
        period=args.period,
        interval=args.interval,
        downloader=downloader,
    )
    if args.json:
        print(json.dumps(sidecar, indent=2, sort_keys=True))
        return 0
    _print_summary(sidecar)
    return 0


def _cmd_info(args, downloader):
    payload = fetch_info(args.ticker, downloader=downloader)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if payload.get("note") == NO_FUNDAMENTALS:
        print(
            "%s: %s from Yahoo (normal for UCITS ETFs); wrote %s"
            % (args.ticker, NO_FUNDAMENTALS, fundamentals_path(args.ticker))
        )
        return 0
    for field in sorted(payload):
        print("%-20s %s" % (field, payload[field]))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="fetch_yf.py",
        description="Fetch Yahoo Finance data into the finance store.",
    )
    sub = parser.add_subparsers(dest="command")

    bars = sub.add_parser("bars", help="fetch OHLCV bars into the store")
    bars.add_argument("ticker", help="Yahoo ticker, e.g. VWCE.DE or MSFT")
    bars.add_argument("--period", default="1y", help="history window (default: 1y)")
    bars.add_argument("--interval", default="1d", help="bar interval (default: 1d)")
    bars.add_argument("--json", action="store_true", help="machine-readable output")
    bars.set_defaults(func=_cmd_bars)

    info = sub.add_parser("info", help="fetch a compact fundamentals dump")
    info.add_argument("ticker", help="Yahoo ticker, e.g. MSFT")
    info.add_argument("--json", action="store_true", help="machine-readable output")
    info.set_defaults(func=_cmd_info)

    return parser


def main(argv=None, downloader=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return 1
    try:
        return args.func(args, downloader)
    except (FetchError, registry.RegistryError, store.StoreError, ValueError) as exc:
        sys.stderr.write("%s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
