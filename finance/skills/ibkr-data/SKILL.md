---
name: ibkr-data
description: >-
  Pull price history and account data from Interactive Brokers through IBKR's remote MCP server.
  Use when the request names Interactive Brokers or IBKR, says "my IBKR account", asks for IBKR
  positions, balances or allocation, or asks for bars from an EU venue such as AEB, IBIS2 (Xetra)
  or LSEETF, or for an FX pair from IDEALPRO. Read-only: this skill never places, changes or
  cancels an order and never writes an alert or a watchlist. It is a data provider that analysis
  skills call to fill the store, and it does not trigger on a ticker mentioned in passing.
---

# IBKR data

Fetches Interactive Brokers market data into the shared store at `~/.finance/` (or
`$FINANCE_STORE`) and prints a summary. Only the model can call an MCP server, so this path is
model-driven: call `get_price_history`, save the result verbatim to a raw JSON file, then run
`ingest.py`, which writes the CSV plus a JSON sidecar recording source, symbol, exchange,
currency, `adjusted` and the delay. Analysis afterwards runs against the store through the
toolkit scripts, never against the numbers in this conversation.

Tool names here are bare (`get_price_history`, `search_contracts`). Every client prefixes them
differently, usually with its own name for the server, so the tool you see listed will be a longer
string ending in the bare name. Match on that trailing bare name.

## When the tools are absent

