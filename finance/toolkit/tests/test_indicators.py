"""Tests for the deterministic indicator engine.

The golden-vector expectations are computed *here*, from the textbook
recursions written out below, never by calling the module under test: an
independent implementation is the only thing that can catch a port that is
self-consistently wrong.

Every test that touches the store points FINANCE_STORE at a temporary
directory, and every instrument is synthetic (TESTA / TESTB).
"""

from __future__ import annotations

import io
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import indicators  # noqa: E402
import store  # noqa: E402


# ---------------------------------------------------------------------------
# Independent reference implementations (textbook form)
# ---------------------------------------------------------------------------

def ref_ema(values, period):
    """SMA-seeded EMA, written as prev + k * (value - prev)."""
    out = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = prev + k * (values[i] - prev)
        out[i] = prev
    return out


def ref_rsi(close, period=14):
    """Wilder RSI, written as the running-average recursion."""
    out = [None] * len(close)
    if len(close) < period + 1:
        return out
    up = 0.0
    down = 0.0
    for i in range(1, period + 1):
        change = close[i] - close[i - 1]
        if change > 0:
            up += change
        else:
            down += -change
    avg_up = up / period
    avg_down = down / period
    out[period] = 100.0 if avg_down == 0 else 100.0 - 100.0 / (1 + avg_up / avg_down)
    for i in range(period + 1, len(close)):
        change = close[i] - close[i - 1]
        gain = change if change > 0 else 0.0
        loss = -change if change < 0 else 0.0
        avg_up = (avg_up * (period - 1) + gain) / period
        avg_down = (avg_down * (period - 1) + loss) / period
        out[i] = (
            100.0 if avg_down == 0 else 100.0 - 100.0 / (1 + avg_up / avg_down)
        )
    return out


