"""Tests for the on-disk bar store.

Every test points FINANCE_STORE at a temporary directory so nothing touches
the real ~/.finance. Instruments are synthetic (TESTA / TESTB).
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

import store  # noqa: E402


def make_rows(n=3):
    rows = []
    for i in range(n):
        rows.append(
            {
                "date": "2026-01-%02d" % (i + 1),
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 1000.0 + i,
            }
        )
    return rows


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="finance-store-test-")
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
            code = store.main(argv)
        return code, out.getvalue(), err.getvalue()


class TestRoot(StoreTestCase):
    def test_env_override_is_honoured(self):
        self.assertEqual(store.root(), self.tmp)

    def test_default_root_is_home_finance(self):
        os.environ.pop("FINANCE_STORE", None)
        self.assertEqual(store.root(), os.path.join(os.path.expanduser("~"), ".finance"))

    def test_root_expands_user_and_env_vars(self):
        os.environ["FINANCE_STORE"] = "~/some-store"
        self.assertEqual(
            store.root(), os.path.join(os.path.expanduser("~"), "some-store")
        )


class TestKey(unittest.TestCase):
    def test_ibkr_key_is_exchange_underscore_symbol(self):
        self.assertEqual(store.key("ibkr", "IBIS2", "TESTA"), "IBIS2_TESTA")

    def test_ibkr_key_is_upper_cased(self):
        self.assertEqual(store.key("ibkr", "ibis2", "testa"), "IBIS2_TESTA")

    def test_yfinance_key_is_the_raw_ticker(self):
        self.assertEqual(store.key("yfinance", "GER", "TESTA.DE"), "TESTA.DE")
        self.assertEqual(store.key("yfinance", None, "TESTFX=X"), "TESTFX=X")

    def test_ibkr_key_without_exchange_falls_back_to_symbol(self):
        self.assertEqual(store.key("ibkr", None, "TESTA"), "TESTA")


class TestSessionDate(unittest.TestCase):
    def test_daily_epoch_is_utc_date(self):
        self.assertEqual(store.session_date(1788566398, "1d"), "2026-09-04")

    def test_weekly_and_monthly_are_dates(self):
        self.assertEqual(store.session_date(1788566398, "1w"), "2026-09-04")
        self.assertEqual(store.session_date(1788566398, "1mo"), "2026-09-04")

    def test_float_epoch_accepted(self):
        self.assertEqual(store.session_date(1788566398.0, "1d"), "2026-09-04")

    def test_iso_string_input(self):
        self.assertEqual(store.session_date("2026-09-04T23:59:58Z", "1d"), "2026-09-04")
        self.assertEqual(store.session_date("2026-09-04", "1d"), "2026-09-04")

    def test_iso_string_with_offset_is_normalised_to_utc(self):
        # 2026-09-05T01:30:00+03:00 is 2026-09-04T22:30:00Z.
        self.assertEqual(
            store.session_date("2026-09-05T01:30:00+03:00", "1d"), "2026-09-04"
        )

    def test_intraday_keeps_time(self):
        self.assertEqual(
            store.session_date(1788566398, "1h"), "2026-09-04T23:59:58Z"
        )
        self.assertEqual(
            store.session_date("2026-09-04T21:15:00Z", "5m"), "2026-09-04T21:15:00Z"
        )

    def test_fx_evening_bar_carries_that_calendar_day(self):
        # 21:15Z is still 2026-09-04 in UTC; the docstring documents that this
        # is the prior calendar day for venues stamping the close after
        # midnight local time.
        self.assertEqual(store.session_date("2026-09-04T21:15:00Z", "1d"), "2026-09-04")

    def test_bad_input_raises_value_error(self):
        with self.assertRaises(ValueError):
            store.session_date("not-a-date", "1d")


class TestWriteRead(StoreTestCase):
    def test_round_trip_rows_and_meta(self):
        rows = make_rows(3)
        meta = store.write_bars(
            "ibkr",
            "IBIS2_TESTA",
            "1d",
            rows,
            {
                "symbol": "TESTA",
                "exchange": "IBIS2",
                "currency": "EUR",
                "contract_id": 101,
                "isin": None,
                "adjusted": None,
                "delayed_sec": 900,
                "price_source": "Last",
            },
        )
        self.assertEqual(meta["schema_version"], 1)
        self.assertEqual(meta["source"], "ibkr")
        self.assertEqual(meta["key"], "IBIS2_TESTA")
        self.assertEqual(meta["interval"], "1d")
        self.assertEqual(meta["bar_count"], 3)
        self.assertEqual(meta["start"], "2026-01-01")
        self.assertEqual(meta["end"], "2026-01-03")
        self.assertTrue(meta["fetched_at"].endswith("Z"))

        back_rows, back_meta = store.read_bars("ibkr", "IBIS2_TESTA", "1d")
        self.assertEqual(len(back_rows), 3)
        self.assertEqual(back_rows[0]["date"], "2026-01-01")
        self.assertEqual(back_rows[0]["open"], 100.0)
        self.assertEqual(back_rows[2]["close"], 102.5)
        self.assertEqual(back_rows[1]["volume"], 1001.0)
        self.assertIsInstance(back_rows[0]["close"], float)
        self.assertEqual(back_meta, meta)

    def test_files_land_at_the_documented_paths(self):
        store.write_bars("ibkr", "IBIS2_TESTA", "1d", make_rows(2), {})
        base = os.path.join(self.tmp, "bars", "ibkr")
        self.assertTrue(os.path.isfile(os.path.join(base, "IBIS2_TESTA_1d.csv")))
        self.assertTrue(os.path.isfile(os.path.join(base, "IBIS2_TESTA_1d.meta.json")))

    def test_csv_header_and_order(self):
        store.write_bars("ibkr", "IBIS2_TESTA", "1d", make_rows(3), {})
        path = os.path.join(self.tmp, "bars", "ibkr", "IBIS2_TESTA_1d.csv")
        with open(path) as fh:
            lines = fh.read().splitlines()
        self.assertEqual(lines[0], "date,open,high,low,close,volume")
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[1].startswith("2026-01-01,"))
        self.assertTrue(lines[3].startswith("2026-01-03,"))

    def test_rows_are_sorted_ascending_on_write(self):
        rows = list(reversed(make_rows(3)))
        meta = store.write_bars("yfinance", "TESTA", "1d", rows, {})
        self.assertEqual(meta["start"], "2026-01-01")
        self.assertEqual(meta["end"], "2026-01-03")
        back, _ = store.read_bars("yfinance", "TESTA", "1d")
        self.assertEqual([r["date"] for r in back], ["2026-01-01", "2026-01-02", "2026-01-03"])

    def test_volume_none_round_trips_as_empty_cell(self):
        rows = make_rows(2)
        for row in rows:
            row["volume"] = None
        store.write_bars("ibkr", "IDEALPRO_TESTFX", "1d", rows, {"price_source": "MidPoint"})
        path = os.path.join(self.tmp, "bars", "ibkr", "IDEALPRO_TESTFX_1d.csv")
        with open(path) as fh:
            lines = fh.read().splitlines()
        self.assertTrue(lines[1].endswith(","))
        back, meta = store.read_bars("ibkr", "IDEALPRO_TESTFX", "1d")
        self.assertIsNone(back[0]["volume"])
        self.assertIsNone(back[1]["volume"])
        self.assertEqual(meta["price_source"], "MidPoint")

    def test_nullable_meta_fields_written_as_json_null(self):
        store.write_bars("yfinance", "TESTA", "1d", make_rows(2), {"adjusted": True})
        path = os.path.join(self.tmp, "bars", "yfinance", "TESTA_1d.meta.json")
        with open(path) as fh:
            raw = json.load(fh)
        for field in ("contract_id", "isin", "exchange", "currency"):
            self.assertIn(field, raw)
            self.assertIsNone(raw[field])
        self.assertIs(raw["adjusted"], True)

    def test_write_creates_the_store_directory(self):
        nested = os.path.join(self.tmp, "deep", "nested")
        os.environ["FINANCE_STORE"] = nested
        store.write_bars("ibkr", "IBIS2_TESTA", "1d", make_rows(1), {})
        self.assertTrue(os.path.isfile(
            os.path.join(nested, "bars", "ibkr", "IBIS2_TESTA_1d.csv")
        ))

    def test_write_rejects_empty_rows(self):
        with self.assertRaises(ValueError):
            store.write_bars("ibkr", "IBIS2_TESTA", "1d", [], {})

    def test_write_rejects_row_missing_close(self):
        rows = make_rows(3)
        del rows[1]["close"]
        with self.assertRaises(ValueError) as caught:
            store.write_bars("ibkr", "IBIS2_TESTA", "1d", rows, {})
        message = str(caught.exception)
        self.assertIn("1", message)
        self.assertIn("close", message)
        csv_path, _ = store.paths("ibkr", "IBIS2_TESTA", "1d")
        self.assertFalse(os.path.exists(csv_path))

    def test_write_rejects_row_with_none_price(self):
        rows = make_rows(2)
        rows[0]["open"] = None
        with self.assertRaises(ValueError):
            store.write_bars("ibkr", "IBIS2_TESTA", "1d", rows, {})

    def test_write_rejects_row_missing_date(self):
        rows = make_rows(2)
        del rows[0]["date"]
        with self.assertRaises(ValueError) as caught:
            store.write_bars("ibkr", "IBIS2_TESTA", "1d", rows, {})
        self.assertIn("date", str(caught.exception))

    def test_write_rejects_duplicate_dates(self):
        rows = make_rows(3)
        rows[2]["date"] = rows[0]["date"]
        with self.assertRaises(store.StoreError) as caught:
            store.write_bars("ibkr", "IBIS2_TESTA", "1d", rows, {})
        message = str(caught.exception)
        self.assertIn(rows[0]["date"], message)
        self.assertIn("0", message)
        self.assertIn("2", message)
        csv_path, meta_path = store.paths("ibkr", "IBIS2_TESTA", "1d")
        self.assertFalse(os.path.exists(csv_path))
        self.assertFalse(os.path.exists(meta_path))

    def test_write_accepts_row_with_no_volume_key(self):
        rows = make_rows(2)
        for row in rows:
            del row["volume"]
        meta = store.write_bars("ibkr", "IDEALPRO_TESTFX", "1d", rows, {})
        self.assertEqual(meta["bar_count"], 2)
        back, _ = store.read_bars("ibkr", "IDEALPRO_TESTFX", "1d")
        self.assertIsNone(back[0]["volume"])
        self.assertEqual(back[1]["close"], 101.5)

    def test_intraday_entry_round_trips(self):
        rows = [
            {
                "date": "2026-09-04T20:00:00Z",
                "open": 1.0,
                "high": 1.1,
                "low": 0.9,
                "close": 1.05,
                "volume": None,
            },
            {
                "date": "2026-09-04T21:00:00Z",
                "open": 1.05,
                "high": 1.2,
                "low": 1.0,
                "close": 1.15,
                "volume": None,
            },
        ]
        meta = store.write_bars("ibkr", "IDEALPRO_TESTFX", "1h", rows, {})
        self.assertEqual(meta["start"], "2026-09-04T20:00:00Z")
        back, _ = store.read_bars("ibkr", "IDEALPRO_TESTFX", "1h")
        self.assertEqual(back[1]["date"], "2026-09-04T21:00:00Z")

    def test_read_missing_entry_raises(self):
        with self.assertRaises(store.StoreError):
            store.read_bars("ibkr", "NOPE_TESTA", "1d")

    def test_read_meta(self):
        store.write_bars("ibkr", "IBIS2_TESTA", "1d", make_rows(2), {"currency": "EUR"})
        meta = store.read_meta("ibkr", "IBIS2_TESTA", "1d")
        self.assertEqual(meta["currency"], "EUR")
        self.assertEqual(meta["bar_count"], 2)

    def test_read_meta_missing_raises(self):
        with self.assertRaises(store.StoreError):
            store.read_meta("ibkr", "NOPE_TESTA", "1d")


class TestListEntries(StoreTestCase):
    def populate(self):
        store.write_bars("ibkr", "IBIS2_TESTA", "1d", make_rows(2), {})
        store.write_bars("ibkr", "IBIS2_TESTB", "1w", make_rows(2), {})
        store.write_bars("yfinance", "TESTA.DE", "1d", make_rows(2), {})

    def test_lists_all_entries_sorted(self):
        self.populate()
        self.assertEqual(
            store.list_entries(),
            [
                ("ibkr", "IBIS2_TESTA", "1d"),
                ("ibkr", "IBIS2_TESTB", "1w"),
                ("yfinance", "TESTA.DE", "1d"),
            ],
        )

    def test_filters_by_source(self):
        self.populate()
        self.assertEqual(
            store.list_entries("yfinance"), [("yfinance", "TESTA.DE", "1d")]
        )
        self.assertEqual(len(store.list_entries("ibkr")), 2)

    def test_empty_store_lists_nothing(self):
        self.assertEqual(store.list_entries(), [])


class TestCli(StoreTestCase):
    def populate(self):
        store.write_bars(
            "ibkr",
            "IBIS2_TESTA",
            "1d",
            make_rows(3),
            {"symbol": "TESTA", "exchange": "IBIS2", "currency": "EUR"},
        )
        store.write_bars("yfinance", "TESTA.DE", "1d", make_rows(3), {"adjusted": True})

    def test_list_reports_entries(self):
        self.populate()
        code, out, err = self.run_cli(["list"])
        self.assertEqual(code, 0, err)
        self.assertIn("IBIS2_TESTA", out)
        self.assertIn("TESTA.DE", out)

    def test_list_filters_by_source(self):
        self.populate()
        code, out, _ = self.run_cli(["list", "--source", "yfinance"])
        self.assertEqual(code, 0)
        self.assertIn("TESTA.DE", out)
        self.assertNotIn("IBIS2_TESTA", out)

    def test_list_json(self):
        self.populate()
        code, out, _ = self.run_cli(["list", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(len(payload), 2)
        self.assertEqual(
            sorted(e["key"] for e in payload), ["IBIS2_TESTA", "TESTA.DE"]
        )

    def test_list_empty_store_exits_zero(self):
        code, out, _ = self.run_cli(["list"])
        self.assertEqual(code, 0)
        self.assertTrue(out.strip())

    def test_show_prints_sidecar_never_bar_rows(self):
        self.populate()
        code, out, _ = self.run_cli(["show", "IBIS2_TESTA"])
        self.assertEqual(code, 0)
        self.assertIn("bar_count", out)
        self.assertIn("EUR", out)
        for row in make_rows(3):
            self.assertNotIn("%.1f" % row["high"], out)
            self.assertNotIn("%.1f" % row["open"], out)
        self.assertNotIn("2026-01-02", out)

    def test_show_json_has_no_rows_key(self):
        self.populate()
        code, out, _ = self.run_cli(["show", "IBIS2_TESTA", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertNotIn("rows", payload)
        self.assertEqual(payload["key"], "IBIS2_TESTA")
        self.assertEqual(payload["bar_count"], 3)

    def test_show_missing_key_exits_one(self):
        self.populate()
        code, out, err = self.run_cli(["show", "NOSUCH"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("NOSUCH", err)

    def test_show_ambiguous_key_exits_one(self):
        store.write_bars("ibkr", "IBIS2_TESTA", "1d", make_rows(2), {})
        store.write_bars("ibkr", "IBIS2_TESTA", "1w", make_rows(2), {})
        code, out, err = self.run_cli(["show", "IBIS2_TESTA"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("ambiguous", err.lower())

    def test_show_ambiguous_resolved_by_interval(self):
        store.write_bars("ibkr", "IBIS2_TESTA", "1d", make_rows(2), {})
        store.write_bars("ibkr", "IBIS2_TESTA", "1w", make_rows(2), {})
        code, out, err = self.run_cli(["show", "IBIS2_TESTA", "--interval", "1w"])
        self.assertEqual(code, 0, err)
        self.assertIn("1w", out)

    def test_show_ambiguous_resolved_by_source(self):
        self.populate()
        store.write_bars("yfinance", "IBIS2_TESTA", "1d", make_rows(2), {})
        code, _, err = self.run_cli(["show", "IBIS2_TESTA"])
        self.assertEqual(code, 1)
        code, out, err = self.run_cli(["show", "IBIS2_TESTA", "--source", "ibkr"])
        self.assertEqual(code, 0, err)
        self.assertIn("ibkr", out)


class TestPathComponentValidation(StoreTestCase):
    """A key or interval must never be able to steer a write out of the root."""

    #: Keys that must be refused: traversal, separators, empty, over-long.
    BAD_KEYS = ("../escape", "a/b", "..", "", "A" * 65)

    #: Real-world keys that must keep working.
    GOOD_KEYS = ("VWCE.DE", "LIFCO-B.ST", "EURUSD=X", "^GSPC", "IBIS2_VWCE")

    def setUp(self):
        super().setUp()
        self.sandbox = self.tmp
        self.store_root = os.path.join(self.sandbox, "store")
        os.makedirs(self.store_root)
        os.environ["FINANCE_STORE"] = self.store_root

    def assert_nothing_escaped(self):
        self.assertEqual(sorted(os.listdir(self.sandbox)), ["store"])

    def test_write_bars_rejects_bad_keys(self):
        for bad in self.BAD_KEYS:
            with self.subTest(key=bad):
                with self.assertRaises(store.StoreError):
                    store.write_bars("yfinance", bad, "1d", make_rows(2), {})
                self.assert_nothing_escaped()

    def test_read_bars_rejects_bad_keys(self):
        for bad in self.BAD_KEYS:
            with self.subTest(key=bad):
                with self.assertRaises(store.StoreError):
                    store.read_bars("yfinance", bad, "1d")
                self.assert_nothing_escaped()

    def test_escaping_key_writes_nothing_outside_the_root(self):
        # bars/<source>/ is two levels below the root, so three ".." would
        # land the file in the sandbox beside the store itself.
        with self.assertRaises(store.StoreError):
            store.write_bars("yfinance", "../../../escaped", "1d", make_rows(2), {})
        self.assert_nothing_escaped()

    def test_good_keys_are_accepted(self):
        for good in self.GOOD_KEYS:
            with self.subTest(key=good):
                self.assertEqual(store.validate_key(good), good)
                store.write_bars("yfinance", good, "1d", make_rows(2), {})
                rows, meta = store.read_bars("yfinance", good, "1d")
                self.assertEqual(len(rows), 2)
                self.assertEqual(meta["key"], good)

    def test_good_intervals_are_accepted(self):
        for good in ("1d", "1wk", "1mo", "5m", "1w", "1h", "15m", "60m"):
            with self.subTest(interval=good):
                self.assertEqual(store.validate_interval(good), good)

    def test_bad_intervals_are_rejected(self):
        for bad in ("../x", "1d/../x", "", "d", "1y", "1d/", "1" * 65):
            with self.subTest(interval=bad):
                with self.assertRaises(store.StoreError):
                    store.validate_interval(bad)

    def test_write_bars_rejects_a_traversing_interval(self):
        with self.assertRaises(store.StoreError):
            store.write_bars("yfinance", "TESTA", "../../../x", make_rows(2), {})
        self.assert_nothing_escaped()

    def test_paths_rejects_a_traversing_source(self):
        with self.assertRaises(store.StoreError):
            store.paths("../../..", "TESTA", "1d")

    def test_paths_rejects_bad_sources(self):
        # "../s" resolves back inside the root but outside bars/<source>/, so
        # the root check alone would not catch it; the allowlist must.
        for bad in ("../s", "s/t", ".s", "", "s" * 33):
            with self.subTest(source=bad):
                with self.assertRaises(store.StoreError):
                    store.paths(bad, "TESTA", "1d")
                self.assert_nothing_escaped()

    def test_good_sources_are_accepted(self):
        for good in ("ibkr", "yfinance", "my-source"):
            with self.subTest(source=good):
                self.assertEqual(store.validate_source(good), good)
                csv_path, _ = store.paths(good, "TESTA", "1d")
                self.assertIn(os.path.join("bars", good), csv_path)

    def test_paths_of_a_valid_entry_stay_inside_the_root(self):
        csv_path, meta_path = store.paths("yfinance", "^GSPC", "1d")
        for path in (csv_path, meta_path):
            self.assertTrue(
                os.path.realpath(path).startswith(
                    os.path.realpath(self.store_root) + os.sep
                ),
                path,
            )


if __name__ == "__main__":
    unittest.main()
