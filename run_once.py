"""
Runs ONE combined check cycle - EQUITY watchlist + NIFTY OPTIONS - then exits.
Called every 10 minutes by GitHub Actions during market hours
(.github/workflows/bot.yml).

Two completely separate virtual portfolios are tracked (separate starting
capital, separate P&L, separate trade logs) so you can judge each strategy's
accuracy independently before deciding which (if either) to ever go live with:

  - Equity: config.WATCHLIST stocks, scoring strategy from strategy.py
  - Options: config.UNDERLYING (NIFTY) CE/PE buying, same scoring strategy
    applied to the index, with expiry-rollover and same-day square-off rules

Telegram alerts (if configured) are sent directly from inside
PaperPortfolio / PaperOptionsPortfolio at the moment each trade happens -
see notifier.py. This file does not send Telegram messages itself, so
there's exactly one place that fires each alert.

Both sections get written into one status.json so the dashboard can show
both side by side.
"""
import csv
import datetime as dt
import json

import config
from angel_data_feed import AngelFeed, is_market_open
from strategy import score_symbol
from paper_trader import PaperPortfolio
from options_paper_trader import (
    PaperOptionsPortfolio,
    is_past_square_off_time,
    is_within_entry_window,
)

STATUS_FILE = "status.json"


def read_recent_rows(path, n=20):
    try:
        with open(path) as f:
            rows = list(csv.DictReader(f))
            return list(reversed(rows[-n:]))
    except FileNotFoundError:
        return []


def run_equity_pass(feed: AngelFeed) -> dict:
    portfolio = PaperPortfolio()
    notes = []

    for symbol in config.WATCHLIST:
        try:
            ltp = feed.get_ltp(symbol)

            if portfolio.has_position(symbol):
                portfolio.check_exit(symbol, ltp)
                notes.append(f"{symbol}: holding/checked, LTP={ltp:.2f}")
                continue

            df = feed.get_historical_df(symbol)
            signal = score_symbol(df)

            if signal["grade"] in ("A+", "B"):
                portfolio.open_position(symbol, signal)
                notes.append(f"{symbol}: ENTERED {signal['direction']} "
                              f"(grade {signal['grade']}, score {signal['score']}/9)")
            else:
                notes.append(f"{symbol}: no trade (score {signal['score']}/9, grade {signal['grade']})")
        except Exception as e:
            notes.append(f"{symbol}: ERROR - {e}")

    pnl = portfolio.cash - config.STARTING_CAPITAL
    return {
        "starting_capital": config.STARTING_CAPITAL,
        "cash": round(portfolio.cash, 2),
        "total_pnl": round(pnl, 2),
        "total_pnl_pct": round(pnl / config.STARTING_CAPITAL * 100, 2),
        "open_positions": portfolio.positions,
        "recent_trades": read_recent_rows(config.TRADE_LOG_FILE),
        "notes": notes,
    }


def run_options_pass(feed: AngelFeed) -> dict:
    portfolio = PaperOptionsPortfolio()
    notes = []

    if portfolio.positions:
        symbol = next(iter(portfolio.positions))
        pos = portfolio.positions[symbol]
        try:
            premium = feed.get_ltp_by_token(config.OPTIONS_EXCH_SEG, symbol, pos["token"])
            force_close = is_past_square_off_time()
            portfolio.check_exit(symbol, premium, force_square_off=force_close)
            if force_close:
                notes.append(f"{symbol}: forced same-day square-off at {premium:.2f}")
            else:
                notes.append(f"{symbol}: holding/checked, premium={premium:.2f}, "
                              f"SL={pos['stop_loss']}, target={pos['target']}")
        except Exception as e:
            notes.append(f"{symbol}: ERROR checking position - {e}")

    elif not is_within_entry_window():
        notes.append(f"Outside entry window ({config.NO_NEW_ENTRY_BEFORE}-"
                      f"{config.NO_NEW_ENTRY_AFTER}) - no new option trades.")

    else:
        try:
            index_df = feed.get_index_historical_df(config.INDEX_SPOT_SYMBOL)
            signal = score_symbol(index_df)

            if signal["grade"] not in ("A+", "B"):
                notes.append(f"{config.UNDERLYING}: no trade (score {signal['score']}/9, "
                              f"grade {signal['grade']})")
            else:
                option_type = "CE" if signal["direction"] == "LONG" else "PE"
                expiry = feed.pick_expiry(config.UNDERLYING, config.MIN_DAYS_TO_EXPIRY)
                days_left = (expiry - dt.date.today()).days
                notes.append(f"Selected expiry {expiry.isoformat()} ({days_left} days left)")

                spot = feed.get_index_ltp(config.INDEX_SPOT_SYMBOL)
                strike = feed.nearest_strike(spot, config.STRIKE_INTERVAL)
                contract = feed.get_option_contract(config.UNDERLYING, expiry, strike, option_type)
                entry_premium = feed.get_ltp_by_token(
                    config.OPTIONS_EXCH_SEG, contract["symbol"], contract["token"])

                portfolio.open_position(contract, signal, expiry, strike, option_type, entry_premium)
                notes.append(f"ENTERED {contract['symbol']} @ {entry_premium:.2f} "
                              f"(grade {signal['grade']}, score {signal['score']}/9)")
        except Exception as e:
            notes.append(f"ERROR during entry evaluation - {e}")

    pnl = portfolio.cash - config.STARTING_CAPITAL
    return {
        "starting_capital": config.STARTING_CAPITAL,
        "cash": round(portfolio.cash, 2),
        "total_pnl": round(pnl, 2),
        "total_pnl_pct": round(pnl / config.STARTING_CAPITAL * 100, 2),
        "open_positions": portfolio.positions,
        "recent_trades": read_recent_rows(config.OPTIONS_TRADE_LOG_FILE),
        "notes": notes,
    }


def write_status(market_open: bool, equity: dict = None, options: dict = None):
    status = {
        "last_run": dt.datetime.now().isoformat(timespec="seconds"),
        "market_open": market_open,
        "live_trading": config.LIVE_TRADING,
        "equity": equity,
        "options": options,
    }
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2, default=str)


def main():
    market_open = is_market_open()

    if not market_open:
        write_status(market_open, equity=None, options=None)
        print("Market closed. Nothing to do.")
        return

    feed = AngelFeed()
    feed.login()
    feed.load_instrument_master()

    equity_result = run_equity_pass(feed)
    options_result = run_options_pass(feed)

    write_status(market_open, equity=equity_result, options=options_result)
    print("Equity notes:", equity_result["notes"])
    print("Options notes:", options_result["notes"])


if __name__ == "__main__":
    main()
