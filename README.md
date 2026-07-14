# oil-data-collector

Automated collection of high-density oil price data using GitHub Actions and `yfinance`. Tracks the two global crude benchmarks (Brent and WTI) in USD, and derives prices in other currencies (EUR by default) so that oil-supply moves can be separated from currency moves.

## Design: store USD + rate, derive the rest

Crude oil is quoted in USD per barrel globally. If you only stored a EUR price, you would permanently blend two different signals — the oil move and the USD move — with no way to separate them later.

Instead, each row stores:

- `price_usd` — the raw benchmark price in USD
- `rate_eur` — the EUR/USD exchange rate at that moment
- `price_eur` — the derived EUR price (`price_usd / rate_eur`)

Because the raw rate is stored, you can reconstruct the price in *any* currency afterward without re-collecting data.

## Instruments

| Instrument | yfinance ticker | Notes |
|---|---|---|
| Brent Crude | `BZ=F` | International / European benchmark |
| WTI Crude | `CL=F` | US benchmark |
| EUR/USD | `EURUSD=X` | Quoted as USD per 1 EUR (inverted in code) |

## How it works

- `.github/workflows/collect.yml` runs the collector on a cron schedule — no laptop or server needs to stay on.
- `scripts/fetch_oil.py` fetches 1-minute bars for each benchmark, aligns the FX rate to each bar by timestamp, and writes one CSV per benchmark to `data/`.
- Each run merges new data into the existing CSV, drops duplicate timestamps (keeping the freshest), and commits the result back to the repo.

## Repo structure

```
oil-data-collector/
├── .github/
│   └── workflows/
│       └── collect.yml       # schedule + CI steps
├── scripts/
│   └── fetch_oil.py          # fetch + currency-conversion logic
├── data/                     # CSVs land here (auto-committed): Brent.csv, WTI.csv
├── requirements.txt
├── .gitignore
└── README.md
```

## Setup

1. Create the repo on GitHub and add these files.
2. In **Settings → Actions → General → Workflow permissions**, select **"Read and write permissions"** so the workflow can commit data back.
3. Go to the **Actions** tab and manually trigger the workflow once (`Run workflow`) to confirm it works before relying on the schedule.

## Adjustments

### Adding more currencies

Edit the `FX` dictionary in `scripts/fetch_oil.py`. For most pairs yfinance quotes "units per 1 USD", so the price is `USD * rate`; EUR is the exception (quoted as USD per 1 EUR), handled in code:

```python
FX = {
    "EUR": "EURUSD=X",  # USD per 1 EUR  -> EUR price = USD / rate
    "NOK": "NOK=X",     # NOK per 1 USD  -> NOK price = USD * rate
    "SEK": "SEK=X",     # SEK per 1 USD  -> SEK price = USD * rate
}
```

### Adjusting the schedule

Oil futures trade nearly 24h a day, Mon-Fri, so the default window is wide. Edit the `cron` line in `.github/workflows/collect.yml` (all times UTC):

| Goal | Cron | Approx. runs/month |
|---|---|---|
| Every 15 min, 24h, weekdays | `*/15 0-23 * * 1-5` | ~2900 |
| Every 30 min, 24h, weekdays (default) | `*/30 0-23 * * 1-5` | ~1450 |
| Every 30 min, incl. Sunday evening session | `*/30 0-23 * * 0-5` | ~1750 |
| Once per hour, 24h, weekdays | `0 0-23 * * 1-5` | ~730 |
| Every 30 min, main EU+US overlap only (12-21 UTC) | `*/30 12-21 * * 1-5` | ~430 |

Note: the wide 24h window uses more GitHub Actions minutes than the stock collector. With the free tier (2,000 min/month) or the Student Pack bump (3,000 min/month), every-30-min is comfortable; every-15-min in a private repo could get tight. A public repo has unlimited Actions minutes.

### CSV vs. other formats

CSV is fine at this scale (a few instruments, minute resolution) and stays git-diff-friendly. If you later expand to many instruments or want smaller files with typed columns, Parquet is the natural upgrade (`df.to_parquet(...)` instead of `to_csv`), at the cost of no longer being human-readable in diffs. For very long-term or high-instrument-count collection, a time-series database (TimescaleDB, InfluxDB) is the better home than files in git.


## Visualization

`Modes:`
  grid        : each benchmark in its OWN panel, own axis + unit (small multiples). [default]
  candlestick : one benchmark as OHLC candlesticks + volume sub-panel.
  compare     : all benchmarks rebased to 100 on one axis (relative moves).

Optionally converts prices into another currency using data/fx_rates.csv.

`Usage:`
    python visu.py                                        # grid, USD -> oil_chart.png


```powershell
visu.py — static charts from the collected energy data, saved as PNG.
Pure matplotlib: no Kaleido, no Chrome, no browser. Just writes an image file.

Modes:
  grid        : each selected benchmark in its OWN panel, own axis + unit. [default]
  candlestick : one benchmark as OHLC candlesticks + volume sub-panel.
  compare     : selected benchmarks rebased to 100 on one axis (relative moves).

Key options:
  --days N        only plot the last N days of data (default: all)
  --daycount      x-axis shows elapsed day number (1, 2, 3...) instead of calendar dates
  --only A[,B]    only these benchmarks (default: all five)
  --currency CUR  convert prices via data/fx_rates.csv

Usage:
    python visu.py                                     # all benchmarks, all data
    python visu.py --days 3                            # last 3 days only
    python visu.py --only Brent                        # just Brent, single panel
    python visu.py --only Brent,WTI --days 5           # two benchmarks, last 5 days
    python visu.py --daycount                          # x-axis = 1, 2, 3, ... not dates
    python visu.py --only Brent --daycount --days 7
    python visu.py --mode candlestick --benchmark Brent --days 1
    python visu.py --mode compare --currency EUR --days 7 --daycount


    Excamples: python visu.py --only NatGas --daycount
              python visu.py --only Brent,WTI --daycount
              python visu.py --only NatGas,Brent --daycount
              python visu.py --only NatGas
```
## License

Personal research project — no license specified.
