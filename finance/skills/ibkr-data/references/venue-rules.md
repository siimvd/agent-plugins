# Picking a venue

The same instrument lists on several exchanges in several currencies, and IBKR keys on
`contract_id` per venue, so the venue is part of the instrument's identity. Picking the wrong line
gives real prices for something the user does not hold.

## The rules

1. **Primary listing in the instrument's trading currency.** A Nordic operating company trades in
   SEK on its home exchange; a US name trades in USD. Prefer that line over a foreign secondary
   listing or an unsponsored depositary receipt, which is thinner and prices off an FX rate.
2. **UCITS ETFs: the EUR line on IBIS2 or AEB.** IBIS2 is Xetra, AEB is Euronext Amsterdam. The
   same fund also lists on LSEETF in GBP or USD; use it only when the user actually holds the
   London line. Pass the exchange explicitly, since these do not route through SMART.
3. **US stocks and ETFs: omit `exchange`.** The call then routes through SMART, which is what the
   IBKR account itself uses.
4. **FX: `IDEALPRO` with `security_type: "CASH"`.** `search_contracts("EUR.USD")` returns symbol
   `EUR` on `IDEALPRO`. Fetch with `outside_rth: true`, since FX trades nearly around the clock.
   The response carries no `volume` and its `source` is `MidPoint`.
5. **Futures: the native exchange, always explicit.** `search_futures` gives the root and the
   expiries.

`exchange` is optional in `get_price_history` and only defaults sensibly for US stocks and ETFs.
For everything else, pass the `exchange` from the `search_contracts` row you chose.

## Reading `search_contracts` rows

A row carries `underlying_contract_id`, `exchange`, `symbol`, `description`, `country_code` and
`sections`, where each section names a `security_type` (`STK`, `OPT`, `FUT`, `CASH` and so on).
Work through them in this order:

- **Match `symbol` exactly.** A prefix match is not a match. Ticker space is crowded and adjacent
  tickers are usually a different product from the same issuer.
- **Check `country_code` against the venue you want.** It separates the home listing from foreign
  cross-listings that share a description.
- **Check `sections` for the `security_type` you intend to pass.** A row whose sections list only
  `OPT` is not a line you can fetch stock bars from, and `security_type` in `get_price_history` has
  to match what the venue actually offers.
- **Read `description` before deciding.** Leveraged, inverse and income products describe
  themselves: `AAPU` is a 2x leveraged Apple ETF and `AAPD` an inverse one, and neither is Apple.
  A covered-call or "income" variant of a fund tracks the same index and pays a different total
  return, so it is a different series.

Querying by ISIN returns every listing of one fund in a single call, which is the cheapest way to
see the venue choices side by side. The reverse does not work: `search_contracts` accepts an ISIN
but never emits one, so an ISIN for the registry has to come from the user or from the query that
found the contract.

When two rows still look equally plausible, ask which listing is meant. Do not pick by volume or
by row order.

## Keying the store

The store key for an IBKR series is `EXCH_SYM`, uppercase, with the exchange first: `AEB_IWDA`,
`IBIS2_VWCE`, `IDEALPRO_EURUSD`. Files land at
`bars/ibkr/<KEY>_<interval>.csv` plus a `.meta.json` sidecar, and the raw response at
`raw/ibkr_<KEY>_<interval>_<YYYYMMDD>.json`.

The key is deliberately venue-scoped: two listings of the same fund are two series with different
currencies, different trading calendars and different closing stamps, and merging them by symbol
would produce a series that never traded. The ISIN in the registry is what says they are the same
instrument.
