#!/usr/bin/env python3
"""On-disk store for price bars and their sidecar metadata.

Layout, rooted at ``$FINANCE_STORE`` if set, else ``~/.finance``::

    bars/<source>/<KEY>_<interval>.csv        header date,open,high,low,close,volume
    bars/<source>/<KEY>_<interval>.meta.json  sidecar, schema_version 1

``<source>`` is the provider (``ibkr``, ``yfinance``). ``<KEY>`` is provider
native: ``<EXCHANGE>_<SYMBOL>`` for IBKR (``IBIS2_VWCE``), the raw ticker for
yfinance (``VWCE.DE``). Keys are provider native rather than ISIN so that
ingest never has to wait on registry state; the ISIN, when known, is recorded
in the sidecar.

Session dates
-------------
``session_date`` maps a bar timestamp to the ``date`` column. For ``1d``,
``1w`` and ``1mo`` the value is the **UTC calendar date** of the bar
timestamp; for intraday intervals (``1h``, ``5m``, ...) it is the full ISO
8601 UTC datetime, so intraday resolution is not thrown away.

This has a consequence worth stating plainly: a venue that stamps its daily
close after midnight in its own local time still lands on the UTC date of that
timestamp. IDEALPRO FX daily bars are stamped 21:15Z, which is 00:15 the next
day in Tallinn — so such a bar carries the *prior* calendar day as its session
date relative to local reckoning. Equity venues stamp mid-session (13:30Z for
US, 07:00Z for European opens), so they are unaffected.

``returns.py`` aligns series on this ``date`` field with an inner join, so the
rule only has to be consistent, not locale-correct: every source that runs
through this module gets the same UTC-date treatment, and a same-day FX bar
lines up with the same-day equity bar.

Usage as a library::

    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    import store

Usage as a CLI::

    python3 store.py list [--source S] [--json]
    python3 store.py show KEY [--source S] [--interval I] [--json]

``show`` prints the sidecar only — never bar rows.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import re
import sys

SCHEMA_VERSION = 1

CSV_HEADER = ["date", "open", "high", "low", "close", "volume"]

#: Intervals whose session date is a plain calendar date.
DATE_INTERVALS = ("1d", "1w", "1mo")

#: Sidecar fields a caller may supply; each defaults to None when omitted.
OPTIONAL_META_FIELDS = (
    "symbol",
    "exchange",
    "contract_id",
    "isin",
    "currency",
    "adjusted",
    "delayed_sec",
    "price_source",
)

_META_SUFFIX = ".meta.json"

#: Longest accepted store key or interval, in characters.
MAX_COMPONENT_LEN = 64

#: Longest accepted source name, in characters. A source is a short provider
#: identifier, not an instrument identifier, so it gets a tighter bound.
MAX_SOURCE_LEN = 32

#: A store key must look like a real instrument identifier. Yahoo tickers use
#: ``.``, ``-``, ``=`` and a leading ``^`` (``VWCE.DE``, ``LIFCO-B.ST``,
#: ``EURUSD=X``, ``^GSPC``); IBKR keys use ``_`` (``IBIS2_VWCE``). Everything
#: else - separators, a leading dot, anything non-ASCII - is rejected, so no
#: key can steer a write out of the store root.
_KEY_RE = re.compile(r"[A-Za-z0-9^][A-Za-z0-9._=^-]*\Z")

#: An interval is a count plus a unit: 5m, 1h, 1d, 1w, 1wk, 1mo.
_INTERVAL_RE = re.compile(r"[0-9]+(m|h|d|w|mo|wk)\Z")

#: A source is a short provider identifier (``ibkr``, ``yfinance``). It names a
#: directory under ``bars/``, so it is held to the same allowlist as a key: no
#: separators, no leading dot, ASCII alphanumerics plus ``_`` and ``-``.
_SOURCE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")


class StoreError(Exception):
    """Raised when a store entry is missing or malformed."""


def _check_component(value, label, pattern, max_len=MAX_COMPONENT_LEN):
    """Raise StoreError unless ``value`` is safe to join into a store path."""
    if not isinstance(value, str) or not value:
        raise StoreError("%s must be a non-empty string, got %r" % (label, value))
    if len(value) > max_len:
        raise StoreError(
            "%s is longer than %d characters: %r" % (label, max_len, value[:80])
        )
    if "/" in value or "\\" in value or "\0" in value or ".." in value:
        raise StoreError("%s contains a path separator or '..': %r" % (label, value))
    if not pattern.match(value):
        raise StoreError("%s is not a valid store path component: %r" % (label, value))
    return value


def validate_key(key_):
    """Return ``key_`` if it is a safe store key; raise StoreError otherwise."""
    return _check_component(key_, "store key", _KEY_RE)


def validate_interval(interval):
    """Return ``interval`` if it is a safe interval name; else raise StoreError."""
    return _check_component(interval, "interval", _INTERVAL_RE)


def validate_source(source):
    """Return ``source`` if it is a safe source name; raise StoreError otherwise."""
    return _check_component(source, "source", _SOURCE_RE, MAX_SOURCE_LEN)


def assert_inside_root(path):
    """Raise StoreError unless ``path`` resolves inside the store root."""
    resolved = os.path.realpath(path)
    base = os.path.realpath(root())
    if resolved != base and not resolved.startswith(base + os.sep):
        raise StoreError("refusing a path outside the store root: %s" % (path,))
    return path


def root():
    """Return the store root directory. Not created here; writes create it."""
    value = os.environ.get("FINANCE_STORE")
    if not value:
        value = os.path.join("~", ".finance")
    return os.path.abspath(os.path.expanduser(os.path.expandvars(value)))


def bars_dir(source):
    """Return the directory holding one source's bar files."""
    return os.path.join(root(), "bars", source)


