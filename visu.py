"""

"""
import argparse
import math
import os
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator

# ---- Aesthetic theme ---------------------------------------------------------
BG     = "#0d1117"
PANEL  = "#131a24"
GRID   = "#243040"
TEXT   = "#e6edf3"
MUTED  = "#8b98a5"
UP     = "#26c281"
DOWN   = "#ef5f6b"
ACCENT = "#f2a900"

PALETTE = {
    "Brent":    "#f2a900",
    "WTI":      "#4ea8de",
    "NatGas":   "#26c281",
    "HeatOil":  "#c77dff",
    "Gasoline": "#ef5f6b",
}
BENCHMARKS = ["Brent", "WTI", "NatGas", "HeatOil", "Gasoline"]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.edgecolor": GRID,
    "axes.linewidth": 0.8,
})


def _load(benchmark, data_dir, days=None):
    """Load a benchmark CSV, optionally trimmed to the last `days` days."""
    path = os.path.join(data_dir, f"{benchmark}.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if df.empty:
        return None
    if days is not None:
        cutoff = df.index.max() - pd.Timedelta(days=days)
        df = df[df.index >= cutoff]
        if df.empty:
            return None
    return df


def _select(only):
    """Resolve the --only argument into a validated list of benchmarks."""
    if not only:
        return BENCHMARKS
    lookup = {b.lower(): b for b in BENCHMARKS}
    chosen = []
    for raw in only.split(","):
        key = raw.strip().lower()
        if key not in lookup:
            raise SystemExit(
                f"Unknown benchmark '{raw.strip()}'. Choose from: {', '.join(BENCHMARKS)}"
            )
        chosen.append(lookup[key])
    return chosen


def _convert(df, currency, data_dir):
    cur = currency.lower()
    if cur == "usd":
        return df["price_usd"], "USD"
    fx = pd.read_csv(os.path.join(data_dir, "fx_rates.csv"), index_col=0, parse_dates=True)
    rate = fx[cur].reindex(df.index, method="ffill")
    if cur == "eur":
        price = df["price_usd"] / rate      # EURUSD is USD per 1 EUR
    else:
        price = df["price_usd"] * rate      # <CCY>=X is CCY per 1 USD
    return price, currency.upper()


def _theme_ax(ax):
    ax.set_facecolor(PANEL)
    ax.grid(True, color=GRID, linewidth=0.6, alpha=0.7)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))
    ax.xaxis.set_major_locator(MaxNLocator(6))


def _theme_ax_daycount(ax):
    """Same theme, but the x-axis is a plain numeric day counter (1, 2, 3...)."""
    ax.set_facecolor(PANEL)
    ax.grid(True, color=GRID, linewidth=0.6, alpha=0.7)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("Day", color=MUTED, fontsize=9)


def _to_daycount(index, origin):
    """Convert a datetime index into elapsed days since `origin`, starting at day 1."""
    return (index - origin).total_seconds() / 86400.0 + 1.0


def _span_label(days):
    return f"last {days} day{'s' if days != 1 else ''}" if days else "all data"


