---
name: yfinance-data
description: >-
  Pull price history and fundamentals from Yahoo Finance through the yfinance library, for US
  tickers and for EU listings carrying a Yahoo venue suffix (.DE, .AS, .ST, .L). Use when the
  request names Yahoo Finance or yfinance, or asks to fetch, download or refresh bars,
  historical prices, OHLCV, fundamentals or company statements for a named instrument. This is a
  data provider that analysis skills call to fill the store; it does not trigger on a ticker
  mentioned in passing, and a bare ticker in a question is not a request to fetch anything.
---

# yfinance data

Fetches Yahoo Finance data into the shared store at `~/.finance/` (or `$FINANCE_STORE`) and prints
a summary. Bars land as CSV plus a JSON sidecar recording source, currency, exchange and the
adjustment flag; fundamentals land as one small JSON file per ticker. The fetch script writes to
disk and prints roughly eight lines, so a year of daily bars costs the conversation nothing beyond
that summary. Analysis then runs against the store through the toolkit scripts.

## How to run it

```bash
uv run --python 3.12 --with yfinance --with pandas python \
  ${CLAUDE_PLUGIN_ROOT}/toolkit/fetch_yf.py bars TICKER --period 1y
```

(`${CLAUDE_PLUGIN_ROOT}` is this plugin's root directory, substituted automatically by Claude Code.
On a tool that does not substitute it, resolve it yourself relative to this file: two levels up
from `skills/yfinance-data/`.)

The `uv run` prefix is not optional. The system Python has neither yfinance nor pandas, and nothing
here installs packages into it. The first run is slow while uv resolves the environment; later runs
reuse the cache. If `uv` is missing, say so and stop rather than falling back to `pip install`.

## What to run for which request

| Request | Command | Notes |
|---|---|---|
| Price history, chart data, "get me N years of X" | `bars TICKER --period 1y` | Writes `bars/yfinance/TICKER_1d.csv` |
| Weekly bars for a multi-year window | `bars TICKER --period 5y --interval 1wk` | Prefer weekly over daily past two years |
| Intraday | `bars TICKER --period 5d --interval 5m` | 1m goes back about 7 days, 5m about 60, 1h about 730 |
| Company overview, sector, market cap, P/E, 52-week range | `info TICKER` | Writes `fundamentals/TICKER.json` |
| Machine-readable output for a follow-up script | add `--json` | Prints the sidecar or the fundamentals dict |

Periods: `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max`.
Intervals: `1m`, `2m`, `5m`, `15m`, `30m`, `60m`, `90m`, `1h`, `1d`, `1wk`, `1mo`.
`1wk` and `60m` are stored as `1w` and `1h`, which is the store's vocabulary.

## Yahoo venue suffixes

| Venue | Suffix | Example | Currency reported |
|---|---|---|---|
| US (NYSE, Nasdaq) | none | `MSFT` | USD |
| Xetra | `.DE` | `VWCE.DE` | EUR |
| Euronext Amsterdam | `.AS` | `IWDA.AS` | EUR |
| Nasdaq Stockholm | `.ST` | `LIFCO-B.ST` | SEK |
| London | `.L` | `GLEN.L` | GBp, meaning pence |

London quotes come back in pence, not pounds, and the sidecar records `GBp` because that is what the
venue means. Anything converting a `.L` series to EUR has to divide by 100 first.

Never guess a suffix. The same fund trades under different tickers on different venues, and a wrong
guess returns either nothing or another instrument's prices. If the venue is not known, ask which
listing is meant.

## What to report back

After a `bars` run, report: the ticker and store key, the bar count and date range, `source:
yfinance`, the currency, `adjusted: true`, the as-of date (the last bar), and the ISIN when the
sidecar carries one. Yahoo bars are fetched with `auto_adjust=True`, so closes are split- and
dividend-adjusted; say so, because mixing them with an unadjusted series corrupts every return
computed downstream.

Never print the CSV, paste bar rows into the conversation, or summarise the series by reading it.
The point of the store is that the rows stay on disk. When Yahoo returns nothing the command exits
1 with a message naming the ticker: report that the fetch failed and stop, rather than retrying with
a different suffix or period until something comes back.

## Fundamentals are thin for European funds

`info` keeps a fixed whitelist of fields and drops the rest of Yahoo's several-hundred-key payload.
For US equities the whitelist is well populated. For UCITS ETFs it mostly is not: Yahoo either
answers with a 404 ("No fundamentals data found") or returns a handful of fields with no sector,
market cap, P/E or shares outstanding. Verified on 2026-09-06, `info VWCE.DE` returned name, quote
type, currency, exchange and the 52-week range and nothing else. Either way the command exits 0 and
records what it got, so an empty-looking result means Yahoo has nothing, not that the fetch broke.
For fund-level data, use the issuer's factsheet.

## Not in this slice

Options chains, holders and insider transactions, the Yahoo screener, sector and industry
aggregates, and the financial statement frames (`income_stmt`, `balance_sheet`, `cashflow`) are all
available in yfinance but are not wired into the store yet. They arrive with the screener and
valuation skills. Do not hand-roll them here.

Method signatures and edge cases are in
[`${CLAUDE_SKILL_DIR}/references/api-reference.md`](./references/api-reference.md).
(`${CLAUDE_SKILL_DIR}` is this skill's own directory, substituted automatically by Claude Code. On a
tool that does not substitute it, resolve it yourself as this skill's directory, using this file's
known location.)

This skill drafts analysis for your review. It makes no investment recommendations and executes nothing.