def paths(source, key_, interval):
    """Return ``(csv_path, meta_path)`` for one entry.

    Every read and write funnels through here, so the source, key and interval
    are validated and the result is checked against the store root: a traversing
    component raises :class:`StoreError` instead of reaching the disk. The
    source is checked too, not only the two path-escaping components: a source
    of ``../s`` resolves *inside* the root but outside ``bars/<source>/``, which
    ``assert_inside_root`` alone would let through.
    """
    validate_source(source)
    validate_key(key_)
    validate_interval(interval)
    base = os.path.join(bars_dir(source), "%s_%s" % (key_, interval))
    csv_path, meta_path = base + ".csv", base + _META_SUFFIX
    assert_inside_root(csv_path)
    assert_inside_root(meta_path)
    return csv_path, meta_path


def key(source, exchange, symbol):
    """Build the store key for a provider's instrument.

    IBKR keys are ``<EXCHANGE>_<SYMBOL>`` upper-cased; yfinance keys are the
    raw ticker, which is already venue-qualified (``VWCE.DE``, ``EURUSD=X``).
    """
    if not symbol:
        raise ValueError("symbol is required to build a store key")
    if source == "yfinance":
        return symbol
    if exchange:
        return ("%s_%s" % (exchange, symbol)).upper()
    return symbol.upper()


