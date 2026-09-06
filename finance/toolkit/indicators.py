#!/usr/bin/env python3
"""Deterministic indicator engine: EMA, RSI, MACD, TRIX and Bollinger bands.

Ported from ``scripts/indicators.py`` of Oft3r/agentic-trading-desk (MIT
licence); the arithmetic is unchanged, the input path is not. Upstream took a
JSON array of closes on the command line; here the closes come from the bar
store, so a reading is reproducible from a stored entry rather than from a
paste.

The point of the module is that indicator values are *computed*, never
estimated by a model reading bars. Every function is pure and stdlib only.

Conventions, chosen to match TradingView and ta-lib (``adjust=False``):

* EMA is seeded with the SMA of the first ``period`` observations.
* RSI uses Wilder smoothing, seeded with a simple average of the first
  ``period`` changes.
* MACD is 12/26/9, TRIX 15 with a 9-period signal, Bollinger 20/2 with a
  population standard deviation.
* Warmup positions are ``None`` rather than dropped, so an index into a
  returned series is the index of the same bar in the input.

Usage as a library::

    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    import indicators
    snapshot = indicators.compute([bar["close"] for bar in rows])

Usage as a CLI::

    python3 indicators.py KEY [--source ibkr|yfinance] [--interval 1d] [--json]
    python3 indicators.py --closes CLOSES.json [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from statistics import pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import store  # noqa: E402

#: Bars needed before EMA200 stops being None.
EMA200_PERIOD = 200


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------

def ema_series(values, period):
    """EMA of ``values``, None-padded through the warmup.

    The seed is the SMA of the first ``period`` observations. The result is
    the same length as ``values``; positions before ``period - 1`` are None.
    """
    n = len(values)
    out = [None] * n
    if n < period:
        return out
    k = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, n):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def _strip(values):
    return [v for v in values if v is not None]


def rsi_wilder(close, period=14):
    """RSI with Wilder smoothing, None-padded through the warmup."""
    n = len(close)
    out = [None] * n
    if n < period + 1:
        return out
    gains, losses = [], []
    for i in range(1, n):
        change = close[i] - close[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    # First a simple average over the first `period` changes, then Wilder.
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def rsi_val(ag, al):
        if al == 0:
            return 100.0
        rs = ag / al
        return 100.0 - 100.0 / (1.0 + rs)

    out[period] = rsi_val(avg_gain, avg_loss)
    for i in range(period + 1, n):
        gain, loss = gains[i - 1], losses[i - 1]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = rsi_val(avg_gain, avg_loss)
    return out


def macd(close, fast=12, slow=26, signal=9):
    """Return ``(macd_line, signal_line, histogram)``, all None-padded.

    The signal EMA runs over the MACD line's non-None values and is then
    re-aligned to the input's indices.
    """
    ef = ema_series(close, fast)
    es = ema_series(close, slow)
    line = [
        (a - b) if (a is not None and b is not None) else None for a, b in zip(ef, es)
    ]
    valid = _strip(line)
    sig_valid = ema_series(valid, signal)
    # re-align signal to original length
    sig = [None] * len(close)
    first = next((i for i, v in enumerate(line) if v is not None), None)
    if first is not None:
        for off, v in enumerate(sig_valid):
            sig[first + off] = v
    hist = [
        (m - s) if (m is not None and s is not None) else None for m, s in zip(line, sig)
    ]
    return line, sig, hist


def trix(close, period=15, signal=9):
    """TRIX (percent rate of change of a triple EMA) and its signal.

    Both are None-padded to the input's length. TRIX is the most lagging
    indicator in the stack: with ``period=15`` it needs 44 bars before it
    produces a value, and its signal 52.
    """
    n = len(close)
    e1 = _strip(ema_series(close, period))
    e2 = _strip(ema_series(e1, period))
    e3 = _strip(ema_series(e2, period))
    trix_valid = []
    for i in range(1, len(e3)):
        prev = e3[i - 1]
        trix_valid.append((e3[i] - prev) / prev * 100.0 if prev != 0 else 0.0)
    sig_valid = _strip(ema_series(trix_valid, signal))
    # align to the end of the series
    t = [None] * n
    for off, v in enumerate(trix_valid):
        idx = n - len(trix_valid) + off
        if idx >= 0:
            t[idx] = v
    s = [None] * n
    for off, v in enumerate(sig_valid):
        idx = n - len(sig_valid) + off
        if idx >= 0:
            s[idx] = v
    return t, s


def bollinger(close, period=20, mult=2.0):
    """Return ``(mid, upper, lower, percent_b)`` for the last bar."""
    if len(close) < period:
        return None, None, None, None
    window = close[-period:]
    mid = sum(window) / period
    sd = pstdev(window)  # population, like TradingView
    upper = mid + mult * sd
    lower = mid - mult * sd
    rng = upper - lower
    pct_b = (close[-1] - lower) / rng if rng != 0 else 0.5
    return mid, upper, lower, pct_b


# --------------------------------------------------------------------------
# High-level API
# --------------------------------------------------------------------------

def _slope(series, lookback):
    """Change in the indicator relative to ``lookback`` valid values ago."""
    valid = _strip(series)
    if len(valid) <= lookback:
        return None
    return valid[-1] - valid[-1 - lookback]


def compute(close, slope_lookback=5):
    """Compute the whole stack; return the latest values and recent slopes.

    ``slope_lookback`` is the number of bars a slope is measured over
    (default 5, roughly one week of daily bars).
    """
    if len(close) < 210:
        # Not fatal: EMA200 is simply None. The caller is told so.
        warn = "Only %d bars; EMA200/some indicators may be None. Ideal >=220." % len(
            close
        )
    else:
        warn = None

    ema20 = ema_series(close, 20)
    ema50 = ema_series(close, 50)
    ema200 = ema_series(close, EMA200_PERIOD)
    rsi = rsi_wilder(close, 14)
    macd_line, macd_sig, macd_hist = macd(close, 12, 26, 9)
    trix_line, trix_sig = trix(close, 15, 9)
    bb_mid, bb_up, bb_lo, pct_b = bollinger(close, 20, 2.0)

    def last(s):
        v = _strip(s)
        return v[-1] if v else None

    def prev(s):
        v = _strip(s)
        return v[-2] if len(v) >= 2 else None

    # Bars since the last close BELOW the EMA20 (0 = the current bar closed
    # below it). None if it never did within the available window. This
    # separates a genuine reclaim of the EMA20 after a dip from the ordinary
    # state of a trend that has simply never touched it.
    bars_since_below_ema20 = None
    for back in range(len(close)):
        i = len(close) - 1 - back
        e = ema20[i]
        if e is not None and close[i] < e:
            bars_since_below_ema20 = back
            break

    return {
        "n_bars": len(close),
        "warning": warn,
        "close": close[-1],
        "ema20": last(ema20), "ema50": last(ema50), "ema200": last(ema200),
        "ema20_slope": _slope(ema20, slope_lookback),
        "ema50_slope": _slope(ema50, slope_lookback),
        "ema200_slope": _slope(ema200, slope_lookback),
        "rsi14": last(rsi), "rsi14_prev": prev(rsi),
        "macd_line": last(macd_line), "macd_signal": last(macd_sig),
        "macd_hist": last(macd_hist), "macd_hist_prev": prev(macd_hist),
        "trix": last(trix_line), "trix_prev": prev(trix_line),
        "trix_signal": last(trix_sig), "trix_signal_prev": prev(trix_sig),
        "bars_since_below_ema20": bars_since_below_ema20,
        "bb_mid": bb_mid, "bb_upper": bb_up, "bb_lower": bb_lo, "percent_b": pct_b,
    }


def _round(d, nd=4):
    return {k: (round(v, nd) if isinstance(v, float) else v) for k, v in d.items()}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

#: Fields printed before the indicator block, in this order.
_CONTEXT_FIELDS = (
    "key",
    "source",
    "interval",
    "as_of",
    "bar_count",
    "adjusted",
    "delayed_sec",
)

#: Indicator fields printed for a reading, in this order.
_INDICATOR_FIELDS = (
    "close",
    "ema20",
    "ema50",
    "ema200",
    "rsi14",
    "macd_line",
    "macd_signal",
    "macd_hist",
    "trix",
    "trix_signal",
    "percent_b",
)


def _load_closes_file(path):
    """Read the escape-hatch input: a JSON list of closes, or ``{"close": []}``."""
    try:
        with open(path) as handle:
            raw = json.load(handle)
    except IOError as exc:
        raise ValueError("cannot read %s: %s" % (path, exc.strerror or exc))
    except ValueError as exc:
        raise ValueError("malformed JSON in %s: %s" % (path, exc))
    values = raw.get("close") if isinstance(raw, dict) else raw
    if not isinstance(values, list) or not values:
        raise ValueError("%s: expected a non-empty JSON list of closes" % path)
    try:
        return [float(v) for v in values]
    except (TypeError, ValueError):
        raise ValueError("%s: closes must all be numbers" % path)


def _resolve_entry(key_, source, interval):
    """Return the single store entry a key names, or raise ValueError."""
    matches = store.find_entries(key_, source, interval)
    if not matches:
        raise ValueError("no store entry for key %s" % key_)
    if len(matches) > 1:
        lines = ["ambiguous key %s; narrow with --source/--interval. Matches:" % key_]
        lines += ["  %s %s %s" % match for match in matches]
        raise ValueError("\n".join(lines))
    return matches[0]


#: Placeholder for a context field the --closes path cannot know.
_NOT_APPLICABLE = "n/a"


def _format(value):
    if value is None:
        return "null"
    if isinstance(value, float):
        return "%.4f" % value
    return str(value)


def _print_human(context, snapshot):
    for field in _CONTEXT_FIELDS:
        print("%-14s %s" % (field, _format(context[field])))
    for field in _INDICATOR_FIELDS:
        print("%-14s %s" % (field, _format(snapshot[field])))


def _cmd_read(args):
    """Read closes from the store (or --closes) and print one indicator snapshot."""
    if args.closes:
        close = _load_closes_file(args.closes)
        context = dict((field, _NOT_APPLICABLE) for field in _CONTEXT_FIELDS)
        json_context = dict((field, None) for field in _CONTEXT_FIELDS)
    else:
        if not args.key:
            raise ValueError("a store KEY or --closes FILE is required")
        source, key_, interval = _resolve_entry(args.key, args.source, args.interval)
        rows, meta = store.read_bars(source, key_, interval)
        if not rows:
            raise ValueError(
                "store entry %s %s %s has no bars" % (source, key_, interval)
            )
        close = [row["close"] for row in rows]
        context = {
            "key": key_,
            "source": source,
            "interval": interval,
            "as_of": rows[-1]["date"],
            "adjusted": meta.get("adjusted"),
            "delayed_sec": meta.get("delayed_sec"),
        }
        json_context = dict(context)
    context["bar_count"] = json_context["bar_count"] = len(close)

    snapshot = compute(close, args.slope_lookback)

    if args.json:
        payload = _round(snapshot)
        payload.update(json_context)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    _print_human(context, snapshot)
    if len(close) < EMA200_PERIOD:
        print(
            "warning: %d bars is under %d, so ema200 is null"
            % (len(close), EMA200_PERIOD)
        )
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="indicators.py",
        description="Compute the indicator stack for a stored instrument.",
    )
    parser.add_argument(
        "key", nargs="?", help="store key, e.g. IBIS2_VWCE; omit when using --closes"
    )
    parser.add_argument("--source", help="restrict to one source, e.g. ibkr")
    parser.add_argument("--interval", help="restrict to one interval, e.g. 1d")
    parser.add_argument(
        "--closes",
        help="JSON list of closes (or {'close': [...]}); bypasses the store",
    )
    parser.add_argument(
        "--slope-lookback",
        type=int,
        default=5,
        dest="slope_lookback",
        help="bars a slope is measured over (default: 5)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.set_defaults(func=_cmd_read)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (store.StoreError, ValueError) as exc:
        sys.stderr.write("%s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
