"""Tests for log returns, session-date alignment, correlation and beta.

Every expectation that can be stated in closed form is stated in closed form
here (hand-computed log returns, corr(x, x) == 1, beta of a doubled series
== 2), so a self-consistently wrong implementation cannot pass. Store-backed
tests point FINANCE_STORE at a temporary directory and use synthetic keys
only (TESTA, TESTB, ...).
"""

from __future__ import annotations

import datetime
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import returns  # noqa: E402
import store  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def dates_from(start, count, offset=0):
    """``count`` consecutive ISO dates beginning ``offset`` days after start."""
    first = datetime.date(*[int(part) for part in start.split("-")])
    return [
        (first + datetime.timedelta(days=index + offset)).isoformat()
        for index in range(count)
    ]


def walk(count, seed, base=100.0):
    """A deterministic pseudo-random price walk (LCG), rounded to 4 places."""
    state = seed
    value = base
    out = []
    for _ in range(count):
        state = (1103515245 * state + 12345) % 2147483648
        value *= 1.0 + ((state / 2147483648.0) - 0.5) * 0.02
        out.append(round(value, 4))
    return out


def write_series(source, key_, closes, dates, meta=None, interval="1d"):
    rows = [
        {
            "date": date,
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1000.0,
        }
        for date, close in zip(dates, closes)
    ]
    payload = {"currency": "EUR", "adjusted": True, "delayed_sec": 0}
    payload.update(meta or {})
    return store.write_bars(source, key_, interval, rows, payload)