def _to_utc(value):
    """Coerce epoch seconds or an ISO 8601 string to an aware UTC datetime."""
    if isinstance(value, bool):
        raise ValueError("timestamp must be a number or an ISO 8601 string")
    if isinstance(value, (int, float)):
        return datetime.datetime.fromtimestamp(float(value), datetime.timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("empty timestamp")
        if text.endswith("Z") or text.endswith("z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.datetime.fromisoformat(text)
        except ValueError:
            try:
                return datetime.datetime.fromtimestamp(
                    float(text), datetime.timezone.utc
                )
            except ValueError:
                raise ValueError("cannot parse timestamp: %r" % (value,))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed.astimezone(datetime.timezone.utc)
    raise ValueError("cannot parse timestamp: %r" % (value,))


def session_date(epoch_seconds, interval):
    """Map a bar timestamp to its ``date`` column value.

    ``epoch_seconds`` may be epoch seconds (int or float) or an ISO 8601
    string — IBKR returns ISO strings in ``time[]``. Returns ``YYYY-MM-DD``
    for ``1d``/``1w``/``1mo`` and an ISO 8601 UTC datetime (``...Z``) for
    intraday intervals. See the module docstring for the 21:15Z FX caveat.
    """
    moment = _to_utc(epoch_seconds)
    if interval in DATE_INTERVALS:
        return moment.strftime("%Y-%m-%d")
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_number(value):
    if value is None:
        return ""
    return repr(float(value))


#: Row fields that must be present on every bar. ``volume`` is deliberately
#: absent: FX bars carry no volume, so it may be missing or None.
REQUIRED_ROW_FIELDS = ("date", "open", "high", "low", "close")


def _check_rows(rows):
    """Raise ValueError naming the row and field when a price field is absent."""
    for index, row in enumerate(rows):
        for field in REQUIRED_ROW_FIELDS:
            if row.get(field) is None:
                raise ValueError(
                    "row %d is missing required field %r" % (index, field)
                )


def write_bars(source, key_, interval, rows, meta=None):
    """Write one entry's CSV and sidecar; return the sidecar that was written.

    ``rows`` is a list of dicts with ``date, open, high, low, close, volume``.
    Every field in :data:`REQUIRED_ROW_FIELDS` must be present and non-None on
    every row, or ValueError is raised naming the row index and the field.
    ``volume`` may be absent or None and is then written as an empty cell.
    Rows are sorted ascending by ``date`` before writing. ``meta`` is merged
    over the computed fields; every field in :data:`OPTIONAL_META_FIELDS` is
    present in the sidecar, as JSON null when the caller did not supply it.
    """
    if not rows:
        raise ValueError("refusing to write an entry with no rows")
    _check_rows(rows)

    ordered = sorted(rows, key=lambda row: row["date"])

    sidecar = {"schema_version": SCHEMA_VERSION, "source": source, "key": key_}
    for field in OPTIONAL_META_FIELDS:
        sidecar[field] = None
    for field, value in (meta or {}).items():
        sidecar[field] = value
    sidecar["interval"] = interval
    sidecar["start"] = ordered[0]["date"]
    sidecar["end"] = ordered[-1]["date"]
    sidecar["bar_count"] = len(ordered)
    sidecar["fetched_at"] = _utc_now_iso()

    csv_path, meta_path = paths(source, key_, interval)
    directory = bars_dir(source)
    if not os.path.isdir(directory):
        os.makedirs(directory)

    with open(csv_path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_HEADER)
        for row in ordered:
            writer.writerow(
                [row["date"]]
                + [_format_number(row.get(field)) for field in CSV_HEADER[1:]]
            )
    with open(meta_path, "w") as handle:
        json.dump(sidecar, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return sidecar


def _parse_number(text):
    if text is None or text == "":
        return None
    return float(text)


def read_bars(source, key_, interval):
    """Return ``(rows, meta)`` for one entry, numeric fields parsed to float."""
    csv_path, _ = paths(source, key_, interval)
    if not os.path.isfile(csv_path):
        raise StoreError("no bars at %s" % csv_path)
    rows = []
    with open(csv_path, newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            row = {"date": raw["date"]}
            for field in CSV_HEADER[1:]:
                row[field] = _parse_number(raw.get(field))
            rows.append(row)
    return rows, read_meta(source, key_, interval)


def read_meta(source, key_, interval):
    """Return the sidecar dict for one entry."""
    _, meta_path = paths(source, key_, interval)
    if not os.path.isfile(meta_path):
        raise StoreError("no sidecar at %s" % meta_path)
    with open(meta_path) as handle:
        try:
            return json.load(handle)
        except ValueError as exc:
            raise StoreError("malformed sidecar %s: %s" % (meta_path, exc))


def list_entries(source=None):
    """Return sorted ``(source, key, interval)`` tuples, optionally filtered."""
    base = os.path.join(root(), "bars")
    if not os.path.isdir(base):
        return []
    entries = []
    for name in sorted(os.listdir(base)):
        if source is not None and name != source:
            continue
        source_dir = os.path.join(base, name)
        if not os.path.isdir(source_dir):
            continue
        for filename in sorted(os.listdir(source_dir)):
            if not filename.endswith(_META_SUFFIX):
                continue
            stem = filename[: -len(_META_SUFFIX)]
            if "_" not in stem:
                continue
            entry_key, _, interval = stem.rpartition("_")
            entries.append((name, entry_key, interval))
    return sorted(entries)


def find_entries(key_, source=None, interval=None):
    """Return the entries matching a key, narrowed by source and interval."""
    return [
        entry
        for entry in list_entries(source)
        if entry[1] == key_ and (interval is None or entry[2] == interval)
    ]


def _describe(entry):
    source, entry_key, interval = entry
    try:
        meta = read_meta(source, entry_key, interval)
    except StoreError:
        meta = {}
    return {
        "source": source,
        "key": entry_key,
        "interval": interval,
        "bar_count": meta.get("bar_count"),
        "start": meta.get("start"),
        "end": meta.get("end"),
        "currency": meta.get("currency"),
        "adjusted": meta.get("adjusted"),
        "fetched_at": meta.get("fetched_at"),
    }


def _cmd_list(args):
    rows = [_describe(entry) for entry in list_entries(args.source)]
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    if not rows:
        print("store %s: no entries" % root())
        return 0
    print("store %s: %d entries" % (root(), len(rows)))
    for row in rows:
        print(
            "  %-9s %-18s %-4s %5s bars  %s -> %s"
            % (
                row["source"],
                row["key"],
                row["interval"],
                row["bar_count"] if row["bar_count"] is not None else "?",
                row["start"] or "?",
                row["end"] or "?",
            )
        )
    return 0


def _cmd_show(args):
    matches = find_entries(args.key, args.source, args.interval)
    if not matches:
        sys.stderr.write("no store entry for key %s\n" % args.key)
        return 1
    if len(matches) > 1:
        sys.stderr.write(
            "ambiguous key %s; narrow with --source/--interval. Matches:\n" % args.key
        )
        for source, entry_key, interval in matches:
            sys.stderr.write("  %s %s %s\n" % (source, entry_key, interval))
        return 1
    source, entry_key, interval = matches[0]
    meta = read_meta(source, entry_key, interval)
    if args.json:
        print(json.dumps(meta, indent=2, sort_keys=True))
        return 0
    for field in sorted(meta):
        value = meta[field]
        print("%-14s %s" % (field, "null" if value is None else value))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="store.py", description="Inspect the finance bar store."
    )
    sub = parser.add_subparsers(dest="command")

    listing = sub.add_parser("list", help="list stored entries")
    listing.add_argument("--source", help="restrict to one source, e.g. ibkr")
    listing.add_argument("--json", action="store_true", help="machine-readable output")
    listing.set_defaults(func=_cmd_list)

    show = sub.add_parser("show", help="print one entry's sidecar metadata")
    show.add_argument("key", help="store key, e.g. IBIS2_VWCE")
    show.add_argument("--source", help="restrict to one source")
    show.add_argument("--interval", help="restrict to one interval, e.g. 1d")
    show.add_argument("--json", action="store_true", help="machine-readable output")
    show.set_defaults(func=_cmd_show)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return 1
    try:
        return args.func(args)
    except StoreError as exc:
        sys.stderr.write("%s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