def ref_macd_hist(close, fast=12, slow=26, signal=9):
    """MACD histogram: (fast EMA - slow EMA) minus the EMA of that line."""
    ema_fast = ref_ema(close, fast)
    ema_slow = ref_ema(close, slow)
    line = [None] * len(close)
    for i in range(len(close)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            line[i] = ema_fast[i] - ema_slow[i]
    dense = [v for v in line if v is not None]
    dense_signal = ref_ema(dense, signal)
    first = slow - 1
    hist = [None] * len(close)
    for offset, value in enumerate(dense_signal):
        if value is not None:
            hist[first + offset] = line[first + offset] - value
    return hist


def golden_series(n=300):
    """A deterministic, non-monotonic price path with enough shape to matter."""
    return [
        round(100.0 + 12.0 * math.sin(i / 17.0) + 5.0 * math.cos(i / 5.0) + i * 0.04, 4)
        for i in range(n)
    ]


def bars_from_closes(closes, start_day=1):
    rows = []
    for i, close in enumerate(closes):
        day = start_day + i
        rows.append(
            {
                "date": "2026-%02d-%02d" % (1 + day // 28, 1 + day % 28),
                "open": close,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1000.0 + i,
            }
        )
    return rows


class IndicatorsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="finance-indicators-test-")
        self._prev = os.environ.get("FINANCE_STORE")
        os.environ["FINANCE_STORE"] = self.tmp

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("FINANCE_STORE", None)
        else:
            os.environ["FINANCE_STORE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, argv):
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = indicators.main(argv)
        return code, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

class TestEma(unittest.TestCase):
    def test_constant_series_ema_equals_the_constant(self):
        series = indicators.ema_series([42.0] * 60, 20)
        for value in series[19:]:
            self.assertAlmostEqual(value, 42.0, places=10)

    def test_warmup_is_none_padded_to_period_minus_one(self):
        series = indicators.ema_series([float(i) for i in range(60)], 20)
        self.assertEqual(series[:19], [None] * 19)
        self.assertIsNotNone(series[19])
        self.assertEqual(len(series), 60)

    def test_seed_is_the_sma_of_the_first_period(self):
        values = [float(i) for i in range(1, 61)]
        series = indicators.ema_series(values, 20)
        self.assertAlmostEqual(series[19], sum(values[:20]) / 20.0, places=10)

    def test_series_shorter_than_period_is_all_none(self):
        self.assertEqual(indicators.ema_series([1.0, 2.0], 20), [None] * 2)


class TestRsi(unittest.TestCase):
    def test_strictly_rising_series_is_100(self):
        rsi = indicators.rsi_wilder([100.0 + i for i in range(40)], 14)
        self.assertEqual(rsi[-1], 100.0)

    def test_strictly_falling_series_is_0(self):
        rsi = indicators.rsi_wilder([100.0 - i for i in range(40)], 14)
        self.assertEqual(rsi[-1], 0.0)

    def test_warmup_is_none_padded_to_period(self):
        rsi = indicators.rsi_wilder([100.0 + i for i in range(40)], 14)
        self.assertEqual(rsi[:14], [None] * 14)
        self.assertIsNotNone(rsi[14])
        self.assertEqual(len(rsi), 40)

    def test_series_shorter_than_period_plus_one_is_all_none(self):
        self.assertEqual(indicators.rsi_wilder([100.0] * 14, 14), [None] * 14)


class TestMacdWarmup(unittest.TestCase):
    def test_line_starts_at_slow_minus_one_and_signal_eight_later(self):
        close = golden_series(80)
        line, signal, hist = indicators.macd(close, 12, 26, 9)
        self.assertEqual(line[:25], [None] * 25)
        self.assertIsNotNone(line[25])
        self.assertEqual(signal[:33], [None] * 33)
        self.assertIsNotNone(signal[33])
        self.assertEqual(hist[:33], [None] * 33)
        self.assertIsNotNone(hist[33])
        self.assertEqual([len(line), len(signal), len(hist)], [80, 80, 80])


class TestTrixWarmup(unittest.TestCase):
    def test_trix_and_signal_warmup_counts(self):
        close = golden_series(120)
        line, signal = indicators.trix(close, 15, 9)
        # three chained 15-period EMAs consume 3 * 14 bars, the percent change
        # one more, and the 9-period signal a further 8.
        self.assertEqual(line[:43], [None] * 43)
        self.assertIsNotNone(line[43])
        self.assertEqual(signal[:51], [None] * 51)
        self.assertIsNotNone(signal[51])
        self.assertEqual([len(line), len(signal)], [120, 120])


class TestBollinger(unittest.TestCase):
    def test_percent_b_is_one_when_close_sits_on_the_upper_band(self):
        # With 19 values symmetric about a base B and a last value B + x, the
        # window has mean B + x/20 and population variance (S + 0.95 x^2)/20,
        # where S is the others' summed squared deviation. Solving
        # B + x == mean + 2 * sd gives x^2 = (0.2 / 0.7125) * S.
        base = 100.0
        unit = 1.0
        others = [base + unit] * 9 + [base - unit] * 9 + [base]
        summed_sq = 18 * unit * unit
        x = math.sqrt((0.2 / 0.7125) * summed_sq)
        window = others + [base + x]
        mid, upper, lower, pct_b = indicators.bollinger(window, 20, 2.0)
        self.assertAlmostEqual(upper, window[-1], places=9)
        self.assertAlmostEqual(pct_b, 1.0, places=9)
        self.assertAlmostEqual(mid, sum(window) / 20.0, places=10)
        self.assertAlmostEqual(lower, 2 * mid - upper, places=9)

    def test_flat_window_gives_half(self):
        self.assertEqual(indicators.bollinger([5.0] * 20, 20, 2.0)[3], 0.5)

    def test_short_window_is_all_none(self):
        self.assertEqual(indicators.bollinger([1.0] * 19, 20, 2.0), (None, None, None, None))


# ---------------------------------------------------------------------------
# Golden vector
# ---------------------------------------------------------------------------

class TestGoldenVector(unittest.TestCase):
    INDICES = (120, 233, 299)

    def setUp(self):
        self.close = golden_series(300)

    def test_ema20_matches_independent_recursion(self):
        got = indicators.ema_series(self.close, 20)
        want = ref_ema(self.close, 20)
        for index in self.INDICES:
            self.assertAlmostEqual(got[index], want[index], places=8)

    def test_rsi14_matches_independent_recursion(self):
        got = indicators.rsi_wilder(self.close, 14)
        want = ref_rsi(self.close, 14)
        for index in self.INDICES:
            self.assertAlmostEqual(got[index], want[index], places=8)

    def test_macd_histogram_matches_independent_recursion(self):
        _, _, got = indicators.macd(self.close, 12, 26, 9)
        want = ref_macd_hist(self.close, 12, 26, 9)
        for index in self.INDICES:
            self.assertAlmostEqual(got[index], want[index], places=8)

    def test_reference_values_are_not_degenerate(self):
        # Guards the golden vector itself: a flat or all-None series would
        # make the three comparisons above pass vacuously.
        want = [ref_rsi(self.close, 14)[i] for i in self.INDICES]
        self.assertNotIn(None, want)
        self.assertEqual(len(set(want)), 3)


class TestCompute(unittest.TestCase):
    def test_returns_latest_values_and_bar_count(self):
        close = golden_series(300)
        result = indicators.compute(close)
        self.assertEqual(result["n_bars"], 300)
        self.assertEqual(result["close"], close[-1])
        self.assertAlmostEqual(result["ema20"], ref_ema(close, 20)[-1], places=8)
        self.assertAlmostEqual(result["rsi14"], ref_rsi(close, 14)[-1], places=8)
        self.assertIsNotNone(result["ema200"])
        self.assertIsNone(result["warning"])

    def test_short_series_leaves_ema200_none_and_warns(self):
        result = indicators.compute(golden_series(120))
        self.assertIsNone(result["ema200"])
        self.assertIsNotNone(result["warning"])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCliStorePath(IndicatorsTestCase):
    def setUp(self):
        IndicatorsTestCase.setUp(self)
        self.close = golden_series(300)
        store.write_bars(
            "ibkr",
            "TESTX_TESTA",
            "1d",
            bars_from_closes(self.close),
            {"adjusted": False, "delayed_sec": 900, "currency": "EUR"},
        )

    def test_human_output_lists_every_field(self):
        code, out, err = self.run_cli(["TESTX_TESTA"])
        self.assertEqual(code, 0, err)
        for field in (
            "key",
            "source",
            "interval",
            "as_of",
            "bar_count",
            "adjusted",
            "delayed_sec",
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
        ):
            self.assertIn(field, out)
        self.assertIn("TESTX_TESTA", out)
        self.assertIn("ibkr", out)
        self.assertIn("900", out)

    def test_no_warning_line_with_enough_bars(self):
        _, out, _ = self.run_cli(["TESTX_TESTA"])
        self.assertNotIn("warning", out)

    def test_json_output_has_compute_and_store_keys(self):
        code, out, err = self.run_cli(["TESTX_TESTA", "--json"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        for field in (
            "n_bars",
            "close",
            "ema20",
            "ema50",
            "ema200",
            "ema20_slope",
            "rsi14",
            "macd_line",
            "macd_signal",
            "macd_hist",
            "trix",
            "trix_signal",
            "percent_b",
            "bb_upper",
            "key",
            "source",
            "interval",
            "bar_count",
            "as_of",
            "adjusted",
            "delayed_sec",
        ):
            self.assertIn(field, payload)
        self.assertEqual(payload["key"], "TESTX_TESTA")
        self.assertEqual(payload["source"], "ibkr")
        self.assertEqual(payload["interval"], "1d")
        self.assertEqual(payload["bar_count"], 300)
        self.assertEqual(payload["adjusted"], False)
        self.assertEqual(payload["delayed_sec"], 900)
        self.assertEqual(payload["as_of"], bars_from_closes(self.close)[-1]["date"])
        self.assertAlmostEqual(payload["rsi14"], ref_rsi(self.close, 14)[-1], places=3)

    def test_source_and_interval_narrow_the_lookup(self):
        code, _, err = self.run_cli(
            ["TESTX_TESTA", "--source", "ibkr", "--interval", "1d"]
        )
        self.assertEqual(code, 0, err)

    def test_short_history_warns_on_stdout(self):
        store.write_bars(
            "ibkr", "TESTX_TESTB", "1d", bars_from_closes(golden_series(120))
        )
        code, out, err = self.run_cli(["TESTX_TESTB"])
        self.assertEqual(code, 0, err)
        warnings = [line for line in out.splitlines() if line.startswith("warning")]
        self.assertEqual(len(warnings), 1)
        self.assertIn("200", warnings[0])


class TestCliErrors(IndicatorsTestCase):
    def test_missing_key_exits_1(self):
        code, _, err = self.run_cli(["TESTX_NOPE"])
        self.assertEqual(code, 1)
        self.assertIn("TESTX_NOPE", err)

    def test_ambiguous_key_exits_1_and_lists_matches(self):
        rows = bars_from_closes(golden_series(60))
        store.write_bars("ibkr", "TESTX_TESTA", "1d", rows)
        store.write_bars("yfinance", "TESTX_TESTA", "1d", rows)
        code, _, err = self.run_cli(["TESTX_TESTA"])
        self.assertEqual(code, 1)
        self.assertIn("ambiguous", err)
        self.assertIn("ibkr", err)
        self.assertIn("yfinance", err)
        self.assertIn("--source", err)

    def test_no_key_and_no_closes_exits_1(self):
        code, _, err = self.run_cli([])
        self.assertEqual(code, 1)
        self.assertTrue(err.strip())


class TestCliClosesEscapeHatch(IndicatorsTestCase):
    def write_json(self, payload):
        path = os.path.join(self.tmp, "closes.json")
        with open(path, "w") as handle:
            json.dump(payload, handle)
        return path

    def test_bare_list_of_closes(self):
        close = golden_series(300)
        code, out, err = self.run_cli(["--closes", self.write_json(close)])
        self.assertEqual(code, 0, err)
        self.assertIn("n/a", out)

    def test_close_keyed_object(self):
        close = golden_series(300)
        path = self.write_json({"close": close})
        code, out, err = self.run_cli(["--closes", path, "--json"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertIsNone(payload["key"])
        self.assertIsNone(payload["source"])
        self.assertIsNone(payload["as_of"])
        self.assertEqual(payload["bar_count"], 300)
        self.assertAlmostEqual(payload["ema20"], ref_ema(close, 20)[-1], places=3)

    def test_closes_bypasses_the_store_entirely(self):
        # No entry for this key exists; --closes must not consult the store.
        close = golden_series(300)
        code, _, err = self.run_cli(["TESTX_TESTA", "--closes", self.write_json(close)])
        self.assertEqual(code, 0, err)

    def test_malformed_closes_file_exits_1(self):
        path = os.path.join(self.tmp, "bad.json")
        with open(path, "w") as handle:
            handle.write("{not json")
        code, _, err = self.run_cli(["--closes", path])
        self.assertEqual(code, 1)
        self.assertTrue(err.strip())


if __name__ == "__main__":
    unittest.main()
