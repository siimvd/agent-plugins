"""Tests for the yfinance fetcher.

These run on the system Python 3.9, which has neither yfinance nor pandas, so
the module under test must import cleanly without them and every fetch goes
through a fake downloader. Nothing here touches the network or the real
~/.finance: FINANCE_STORE points at a temporary directory throughout. Tickers
are synthetic (TESTA.XX) except where a shape-specific case needs a realistic
suffix.
"""

from __future__ import annotations

import calendar
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fetch_yf  # noqa: E402
import registry  # noqa: E402
import store  # noqa: E402

#: Synthetic ISIN with a valid check digit; not issued to any real instrument.
ISIN_TESTA = "ZZ0000TESTA1"

NAN = float("nan")


def epoch(text):
    """Return epoch seconds for a ``YYYY-MM-DDTHH:MM:SSZ`` string."""
    return calendar.timegm(
        tuple(
            int(part)
            for part in (
                text[0:4],
                text[5:7],
                text[8:10],
                text[11:13],
                text[14:16],
                text[17:19],
                0,
                0,
                0,
            )
        )
    )


def bar(local_date, stamp, close=10.0, volume=100.0):
    """Build one downloader row the way the real wrapper flattens a DataFrame."""
    return {
        "local_date": local_date,
        "epoch": epoch(stamp),
        "open": close - 1.0,
        "high": close + 1.0,
        "low": close - 2.0,
        "close": close,
        "volume": volume,
    }


class FakeDownloader:
    """Stand-in for the yfinance wrapper; returns plain rows, needs no pandas."""

    def __init__(self, rows=None, fast=None, info=None, info_error=None):
        self.rows = [] if rows is None else rows
        self.fast = {} if fast is None else fast
        self._info = {} if info is None else info
        self.info_error = info_error
        self.calls = []

    def history(self, ticker, period, interval):
        self.calls.append(("history", ticker, period, interval))
        return list(self.rows)

    def fast_info(self, ticker):
        self.calls.append(("fast_info", ticker))
        return dict(self.fast)

    def info(self, ticker):
        self.calls.append(("info", ticker))
        if self.info_error is not None:
            raise self.info_error
        return dict(self._info)


class FetchYfTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="finance-fetchyf-test-")
        self._prev = os.environ.get("FINANCE_STORE")
        os.environ["FINANCE_STORE"] = self.tmp

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("FINANCE_STORE", None)
        else:
            os.environ["FINANCE_STORE"] = self._prev
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, argv, downloader):
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = fetch_yf.main(argv, downloader=downloader)
        return code, out.getvalue(), err.getvalue()

    def read_csv(self, key_, interval="1d"):
        csv_path, _ = store.paths("yfinance", key_, interval)
        with open(csv_path) as handle:
            return handle.read().strip().splitlines()


class ImportSurfaceTest(FetchYfTestCase):
    def test_module_imports_without_yfinance(self):
        self.assertNotIn("yfinance", sys.modules)
        self.assertNotIn("pandas", sys.modules)


def daily_rows():
    """Two Amsterdam daily bars, each stamped at local midnight (22:00Z prior)."""
    return [
        bar("2026-09-03", "2026-09-02T22:00:00Z", close=10.0),
        bar("2026-09-04", "2026-09-03T22:00:00Z", close=11.0),
    ]