def run(argv):
    """Run the CLI, returning ``(exit_code, stdout, stderr)``."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = returns.main(argv)
    return code, out.getvalue(), err.getvalue()


class StoreBackedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="finance-returns-")
        self._saved = os.environ.get("FINANCE_STORE")
        os.environ["FINANCE_STORE"] = self.tmp

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("FINANCE_STORE", None)
        else:
            os.environ["FINANCE_STORE"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

class LogReturnsTest(unittest.TestCase):
    #: 100 -> 110 -> 121 -> 108.9 -> 108.9; ratios 1.1, 1.1, 0.9, 1.0.
    CLOSES = [100.0, 110.0, 121.0, 108.9, 108.9]
    DATES = ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08"]
    EXPECTED = [
        0.09531017980432493,
        0.09531017980432493,
        -0.10536051565782628,
        0.0,
    ]

    def rows(self):
        return [
            {"date": date, "close": close}
            for date, close in zip(self.DATES, self.CLOSES)
        ]

    def test_values_match_hand_computed_logs(self):
        result = returns.log_returns(self.rows())
        self.assertEqual(len(result), 4)
        for (_, value), expected in zip(result, self.EXPECTED):
            self.assertAlmostEqual(value, expected, places=15)

    def test_return_is_stamped_with_the_later_date(self):
        result = returns.log_returns(self.rows())
        self.assertEqual([date for date, _ in result], self.DATES[1:])

    def test_non_positive_close_is_rejected(self):
        rows = self.rows()
        rows[2]["close"] = 0.0
        with self.assertRaises(ValueError):
            returns.log_returns(rows)


class AlignTest(unittest.TestCase):
    def test_inner_join_drops_non_overlapping_dates_and_reports_counts(self):
        a = [("2025-01-01", 1.0), ("2025-01-02", 2.0), ("2025-01-03", 3.0)]
        b = [("2025-01-02", 9.0), ("2025-01-03", 8.0), ("2025-01-04", 7.0)]
        dates, values, report = returns.align({"A": a, "B": b})

        self.assertEqual(dates, ["2025-01-02", "2025-01-03"])
        self.assertEqual(values["A"], [2.0, 3.0])
        self.assertEqual(values["B"], [9.0, 8.0])
        self.assertEqual(report["A"], {"input": 3, "overlap": 2, "dropped": 1})
        self.assertEqual(report["B"], {"input": 3, "overlap": 2, "dropped": 1})

    def test_disjoint_series_give_an_empty_overlap(self):
        a = [("2025-01-01", 1.0)]
        b = [("2025-02-01", 1.0)]
        dates, _, report = returns.align({"A": a, "B": b})
        self.assertEqual(dates, [])
        self.assertEqual(report["A"]["dropped"], 1)

    def test_dates_come_back_sorted(self):
        a = [("2025-01-03", 1.0), ("2025-01-01", 2.0)]
        b = [("2025-01-01", 3.0), ("2025-01-03", 4.0)]
        dates, values, _ = returns.align({"A": a, "B": b})
        self.assertEqual(dates, ["2025-01-01", "2025-01-03"])
        self.assertEqual(values["A"], [2.0, 1.0])

    def test_duplicate_date_in_a_series_raises(self):
        a = [("2025-01-01", 1.0), ("2025-01-02", 2.0), ("2025-01-02", 5.0)]
        b = [("2025-01-01", 3.0), ("2025-01-02", 4.0)]
        with self.assertRaises(ValueError) as caught:
            returns.align({"A": a, "B": b})
        message = str(caught.exception)
        self.assertIn("A", message)
        self.assertIn("2025-01-02", message)


class PearsonBetaTest(unittest.TestCase):
    SERIES = [0.01, -0.02, 0.03, 0.005, -0.011, 0.02, -0.004, 0.017]

    def test_correlation_with_itself_is_one(self):
        self.assertAlmostEqual(returns.pearson(self.SERIES, self.SERIES), 1.0, delta=1e-12)

    def test_correlation_with_its_negation_is_minus_one(self):
        negated = [-value for value in self.SERIES]
        self.assertAlmostEqual(returns.pearson(self.SERIES, negated), -1.0, delta=1e-12)

    def test_beta_of_a_doubled_series_is_two(self):
        doubled = [2.0 * value for value in self.SERIES]
        self.assertAlmostEqual(returns.beta(doubled, self.SERIES), 2.0, delta=1e-12)

    def test_beta_of_a_series_on_itself_is_one(self):
        self.assertAlmostEqual(returns.beta(self.SERIES, self.SERIES), 1.0, delta=1e-12)

    def test_length_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            returns.pearson(self.SERIES, self.SERIES[:-1])

    def test_constant_series_has_no_correlation(self):
        with self.assertRaises(ValueError):
            returns.pearson(self.SERIES, [1.0] * len(self.SERIES))


class RollingPearsonTest(unittest.TestCase):
    def test_window_count_is_n_minus_window_plus_one(self):
        a = walk(90, 11)
        b = walk(90, 29)
        dates = dates_from("2025-01-01", 90)
        rolled = returns.rolling_pearson(dates, a, b, 60)
        self.assertEqual(len(rolled), 90 - 60 + 1)

    def test_window_is_stamped_with_its_end_date(self):
        dates = dates_from("2025-01-01", 10)
        rolled = returns.rolling_pearson(dates, walk(10, 3), walk(10, 5), 4)
        self.assertEqual(rolled[0][0], dates[3])
        self.assertEqual(rolled[-1][0], dates[-1])

    def test_window_longer_than_the_series_is_rejected(self):
        with self.assertRaises(ValueError):
            returns.rolling_pearson(dates_from("2025-01-01", 5), walk(5, 1), walk(5, 2), 6)


# ---------------------------------------------------------------------------
# CLI: pair
# ---------------------------------------------------------------------------

class PairCliTest(StoreBackedTest):
    def seed(self, adjusted_a=True, adjusted_b=True, count=120):
        self.dates = dates_from("2025-01-01", count)
        self.closes_a = walk(count, 7)
        self.closes_b = walk(count, 13)
        write_series("yfinance", "TESTA", self.closes_a, self.dates,
                     {"adjusted": adjusted_a})
        write_series("yfinance", "TESTB", self.closes_b, self.dates,
                     {"adjusted": adjusted_b})

    def test_pair_reports_correlation_overlap_beta_and_adjusted(self):
        self.seed()
        code, out, err = run(["pair", "TESTA", "TESTB"])
        self.assertEqual(code, 0, err)
        self.assertIn("correlation", out)
        self.assertIn("beta_a_on_b", out)
        self.assertIn("overlap", out)
        self.assertIn("adjusted_a", out)
        self.assertIn("adjusted_b", out)
        self.assertNotIn("WARNING", out)

    def test_pair_json_carries_the_numbers(self):
        self.seed()
        code, out, _ = run(["pair", "TESTA", "TESTB", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["overlap"], 119)
        self.assertIsInstance(payload["correlation"], float)
        self.assertIsInstance(payload["beta_a_on_b"], float)
        self.assertTrue(-1.0 <= payload["correlation"] <= 1.0)

    def test_pair_warns_when_adjusted_flags_differ(self):
        self.seed(adjusted_a=True, adjusted_b=False)
        code, out, _ = run(["pair", "TESTA", "TESTB"])
        self.assertEqual(code, 0)
        self.assertIn("WARNING", out)

    def test_pair_warns_when_an_adjusted_flag_is_unknown(self):
        self.seed(adjusted_a=True, adjusted_b=None)
        code, out, _ = run(["pair", "TESTA", "TESTB"])
        self.assertEqual(code, 0)
        self.assertIn("WARNING", out)
        self.assertIn("null", out)

    def test_pair_exits_one_below_min_overlap(self):
        self.seed(count=40)
        code, _, err = run(["pair", "TESTA", "TESTB"])
        self.assertEqual(code, 1)
        self.assertIn("overlap", err)
        self.assertIn("60", err)

    def test_pair_accepts_a_lower_min_overlap(self):
        self.seed(count=40)
        code, _, err = run(["pair", "TESTA", "TESTB", "--min-overlap", "10"])
        self.assertEqual(code, 0, err)

    def test_pair_resolves_the_source_slash_key_form(self):
        self.seed()
        write_series("ibkr", "TESTA", walk(120, 99), self.dates)
        ambiguous, _, err = run(["pair", "TESTA", "TESTB"])
        self.assertEqual(ambiguous, 1)
        self.assertIn("ambiguous", err)
        code, out, err = run(["pair", "yfinance/TESTA", "yfinance/TESTB"])
        self.assertEqual(code, 0, err)
        self.assertIn("yfinance/TESTA", out)

    def test_pair_prints_no_bar_rows(self):
        self.seed()
        _, out, _ = run(["pair", "TESTA", "TESTB"])
        # the block names the first and last aligned session as provenance;
        # no interior session date, and no price, may appear.
        for date in self.dates[2:-1]:
            self.assertNotIn(date, out)
        for close in self.closes_a[1:-1]:
            self.assertNotIn(repr(close), out)

    def test_missing_key_exits_one(self):
        self.seed()
        code, _, err = run(["pair", "TESTA", "NOPE"])
        self.assertEqual(code, 1)
        self.assertIn("NOPE", err)

    def test_pair_rejects_mixed_intervals_when_interval_is_omitted(self):
        self.seed()
        write_series("yfinance", "TESTC", walk(30, 41), dates_from("2025-01-01", 30),
                     interval="1w")
        code, out, err = run(["pair", "TESTA", "TESTC"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("TESTA", err)
        self.assertIn("TESTC", err)
        self.assertIn("1d", err)
        self.assertIn("1w", err)

    def test_pair_same_interval_still_works(self):
        self.seed()
        write_series("yfinance", "TESTC", walk(120, 41), self.dates, interval="1d")
        code, out, err = run(["pair", "TESTA", "TESTC"])
        self.assertEqual(code, 0, err)
        self.assertIn("correlation", out)


# ---------------------------------------------------------------------------
# CLI: matrix
# ---------------------------------------------------------------------------

class MatrixCliTest(StoreBackedTest):
    def seed(self, count=120, keys=("TESTA", "TESTB", "TESTC")):
        self.dates = dates_from("2025-01-01", count)
        self.closes = {}
        for index, key_ in enumerate(keys):
            closes = walk(count, 17 + index * 31)
            self.closes[key_] = closes
            write_series("yfinance", key_, closes, self.dates)
        return list(keys)

    def test_matrix_prints_one_table_and_one_summary_line(self):
        keys = self.seed()
        code, out, err = run(["matrix"] + keys)
        self.assertEqual(code, 0, err)
        lines = out.rstrip("\n").split("\n")
        # header + separator + one row per key + one summary line
        self.assertEqual(len(lines), 2 + len(keys) + 1)
        self.assertTrue(lines[0].startswith("|"))
        self.assertTrue(lines[1].startswith("|---"))
        self.assertFalse(lines[-1].startswith("|"))
        self.assertIn("3 keys", lines[-1])

    def test_diagonal_is_one_and_matrix_is_symmetric(self):
        keys = self.seed()
        code, out, _ = run(["matrix"] + keys + ["--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        cells = payload["matrix"]
        for key_ in keys:
            self.assertAlmostEqual(cells[key_][key_], 1.0, delta=1e-12)
        self.assertAlmostEqual(cells["TESTA"]["TESTB"], cells["TESTB"]["TESTA"], delta=1e-12)

    def test_matrix_names_the_pair_below_min_overlap(self):
        keys = self.seed()
        short = dates_from("2025-01-01", 30)
        write_series("yfinance", "TESTSHORT", walk(30, 5), short)
        code, out, err = run(["matrix"] + keys + ["TESTSHORT"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("TESTSHORT", err)
        self.assertIn("TESTA", err)
        self.assertIn("60", err)

    def test_twenty_keys_stay_under_thirty_lines(self):
        keys = ["TEST%02d" % index for index in range(20)]
        self.seed(count=150, keys=keys)
        code, out, err = run(["matrix"] + keys)
        self.assertEqual(code, 0, err)
        lines = out.rstrip("\n").split("\n")
        self.assertLess(len(lines), 30)
        self.assertEqual(sum(1 for line in lines if line.startswith("|---")), 1)
        self.assertEqual(sum(1 for line in lines if not line.startswith("|")), 1)
        self.assertIn("20 keys", lines[-1])

    def test_matrix_prints_no_bar_rows(self):
        keys = self.seed()
        _, out, _ = run(["matrix"] + keys)
        # the summary line names the first and last aligned session; no
        # interior session date may appear anywhere.
        for date in self.dates[2:-1]:
            self.assertNotIn(date, out)
        for close in self.closes["TESTA"][1:-1]:
            self.assertNotIn(repr(close), out)

    def test_matrix_needs_at_least_two_keys(self):
        self.seed()
        code, _, err = run(["matrix", "TESTA"])
        self.assertEqual(code, 1)
        self.assertIn("two", err)

    def test_matrix_rejects_an_odd_interval_key(self):
        keys = self.seed()
        write_series("yfinance", "TESTODD", walk(30, 41), dates_from("2025-01-01", 30),
                     interval="1w")
        code, out, err = run(["matrix"] + keys + ["TESTODD"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("TESTODD", err)
        self.assertIn("1w", err)


# ---------------------------------------------------------------------------
# CLI: rolling
# ---------------------------------------------------------------------------

class RollingCliTest(StoreBackedTest):
    def seed(self, count=150):
        self.dates = dates_from("2025-01-01", count)
        self.closes_a = walk(count, 41)
        self.closes_b = walk(count, 67)
        write_series("yfinance", "TESTA", self.closes_a, self.dates)
        write_series("yfinance", "TESTB", self.closes_b, self.dates)

    def test_window_count_equals_n_minus_window_plus_one(self):
        self.seed(count=150)
        code, out, err = run(["rolling", "TESTA", "TESTB", "--window", "60", "--json"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        aligned = payload["aligned_returns"]
        self.assertEqual(aligned, 149)
        self.assertEqual(payload["window_count"], aligned - 60 + 1)

    def test_header_states_the_window_count(self):
        self.seed()
        code, out, err = run(["rolling", "TESTA", "TESTB", "--window", "60"])
        self.assertEqual(code, 0, err)
        header = out.split("\n")[0]
        self.assertIn("90 windows", header)

    def test_table_shows_min_and_max_windows_with_their_dates(self):
        self.seed()
        code, out, _ = run(["rolling", "TESTA", "TESTB", "--window", "60", "--json"])
        payload = json.loads(out)
        code, table, err = run(["rolling", "TESTA", "TESTB", "--window", "60"])
        self.assertEqual(code, 0, err)
        self.assertIn(payload["min_date"], table)
        self.assertIn(payload["max_date"], table)
        self.assertIn("min", table)
        self.assertIn("max", table)

    def test_table_shows_every_fifth_window(self):
        self.seed()
        _, table, _ = run(["rolling", "TESTA", "TESTB", "--window", "60"])
        rows = [line for line in table.split("\n") if line.startswith("| 20")]
        # 90 windows -> every 5th is 18 rows, plus at most two for min and max
        self.assertGreaterEqual(len(rows), 18)
        self.assertLessEqual(len(rows), 20)

    def test_window_longer_than_the_overlap_exits_one(self):
        self.seed(count=40)
        code, _, err = run(["rolling", "TESTA", "TESTB", "--window", "60"])
        self.assertEqual(code, 1)
        self.assertIn("window", err)

    def test_rolling_prints_no_prices(self):
        self.seed()
        _, out, _ = run(["rolling", "TESTA", "TESTB", "--window", "60"])
        for close in self.closes_a[1:-1]:
            self.assertNotIn(repr(close), out)


class ParserTest(unittest.TestCase):
    def test_help_documents_the_source_slash_key_form(self):
        parser = returns.build_parser()
        out = io.StringIO()
        with redirect_stdout(out):
            try:
                parser.parse_args(["pair", "--help"])
            except SystemExit:
                pass
        self.assertIn("source/KEY", out.getvalue())

    def test_no_subcommand_exits_one(self):
        code, _, _ = run([])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
