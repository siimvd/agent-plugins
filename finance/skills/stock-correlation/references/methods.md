# Methods

What `toolkit/returns.py` computes, and the assumptions behind each number.

## Log returns

For consecutive closes, the return is `r_t = ln(close_t / close_{t-1})`, stamped with the later
bar's session date. A series of n bars yields n-1 returns. Log returns add over time, which is why
they are used here: a window's total return is the sum of its daily returns, and no compounding
correction is needed when a window is resampled.

Log and simple returns are close for small moves and diverge as moves get large, so a correlation
computed on log returns is not identical to one computed on simple returns. Say which you used.
This toolkit always uses log.

## Pearson correlation

`corr(a, b) = cov(a, b) / (sd(a) * sd(b))`, computed from centred sums of products over the
aligned returns. Range -1 to 1. It measures the strength of the linear relationship only: two
series with an obvious non-linear relationship can show a correlation near zero.

The estimate is noisy: with 250 daily observations the standard error of a correlation near zero is
roughly `1 / sqrt(n)`, about 0.06, so a reported 0.05 and a reported -0.05 are the same result.

## Beta

`beta(a, b) = cov(a, b) / var(b)`, with `b` the benchmark. It answers how far `a` moves per unit
move of `b`, in the same units as the returns. Correlation is scale-free and beta is not, so a low
correlation with a high beta means `a` responds strongly but erratically.

`returns.py pair` reports `beta_a_on_b`: the first key regressed on the second. Swapping the
arguments changes beta but not the correlation.

## R-squared

The square of the correlation, the share of one series' variance the other accounts for under a
linear fit. A correlation of 0.60 is an R-squared of 0.36, so most of the variation is
still unexplained, which is what stops a 0.6 being read as "mostly the same thing".

## Rolling window

`returns.py rolling` recomputes the correlation over each window of consecutive aligned returns,
default 60, and stamps each with its last session's date. With m aligned returns there are
`m - window + 1` windows. Long windows are stable and slow to notice a regime change; short
windows react quickly and are mostly noise. 60 sessions, about a quarter, is the compromise this
skill defaults to.

The printed table is strided so it stays short; the minimum and maximum windows are always
included and labelled.

## Alignment and minimum overlap

Two series are inner-joined on the session date from the store's `date` column, never by position.
Position alignment silently pairs a Tuesday in Amsterdam with a Monday in New York the moment one
venue takes a holiday the other does not, and the correlation that comes out looks fine.

The inner join means overlap is at most the shorter series and usually less. US and EU venues keep
different holiday calendars: over a year, MSFT (252 bars) and ASML.AS (256 bars) share 248
sessions. A large drop is a signal, not an inconvenience, and `returns.py` reports the dropped
count per key.

Below 60 shared sessions no correlation is printed at all; the command fails with the overlap it
found. Override with `--min-overlap` only when you intend to look at a short window and will say
so in the answer.

Sessions on different continents also do not overlap in clock time. The European close is hours
before the US close, so same-date returns compare partially different information sets and a
cross-venue correlation understates the contemporaneous relationship. Weekly bars mostly absorb the
gap, and an EU name's US listing removes it entirely by putting both legs in one session. Lagging
one leg by a day is not implemented and is a later toolkit item.

## Adjusted mismatch

The sidecar's `adjusted` flag records whether the provider's closes are adjusted for dividends and
splits. Yahoo bars are fetched with `auto_adjust=True` and stored `adjusted: true`. IBKR history
closes are not dividend-adjusted and are stored `adjusted: false`.

An unadjusted series shows a fake negative return on every ex-dividend date, of the size of the
dividend, and a fake jump of the split ratio on every split. An adjusted one does not. Correlating
one against the other injects a spurious move into one leg on dates where the other has none, which
biases the correlation and can flip the sign of a weak one. `returns.py` prints a WARNING when the
flags disagree or when either is unknown, and the fix is to refetch both legs from one provider,
not to ignore the line.

## Not implemented

Regime-conditional correlation (splitting returns into up days, down days, high-volatility days and
drawdowns, then correlating within each) is in the source skill and is not implemented here. It
needs a defensible regime definition and enough observations per bucket, and the rolling window
answers most of what it was used for.

Also absent: hierarchical clustering of a matrix, spread z-scores for pair trading, and any peer
screen. Sub-skill A in the source skill relied on Yahoo's screener; this skill asks you to name the
universe instead.

## Credit

The sub-skill structure (pair, matrix, rolling), the defaults table and the standing caveats come
from himself65/finance-skills, `plugins/market-analysis/skills/stock-correlation`. The
implementation here is stdlib Python over an on-disk store rather than pandas over live downloads.
