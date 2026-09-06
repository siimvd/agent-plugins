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

## Adjustment finding

PENDING: supplied by orchestrator

Until this is filled in, `ingest.py` writes `adjusted: null` for IBKR series, meaning unknown, and
`--adjusted true|false` overrides it per fetch. Unknown is the honest value: mixing an adjusted
series with an unadjusted one corrupts every return computed across a dividend or a split, and a
null flag at least makes the mixing detectable.