def grid(currency, data_dir, days=None, only=None, daycount=False):
    names = _select(only)
    loaded = [(bm, _load(bm, data_dir, days)) for bm in names]
    loaded = [(bm, df) for bm, df in loaded if df is not None]
    if not loaded:
        raise SystemExit(f"No data found in {data_dir}/ for: {', '.join(names)}")

    # A single benchmark gets one big panel; more than one uses a 2-col grid.
    cols = 1 if len(loaded) == 1 else 2
    rows = math.ceil(len(loaded) / cols)
    height = 6.5 if len(loaded) == 1 else 3.1 * rows

    fig, axes = plt.subplots(rows, cols, figsize=(13, height))
    fig.patch.set_facecolor(BG)
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    # For day-count mode, day 1 starts at the earliest timestamp across ALL selected
    # benchmarks, so every panel shares the same day numbering.
    origin = min(df.index.min() for _, df in loaded) if daycount else None

    cur_label = currency.upper()
    for i, (bm, df) in enumerate(loaded):
        ax = axes[i]
        price, cur_label = _convert(df, currency, data_dir)
        price = price.dropna()
        color = PALETTE.get(bm, ACCENT)

        x = _to_daycount(price.index, origin) if daycount else price.index

        ax.plot(x, price, color=color, linewidth=1.7)
        ax.fill_between(x, price, price.min(), color=color, alpha=0.08)

        last = price.iloc[-1]
        last_x = x[-1] if daycount else price.index[-1]
        ax.scatter([last_x], [last], color=color, s=22, zorder=5)
        ax.annotate(f" {last:,.2f}", xy=(last_x, last), color=color,
                    fontsize=10, fontweight="bold", va="center")

        _theme_ax_daycount(ax) if daycount else _theme_ax(ax)
        unit = (df["unit"].iloc[-1] if "unit" in df else "").replace("USD", cur_label)
        title_size = 16 if len(loaded) == 1 else 13
        ax.set_title(bm, color=TEXT, fontsize=title_size, fontweight="bold", loc="left", pad=8)
        ax.text(0.0, 1.02, unit, transform=ax.transAxes, color=MUTED, fontsize=9)

        lo, hi = price.min(), price.max()
        pad = (hi - lo) * 0.08 or 0.5
        ax.set_ylim(lo - pad, hi + pad)

    for j in range(len(loaded), len(axes)):
        axes[j].axis("off")

    fig.suptitle("Energy benchmarks — price levels",
                 color=TEXT, fontsize=19, fontweight="bold", x=0.065, ha="left", y=0.99)
    fig.text(0.065, 0.945 if len(loaded) == 1 else 0.955,
             f"each panel on its own axis · priced in {cur_label} · {_span_label(days)}",
             color=MUTED, fontsize=11, ha="left")
    fig.subplots_adjust(left=0.07, right=0.97, top=0.88 if len(loaded) == 1 else 0.92,
                        bottom=0.10 if len(loaded) == 1 else 0.07,
                        hspace=0.55, wspace=0.16)
    return fig


def candlestick(benchmark, currency, data_dir, days=None, daycount=False):
    df = _load(benchmark, data_dir, days)
    if df is None:
        raise SystemExit(f"No data found for {benchmark} in {data_dir}/ ({_span_label(days)})")
    price, cur = _convert(df, currency, data_dir)
    unit = (df["unit"].iloc[-1] if "unit" in df else "price").replace("USD", cur)
    name = df["name"].iloc[-1] if "name" in df else benchmark

    have_ohlc = all(c in df.columns for c in ["Open", "High", "Low", "Close"])
    have_vol = "Volume" in df.columns

    if have_vol:
        fig, (ax, axv) = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True,
                                      gridspec_kw={"height_ratios": [3.4, 1], "hspace": 0.08})
    else:
        fig, ax = plt.subplots(figsize=(13, 7)); axv = None
    fig.patch.set_facecolor(BG)

    if daycount:
        origin = df.index.min()
        x = _to_daycount(df.index, origin).values
    else:
        x = mdates.date2num(df.index.to_pydatetime())
    if have_ohlc:
        factor = (price / df["Close"]).values
        o = df["Open"].values * factor; h = df["High"].values * factor
        l = df["Low"].values * factor;  c = df["Close"].values * factor
        w = (x[1] - x[0]) * 0.7 if len(x) > 1 else 0.0004
        for xi, oi, hi, li, ci in zip(x, o, h, l, c):
            col = UP if ci >= oi else DOWN
            ax.vlines(xi, li, hi, color=col, linewidth=0.8)
            ax.add_patch(Rectangle((xi - w/2, min(oi, ci)), w, max(abs(ci - oi), 1e-9),
                                   facecolor=col, edgecolor=col, linewidth=0.5))
    else:
        ax.plot(x, price, color=PALETTE.get(benchmark, ACCENT), linewidth=1.6)

    last = price.dropna().iloc[-1]
    last_x = x[-1] if daycount else price.dropna().index[-1]
    ax.annotate(f" {last:,.2f} {cur}", xy=(last_x, last),
                color=ACCENT, fontsize=12, fontweight="bold", va="center")

    _theme_ax_daycount(ax) if daycount else _theme_ax(ax)
    ax.set_ylabel(unit, color=TEXT, fontsize=10)
    ax.set_title(name, color=TEXT, fontsize=18, fontweight="bold", loc="left", pad=14)
    ax.text(0.0, 1.015,
            f"Front-month futures · priced in {cur} · {unit} · {_span_label(days)}",
            transform=ax.transAxes, color=MUTED, fontsize=10)

    if axv is not None:
        vol_w = (1/24/60) if not daycount else (1/24/60)
        axv.bar(x, df["Volume"], width=vol_w, color=MUTED, alpha=0.5)
        _theme_ax_daycount(axv) if daycount else _theme_ax(axv)
        axv.set_ylabel("Volume", color=TEXT, fontsize=9)

    fig.subplots_adjust(left=0.07, right=0.97, top=0.90, bottom=0.12)
    return fig


