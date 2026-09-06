---
name: stock-correlation
description: >-
  Correlation, beta and co-movement between instruments already in the finance store, or fetched
  into it first. Use when the request asks about correlated stocks, a correlation matrix, rolling
  correlation, pair trading, a hedging pair, co-movement, beta to a benchmark, what moves with a
  named instrument, stocks that move together or inversely, or a well-known pair such as AMD and
  NVDA. Also use for "has the correlation changed" and "when X drops, what else drops". Given one
  ticker it looks for peers only when the user asks for peers; a ticker mentioned in passing is
  not a request for a correlation.
---

# Stock correlation

Computes correlation, beta and rolling correlation from bars already on disk. Everything is read
from the store at `~/.finance/` (or `$FINANCE_STORE`) and computed by
`${CLAUDE_PLUGIN_ROOT}/toolkit/returns.py`, which prints a table or a short key/value block and
never a bar row. Do not read a CSV, do not paste prices into the conversation, and do not compute
a correlation by eye. A year of daily bars for twenty tickers is roughly half a megabyte on disk
and about twenty lines in the transcript, and that gap is the whole point of the store.

(`${CLAUDE_PLUGIN_ROOT}` is this plugin's root directory, substituted automatically by Claude Code.
On a tool that does not substitute it, resolve it yourself relative to this file: two levels up
from `skills/stock-correlation/`.)

## Step 1: resolve each ticker to a store key

Work through these in order, per ticker:

1. **Registry.** `python3 ${CLAUDE_PLUGIN_ROOT}/toolkit/registry.py resolve --yahoo ASML.AS` (or
   `--ibkr AEB:IWDA`) returns the ISIN and every known listing, which is what tells you whether
   the Amsterdam line and the Xetra line are the same fund.
2. **Existing store entry.** `python3 ${CLAUDE_PLUGIN_ROOT}/toolkit/store.py list` prints every
   key with its source, interval, bar count and date range. If the key is already there with
   enough bars, use it. Refetching costs time and changes nothing.
3. **Fetch.** Nothing in the store means calling a provider skill first. Use `yfinance-data` for
   US tickers and for EU listings that carry a Yahoo venue suffix (`.DE`, `.AS`, `.PA`, `.L`,
   `.SW`, `.CO`). Use `ibkr-data` when the user names Interactive Brokers, when the instrument is
   an EU listing Yahoo covers badly, or when venue-exact bars matter (a UCITS ETF quoted on AEB is
   not the same series as its Yahoo `.AS` line at the tick level).

Prefer the same source for both legs of a pair, and say so when you cannot. Yahoo bars are fetched
with `auto_adjust=True` and stored `adjusted: true`; IBKR history closes are not dividend-adjusted
and are stored `adjusted: false`. A correlation across that boundary is wrong on every return that
spans an ex-dividend date, and `returns.py` prints a WARNING line when the flags disagree. Pass
the warning through to the user rather than dropping it.

## Step 2: route the request

| Request | Command |
|---|---|
| Two tickers, relationship details | `returns.py pair KEY_A KEY_B` |
| Three or more tickers, structure | `returns.py matrix KEY [KEY ...]` |
| "Over time", "rolling", "has the correlation changed", "when X drops" | `returns.py rolling KEY_A KEY_B --window 60` |

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/toolkit/returns.py pair yfinance/MSFT yfinance/ASML.AS
python3 ${CLAUDE_PLUGIN_ROOT}/toolkit/returns.py matrix yfinance/AAPL yfinance/MSFT yfinance/NVDA
python3 ${CLAUDE_PLUGIN_ROOT}/toolkit/returns.py rolling yfinance/AAPL yfinance/MSFT --window 60
```

Keys may be written bare (`MSFT`) or qualified (`yfinance/MSFT`). Qualify them whenever the same
symbol could exist under two sources; the script refuses an ambiguous key rather than picking one.
Add `--json` when a follow-up script consumes the numbers, not when a human reads them.

### Defaults

| Parameter | Default |
|---|---|
| Lookback | 1y |
| Interval | daily (`1d`) |
| Method | Pearson on log returns |
| Rolling window | 60 aligned returns |
| Minimum overlap | 60 sessions |
| Notable correlation | 0.60 and above |

Treat 0.60 as the line above which a relationship is worth naming, and say "moderate" between 0.30
and 0.60 rather than reaching for a story. Below 0.30 the honest answer is that these two do not
move together.

### Peer discovery is optional

Finding peers for a single ticker is not wired into the toolkit. Do it only when the user asks for
peers, and do it by hand: assemble a universe of 15 to 30 tickers you can defend (same industry,
same supply chain, the obvious sector names), fetch each one with

```bash
uv run --python 3.12 --with yfinance --with pandas python \
  ${CLAUDE_PLUGIN_ROOT}/toolkit/fetch_yf.py bars TICKER --period 1y
