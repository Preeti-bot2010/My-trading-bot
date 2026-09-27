"""
Runs ONE check cycle across the watchlist, then exits.
Built for GitHub Actions to call every 10 minutes during market hours
(see .github/workflows/bot.yml) - this is why it doesn't loop internally
like paper_trader.py's run() does.

Writes status.json - a single summary file the mobile dashboard reads.
"""
import csv
import datetime as dt
import json

import config
from angel_data_feed import AngelFeed, is_market_open
from strategy import score_symbol
from paper_trader import PaperPortfolio  # reuses the same portfolio logic

STATUS_FILE = "status.json"


def read_recent_trades(n=20):
    trades = []
    try:
        with open(config.TRADE_LOG_FILE) as f:
            rows = list(csv.DictReader(f))
            trades = rows[-n:]
    except FileNotFoundError:
        pass
    return list(reversed(trades))


def write_status(portfolio: PaperPortfolio, market_open: bool, notes: list):
    pnl = portfolio.cash - config.STARTING_CAPITAL
    status = {
        "last_run": dt.datetime.now().isoformat(timespec="seconds"),
        "market_open": market_open,
        "live_trading": config.LIVE_TRADING,
        "starting_capital": config.STARTING_CAPITAL,
        "cash": round(portfolio.cash, 2),
        "total_pnl": round(pnl, 2),
        "total_pnl_pct": round(pnl / config.STARTING_CAPITAL * 100, 2),
        "open_positions": portfolio.positions,
        "recent_trades": read_recent_trades(),
        "notes": notes,
    }
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2, default=str)


def main():
    portfolio = PaperPortfolio()
    market_open = is_market_open()
    notes = []

    if not market_open:
        write_status(portfolio, market_open, ["Market closed right now - bot is idle."])
        print("Market closed. Nothing to do.")
        return

    feed = AngelFeed()
    feed.login()
    feed.load_instrument_master()

    for symbol in config.WATCHLIST:
        try:
            ltp = feed.get_ltp(symbol)

            if portfolio.has_position(symbol):
                portfolio.check_exit(symbol, ltp)
                notes.append(f"{symbol}: holding position, LTP={ltp:.2f}")
                continue

            df = feed.get_historical_df(symbol)
            signal = score_symbol(df)

            if signal["grade"] in ("A+", "B"):
                portfolio.open_position(symbol, signal)
                notes.append(
                    f"{symbol}: ENTERED {signal['direction']} (grade {signal['grade']}, "
                    f"score {signal['score']}/9)"
                )
            else:
                notes.append(
                    f"{symbol}: no trade (score {signal['score']}/9, grade {signal['grade']})"
                )
        except Exception as e:
            notes.append(f"{symbol}: ERROR - {e}")

    write_status(portfolio, market_open, notes)
    print("Run complete:", notes)


if __name__ == "__main__":
    main()
