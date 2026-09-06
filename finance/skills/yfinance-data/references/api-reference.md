# yfinance API reference

The parts of [yfinance](https://github.com/ranaroussi/yfinance) that `toolkit/fetch_yf.py` uses, plus
what you need to read its output. Trimmed from the reference in
[himself65/agent-skills](https://github.com/himself65/agent-skills) `market-analysis`, which covers
the full API.

yfinance is not affiliated with Yahoo. Data is for research, and Yahoo can change or rate-limit it
without notice.

Run everything under `uv run --python 3.12 --with yfinance --with pandas python ...`. Nothing here
installs into the system Python.

## Ticker.history

```python
import yfinance as yf
frame = yf.Ticker("VWCE.DE").history(period="1y", interval="1d", auto_adjust=True)
```

Returns a DataFrame indexed by a tz-aware timestamp, with columns Open, High, Low, Close, Volume,
Dividends, Stock Splits.

- `auto_adjust=True` (what the fetcher uses) rewrites OHLC for splits and dividends and drops the
  separate Adj Close column. The sidecar records `adjusted: true` because of this flag.
- Periods: `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max`.
- Intervals: `1m`, `2m`, `5m`, `15m`, `30m`, `60m`, `90m`, `1h`, `1d`, `1wk`, `1mo`, `3mo`.
- Intraday history is limited: 1m about 7 days back, 2m to 30m about 60 days, 60m and 1h about 730.
- `start=` and `end=` accept dates instead of a period.
- An unknown ticker returns an empty DataFrame rather than raising.

### Timestamps

The index is exchange-local and tz-aware. A daily Amsterdam bar for 2026-09-04 arrives as
`2026-09-04 00:00:00+02:00`, which is 2026-09-03T22:00Z. Take `.date()` or `strftime("%Y-%m-%d")` of
the index for the session date; converting to UTC first files the bar under the previous day.
Comparing the index against a naive `pd.Timestamp` raises TypeError, so build comparison timestamps
with a `tz=` argument or strip the index with `tz_localize(None)`.

## Ticker.fast_info

A lightweight lookup that skips the full quote payload.

```python
fi = yf.Ticker("GLEN.L").fast_info
fi["currency"]   # "GBp" for London, meaning pence
fi["exchange"]   # "LSE", "GER", "AMS", "STO", "NMS"
fi["lastPrice"]
```

It supports both key and attribute access, and raises for a key it does not carry, so wrap lookups
rather than assuming a field is present. The fetcher takes `currency` and `exchange` from here
instead of from `info`, which is slower and often empty for funds.

## Ticker.info

A dict of several hundred keys. The fetcher keeps a whitelist: `shortName`, `longName`, `sector`,
`industry`, `marketCap`, `currency`, `trailingPE`, `forwardPE`, `dividendYield`,
`fiftyTwoWeekHigh`, `fiftyTwoWeekLow`, `sharesOutstanding`, `quoteType`, `exchange`.

For UCITS ETFs, `info` either raises a 404 ("No fundamentals data found") or returns a few fields
with no sector, market cap or P/E. Both are normal outcomes, not errors to retry.

Do not trust `Ticker.isin`. It returns `-` for many instruments and, for some, an ISIN belonging to
a different listing of the same name. This is why the store keeps its own registry.

## yf.download for several tickers

```python
data = yf.download(
    tickers=["MSFT", "IWDA.AS"],
    period="1y",
    interval="1d",
    auto_adjust=True,
    group_by="ticker",
    threads=True,
    progress=False,
)
close = data["MSFT"]["Close"]
```

Faster than a loop of `Ticker.history` because it threads the requests. The store keeps one entry
per ticker, so a bulk download still has to be split per ticker on write. `progress=False` keeps the
progress bar out of captured output.

## Errors worth handling

- Empty DataFrame: wrong ticker, wrong venue suffix, delisted, or a range with no sessions.
- Rate limiting: too many requests in a short window. Space them out; do not retry in a tight loop.
- Missing `info` keys: expected for ETFs, funds and some non-US listings.
- Mixed adjustment: a series fetched with `auto_adjust=False` cannot be correlated against one
  fetched with it. The sidecar's `adjusted` flag is what makes that detectable later.

## Not covered here

Options chains, dividends and splits series, holders and insider transactions, analyst estimates and
recommendations, news, the screener (`yf.Screener`, `yf.EquityQuery`), sector and industry
aggregates, and the financial statement frames. They are in the upstream reference and arrive in a
later slice of this plugin.