class BarsTest(FetchYfTestCase):
    def test_writes_csv_and_sidecar(self):
        fake = FakeDownloader(
            rows=daily_rows(),
            fast={"currency": "eur", "exchange": "AMS"},
        )
        sidecar = fetch_yf.fetch_bars("TESTA.AS", downloader=fake)

        self.assertEqual(sidecar["source"], "yfinance")
        self.assertEqual(sidecar["key"], "TESTA.AS")
        self.assertEqual(sidecar["symbol"], "TESTA.AS")
        self.assertEqual(sidecar["currency"], "EUR")
        self.assertEqual(sidecar["exchange"], "AMS")
        self.assertEqual(sidecar["adjusted"], True)
        self.assertEqual(sidecar["price_source"], "Close")
        self.assertEqual(sidecar["delayed_sec"], 0)
        self.assertIsNone(sidecar["contract_id"])
        self.assertIsNone(sidecar["isin"])
        self.assertEqual(sidecar["bar_count"], 2)
        self.assertEqual(sidecar["interval"], "1d")
        self.assertEqual(("history", "TESTA.AS", "1y", "1d"), fake.calls[0])

        lines = self.read_csv("TESTA.AS")
        self.assertEqual(lines[0], "date,open,high,low,close,volume")
        self.assertEqual(len(lines), 3)

    def test_daily_dates_use_the_exchange_local_session_date(self):
        # The 2026-09-04 bar is stamped 2026-09-03T22:00Z (Amsterdam midnight).
        # A UTC conversion would file it under 2026-09-03; the calendar date of
        # the index is what the venue means by that session.
        fake = FakeDownloader(rows=daily_rows(), fast={"currency": "EUR"})
        sidecar = fetch_yf.fetch_bars("TESTA.AS", downloader=fake)

        self.assertEqual(sidecar["start"], "2026-09-03")
        self.assertEqual(sidecar["end"], "2026-09-04")
        self.assertTrue(self.read_csv("TESTA.AS")[2].startswith("2026-09-04,"))

    def test_intraday_dates_are_utc_datetimes(self):
        fake = FakeDownloader(rows=daily_rows(), fast={"currency": "EUR"})
        sidecar = fetch_yf.fetch_bars(
            "TESTA.AS", period="5d", interval="5m", downloader=fake
        )

        self.assertEqual(sidecar["interval"], "5m")
        self.assertEqual(sidecar["end"], "2026-09-03T22:00:00Z")

    def test_weekly_interval_is_mapped_to_the_store_name(self):
        fake = FakeDownloader(rows=daily_rows(), fast={"currency": "EUR"})
        sidecar = fetch_yf.fetch_bars(
            "TESTA.AS", interval="1wk", downloader=fake
        )

        self.assertEqual(sidecar["interval"], "1w")
        self.assertEqual(sidecar["end"], "2026-09-04")
        self.assertEqual(("history", "TESTA.AS", "1y", "1wk"), fake.calls[0])

    def test_rows_with_a_nan_close_are_skipped(self):
        rows = daily_rows()
        rows.append(bar("2026-09-07", "2026-09-06T22:00:00Z", close=NAN))
        fake = FakeDownloader(rows=rows, fast={"currency": "EUR"})

        sidecar = fetch_yf.fetch_bars("TESTA.AS", downloader=fake)

        self.assertEqual(sidecar["bar_count"], 2)
        self.assertEqual(sidecar["end"], "2026-09-04")

    def test_nan_volume_becomes_null(self):
        rows = [bar("2026-09-04", "2026-09-03T22:00:00Z", volume=NAN)]
        fake = FakeDownloader(rows=rows, fast={"currency": "EUR"})

        fetch_yf.fetch_bars("TESTA.AS", downloader=fake)

        rows_read, _ = store.read_bars("yfinance", "TESTA.AS", "1d")
        self.assertIsNone(rows_read[0]["volume"])

    def test_empty_history_is_an_error(self):
        fake = FakeDownloader(rows=[], fast={"currency": "EUR"})
        with self.assertRaises(fetch_yf.FetchError):
            fetch_yf.fetch_bars("NOPE.XX", downloader=fake)

    def test_history_of_only_nan_rows_is_an_error(self):
        fake = FakeDownloader(
            rows=[bar("2026-09-04", "2026-09-03T22:00:00Z", close=NAN)],
            fast={"currency": "EUR"},
        )
        with self.assertRaises(fetch_yf.FetchError):
            fetch_yf.fetch_bars("TESTA.AS", downloader=fake)

    def test_registry_hit_fills_the_isin(self):
        registry.add(ISIN_TESTA, name="Test A", class_="etf", yahoo="TESTA.AS")
        fake = FakeDownloader(
            rows=daily_rows(), fast={"currency": "EUR"}
        )

        sidecar = fetch_yf.fetch_bars("TESTA.AS", downloader=fake)

        self.assertEqual(sidecar["isin"], ISIN_TESTA)

    def test_pence_quotes_are_converted_to_pounds(self):
        # Yahoo quotes most London lines in pence and marks it with the
        # case-sensitive "GBp". Storing 601.7 under currency GBP would be off
        # by a factor of 100 for anything reading the store later.
        rows = [bar("2026-09-04", "2026-09-03T23:00:00Z", close=601.7)]
        fake = FakeDownloader(rows=rows, fast={"currency": "GBp", "exchange": "LSE"})

        sidecar = fetch_yf.fetch_bars("TESTA.L", downloader=fake)

        self.assertEqual(sidecar["currency"], "GBP")
        self.assertEqual(sidecar["source_currency"], "GBp")
        self.assertEqual(sidecar["price_scale"], 0.01)

        stored, _ = store.read_bars("yfinance", "TESTA.L", "1d")
        self.assertAlmostEqual(stored[0]["close"], 6.017, delta=1e-9)
        self.assertAlmostEqual(stored[0]["open"], 6.007, delta=1e-9)
        self.assertEqual(stored[0]["volume"], 100.0)

    def test_gbx_is_treated_as_pence(self):
        rows = [bar("2026-09-04", "2026-09-03T23:00:00Z", close=601.7)]
        fake = FakeDownloader(rows=rows, fast={"currency": "GBX"})

        sidecar = fetch_yf.fetch_bars("TESTA.L", downloader=fake)

        self.assertEqual(sidecar["currency"], "GBP")
        self.assertEqual(sidecar["source_currency"], "GBX")
        self.assertEqual(sidecar["price_scale"], 0.01)

    def test_an_ordinary_currency_is_recorded_unscaled(self):
        fake = FakeDownloader(rows=daily_rows(), fast={"currency": "USD"})

        sidecar = fetch_yf.fetch_bars("TESTA", downloader=fake)

        self.assertEqual(sidecar["currency"], "USD")
        self.assertEqual(sidecar["source_currency"], "USD")
        self.assertEqual(sidecar["price_scale"], 1)

        stored, _ = store.read_bars("yfinance", "TESTA", "1d")
        self.assertEqual(stored[0]["close"], 10.0)

    def test_missing_fast_info_leaves_currency_null(self):
        fake = FakeDownloader(rows=daily_rows(), fast={})

        sidecar = fetch_yf.fetch_bars("TESTA.AS", downloader=fake)

        self.assertIsNone(sidecar["currency"])
        self.assertIsNone(sidecar["exchange"])


