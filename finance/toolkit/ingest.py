#!/usr/bin/env python3
"""Convert a raw IBKR ``get_price_history`` response into a store entry.

Only the model can call the IBKR MCP server, so the IBKR path is: the model
fetches, saves the tool result verbatim to a JSON file, and runs this script.
Nothing here talks to a network.

The raw response is parallel arrays::

    {"chart_step": 86400, "delayed": 900, "source": "Last",
     "time": ["2026-08-27T07:00:00Z", ...] | [1756278000, ...],
     "open": [...], "high": [...], "low": [...], "close": [...],
     "volume": [...]}

``delayed`` is absent on live (US) data and means zero seconds of delay when
absent; ``volume`` is absent on FX, where ``source`` is ``MidPoint`` rather
than ``Last``; ``time[]`` is ISO 8601 in the responses seen so far but epoch
seconds is accepted too, because the field has been observed both ways.

``chart_step`` is the bar width in seconds and names the interval when
``--interval`` is not given (see :data:`STEP_INTERVALS`). An unrecognised step
with no ``--interval`` is an error rather than a guess: writing a mislabelled
interval would silently corrupt every later alignment.

This is a system boundary, so the whole response is validated before anything
is written — array lengths, presence of the required series, timestamps and
prices. A rejected response leaves no partial entry behind.

``adjusted`` defaults to None (unknown). Whether IBKR closes are split- and
dividend-adjusted is an empirical question answered in Task 8 and recorded in
the ``ibkr-data`` skill's ``references/quirks.md``; until then the sidecar says
"unknown" rather than asserting either way, and ``--adjusted`` overrides it.

Usage as a library::

    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    import ingest
    sidecar = ingest.ingest_ibkr_history(raw, "VWCE", "IBIS2", "EUR")

Usage as a CLI::

    python3 ingest.py ibkr-history RAW.json --symbol SYM --exchange EXCH
                      --currency CCY [--interval 1d] [--contract-id N]
                      [--adjusted true|false|null] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import registry  # noqa: E402
import store  # noqa: E402

SOURCE = "ibkr"

#: Bar width in seconds -> interval name. IBKR reports the width as
#: ``chart_step``; ``2678400`` is 31 days, which is how IBKR expresses a
#: monthly bar.
STEP_INTERVALS = {
    60: "1m",
    300: "5m",
    900: "15m",
    1800: "30m",
    3600: "1h",
    86400: "1d",
    604800: "1w",
    2678400: "1mo",
}

#: Series that must be present; ``volume`` is optional (FX carries none).
REQUIRED_SERIES = ("time", "open", "high", "low", "close")

_ADJUSTED_VALUES = {"true": True, "false": False, "null": None}


class IngestError(Exception):
    """Raised when a raw response cannot be turned into a store entry."""


def interval_for_step(step):
    """Return the interval name for a ``chart_step``, or None when unknown."""
    try:
        return STEP_INTERVALS.get(int(step))
    except (TypeError, ValueError):
        return None


def _series(raw, name, required):
    """Return one array from the response, checked for shape."""
    if name not in raw:
        if required:
            raise IngestError("raw response has no %r array" % name)
        return None
    value = raw[name]
    if value is None:
        if required:
            raise IngestError("raw response has no %r array" % name)
        return None
    if not isinstance(value, list):
        raise IngestError("raw response field %r is not an array" % name)
    return value


def _number(value, name, index):
    """Coerce one price or volume cell to float, or raise IngestError."""
    if isinstance(value, bool) or value is None:
        raise IngestError("%s[%d] is not a number: %r" % (name, index, value))
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        raise IngestError("%s[%d] is not a number: %r" % (name, index, value))


def _rows(raw, interval):
    """Validate every series and build the store rows. Writes nothing."""
    series = {}
    for name in REQUIRED_SERIES:
        series[name] = _series(raw, name, required=True)
    volume = _series(raw, "volume", required=False)

    count = len(series["time"])
    if count == 0:
        raise IngestError("raw response has an empty time series")
    for name in REQUIRED_SERIES:
        if len(series[name]) != count:
            raise IngestError(
                "raw response array %r has %d entries, expected %d to match "
                "time[]" % (name, len(series[name]), count)
            )
    if volume is not None and len(volume) != count:
        raise IngestError(
            "raw response array 'volume' has %d entries, expected %d to match "
            "time[]" % (len(volume), count)
        )

    rows = []
    for index in range(count):
        try:
            date = store.session_date(series["time"][index], interval)
        except ValueError as exc:
            raise IngestError("time[%d]: %s" % (index, exc))
        row = {"date": date}
        for name in ("open", "high", "low", "close"):
            row[name] = _number(series[name][index], name, index)
        if volume is None or volume[index] is None:
            row["volume"] = None
        else:
            row["volume"] = _number(volume[index], "volume", index)
        rows.append(row)
    return rows


def _isin_for(exchange, symbol):
    """Return the registry's ISIN for this listing, or None when unknown.

    A registry miss is normal — bars are keyed provider-natively precisely so
    that ingest never has to wait on registry state — so it is not an error.
    """
    try:
        return registry.resolve_ibkr(exchange, symbol)
    except registry.RegistryError:
        return None


def ingest_ibkr_history(
    raw,
    symbol,
    exchange,
    currency,
    interval=None,
    contract_id=None,
    adjusted=None,
):
    """Write one IBKR history response to the store; return its sidecar.

    ``interval`` overrides the interval derived from ``chart_step``. ``raw`` is
    not modified. Raises :class:`IngestError` for any malformed response, and
    writes nothing when it does.
    """
    if not isinstance(raw, dict):
        raise IngestError("raw response must be a JSON object")
    if not symbol:
        raise IngestError("--symbol is required")
    if not exchange:
        raise IngestError("--exchange is required")
    if not currency:
        raise IngestError("--currency is required")

    resolved = interval
    if not resolved:
        resolved = interval_for_step(raw.get("chart_step"))
        if not resolved:
            raise IngestError(
                "cannot derive an interval from chart_step %r; pass --interval"
                % (raw.get("chart_step"),)
            )

    rows = _rows(raw, resolved)

    exchange_up = str(exchange).upper()
    delayed = raw.get("delayed")
    try:
        delayed_sec = 0 if delayed is None else int(delayed)
    except (TypeError, ValueError):
        raise IngestError("raw response field 'delayed' is not a number: %r" % (delayed,))

    meta = {
        "symbol": symbol,
        "exchange": exchange_up,
        "contract_id": contract_id,
        "currency": str(currency).upper(),
        "adjusted": adjusted,
        "delayed_sec": delayed_sec,
        "price_source": raw.get("source"),
        "isin": _isin_for(exchange_up, symbol),
    }
    key = store.key(SOURCE, exchange_up, symbol)
    return store.write_bars(SOURCE, key, resolved, rows, meta)


def _load_raw(path):
    try:
        with open(path) as handle:
            return json.load(handle)
    except IOError as exc:
        raise IngestError("cannot read %s: %s" % (path, exc.strerror or exc))
    except ValueError as exc:
        raise IngestError("malformed JSON in %s: %s" % (path, exc))


def _print_summary(sidecar):
    fields = (
        ("key", sidecar.get("key")),
        ("interval", sidecar.get("interval")),
        ("bars", sidecar.get("bar_count")),
        ("range", "%s -> %s" % (sidecar.get("start"), sidecar.get("end"))),
        ("delayed_sec", sidecar.get("delayed_sec")),
        ("price_source", sidecar.get("price_source")),
        ("adjusted", sidecar.get("adjusted")),
        ("isin", sidecar.get("isin")),
    )
    for name, value in fields:
        print("%-14s %s" % (name, "null" if value is None else value))


def _cmd_ibkr_history(args):
    sidecar = ingest_ibkr_history(
        _load_raw(args.raw),
        symbol=args.symbol,
        exchange=args.exchange,
        currency=args.currency,
        interval=args.interval,
        contract_id=args.contract_id,
        adjusted=_ADJUSTED_VALUES[args.adjusted],
    )
    if args.json:
        print(json.dumps(sidecar, indent=2, sort_keys=True))
        return 0
    _print_summary(sidecar)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ingest.py",
        description="Ingest raw provider responses into the finance store.",
    )
    sub = parser.add_subparsers(dest="command")

    history = sub.add_parser(
        "ibkr-history", help="ingest a saved IBKR get_price_history response"
    )
    history.add_argument("raw", help="path to the saved JSON response")
    history.add_argument("--symbol", required=True, help="instrument symbol, e.g. VWCE")
    history.add_argument(
        "--exchange", required=True, help="IBKR exchange, e.g. IBIS2"
    )
    history.add_argument(
        "--currency", required=True, help="trading currency of this listing"
    )
    history.add_argument(
        "--interval",
        help="interval name; derived from chart_step when omitted",
    )
    history.add_argument(
        "--contract-id", type=int, dest="contract_id", help="IBKR contract id"
    )
    history.add_argument(
        "--adjusted",
        choices=sorted(_ADJUSTED_VALUES),
        default="null",
        help="whether closes are split/dividend adjusted (default: null)",
    )
    history.add_argument("--json", action="store_true", help="machine-readable output")
    history.set_defaults(func=_cmd_ibkr_history)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return 1
    try:
        return args.func(args)
    except (IngestError, registry.RegistryError, store.StoreError, ValueError) as exc:
        sys.stderr.write("%s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