```

then run one `matrix` over the lot and read the target's row. Warn the user first: each ticker is
a separate Yahoo call, thirty of them take a few minutes, and the resulting matrix is a 30x30 table
that is unreadable in a transcript. Cap it at 20 unless the user insists, and report the target's
row plus the strongest and weakest pairs instead of the whole grid. Never present the universe as
exhaustive; it is a list you wrote, not a screen.

## Step 3: report

Print the table or block from `returns.py` verbatim. Do not round its numbers again, retype them
into prose, or reformat the matrix.

Then add, in this order:

**Provenance, one line per key.** Read the sidecar with `store.py show`, which takes a bare key
plus the source and interval as flags. The qualified `source/KEY` form works in `returns.py` and
fails here:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/toolkit/store.py show AEB_IWDA --source ibkr --interval 1d
```

That prints the whole sidecar as a key/value block (`source`, `currency`, `adjusted`,
`delayed_sec`, `start`, `end`, `isin` and the rest). Condense it to one line per key. The target
rendering, which you write from those fields rather than copy from the command:

```
ibkr/AEB_IWDA    source ibkr, EUR, adjusted false, as-of 2026-09-04, delayed 900s
yfinance/MSFT    source yfinance, USD, adjusted true, as-of 2026-09-04, real-time
```

When `delayed_sec` is greater than zero, say the series is delayed by that many seconds and that
the last bar is not live. EU venues report 900.

**Overlap and alignment.** Give the overlap count from the output, then the policy: series are
inner-joined on the session date and a correlation is not reported below 60 shared sessions. When
the overlap is under either input's bar count, name the reason: two venues do not keep the same
holidays, so a US and a EU line lose a handful of sessions to each other's closures. MSFT (252
bars) against ASML.AS (256) overlaps on 248 sessions for exactly that reason.

**The adjustment warning, when there is one.** Copy the WARNING line from `returns.py` and say
which leg is unadjusted. Do not bury it under the correlation.

**Caveats.** Always, not only when they seem relevant:

- Correlation is not causation. Two instruments moving together says nothing about one driving the
  other, and a third factor drives most of what you will find.
- It is regime-dependent. Correlations rise in a sell-off, which is when diversification is
  supposed to help and stops helping.
- It is lookback-sensitive. A different window gives a different number; a 1y correlation is one
  estimate, not the relationship.
- Returns are logarithmic, so beta and correlation here are computed on log returns rather than
  simple returns. The two differ slightly, more so for volatile series.
- Sessions on different continents barely overlap. A European close lands hours before the US
  close, so a same-date correlation between a US and a EU line understates the contemporaneous
  relationship. Read a weak cross-venue number as a session artefact before reading it as
  independence. Two ways round it today: refetch both legs weekly (`fetch_yf.py bars TICKER
  --period 2y --interval 1wk`, or `ONE_WEEK` bars through `ibkr-data`) so a full week absorbs the
  close-time gap, or compare the EU name's US listing instead (ASML on Nasdaq against MSFT) so both
  legs share one session. Lagging one leg by a day is not implemented in `returns.py`; it is a
  later toolkit item.

Never recommend a trade, name an entry, or size a position. Present the numbers and let the user
decide.

Method definitions, the alignment rule and what an `adjusted` mismatch does to a return are in
[`${CLAUDE_SKILL_DIR}/references/methods.md`](./references/methods.md).
(`${CLAUDE_SKILL_DIR}` is this skill's own directory, substituted automatically by Claude Code. On
a tool that does not substitute it, resolve it yourself as this skill's directory, using this
file's known location.)

This skill drafts analysis for your review. It makes no investment recommendations and executes nothing.
