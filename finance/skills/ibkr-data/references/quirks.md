# IBKR quirks

Behaviour observed against the live server, each entry dated. These are not bugs to work around
once; they are properties of the data that every consumer has to assume.

## EU venues are delayed 900 seconds and quote no bid/ask (2026-09-06)

`get_price_history` on AEB returned `"delayed": 900` in the response. US venues returned no
`delayed` field at all, which means zero. `ingest.py` writes `delayed_sec` into the sidecar from
this field, defaulting to 0 when it is absent, so the delay survives into every downstream
consumer.

`get_price_snapshot` on the same EU venues returned no bid and no ask: the keys were present with
an empty object as the value. Report a delayed last price as delayed. Never present a 15-minute-old
close as the current price, and never derive a spread from an empty quote.

## Currency labels in responses cannot be trusted (2026-09-06)

`get_pa_allocation` returned figures denominated in EUR under `"currency": "USD"`. The number was
right, the label was wrong.

Currency is therefore taken from the contract and the venue at ingest time, never from a label in a
response. `ingest.py` requires `--currency` for exactly this reason: it is a fact about the listing
you chose, not something read out of the payload.

## Two tools, two classifications (2026-09-06)

`get_pa_allocation` files an EUR overnight-rate ETF (a cash-like money market instrument) under
Cash, while `get_account_summary` counts the same holding inside `gross_position_value`, that is,
as an invested position. Both are defensible and they do not add up to the same picture.

Classification belongs to the store with an explicit policy, set once in the registry's `class`
field. Do not inherit either broker view, and do not sum figures that came from these two tools
without deciding which classification applies.

## Snapshot fields are optional (2026-09-06)

`get_price_snapshot` drops any field that does not resolve within about 10 seconds, silently: the
response simply lacks the key. Field names are hyphenated (`bid-ask`, `top-status`), and
`top-status` reads FROZEN when the market is closed.

Every consumer treats every snapshot field as optional. A missing field means the request timed
out, not that the value is zero, and re-requesting can return a different set of fields.

## Venue timestamps differ, so bars are keyed by session date (2026-09-06)

Daily bars are stamped at the venue's own hour, not at midnight and not in one shared zone:

| Venue | Daily bar stamp |
|---|---|
| US (SMART) | 13:30Z |
| AEB | 07:00Z |
| IDEALPRO (EUR.USD) | 21:15Z |

Aligning two venues on raw timestamps therefore produces zero overlap, and a naive UTC-date
conversion can shift a bar into the neighbouring day. `ingest.py` normalises every daily and
coarser bar to its session date, and `returns.py` inner-joins on that date. Holiday calendars
differ per venue as well, so an inner join across venues is always shorter than either input.

## `search_contracts` accepts an ISIN but never returns one (2026-09-06)

Passing an ISIN as the query works and returns every listing of that instrument, which is the
cheapest way to enumerate venues. No response field carries an ISIN back, on any tool.

That is why the store keys bars provider-natively (`AEB_IWDA`) and why the registry exists: the
ISIN has to come from the user or from the query that found the contract, and it is then written
into `registry.json` by hand. Never infer an ISIN from a symbol.

## Adjustment finding: IBKR closes are not dividend-adjusted (2026-09-06)

Checked on VWRL at AEB (Vanguard FTSE All-World, distributing), IBKR `get_price_history` with
`period: THREE_MONTHS`, `step: ONE_DAY` and `include_corporate_actions: true`. The response's
`corp_actions` reported a CashDividend with ex-date 2026-06-18 of USD 0.905474 (yfinance reported
the same distribution as EUR 0.7883). The same window was fetched from yfinance twice, with
`auto_adjust=False` and with `auto_adjust=True`:

| date | IBKR close | yfinance raw (`auto_adjust=False`) | yfinance adjusted |
|---|---|---|---|
| 2026-06-16 | 159.80 | 159.86 | 159.07 |
| 2026-06-17 | 160.28 | 160.26 | 159.47 |
| 2026-06-18 (ex) | 160.24 | 160.36 | 160.36 |
| 2026-06-19 | 160.30 | 160.30 | 160.30 |

Before the ex-date the IBKR closes match the unadjusted series within a few cents and sit about
0.79 above the adjusted series, which is the distribution. From the ex-date onward the three series
agree, because adjustment only rewrites history before the event.

Conclusion: IBKR history closes are not dividend-adjusted. `ingest.py` therefore defaults
`--adjusted` to `false` for IBKR series, and `--adjusted true|false|null` still overrides per fetch.
Split adjustment was not tested: no split fell inside the window.

The consequence is that an IBKR leg and a yfinance leg of the same instrument drift apart by the
accumulated distributions, growing with every ex-date in the window. `returns.py pair` warns when
the two sidecars disagree on `adjusted`. For a total-return series, use `yfinance-data`, which
stores `adjusted: true`; use IBKR when the price actually traded is what matters, or when the
instrument is an EU listing Yahoo covers badly.

## The documented behaviour held on a live run (2026-09-06)

Three ingests were run end to end against the live server: AAPL through SMART, IWDA on AEB, and
EUR.USD on IDEALPRO as `CASH`. Each behaved as this document describes. The US series carried
`delayed_sec 0` and `price_source Last`; the AEB series carried `delayed_sec 900` and
`price_source Last`; the FX series carried `price_source MidPoint`, no volume, and session dates
taken from the UTC date of the 21:15Z stamp, which is the same calendar day the pair traded.
Observed context cost matched the prediction in the skill: each response entered the transcript
once and was re-emitted once by the heredoc write, so roughly twice its size.

## Not verified

- Whether `${CLAUDE_PLUGIN_ROOT}` is substituted inside an installed SKILL.md at runtime. The check
  was run from a worktree, not from an installed plugin, so it stays open. Both finance skills carry
  the fallback sentence, so the path resolves either way.
- Whether any client can be made to request only `mcp.read` at OAuth time. See `setup.md`.