class BarsCliTest(FetchYfTestCase):
    def test_cli_prints_a_summary(self):
        fake = FakeDownloader(
            rows=daily_rows(), fast={"currency": "EUR", "exchange": "AMS"}
        )
        code, out, err = self.run_cli(
            ["bars", "TESTA.AS", "--period", "6mo"], fake
        )

        self.assertEqual(code, 0, err)
        self.assertIn("TESTA.AS", out)
        self.assertIn("bars", out)
        self.assertIn("2026-09-03 -> 2026-09-04", out)
        self.assertIn("EUR", out)
        self.assertIn("True", out)
        self.assertEqual(("history", "TESTA.AS", "6mo", "1d"), fake.calls[0])

    def test_cli_json_parses(self):
        fake = FakeDownloader(rows=daily_rows(), fast={"currency": "EUR"})
        code, out, err = self.run_cli(["bars", "TESTA.AS", "--json"], fake)

        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["adjusted"], True)
        self.assertEqual(payload["source"], "yfinance")

    def test_cli_empty_history_exits_1(self):
        fake = FakeDownloader(rows=[])
        code, out, err = self.run_cli(["bars", "NOPE.XX"], fake)

        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("NOPE.XX", err)


class InfoTest(FetchYfTestCase):
    def fundamentals_path(self, ticker):
        return os.path.join(self.tmp, "fundamentals", "%s.json" % ticker)

    def test_whitelist_keeps_known_keys_and_drops_the_rest(self):
        fake = FakeDownloader(
            info={
                "shortName": "Test A",
                "sector": "Technology",
                "marketCap": 1234567,
                "currency": "USD",
                "longBusinessSummary": "a very long paragraph",
                "companyOfficers": [{"name": "someone"}],
            }
        )

        payload = fetch_yf.fetch_info("TESTA", downloader=fake)

        self.assertEqual(payload["shortName"], "Test A")
        self.assertEqual(payload["marketCap"], 1234567)
        self.assertNotIn("longBusinessSummary", payload)
        self.assertNotIn("companyOfficers", payload)
        self.assertNotIn("industry", payload)
        self.assertEqual(payload["ticker"], "TESTA")
        self.assertIn("fetched_at", payload)

        with open(self.fundamentals_path("TESTA")) as handle:
            self.assertEqual(json.load(handle), payload)

    def test_exception_from_yahoo_writes_a_note_and_exits_0(self):
        fake = FakeDownloader(
            info_error=Exception("404 Client Error: No fundamentals data found")
        )
        code, out, err = self.run_cli(["info", "TESTETF.DE"], fake)

        self.assertEqual(code, 0, err)
        self.assertIn("no fundamentals data", out)
        with open(self.fundamentals_path("TESTETF.DE")) as handle:
            payload = json.load(handle)
        self.assertEqual(payload["note"], "no fundamentals data")
        self.assertEqual(payload["ticker"], "TESTETF.DE")
        self.assertIn("fetched_at", payload)
        self.assertNotIn("marketCap", payload)

    def test_info_without_any_whitelisted_key_writes_a_note(self):
        fake = FakeDownloader(info={"trailingPegRatio": None, "maxAge": 1})

        payload = fetch_yf.fetch_info("TESTETF.DE", downloader=fake)

        self.assertEqual(payload["note"], "no fundamentals data")

    def test_cli_prints_the_whitelisted_values(self):
        fake = FakeDownloader(
            info={"shortName": "Test A", "marketCap": 42, "currency": "USD"}
        )
        code, out, err = self.run_cli(["info", "TESTA"], fake)

        self.assertEqual(code, 0, err)
        self.assertIn("marketCap", out)
        self.assertIn("42", out)

    def test_cli_json_parses(self):
        fake = FakeDownloader(info={"shortName": "Test A", "currency": "USD"})
        code, out, err = self.run_cli(["info", "TESTA", "--json"], fake)

        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["shortName"], "Test A")


if __name__ == "__main__":
    unittest.main()
