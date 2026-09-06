"""Tests for EUR conversion from stored FX bars.

FX rates are quoted as the store stores them: close = quote currency per EUR
(``EURUSD`` close 1.10 means 1.10 USD buys one EUR), so converting an amount
of the quote currency into EUR divides. Every rate here is synthetic and the
pair keys are pair names, not account identifiers.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fx  # noqa: E402
import store  # noqa: E402


def write_series(source, key_, rows_by_date, meta=None, interval="1d"):
    rows = [
        {
            "date": date,
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1000.0,
        }
        for date, close in sorted(rows_by_date.items())
    ]
    payload = {"currency": "USD", "adjusted": True, "delayed_sec": 0}
    payload.update(meta or {})
    return store.write_bars(source, key_, interval, rows, payload)


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = fx.main(argv)
    return code, out.getvalue(), err.getvalue()


class StoreBackedTest(unittest.TestCase):
    #: USD per EUR on three sessions; 2025-01-03 is deliberately absent.
    RATES = {
        "2025-01-02": 1.0400,
        "2025-01-06": 1.2500,
        "2025-01-07": 1.2000,
    }

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="finance-fx-")
        self._saved = os.environ.get("FINANCE_STORE")
        os.environ["FINANCE_STORE"] = self.tmp

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("FINANCE_STORE", None)
        else:
            os.environ["FINANCE_STORE"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def seed_fx(self, source="ibkr", key_="IDEALPRO_EURUSD", rates=None):
        write_series(source, key_, rates or self.RATES,
                     {"currency": "USD", "price_source": "MidPoint"})


# ---------------------------------------------------------------------------
# rate()
# ---------------------------------------------------------------------------

class RateTest(StoreBackedTest):
    def test_euro_needs_no_pair_and_is_one(self):
        value, used, key_ = fx.rate("EUR", "2025-01-06")
        self.assertEqual(value, 1.0)
        self.assertEqual(used, "2025-01-06")
        self.assertIsNone(key_)

    def test_exact_date_uses_that_bar(self):
        self.seed_fx()
        value, used, key_ = fx.rate("USD", "2025-01-06")
        self.assertAlmostEqual(value, 1.25, places=10)
        self.assertEqual(used, "2025-01-06")
        self.assertEqual(key_, "ibkr/IDEALPRO_EURUSD")

    def test_missing_date_falls_back_to_the_nearest_prior_bar(self):
        self.seed_fx()
        value, used, _ = fx.rate("USD", "2025-01-03")
        self.assertAlmostEqual(value, 1.04, places=10)
        self.assertEqual(used, "2025-01-02")

    def test_date_after_the_last_bar_uses_the_last_bar(self):
        self.seed_fx()
        value, used, _ = fx.rate("USD", "2025-03-01")
        self.assertAlmostEqual(value, 1.20, places=10)
        self.assertEqual(used, "2025-01-07")

    def test_no_date_uses_the_latest_bar(self):
        self.seed_fx()
        value, used, _ = fx.rate("USD")
        self.assertAlmostEqual(value, 1.20, places=10)
        self.assertEqual(used, "2025-01-07")

    def test_raises_when_no_bar_precedes_the_date(self):
        self.seed_fx()
        with self.assertRaises(fx.FxError):
            fx.rate("USD", "2024-12-31")

    def test_raises_when_the_pair_is_not_in_the_store(self):
        self.seed_fx()
        with self.assertRaises(fx.FxError):
            fx.rate("SEK", "2025-01-06")

    def test_yahoo_style_pair_key_is_found(self):
        write_series("yfinance", "EURSEK=X", self.RATES, {"currency": "SEK"})
        value, used, key_ = fx.rate("SEK", "2025-01-06")
        self.assertAlmostEqual(value, 1.25, places=10)
        self.assertEqual(key_, "yfinance/EURSEK=X")

    def test_ibkr_pair_is_preferred_over_the_yahoo_one(self):
        self.seed_fx()
        write_series("yfinance", "EURUSD=X", {"2025-01-06": 9.9}, {"currency": "USD"})
        _, _, key_ = fx.rate("USD", "2025-01-06")
        self.assertEqual(key_, "ibkr/IDEALPRO_EURUSD")


# ---------------------------------------------------------------------------
# CLI: convert
# ---------------------------------------------------------------------------

class ConvertCliTest(StoreBackedTest):
    def test_convert_divides_by_the_rate(self):
        self.seed_fx()
        code, out, err = run(["convert", "250", "USD", "--date", "2025-01-06"])
        self.assertEqual(code, 0, err)
        self.assertIn("200.00", out)
        self.assertIn("USD", out)
        self.assertIn("1.25", out)
        self.assertIn("2025-01-06", out)
        self.assertIn("ibkr/IDEALPRO_EURUSD", out)

    def test_convert_json(self):
        self.seed_fx()
        code, out, err = run(["convert", "250", "USD", "--date", "2025-01-03", "--json"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertAlmostEqual(payload["rate"], 1.04, places=10)
        self.assertEqual(payload["rate_date"], "2025-01-02")
        self.assertEqual(payload["currency"], "USD")
        self.assertAlmostEqual(payload["amount"], 250.0, places=10)
        self.assertAlmostEqual(payload["amount_eur"], 250.0 / 1.04, places=10)
        self.assertEqual(payload["fx_key"], "ibkr/IDEALPRO_EURUSD")

    def test_convert_euro_is_the_identity(self):
        code, out, err = run(["convert", "12.5", "EUR", "--json"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["rate"], 1.0)
        self.assertAlmostEqual(payload["amount_eur"], 12.5, places=10)

    def test_convert_without_a_pair_exits_one(self):
        code, _, err = run(["convert", "10", "SEK"])
        self.assertEqual(code, 1)
        self.assertIn("SEK", err)

    def test_convert_before_the_first_bar_exits_one(self):
        self.seed_fx()
        code, _, err = run(["convert", "10", "USD", "--date", "2024-12-31"])
        self.assertEqual(code, 1)
        self.assertIn("2024-12-31", err)


# ---------------------------------------------------------------------------
# CLI: series
# ---------------------------------------------------------------------------

class SeriesCliTest(StoreBackedTest):
    #: Two sessions with different rates, so the conversion cannot be a
    #: constant scale factor.
    PRICES = {"2025-01-02": 208.0, "2025-01-06": 250.0, "2025-01-07": 120.0}

    def seed_equity(self, source="yfinance", key_="TESTA", currency="USD"):
        write_series(source, key_, self.PRICES,
                     {"currency": currency, "adjusted": True, "delayed_sec": 900,
                      "symbol": "TESTA", "exchange": "NMS"})

    def test_series_writes_a_derived_entry_with_provenance(self):
        self.seed_fx()
        self.seed_equity()
        code, out, err = run(["series", "TESTA", "--to", "EUR"])
        self.assertEqual(code, 0, err)

        rows, meta = store.read_bars("yfinance", "TESTA_EUR", "1d")
        self.assertEqual(meta["currency"], "EUR")
        self.assertEqual(meta["derived_from"], "yfinance/TESTA_1d")
        self.assertEqual(meta["fx_key"], "ibkr/IDEALPRO_EURUSD")
        self.assertEqual(meta["adjusted"], True)
        self.assertEqual(meta["delayed_sec"], 900)
        self.assertEqual(meta["key"], "TESTA_EUR")
        self.assertEqual(meta["bar_count"], 3)
        self.assertIn("TESTA_EUR", out)

    def test_series_converts_each_bar_at_that_date_rate(self):
        self.seed_fx()
        self.seed_equity()
        code, _, err = run(["series", "TESTA", "--to", "EUR"])
        self.assertEqual(code, 0, err)
        rows, _ = store.read_bars("yfinance", "TESTA_EUR", "1d")
        by_date = dict((row["date"], row) for row in rows)
        # 208.00 USD / 1.04 = 200.00 EUR; 250.00 USD / 1.25 = 200.00 EUR
        self.assertAlmostEqual(by_date["2025-01-02"]["close"], 200.0, places=9)
        self.assertAlmostEqual(by_date["2025-01-06"]["close"], 200.0, places=9)
        self.assertAlmostEqual(by_date["2025-01-07"]["close"], 100.0, places=9)
        for field in ("open", "high", "low"):
            self.assertAlmostEqual(by_date["2025-01-06"][field], 200.0, places=9)
        self.assertAlmostEqual(by_date["2025-01-06"]["volume"], 1000.0, places=9)

    def test_series_refuses_a_euro_source(self):
        self.seed_fx()
        self.seed_equity(currency="EUR")
        code, _, err = run(["series", "TESTA", "--to", "EUR"])
        self.assertEqual(code, 1)
        self.assertIn("EUR", err)
        self.assertEqual(store.find_entries("TESTA_EUR"), [])

    def test_series_refuses_an_unknown_source_currency(self):
        self.seed_fx()
        self.seed_equity(currency=None)
        code, _, err = run(["series", "TESTA", "--to", "EUR"])
        self.assertEqual(code, 1)
        self.assertIn("currency", err)

    def test_series_refuses_a_non_eur_target(self):
        self.seed_fx()
        self.seed_equity()
        code, _, err = run(["series", "TESTA", "--to", "USD"])
        self.assertEqual(code, 1)
        self.assertIn("EUR", err)

    def test_series_resolves_the_source_slash_key_form(self):
        self.seed_fx()
        self.seed_equity(source="yfinance")
        self.seed_equity(source="ibkr")
        code, _, err = run(["series", "TESTA", "--to", "EUR"])
        self.assertEqual(code, 1)
        self.assertIn("ambiguous", err)
        code, out, err = run(["series", "ibkr/TESTA", "--to", "EUR"])
        self.assertEqual(code, 0, err)
        self.assertEqual(store.read_meta("ibkr", "TESTA_EUR", "1d")["currency"], "EUR")

    def test_series_exits_one_when_a_bar_predates_every_fx_bar(self):
        self.seed_fx(rates={"2025-01-06": 1.25})
        self.seed_equity()
        code, _, err = run(["series", "TESTA", "--to", "EUR"])
        self.assertEqual(code, 1)
        self.assertIn("2025-01-02", err)

    def test_series_json(self):
        self.seed_fx()
        self.seed_equity()
        code, out, err = run(["series", "TESTA", "--to", "EUR", "--json"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["key"], "TESTA_EUR")
        self.assertEqual(payload["from_currency"], "USD")
        self.assertEqual(payload["to_currency"], "EUR")
        self.assertEqual(payload["bar_count"], 3)
        self.assertEqual(payload["derived_from"], "yfinance/TESTA_1d")

    def test_series_reads_the_fx_entry_once(self):
        """A ten-bar conversion must not re-read the FX CSV ten times."""
        days = ["2025-01-%02d" % day for day in range(2, 12)]
        self.seed_fx(rates=dict((day, 1.0 + index / 100.0)
                                for index, day in enumerate(days)))
        write_series("yfinance", "TESTA",
                     dict((day, 100.0 + index) for index, day in enumerate(days)),
                     {"currency": "USD", "adjusted": True})

        seen = []
        original = store.read_bars

        def counting(source, key_, interval):
            seen.append((source, key_, interval))
            return original(source, key_, interval)

        store.read_bars = counting
        try:
            code, _, err = run(["series", "TESTA", "--to", "EUR"])
        finally:
            store.read_bars = original

        self.assertEqual(code, 0, err)
        fx_reads = [entry for entry in seen if entry[1] == "IDEALPRO_EURUSD"]
        self.assertEqual(fx_reads, [("ibkr", "IDEALPRO_EURUSD", "1d")])
        # exactly two reads in total: the source entry and the FX pair
        self.assertEqual(len(seen), 2)

        rows, _ = store.read_bars("yfinance", "TESTA_EUR", "1d")
        by_date = dict((row["date"], row["close"]) for row in rows)
        # each bar is still converted at its own session's rate
        self.assertAlmostEqual(by_date["2025-01-02"], 100.0 / 1.00, places=9)
        self.assertAlmostEqual(by_date["2025-01-11"], 109.0 / 1.09, places=9)

    def test_series_prints_no_bar_rows(self):
        self.seed_fx()
        self.seed_equity()
        _, out, _ = run(["series", "TESTA", "--to", "EUR"])
        # neither the source prices nor the converted ones, and no interior
        # session date (the first and last are named as the range).
        for close in (208.0, 250.0, 120.0, 200.0, 100.0):
            self.assertNotIn(repr(close), out)
        self.assertNotIn("2025-01-06", out)


class ParserTest(unittest.TestCase):
    def test_help_documents_the_source_slash_key_form(self):
        parser = fx.build_parser()
        out = io.StringIO()
        with redirect_stdout(out):
            try:
                parser.parse_args(["series", "--help"])
            except SystemExit:
                pass
        self.assertIn("source/KEY", out.getvalue())

    def test_no_subcommand_exits_one(self):
        code, _, _ = run([])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