def compare(currency, data_dir, days=None, only=None, daycount=False):
    names = _select(only)
    fig, ax = plt.subplots(figsize=(13, 7))
    fig.patch.set_facecolor(BG)
    n = 0; cur_label = currency.upper()
    series = []
    for bm in names:
        df = _load(bm, data_dir, days)
        if df is None:
            continue
        price, cur_label = _convert(df, currency, data_dir)
        price = price.dropna()
        if price.empty:
            continue
        series.append((bm, price))
    if not series:
        raise SystemExit(f"No data found in {data_dir}/ for: {', '.join(names)}")

    # shared origin so all lines use the same day numbering
    origin = min(p.index.min() for _, p in series) if daycount else None

    for bm, price in series:
        rebased = price / price.iloc[0] * 100.0
        x = _to_daycount(rebased.index, origin) if daycount else rebased.index
        ax.plot(x, rebased, color=PALETTE.get(bm), linewidth=2.0, label=bm)
        n += 1

    ax.axhline(100, color=MUTED, linewidth=1, linestyle=":")
    _theme_ax_daycount(ax) if daycount else _theme_ax(ax)
    ax.set_ylabel("Rebased to 100 at start", color=TEXT, fontsize=10)
    ax.set_title("Energy benchmarks — relative performance",
                 color=TEXT, fontsize=18, fontweight="bold", loc="left", pad=14)
    ax.text(0.0, 1.015,
            f"rebased to 100 · priced in {cur_label} · {_span_label(days)} · "
            f"only RELATIVE moves are comparable",
            transform=ax.transAxes, color=MUTED, fontsize=10)
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, loc="upper left")
    fig.subplots_adjust(left=0.07, right=0.97, top=0.90, bottom=0.12)
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["grid", "candlestick", "compare"], default="grid")
    ap.add_argument("--benchmark", default="Brent", help="for candlestick mode")
    ap.add_argument("--only", default=None,
                    help="comma-separated benchmarks for grid/compare, e.g. 'Brent' or 'Brent,WTI'")
    ap.add_argument("--days", type=float, default=None,
                    help="only plot the last N days of data (default: all)")
    ap.add_argument("--daycount", action="store_true",
                    help="x-axis shows elapsed day number (1, 2, 3...) instead of dates")
    ap.add_argument("--currency", default="USD", help="USD/EUR/NOK/SEK/CNY/JPY")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out", default="oil_chart.png")
    ap.add_argument("--dpi", type=int, default=160)
    ap.add_argument("--show", action="store_true", help="also open a window (needs tkinter)")
    args = ap.parse_args()

    if args.show:
        matplotlib.use("TkAgg")

    if args.mode == "grid":
        fig = grid(args.currency, args.data_dir, args.days, args.only, args.daycount)
    elif args.mode == "candlestick":
        fig = candlestick(args.benchmark, args.currency, args.data_dir, args.days, args.daycount)
    else:
        fig = compare(args.currency, args.data_dir, args.days, args.only, args.daycount)

    fig.savefig(args.out, dpi=args.dpi, facecolor=fig.get_facecolor())
    print(f"Wrote {os.path.abspath(args.out)}")
    if args.show:
        plt.show()


if __name__ == "__main__":
    main()