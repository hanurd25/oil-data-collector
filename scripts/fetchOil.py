import yfinance as yf
import pandas as pd
from datetime import datetime, timezone
import os

# Energy benchmarks — NOTE: units differ per product, so they are NOT interchangeable.
OIL = {
    "BZ=F": {"name": "Brent Crude",   "benchmark": "Brent",   "unit": "USD/barrel"},
    "CL=F": {"name": "WTI Crude",     "benchmark": "WTI",     "unit": "USD/barrel"},
    "NG=F": {"name": "Natural Gas",   "benchmark": "NatGas",  "unit": "USD/MMBtu"},
    "HO=F": {"name": "Heating Oil",   "benchmark": "HeatOil", "unit": "USD/gallon"},
    "RB=F": {"name": "RBOB Gasoline", "benchmark": "Gasoline","unit": "USD/gallon"},
}

# FX rates are collected on their own and stored ONCE in data/fx_rates.csv.
# We store the raw rate only; currency conversion is done later, at analysis time.
# Quoting convention (as returned by yfinance):
#   EUR -> "EURUSD=X" is USD per 1 EUR   (so EUR price = USD / rate)
#   all others       -> "<CCY>=X" is CCY per 1 USD  (so CCY price = USD * rate)
FX = {
    "eur": "EURUSD=X",
    "nok": "NOK=X",
    "sek": "SEK=X",
    "cny": "CNY=X",
    "jpy": "JPY=X",
}


def _flatten(df):
    """yfinance sometimes returns MultiIndex columns; flatten to the top level."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def fetch_close_series(ticker):
    """Fetch the 1-minute Close series for a ticker, or None if unavailable."""
    df = yf.download(ticker, period="1d", interval="1m", progress=False)
    if df.empty:
        return None
    df = _flatten(df)
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close


def _merge_dedupe_save(new_df, outfile):
    """Append new rows to an existing CSV, drop duplicate timestamps, keep freshest."""
    if os.path.exists(outfile):
        existing = pd.read_csv(outfile, index_col=0, parse_dates=True)
        new_df = pd.concat([existing, new_df])
        new_df = new_df[~new_df.index.duplicated(keep="last")]
        new_df = new_df.sort_index()
    new_df.to_csv(outfile)
    return len(new_df)


def save_fx_rates():
    """Fetch all FX rates and store them together in a single data/fx_rates.csv."""
    cols = {}
    for cur, tkr in FX.items():
        series = fetch_close_series(tkr)
        if series is not None:
            cols[cur] = series
    if not cols:
        print("No FX data (markets likely closed)")
        return
    fx_df = pd.DataFrame(cols)          # one column per currency, aligned on timestamp
    fx_df.index.name = "Datetime"
    n = _merge_dedupe_save(fx_df, "data/fx_rates.csv")
    print(f"Updated data/fx_rates.csv ({n} rows, {len(cols)} currencies)")


def save_oil_prices():
    """Fetch each energy benchmark and store its raw USD price + metadata."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    for ticker, meta in OIL.items():
        df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if df.empty:
            print(f"No data for {ticker} (market likely closed)")
            continue
        df = _flatten(df)
        df["price_usd"] = df["Close"]
        df["ticker"] = ticker
        df["benchmark"] = meta["benchmark"]
        df["name"] = meta["name"]
        df["unit"] = meta["unit"]
        df["fetched_at_utc"] = timestamp
        outfile = f"data/{meta['benchmark']}.csv"
        n = _merge_dedupe_save(df, outfile)
        print(f"Updated {outfile} ({n} rows)")


def fetch_and_save():
    os.makedirs("data", exist_ok=True)
    save_fx_rates()     # rates stored once, separately
    save_oil_prices()   # raw USD prices only


if __name__ == "__main__":
    fetch_and_save()