If no IBKR tool is available in this session, say so plainly and stop. Do not guess prices, do not
reconstruct a series from memory, and do not substitute a different instrument. Offer
`yfinance-data` instead, which covers US tickers and EU listings that carry a Yahoo venue suffix,
and note that Yahoo has no account data at all. Setup for each agent is in
[`${CLAUDE_SKILL_DIR}/references/setup.md`](./references/setup.md).
(`${CLAUDE_SKILL_DIR}` is this skill's own directory, substituted automatically by Claude Code. On
a tool that does not substitute it, resolve it yourself as this skill's directory, using this
file's known location.)

## The flow

### 1. Resolve the instrument

Try the registry first, since it holds the venue and contract id already:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/toolkit/registry.py resolve --ibkr AEB:IWDA
```

(`${CLAUDE_PLUGIN_ROOT}` is this plugin's root directory, substituted automatically by Claude Code.
On a tool that does not substitute it, resolve it yourself relative to this file: two levels up
from `skills/ibkr-data/`.)

`registry.py get ISIN` prints every known listing when the ISIN is known. When the registry has
nothing, call `search_contracts`. Query by ISIN when the user gave one, because an ISIN returns
every listing of the same fund in one call; otherwise query the symbol or the name. Pick the venue
with [`${CLAUDE_SKILL_DIR}/references/venue-rules.md`](./references/venue-rules.md), and do not
settle for the first row: leveraged and income look-alikes trade under adjacent tickers.

### 2. Fetch the bars

```
get_price_history(contract_id=<id>, security_type="STK", step="ONE_DAY",
                  outside_rth=false, step_count=60, exchange=<venue or omitted>)
```

Pass `period` (`ONE_DAY` through `FIVE_YEARS`) or `step_count`, never both. Default to
`step_count: 60`, and for a multi-year window use `step: ONE_WEEK` rather than more daily bars, so
one call stays under about 60 bars unless the user asked for more. Omit `exchange` for US stocks
and ETFs, which routes through SMART; pass the row's exchange for anything else (`AEB`, `IBIS2`,
`LSEETF`, `IDEALPRO`, a future's native exchange).

### 3. Save the raw result verbatim

```bash
mkdir -p "${FINANCE_STORE:-$HOME/.finance}/raw"
cat > "${FINANCE_STORE:-$HOME/.finance}/raw/ibkr_AEB_IWDA_1d_20260906.json" <<'JSON'
<the tool result, copied exactly, no reformatting and no trimming>
JSON
```

The file name is `ibkr_<KEY>_<interval>_<YYYYMMDD>.json`, where `KEY` is `EXCH_SYM`. Copy the JSON
as it came back. Rounding a close or dropping a field here corrupts the store silently.

### 4. Ingest

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/toolkit/ingest.py ibkr-history \
  "${FINANCE_STORE:-$HOME/.finance}/raw/ibkr_AEB_IWDA_1d_20260906.json" \
  --symbol IWDA --exchange AEB --currency EUR --contract-id <id>
```

Currency comes from the contract and the venue, never from a label in a response. `--contract-id`
is optional and worth passing, since it is what makes a re-fetch reproducible. `--interval` is
inferred from `chart_step` and only needs passing when the script says it cannot name the step.

`--adjusted` defaults to `false` for IBKR series, because IBKR history closes are not
dividend-adjusted (checked 2026-06-18 ex-date on VWRL, recorded in `quirks.md`). Override it with
`--adjusted true` only for a response you know to be adjusted, or `--adjusted null` when the
provenance of a saved file is genuinely unknown. Leave it alone for a normal fetch.

### 5. Register a new instrument

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/toolkit/registry.py add IE00B4L5Y983 \
  --name "iShares Core MSCI World UCITS ETF" --class etf \
  --ibkr <id>:AEB:IWDA:EUR --yahoo IWDA.AS
```

The ISIN has to come from the user or from the ISIN search that found the contract. IBKR accepts
an ISIN as a query but never returns one, so never infer an ISIN from a symbol.

### 6. Report

Report only the ingest summary line plus: the source (`ibkr`), the currency, `adjusted`, the as-of
date (the last bar), and, when the sidecar shows `delayed_sec` greater than zero, that the data is
delayed by that many seconds. EU venues are delayed 900 seconds; say so rather than presenting the
last bar as live. Never paste bar rows into the conversation.

## FX pairs

Same flow, three differences. `search_contracts("EUR.USD")` returns symbol `EUR` on `IDEALPRO`;
fetch it with `security_type: "CASH"`, `exchange: "IDEALPRO"` and `outside_rth: true`, because FX
trades nearly around the clock. The response has no `volume` and its `source` is `MidPoint` rather
than `Last`. Store it under key `IDEALPRO_EURUSD`:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/toolkit/ingest.py ibkr-history <raw> \
  --symbol EURUSD --exchange IDEALPRO --currency USD
```

The currency is the quote currency of the pair, so EUR.USD is stored as `USD`.

## Context discipline

An MCP result enters the conversation once when the tool returns, and the heredoc in step 3 repeats
the whole payload a second time. Every fetch therefore costs roughly twice the size of the
response, and a year of daily bars is around 15KB before that doubling. Three rules follow:

- Ask for the fewest bars that answer the question. `step_count: 60` is the default for a reason.
- For anything longer than about two years, use `step: ONE_WEEK` or `ONE_MONTH`, not more daily
  bars.
- For a universe wider than five tickers, use `yfinance-data`, whose script writes to the store
  without the series passing through the conversation at all. Reach for IBKR when the instrument is
  an EU listing Yahoo covers badly, when the contract id matters, or when account data is involved.

## Account reads

`get_account_summary`, `get_account_balances`, `get_account_positions`, `get_pa_allocation` and
`get_pa_performance_all_periods` are available and read-only, and they are out of scope for this
slice's analysis: nothing here builds a portfolio view yet. Two cautions apply when they are used
later. Currency labels in these responses are not trustworthy (`get_pa_allocation` has returned
EUR figures labelled `"currency": "USD"`), so take the currency from the contract and the venue.
And the tools disagree on classification: `get_pa_allocation` files an EUR overnight-rate ETF under
Cash while `get_account_summary` counts the same holding inside `gross_position_value`.

## References

- [`${CLAUDE_SKILL_DIR}/references/setup.md`](./references/setup.md): the MCP URL, the OAuth login,
  per-agent config, checking the granted scope.
- [`${CLAUDE_SKILL_DIR}/references/tool-map.md`](./references/tool-map.md): every read tool, what it
  returns, and the write tools this plugin never calls.
- [`${CLAUDE_SKILL_DIR}/references/venue-rules.md`](./references/venue-rules.md): picking a listing
  and reading `search_contracts` rows.
- [`${CLAUDE_SKILL_DIR}/references/quirks.md`](./references/quirks.md): dated findings about delay,
  currency labels, timestamps and adjustment.

This skill drafts analysis for your review. It makes no investment recommendations and executes nothing.
