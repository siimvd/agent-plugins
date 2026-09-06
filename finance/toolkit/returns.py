#!/usr/bin/env python3
"""Log returns, session-date alignment, correlation, beta and rolling windows.

The module exists so a correlation is *computed* from stored bars rather than
eyeballed from a price series pasted into a conversation. Nothing here ever
prints a bar row: every subcommand emits a markdown table or a short
key/value block, which is what makes a twenty-key matrix affordable in
context.

Method, matching the conventions in the ``stock-correlation`` skill:

* Returns are logarithmic, ``ln(close_t / close_{t-1})``, stamped with the
  later bar's session date.
* Series are aligned by an **inner join on the session date** (the ``date``
  column ``store.py`` writes), never by position, because venues differ in
  holidays and in the hour they stamp a close. The default minimum overlap is
  60 sessions; below that a correlation is not reported at all.
* Pearson correlation and beta use the same sums, so the ``n - 1`` divisor
  cancels: ``beta(a, b) = cov(a, b) / var(b)``, with ``b`` the benchmark.
* ``adjusted`` mismatches are surfaced loudly. Mixing an adjusted series with
  an unadjusted one silently corrupts every return spanning an ex-dividend
  date, and the store's flag is the only way to see it coming.

Keys may be given bare (``TESTA``) or qualified (``yfinance/VWCE.DE``) when
the same key exists under more than one source.

Usage as a library::

    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    import returns
    dates, values, report = returns.align({"A": ra, "B": rb})

Usage as a CLI::

    python3 returns.py pair KEY_A KEY_B [--min-overlap 60]
    python3 returns.py matrix KEY... [--min-overlap 60]
    python3 returns.py rolling KEY_A KEY_B --window 60
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import store  # noqa: E402

#: Sessions two series must share before a correlation is reported.
DEFAULT_MIN_OVERLAP = 60

#: Rolling window length, in aligned returns.
DEFAULT_WINDOW = 60

#: One row in every ``ROLLING_STRIDE`` windows is printed, plus the extremes.
ROLLING_STRIDE = 5

#: How a key may be written on the command line.
KEY_FORM_HELP = "store key, either KEY or source/KEY (e.g. yfinance/VWCE.DE)"


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------

def log_returns(rows):
    """Return ``[(date, ln(close_t / close_{t-1})), ...]`` for store rows.

    ``rows`` must be ascending by date, as ``store.read_bars`` returns them.
    The result is one shorter than the input and each return carries the
    *later* bar's session date, so two series align on the session whose
    return is being compared.
    """
    out = []
    previous = None
    for row in rows:
        close = row.get("close")
        if close is None or close <= 0:
            raise ValueError(
                "close on %s is %r; log returns need a positive close"
                % (row.get("date"), close)
            )
        if previous is not None:
            out.append((row["date"], math.log(close / previous)))
        previous = close
    return out


def align(series_by_key):
    """Inner-join ``{key: [(date, value)]}`` on the session date.

    Returns ``(dates, {key: [value]}, report)``. ``dates`` is sorted and holds
    only sessions present in *every* series; each value list is in that order.
    ``report[key]`` gives ``input``, ``overlap`` and ``dropped`` counts, which
    is what tells a caller a series was mostly thrown away rather than mostly
    matched. Raises ValueError naming the key and date if any series carries
    two entries for the same date: overwriting one silently would produce a
    return that looks like a genuine, non-overlapping observation.
    """
    if not series_by_key:
        raise ValueError("align needs at least one series")

    common = None
    for series in series_by_key.values():
        dates = set(date for date, _ in series)
        common = dates if common is None else (common & dates)
    ordered = sorted(common)

    values = {}
    report = {}
    for key_, series in series_by_key.items():
        lookup = {}
        for date, value in series:
            if date in lookup:
                raise ValueError(
                    "series %r has a duplicate date %r" % (key_, date)
                )
            lookup[date] = value
        values[key_] = [lookup[date] for date in ordered]
        report[key_] = {
            "input": len(series),
            "overlap": len(ordered),
            "dropped": len(series) - len(ordered),
        }
    return ordered, values, report


def _centred_sums(a, b):
    """Return ``(Sab, Saa, Sbb)``, the centred sums of products."""
    n = len(a)
    if n != len(b):
        raise ValueError("series lengths differ: %d vs %d" % (n, len(b)))
    if n < 2:
        raise ValueError("need at least 2 observations, got %d" % n)
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    s_ab = s_aa = s_bb = 0.0
    for x, y in zip(a, b):
        dx = x - mean_a
        dy = y - mean_b
        s_ab += dx * dy
        s_aa += dx * dx
        s_bb += dy * dy
    return s_ab, s_aa, s_bb


def pearson(a, b):
    """Pearson correlation of two equal-length sequences."""
    s_ab, s_aa, s_bb = _centred_sums(a, b)
    if s_aa <= 0.0 or s_bb <= 0.0:
        raise ValueError("a series has zero variance; correlation is undefined")
    return s_ab / math.sqrt(s_aa * s_bb)


def beta(a, b):
    """Beta of ``a`` on benchmark ``b``: ``cov(a, b) / var(b)``."""
    s_ab, _, s_bb = _centred_sums(a, b)
    if s_bb <= 0.0:
        raise ValueError("the benchmark has zero variance; beta is undefined")
    return s_ab / s_bb


def rolling_pearson(dates, a, b, window):
    """Return ``[(window_end_date, correlation), ...]``.

    There are ``len(a) - window + 1`` windows; each is stamped with the date
    of its last observation.
    """
    if window < 2:
        raise ValueError("window must be at least 2, got %d" % window)
    if len(a) != len(b) or len(a) != len(dates):
        raise ValueError("dates and both series must be the same length")
    if len(a) < window:
        raise ValueError(
            "window %d exceeds the %d aligned returns available" % (window, len(a))
        )
    out = []
    for end in range(window - 1, len(a)):
        start = end - window + 1
        out.append((dates[end], pearson(a[start:end + 1], b[start:end + 1])))
    return out


# --------------------------------------------------------------------------
# Store access
# --------------------------------------------------------------------------

#: Key resolution lives in store.py; fx.py resolves keys the same way.
resolve_entry = store.resolve_entry


class _Series(object):
    """One resolved store entry and the log returns computed from it."""

    def __init__(self, spec, source=None, interval=None):
        self.source, self.key, self.interval = resolve_entry(spec, source, interval)
        rows, self.meta = store.read_bars(self.source, self.key, self.interval)
        if len(rows) < 2:
            raise ValueError(
                "store entry %s/%s_%s has %d bars; at least 2 are needed"
                % (self.source, self.key, self.interval, len(rows))
            )
        self.returns = log_returns(rows)

    @property
    def label(self):
        return "%s/%s" % (self.source, self.key)

    @property
    def adjusted(self):
        return self.meta.get("adjusted")


def _load(specs, args):
    series = [_Series(spec, args.source, args.interval) for spec in specs]
    intervals = set(item.interval for item in series)
    if len(intervals) > 1:
        named = ", ".join(
            "%s=%s" % (item.label, item.interval) for item in series
        )
        raise ValueError(
            "legs resolved to different intervals (%s); pass --interval to "
            "pin one" % named
        )
    return series


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------

def _text(value):
    if value is None:
        return "null"
    if isinstance(value, float):
        return "%.4f" % value
    return str(value)


def _kv(field, value):
    print("%-14s %s" % (field, _text(value)))


def _adjusted_warning(labels, flags):
    """Return the one-line warning when adjustment flags disagree, else None."""
    if any(flag is None for flag in flags) or len(set(flags)) > 1:
        stated = ", ".join(
            "%s=%s" % (label, _text(flag)) for label, flag in zip(labels, flags)
        )
        return (
            "WARNING: adjustment flags are not uniform (%s). Returns spanning an "
            "ex-dividend or split date are not comparable across a mismatch; "
            "re-fetch both legs from the same provider before trusting this."
            % stated
        )
    return None


# --------------------------------------------------------------------------
# CLI: pair
# --------------------------------------------------------------------------

def _cmd_pair(args):
    left, right = _load([args.key_a, args.key_b], args)
    dates, values, report = align({"a": left.returns, "b": right.returns})
    overlap = len(dates)
    if overlap < args.min_overlap:
        raise ValueError(
            "overlap of %d sessions between %s and %s is below the minimum of "
            "%d; correlation not reported"
            % (overlap, left.label, right.label, args.min_overlap)
        )

    correlation = pearson(values["a"], values["b"])
    payload = {
        "key_a": left.label,
        "key_b": right.label,
        "interval": left.interval,
        "overlap": overlap,
        "dropped_a": report["a"]["dropped"],
        "dropped_b": report["b"]["dropped"],
        "correlation": correlation,
        "beta_a_on_b": beta(values["a"], values["b"]),
        "r_squared": correlation * correlation,
        "adjusted_a": left.adjusted,
        "adjusted_b": right.adjusted,
        "currency_a": left.meta.get("currency"),
        "currency_b": right.meta.get("currency"),
        "first_session": dates[0],
        "last_session": dates[-1],
    }
    warning = _adjusted_warning(
        [left.label, right.label], [left.adjusted, right.adjusted]
    )
    payload["adjusted_warning"] = warning

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    for field in ("key_a", "key_b", "interval", "first_session", "last_session",
                  "overlap", "dropped_a", "dropped_b", "correlation",
                  "beta_a_on_b", "r_squared", "currency_a", "currency_b",
                  "adjusted_a", "adjusted_b"):
        _kv(field, payload[field])
    if warning:
        print(warning)
    return 0


# --------------------------------------------------------------------------
# CLI: matrix
# --------------------------------------------------------------------------

def _cmd_matrix(args):
    if len(args.keys) < 2:
        raise ValueError("matrix needs at least two keys")
    series = _load(args.keys, args)
    labels = [item.key for item in series]
    if len(set(labels)) != len(labels):
        labels = [item.label for item in series]

    cells = dict((label, {label: 1.0}) for label in labels)
    for i in range(len(series)):
        for j in range(i + 1, len(series)):
            dates, values, _ = align({"a": series[i].returns, "b": series[j].returns})
            if len(dates) < args.min_overlap:
                raise ValueError(
                    "%s and %s share only %d sessions, below the minimum of %d; "
                    "no matrix printed"
                    % (series[i].label, series[j].label, len(dates), args.min_overlap)
                )
            value = pearson(values["a"], values["b"])
            cells[labels[i]][labels[j]] = value
            cells[labels[j]][labels[i]] = value

    common, _, _ = align(dict((item.label, item.returns) for item in series))
    span = "%s to %s" % (common[0], common[-1]) if common else "no common session"
    interval = series[0].interval

    if args.json:
        print(json.dumps(
            {
                "keys": [item.label for item in series],
                "labels": labels,
                "interval": interval,
                "matrix": cells,
                "common_overlap": len(common),
                "min_overlap": args.min_overlap,
                "first_session": common[0] if common else None,
                "last_session": common[-1] if common else None,
            },
            indent=2,
            sort_keys=True,
        ))
        return 0

    print("| key | " + " | ".join(labels) + " |")
    print("|---" * (len(labels) + 1) + "|")
    for label in labels:
        print(
            "| %s | " % label
            + " | ".join("%.2f" % cells[label][other] for other in labels)
            + " |"
        )
    print(
        "%d keys, interval %s, pairwise Pearson on daily log returns, common "
        "overlap %d sessions (%s), min overlap %d."
        % (len(labels), interval, len(common), span, args.min_overlap)
    )
    return 0


# --------------------------------------------------------------------------
# CLI: rolling
# --------------------------------------------------------------------------

def _cmd_rolling(args):
    left, right = _load([args.key_a, args.key_b], args)
    dates, values, _ = align({"a": left.returns, "b": right.returns})
    if len(dates) < args.window:
        raise ValueError(
            "window %d exceeds the %d aligned returns shared by %s and %s"
            % (args.window, len(dates), left.label, right.label)
        )

    rolled = rolling_pearson(dates, values["a"], values["b"], args.window)
    correlations = [value for _, value in rolled]
    low = min(range(len(rolled)), key=lambda i: correlations[i])
    high = max(range(len(rolled)), key=lambda i: correlations[i])

    payload = {
        "key_a": left.label,
        "key_b": right.label,
        "interval": left.interval,
        "window": args.window,
        "aligned_returns": len(dates),
        "window_count": len(rolled),
        "first_window_end": rolled[0][0],
        "last_window_end": rolled[-1][0],
        "current": correlations[-1],
        "mean": sum(correlations) / len(correlations),
        "min": correlations[low],
        "min_date": rolled[low][0],
        "max": correlations[high],
        "max_date": rolled[high][0],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print(
        "rolling correlation %s vs %s: interval %s, window %d, %d windows "
        "over %d aligned returns, %s to %s"
        % (left.label, right.label, left.interval, args.window, len(rolled),
           len(dates), rolled[0][0], rolled[-1][0])
    )
    notes = {low: "min", high: "max"}
    shown = sorted(set(list(range(0, len(rolled), ROLLING_STRIDE)) + [low, high]))
    print("| window end | correlation | note |")
    print("|---|---|---|")
    for index in shown:
        date, value = rolled[index]
        print("| %s | %.4f | %s |" % (date, value, notes.get(index, "")))
    return 0


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------

def _add_common(parser):
    parser.add_argument("--source", help="restrict to one source, e.g. yfinance")
    parser.add_argument("--interval", help="restrict to one interval, e.g. 1d")
    parser.add_argument("--json", action="store_true", help="machine-readable output")


def _add_min_overlap(parser):
    parser.add_argument(
        "--min-overlap",
        type=int,
        default=DEFAULT_MIN_OVERLAP,
        dest="min_overlap",
        help="sessions two series must share (default: %d)" % DEFAULT_MIN_OVERLAP,
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="returns.py",
        description=(
            "Correlation and beta over stored bars. Keys may be written KEY or "
            "source/KEY. Output is markdown tables and key/value blocks only; "
            "bar rows are never printed."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    pair = sub.add_parser("pair", help="correlation and beta for two keys")
    pair.add_argument("key_a", metavar="KEY_A", help=KEY_FORM_HELP)
    pair.add_argument("key_b", metavar="KEY_B", help="benchmark; " + KEY_FORM_HELP)
    _add_min_overlap(pair)
    _add_common(pair)
    pair.set_defaults(func=_cmd_pair)

    matrix = sub.add_parser("matrix", help="n x n correlation table")
    matrix.add_argument("keys", metavar="KEY", nargs="+", help=KEY_FORM_HELP)
    _add_min_overlap(matrix)
    _add_common(matrix)
    matrix.set_defaults(func=_cmd_matrix)

    rolling = sub.add_parser("rolling", help="rolling correlation for two keys")
    rolling.add_argument("key_a", metavar="KEY_A", help=KEY_FORM_HELP)
    rolling.add_argument("key_b", metavar="KEY_B", help=KEY_FORM_HELP)
    rolling.add_argument(
        "--window",
        type=int,
        default=DEFAULT_WINDOW,
        help="window length in aligned returns (default: %d)" % DEFAULT_WINDOW,
    )
    _add_common(rolling)
    rolling.set_defaults(func=_cmd_rolling)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return 1
    try:
        return args.func(args)
    except (store.StoreError, ValueError) as exc:
        sys.stderr.write("%s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
