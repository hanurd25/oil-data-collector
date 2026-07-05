import yfinance as yf
import pandas as pd
from datetime import datetime, timezone
import os

# Oil benchmarks — both are quoted in USD per barrel.
OIL = {
    "BZ=F": {"name": "Brent Crude", "benchmark": "Brent"},  # international/European benchmark
    "CL=F": {"name": "WTI Crude", "benchmark": "WTI"},      # US benchmark
}

# FX pairs used to convert the USD price into other currencies.
# Each value is quoted as "how many units of that currency per 1 USD"
# EXCEPT EURUSD, which yfinance quotes as USD per 1 EUR (so we invert it below).
FX = {
    "EUR": "EURUSD=X",  # USD per 1 EUR  -> EUR price = USD / rate
    "NOK": "NOK=X",     # NOK per 1 USD  -> NOK price = USD * rate
    "SEK": "SEK=X",     
    "CNY": "CNY=X",
    "JPY": "JPY=X",  
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


def fetch_and_save():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    os.makedirs("data", exist_ok=True)

    # Fetch all FX series once, up front, so every oil bar in this run uses
    # the same (time-aligned) rates.
    fx_series = {cur: fetch_close_series(tkr) for cur, tkr in FX.items()}

    for ticker, meta in OIL.items():
        df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if df.empty:
            print(f"No data for {ticker} (market likely closed)")
            continue
        df = _flatten(df)

        df["price_usd"] = df["Close"]

        # Derive each requested currency, time-aligning the FX rate to each oil bar.
        for cur, series in fx_series.items():
            if series is None:
                df[f"rate_{cur.lower()}"] = pd.NA
                df[f"price_{cur.lower()}"] = pd.NA
                continue
            aligned = series.reindex(df.index, method="ffill")
            df[f"rate_{cur.lower()}"] = aligned.values
            if cur == "EUR":
                # EURUSD is USD per 1 EUR, so EUR price = USD / rate
                df[f"price_{cur.lower()}"] = df["price_usd"] / df[f"rate_{cur.lower()}"]
            else:
                # e.g. NOK=X is NOK per 1 USD, so NOK price = USD * rate
                df[f"price_{cur.lower()}"] = df["price_usd"] * df[f"rate_{cur.lower()}"]

        df["ticker"] = ticker
        df["benchmark"] = meta["benchmark"]
        df["name"] = meta["name"]
        df["fetched_at_utc"] = timestamp

        outfile = f"data/{meta['benchmark']}.csv"
        if os.path.exists(outfile):
            existing = pd.read_csv(outfile, index_col=0, parse_dates=True)
            df = pd.concat([existing, df])
            df = df[~df.index.duplicated(keep="last")]  # dedupe on timestamp, keep freshest
            df = df.sort_index()

        df.to_csv(outfile)
        print(f"Updated {outfile} ({len(df)} rows)")


if __name__ == "__main__":
    fetch_and_save()
