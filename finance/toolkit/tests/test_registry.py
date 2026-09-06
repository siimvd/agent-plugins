"""Tests for the ISIN instrument registry.

Every test points FINANCE_STORE at a temporary directory so nothing touches
the real ~/.finance. Instrument names are synthetic ("Test Fund A"). The
ISINs below are used purely as check-digit examples and are never paired
with account data.
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

import registry  # noqa: E402

ISIN_A = "IE00BK5BQT80"
ISIN_B = "US5949181045"
ISIN_C = "NL0010273215"
ISIN_BAD = "IE00BK5BQT81"


class RegistryTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="finance-registry-test-")
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
            code = registry.main(argv)
        return code, out.getvalue(), err.getvalue()

    def read_file(self):
        with open(registry.path()) as handle:
            return handle.read()


class TestValidateIsin(RegistryTestCase):
    def test_accepts_valid_check_digits(self):
        for isin in (ISIN_A, ISIN_B, ISIN_C):
            self.assertTrue(registry.validate_isin(isin), isin)

    def test_rejects_bad_check_digit(self):
        self.assertFalse(registry.validate_isin(ISIN_BAD))

    def test_rejects_malformed_shapes(self):
        for bad in ("", "IE00BK5BQT8", "IE00BK5BQT800", "1E00BK5BQT80", "IE00BK5BQT8-"):
            self.assertFalse(registry.validate_isin(bad), bad)

    def test_accepts_lowercase_input(self):
        self.assertTrue(registry.validate_isin(ISIN_A.lower()))


class TestAddAndGet(RegistryTestCase):
    def test_add_then_get(self):
        added = registry.add(
            ISIN_A,
            name="Test Fund A",
            class_="etf",
            ibkr=[
                {
                    "contract_id": 111,
                    "exchange": "IBIS2",
                    "symbol": "TESTA",
                    "currency": "EUR",
                }
            ],
            yahoo="TESTA.DE",
        )
        self.assertEqual(added["name"], "Test Fund A")
        fetched = registry.get(ISIN_A)
        self.assertEqual(fetched, added)
        self.assertEqual(fetched["class"], "etf")
        self.assertEqual(fetched["yahoo"], "TESTA.DE")
        self.assertIsNone(fetched["lhv"])
        self.assertEqual(len(fetched["ibkr"]), 1)

    def test_get_unknown_raises(self):
        with self.assertRaises(registry.RegistryError):
            registry.get(ISIN_A)

    def test_get_invalid_isin_raises(self):
        with self.assertRaises(registry.RegistryError):
            registry.get(ISIN_BAD)

    def test_add_invalid_isin_raises(self):
        with self.assertRaises(registry.RegistryError):
            registry.add(ISIN_BAD, name="Test Fund A")

    def test_add_unknown_class_raises(self):
        with self.assertRaises(registry.RegistryError):
            registry.add(ISIN_A, class_="derivative")

    def test_isin_normalised_to_upper(self):
        registry.add(ISIN_A.lower(), name="Test Fund A")
        self.assertIn(ISIN_A, registry.load()["instruments"])
        self.assertEqual(registry.get(ISIN_A.lower())["name"], "Test Fund A")


class TestMerge(RegistryTestCase):
    def setUp(self):
        RegistryTestCase.setUp(self)
        registry.add(
            ISIN_A,
            name="Test Fund A",
            class_="etf",
            ibkr=[
                {
                    "contract_id": 111,
                    "exchange": "IBIS2",
                    "symbol": "TESTA",
                    "currency": "EUR",
                }
            ],
            yahoo="TESTA.DE",
        )

    def test_second_add_keeps_unsupplied_fields_and_appends_listing(self):
        merged = registry.add(
            ISIN_A,
            ibkr=[
                {
                    "contract_id": 222,
                    "exchange": "LSEETF",
                    "symbol": "TESTA",
                    "currency": "GBP",
                }
            ],
        )
        self.assertEqual(merged["name"], "Test Fund A")
        self.assertEqual(merged["class"], "etf")
        self.assertEqual(merged["yahoo"], "TESTA.DE")
        self.assertEqual(len(merged["ibkr"]), 2)
        pairs = sorted((e["exchange"], e["symbol"]) for e in merged["ibkr"])
        self.assertEqual(pairs, [("IBIS2", "TESTA"), ("LSEETF", "TESTA")])

    def test_same_exchange_symbol_listing_is_replaced(self):
        merged = registry.add(
            ISIN_A,
            ibkr=[
                {
                    "contract_id": 999,
                    "exchange": "IBIS2",
                    "symbol": "TESTA",
                    "currency": "EUR",
                }
            ],
        )
        self.assertEqual(len(merged["ibkr"]), 1)
        self.assertEqual(merged["ibkr"][0]["contract_id"], 999)

    def test_listing_match_is_case_insensitive(self):
        merged = registry.add(
            ISIN_A,
            ibkr=[
                {
                    "contract_id": 999,
                    "exchange": "ibis2",
                    "symbol": "testa",
                    "currency": "EUR",
                }
            ],
        )
        self.assertEqual(len(merged["ibkr"]), 1)
        self.assertEqual(merged["ibkr"][0]["contract_id"], 999)

    def test_yahoo_and_lhv_replaced_when_supplied(self):
        merged = registry.add(ISIN_A, yahoo="TESTA.L", lhv="TESTA")
        self.assertEqual(merged["yahoo"], "TESTA.L")
        self.assertEqual(merged["lhv"], "TESTA")

    def test_incomplete_listing_rejected(self):
        with self.assertRaises(registry.RegistryError):
            registry.add(ISIN_A, ibkr=[{"exchange": "IBIS2", "symbol": "TESTA"}])


class TestResolve(RegistryTestCase):
    def setUp(self):
        RegistryTestCase.setUp(self)
        registry.add(
            ISIN_A,
            name="Test Fund A",
            class_="etf",
            ibkr=[
                {
                    "contract_id": 111,
                    "exchange": "IBIS2",
                    "symbol": "TESTA",
                    "currency": "EUR",
                }
            ],
            yahoo="TESTA.DE",
            lhv="TESTA",
        )
        registry.add(ISIN_B, name="Test Corp B", class_="equity", yahoo="TESTB")

    def test_resolve_yahoo(self):
        self.assertEqual(registry.resolve_yahoo("TESTA.DE"), ISIN_A)
        self.assertEqual(registry.resolve_yahoo("TESTB"), ISIN_B)

    def test_resolve_ibkr_case_insensitive(self):
        self.assertEqual(registry.resolve_ibkr("IBIS2", "TESTA"), ISIN_A)
        self.assertEqual(registry.resolve_ibkr("ibis2", "testa"), ISIN_A)

    def test_resolve_lhv(self):
        self.assertEqual(registry.resolve_lhv("TESTA"), ISIN_A)

    def test_resolve_misses_raise(self):
        with self.assertRaises(registry.RegistryError):
            registry.resolve_yahoo("NOPE")
        with self.assertRaises(registry.RegistryError):
            registry.resolve_ibkr("IBIS2", "NOPE")
        with self.assertRaises(registry.RegistryError):
            registry.resolve_lhv("NOPE")


class TestFile(RegistryTestCase):
    def test_file_created_on_first_add(self):
        self.assertFalse(os.path.exists(registry.path()))
        registry.add(ISIN_A, name="Test Fund A")
        self.assertTrue(os.path.isfile(registry.path()))
        data = json.loads(self.read_file())
        self.assertEqual(data["schema_version"], 1)
        self.assertIn(ISIN_A, data["instruments"])

    def test_root_created_when_missing(self):
        nested = os.path.join(self.tmp, "deep", "store")
        os.environ["FINANCE_STORE"] = nested
        registry.add(ISIN_A, name="Test Fund A")
        self.assertTrue(os.path.isfile(os.path.join(nested, "registry.json")))

    def test_file_is_sorted_and_indented(self):
        registry.add(ISIN_C, name="Test Fund C")
        registry.add(ISIN_A, name="Test Fund A")
        text = self.read_file()
        self.assertLess(text.index(ISIN_A), text.index(ISIN_C))
        self.assertLess(text.index('"instruments"'), text.index('"schema_version"'))
        self.assertIn('\n  "instruments": {', text)
        self.assertTrue(text.endswith("\n"))

    def test_load_on_empty_store(self):
        reg = registry.load()
        self.assertEqual(reg, {"schema_version": 1, "instruments": {}})

    def test_malformed_file_raises(self):
        os.makedirs(os.path.dirname(registry.path()), exist_ok=True)
        with open(registry.path(), "w") as handle:
            handle.write("{not json")
        with self.assertRaises(registry.RegistryError):
            registry.load()

    def test_no_temp_files_left_behind(self):
        registry.add(ISIN_A, name="Test Fund A")
        self.assertEqual(
            os.listdir(os.path.dirname(registry.path())), ["registry.json"]
        )


class TestCli(RegistryTestCase):
    def test_add_get_and_resolve(self):
        code, out, err = self.run_cli(
            [
                "add",
                ISIN_A,
                "--name",
                "Test Fund A",
                "--class",
                "etf",
                "--ibkr",
                "111:IBIS2:TESTA:EUR",
                "--ibkr",
                "222:LSEETF:TESTA:GBP",
                "--yahoo",
                "TESTA.DE",
                "--lhv",
                "TESTA",
            ]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("Test Fund A", out)

        code, out, err = self.run_cli(["get", ISIN_A, "--json"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(len(payload["ibkr"]), 2)
        self.assertEqual(payload["yahoo"], "TESTA.DE")

        code, out, err = self.run_cli(["get", ISIN_A])
        self.assertEqual(code, 0, err)
        self.assertIn("etf", out)

        code, out, err = self.run_cli(["resolve", "--yahoo", "TESTA.DE"])
        self.assertEqual(code, 0, err)
        self.assertIn(ISIN_A, out)

        code, out, err = self.run_cli(["resolve", "--ibkr", "ibis2:testa", "--json"])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out), {"isin": ISIN_A})

        code, out, err = self.run_cli(["resolve", "--lhv", "TESTA", "--json"])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out), {"isin": ISIN_A})

    def test_resolve_miss_exits_1(self):
        code, out, err = self.run_cli(["resolve", "--yahoo", "NOPE"])
        self.assertEqual(code, 1)
        self.assertTrue(err.strip())

    def test_get_unknown_exits_1(self):
        code, out, err = self.run_cli(["get", ISIN_A])
        self.assertEqual(code, 1)
        self.assertTrue(err.strip())

    def test_add_invalid_isin_exits_1(self):
        code, out, err = self.run_cli(["add", ISIN_BAD, "--name", "Test Fund A"])
        self.assertEqual(code, 1)
        self.assertIn("ISIN", err)

    def test_add_unknown_class_exits_1(self):
        code, out, err = self.run_cli(["add", ISIN_A, "--class", "derivative"])
        self.assertEqual(code, 1)
        self.assertTrue(err.strip())

    def test_malformed_ibkr_exits_1(self):
        for bad in ("111:IBIS2:TESTA", "abc:IBIS2:TESTA:EUR", "111:IBIS2:TESTA:EUR:X", ""):
            code, out, err = self.run_cli(["add", ISIN_A, "--ibkr", bad])
            self.assertEqual(code, 1, "expected failure for %r" % bad)
            self.assertTrue(err.strip())

    def test_resolve_requires_one_selector(self):
        code, out, err = self.run_cli(["resolve"])
        self.assertEqual(code, 1)
        self.assertTrue(err.strip())

    def test_no_subcommand_prints_help(self):
        code, out, err = self.run_cli([])
        self.assertEqual(code, 1)
        self.assertIn("usage", err)


if __name__ == "__main__":
    unittest.main()
