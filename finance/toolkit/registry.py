#!/usr/bin/env python3
"""Instrument registry mapping ISIN to per-provider identifiers.

The registry lives at ``registry.json`` in the store root (``$FINANCE_STORE``
if set, else ``~/.finance``) and is the join key between providers, because
no provider emits ISIN reliably: yfinance returns ``-`` or, for some names, a
CEDEAR ISIN; IBKR accepts an ISIN as a search query but never returns one.
Bars are therefore keyed provider-natively in the store, and this file is what
ties ``IBIS2_VWCE`` and ``VWCE.DE`` to the same instrument.

File shape, schema version 1::

    {
      "schema_version": 1,
      "instruments": {
        "<ISIN>": {
          "name": "...",
          "class": "etf",
          "ibkr": [{"contract_id": 1, "exchange": "IBIS2",
                    "symbol": "VWCE", "currency": "EUR"}],
          "yahoo": "VWCE.DE",
          "lhv": null
        }
      }
    }

An instrument may hold several IBKR listings (the same fund quoted on IBIS2 in
EUR and on LSEETF in GBP), so ``ibkr`` is a list keyed by
``(exchange, symbol)``. ``name``, ``class``, ``yahoo`` and ``lhv`` are single
valued and nullable.

Writes are whole-file: :func:`save` renders the registry to a temporary file in
the store root and ``os.replace``\\ s it into place, so a crash mid-write leaves
the previous registry intact. Keys are sorted and the indent is 2 so that a
registry kept under version control diffs one line per change.

Usage as a library::

    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    import registry

Usage as a CLI::

    python3 registry.py add ISIN [--name N] [--class C]
                                 [--ibkr CID:EXCH:SYM:CCY]... [--yahoo T]
                                 [--lhv S] [--json]
    python3 registry.py get ISIN [--json]
    python3 registry.py resolve (--yahoo T | --ibkr EXCH:SYM | --lhv S) [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import store  # noqa: E402

SCHEMA_VERSION = 1

REGISTRY_FILENAME = "registry.json"

#: Instrument classes the registry accepts. Phase 2 extends this set; the
#: schema version guards that change.
INSTRUMENT_CLASSES = ("equity", "etf", "bond", "commodity", "cash_equivalent", "fx")

#: Fields every IBKR listing must carry.
IBKR_LISTING_FIELDS = ("contract_id", "exchange", "symbol", "currency")

#: Single-valued instrument fields, in the order the human output prints them.
INSTRUMENT_FIELDS = ("name", "class", "yahoo", "lhv")

_ISIN_LENGTH = 12


class RegistryError(Exception):
    """Raised for an invalid ISIN, an unknown instrument or a malformed file."""


def path():
    """Return the absolute path of ``registry.json`` in the store root."""
    return os.path.join(store.root(), REGISTRY_FILENAME)


def validate_isin(isin):
    """Return True when ``isin`` is a well-formed ISIN with a valid check digit.

    An ISIN is two letters (the issuing country), nine alphanumerics and a
    check digit. The check digit is verified by expanding every letter to its
    two-digit ordinal (A=10 ... Z=35) and applying the Luhn algorithm to the
    resulting digit string, including the expanded check digit itself.
    """
    if not isinstance(isin, str):
        return False
    text = isin.strip().upper()
    if len(text) != _ISIN_LENGTH:
        return False
    if not text[:2].isalpha():
        return False
    if not text.isalnum() or not text.isascii():
        return False
    if not text[-1].isdigit():
        return False

    digits = ""
    for char in text:
        if char.isdigit():
            digits += char
        else:
            digits += str(ord(char) - ord("A") + 10)

    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char)
        if position % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _require_isin(isin):
    """Return the normalised ISIN or raise RegistryError."""
    if not validate_isin(isin):
        raise RegistryError("invalid ISIN: %r" % (isin,))
    return isin.strip().upper()


def _empty():
    return {"schema_version": SCHEMA_VERSION, "instruments": {}}


def load():
    """Return the registry dict; an empty registry when the file is absent."""
    target = path()
    if not os.path.isfile(target):
        return _empty()
    with open(target) as handle:
        try:
            data = json.load(handle)
        except ValueError as exc:
            raise RegistryError("malformed registry %s: %s" % (target, exc))
    if not isinstance(data, dict) or not isinstance(data.get("instruments"), dict):
        raise RegistryError("malformed registry %s: missing instruments" % target)
    data.setdefault("schema_version", SCHEMA_VERSION)
    return data


def save(reg):
    """Write the registry atomically, keys sorted, indent 2."""
    target = path()
    directory = os.path.dirname(target)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    temporary = target + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(reg, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, target)


def _clean_listing(listing):
    """Validate and normalise one IBKR listing dict."""
    if not isinstance(listing, dict):
        raise RegistryError("IBKR listing must be a mapping, got %r" % (listing,))
    missing = [f for f in IBKR_LISTING_FIELDS if listing.get(f) in (None, "")]
    if missing:
        raise RegistryError(
            "IBKR listing is missing %s" % ", ".join(sorted(missing))
        )
    try:
        contract_id = int(listing["contract_id"])
    except (TypeError, ValueError):
        raise RegistryError(
            "IBKR contract_id must be an integer, got %r" % (listing["contract_id"],)
        )
    return {
        "contract_id": contract_id,
        "exchange": str(listing["exchange"]).upper(),
        "symbol": str(listing["symbol"]).upper(),
        "currency": str(listing["currency"]).upper(),
    }


def _merge_listings(existing, incoming):
    """Merge IBKR listings by ``(exchange, symbol)``; incoming wins."""
    merged = list(existing)
    for listing in incoming:
        pair = (listing["exchange"], listing["symbol"])
        for index, current in enumerate(merged):
            if (current.get("exchange"), current.get("symbol")) == pair:
                merged[index] = listing
                break
        else:
            merged.append(listing)
    return merged


def add(isin, name=None, class_=None, ibkr=None, yahoo=None, lhv=None):
    """Add or update one instrument; return the stored instrument dict.

    An existing ISIN keeps every field not supplied here. ``ibkr`` listings
    merge by ``(exchange, symbol)`` — a new listing for a pair already present
    replaces it — while ``name``, ``class_``, ``yahoo`` and ``lhv`` replace the
    stored value whenever they are supplied.
    """
    key = _require_isin(isin)
    if class_ is not None and class_ not in INSTRUMENT_CLASSES:
        raise RegistryError(
            "unknown instrument class %r; expected one of %s"
            % (class_, ", ".join(INSTRUMENT_CLASSES))
        )
    listings = [_clean_listing(entry) for entry in (ibkr or [])]

    reg = load()
    instruments = reg.setdefault("instruments", {})
    instrument = instruments.get(key) or {}
    for field in INSTRUMENT_FIELDS:
        instrument.setdefault(field, None)
    instrument.setdefault("ibkr", [])

    if name is not None:
        instrument["name"] = name
    if class_ is not None:
        instrument["class"] = class_
    if yahoo is not None:
        instrument["yahoo"] = yahoo
    if lhv is not None:
        instrument["lhv"] = lhv
    if listings:
        instrument["ibkr"] = _merge_listings(instrument["ibkr"], listings)

    instruments[key] = instrument
    reg["schema_version"] = SCHEMA_VERSION
    save(reg)
    return instrument


def get(isin):
    """Return one instrument dict, or raise RegistryError when it is absent."""
    key = _require_isin(isin)
    instrument = load()["instruments"].get(key)
    if instrument is None:
        raise RegistryError("no instrument registered for ISIN %s" % key)
    return instrument


def resolve_yahoo(ticker):
    """Return the ISIN carrying this Yahoo ticker."""
    for isin, instrument in sorted(load()["instruments"].items()):
        if instrument.get("yahoo") == ticker:
            return isin
    raise RegistryError("no instrument with Yahoo ticker %s" % ticker)


def resolve_ibkr(exchange, symbol):
    """Return the ISIN listed on this IBKR exchange under this symbol."""
    pair = (str(exchange).upper(), str(symbol).upper())
    for isin, instrument in sorted(load()["instruments"].items()):
        for listing in instrument.get("ibkr") or []:
            current = (
                str(listing.get("exchange", "")).upper(),
                str(listing.get("symbol", "")).upper(),
            )
            if current == pair:
                return isin
    raise RegistryError("no instrument listed on %s as %s" % pair)


def resolve_lhv(symbol):
    """Return the ISIN carrying this LHV symbol."""
    for isin, instrument in sorted(load()["instruments"].items()):
        if instrument.get("lhv") == symbol:
            return isin
    raise RegistryError("no instrument with LHV symbol %s" % symbol)


def parse_ibkr_option(text):
    """Parse a ``CID:EXCH:SYM:CCY`` CLI value into a listing dict."""
    parts = (text or "").split(":")
    if len(parts) != 4:
        raise RegistryError(
            "--ibkr expects CID:EXCH:SYM:CCY, got %r" % (text,)
        )
    contract_id, exchange, symbol, currency = [part.strip() for part in parts]
    if not contract_id.lstrip("-").isdigit():
        raise RegistryError("--ibkr contract id must be an integer, got %r" % contract_id)
    return _clean_listing(
        {
            "contract_id": int(contract_id),
            "exchange": exchange,
            "symbol": symbol,
            "currency": currency,
        }
    )


def _print_instrument(isin, instrument):
    print("%-14s %s" % ("isin", isin))
    for field in INSTRUMENT_FIELDS:
        value = instrument.get(field)
        print("%-14s %s" % (field, "null" if value is None else value))
    listings = instrument.get("ibkr") or []
    if not listings:
        print("%-14s %s" % ("ibkr", "null"))
        return
    for listing in listings:
        print(
            "%-14s %s:%s %s cid=%s"
            % (
                "ibkr",
                listing.get("exchange"),
                listing.get("symbol"),
                listing.get("currency"),
                listing.get("contract_id"),
            )
        )


def _cmd_add(args):
    listings = [parse_ibkr_option(value) for value in (args.ibkr or [])]
    instrument = add(
        args.isin,
        name=args.name,
        class_=getattr(args, "class"),
        ibkr=listings,
        yahoo=args.yahoo,
        lhv=args.lhv,
    )
    isin = args.isin.strip().upper()
    if args.json:
        print(json.dumps(instrument, indent=2, sort_keys=True))
        return 0
    _print_instrument(isin, instrument)
    return 0


def _cmd_get(args):
    instrument = get(args.isin)
    if args.json:
        print(json.dumps(instrument, indent=2, sort_keys=True))
        return 0
    _print_instrument(args.isin.strip().upper(), instrument)
    return 0


def _cmd_resolve(args):
    selectors = [bool(args.yahoo), bool(args.ibkr), bool(args.lhv)]
    if sum(selectors) != 1:
        raise RegistryError("resolve needs exactly one of --yahoo, --ibkr, --lhv")
    if args.yahoo:
        isin = resolve_yahoo(args.yahoo)
    elif args.lhv:
        isin = resolve_lhv(args.lhv)
    else:
        parts = args.ibkr.split(":")
        if len(parts) != 2 or not all(part.strip() for part in parts):
            raise RegistryError("--ibkr expects EXCH:SYM, got %r" % (args.ibkr,))
        isin = resolve_ibkr(parts[0].strip(), parts[1].strip())
    if args.json:
        print(json.dumps({"isin": isin}))
        return 0
    print(isin)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="registry.py", description="Map ISINs to per-provider identifiers."
    )
    sub = parser.add_subparsers(dest="command")

    adder = sub.add_parser("add", help="add or update an instrument")
    adder.add_argument("isin", help="ISIN, e.g. IE00B4L5Y983")
    adder.add_argument("--name", help="instrument name")
    adder.add_argument(
        "--class",
        dest="class",
        help="one of %s" % ", ".join(INSTRUMENT_CLASSES),
    )
    adder.add_argument(
        "--ibkr",
        action="append",
        metavar="CID:EXCH:SYM:CCY",
        help="IBKR listing; repeat for several venues",
    )
    adder.add_argument("--yahoo", help="Yahoo ticker, e.g. VWCE.DE")
    adder.add_argument("--lhv", help="LHV symbol")
    adder.add_argument("--json", action="store_true", help="machine-readable output")
    adder.set_defaults(func=_cmd_add)

    getter = sub.add_parser("get", help="print one instrument by ISIN")
    getter.add_argument("isin", help="ISIN to look up")
    getter.add_argument("--json", action="store_true", help="machine-readable output")
    getter.set_defaults(func=_cmd_get)

    resolver = sub.add_parser("resolve", help="resolve a provider symbol to an ISIN")
    resolver.add_argument("--yahoo", help="Yahoo ticker")
    resolver.add_argument("--ibkr", metavar="EXCH:SYM", help="IBKR exchange and symbol")
    resolver.add_argument("--lhv", help="LHV symbol")
    resolver.add_argument("--json", action="store_true", help="machine-readable output")
    resolver.set_defaults(func=_cmd_resolve)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return 1
    try:
        return args.func(args)
    except (RegistryError, store.StoreError) as exc:
        sys.stderr.write("%s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
