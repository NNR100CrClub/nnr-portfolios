"""
NNR Portfolio Tracker — Price Updater
======================================
Reads data/portfolios.json, fetches live prices from Yahoo Finance
for all tickers (NSE + NYSE/Nasdaq), writes data/prices.json.

Run locally:
    pip install yfinance
    python scripts/update_prices.py

Run via GitHub Actions (automated daily).
"""

import json
import os
import sys
from datetime import datetime, timezone

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance not installed. Run: pip install yfinance")
    sys.exit(1)

# Paths
SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR        = os.path.dirname(SCRIPT_DIR)
PORTFOLIOS_FILE = os.path.join(ROOT_DIR, "data", "portfolios.json")
PRICES_FILE     = os.path.join(ROOT_DIR, "data", "prices.json")


def load_portfolios():
    with open(PORTFOLIOS_FILE, "r") as f:
        data = json.load(f)
    return data.get("portfolios", [])


def extract_all_tickers(portfolios):
    tickers = {}
    for portfolio in portfolios:
        for holding in portfolio.get("holdings", []):
            ticker = holding["ticker"]
            name   = holding.get("name", ticker)
            tickers[ticker] = name
    return tickers


def fetch_prices(tickers: dict) -> dict:
    prices = {}
    ticker_list = list(tickers.keys())
    print(f"  Fetching prices for {len(ticker_list)} tickers: {', '.join(ticker_list)}")

    try:
        data = yf.download(
            ticker_list,
            period="2d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            group_by="ticker"
        )

        for ticker in ticker_list:
            try:
                if len(ticker_list) == 1:
                    closes = data["Close"].dropna()
                else:
                    closes = data[ticker]["Close"].dropna()

                if len(closes) < 1:
                    print(f"  No data for {ticker}")
                    prices[ticker] = {"price": 0.0, "change_pct": 0.0, "name": tickers[ticker]}
                    continue

                current = float(closes.iloc[-1])
                prev    = float(closes.iloc[-2]) if len(closes) >= 2 else current
                change_pct = round(((current - prev) / prev) * 100, 2) if prev else 0.0

                prices[ticker] = {
                    "price":      round(current, 2),
                    "change_pct": change_pct,
                    "name":       tickers[ticker]
                }
                sign = "+" if change_pct >= 0 else ""
                print(f"  OK {ticker:15s} {current:10.2f}  ({sign}{change_pct:.2f}%)")

            except Exception as e:
                print(f"  Error for {ticker}: {e}")
                prices[ticker] = {"price": 0.0, "change_pct": 0.0, "name": tickers[ticker]}

    except Exception as e:
        print(f"  Bulk download failed: {e}")
        print("  Falling back to individual ticker fetches...")
        for ticker, name in tickers.items():
            try:
                tk   = yf.Ticker(ticker)
                hist = tk.history(period="2d")
                if hist.empty:
                    raise ValueError("Empty history")
                current = float(hist["Close"].iloc[-1])
                prev    = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
                change_pct = round(((current - prev) / prev) * 100, 2) if prev else 0.0
                prices[ticker] = {"price": round(current, 2), "change_pct": change_pct, "name": name}
                print(f"  OK {ticker:15s} {current:10.2f}")
            except Exception as e2:
                print(f"  Failed {ticker}: {e2}")
                prices[ticker] = {"price": 0.0, "change_pct": 0.0, "name": name}

    return prices


def write_prices(prices: dict):
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    output = {
        "last_updated": now_utc,
        "source":       "Yahoo Finance via yfinance",
        "prices":       prices
    }
    os.makedirs(os.path.dirname(PRICES_FILE), exist_ok=True)
    with open(PRICES_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {len(prices)} prices to {PRICES_FILE}")
    print(f"Timestamp: {now_utc} UTC")


def main():
    print("=" * 55)
    print("  NNR Portfolio Tracker - Price Updater")
    print("=" * 55)

    print("\nLoading portfolios...")
    portfolios = load_portfolios()
    print(f"   Found {len(portfolios)} portfolio(s)")

    print("\nExtracting tickers...")
    tickers = extract_all_tickers(portfolios)
    print(f"   {len(tickers)} unique ticker(s) across all portfolios")

    print("\nFetching live prices from Yahoo Finance...")
    prices = fetch_prices(tickers)

    print("\nWriting prices.json...")
    write_prices(prices)

    print("\nDone! GitHub Actions will commit this file automatically.")
    print("=" * 55)


if __name__ == "__main__":
    main()
