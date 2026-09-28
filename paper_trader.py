"""
Main bot loop.

Default mode: PAPER TRADING ONLY.
  - Connects to AngelOne for real, live market data (candles + LTP)
  - Runs the scoring strategy on your watchlist every POLL_INTERVAL_SECONDS
  - "Enters" and "exits" virtual trades, tracks a virtual P&L
  - Logs every trade to trades_log.csv so you can review accuracy honestly

Live mode:
  - Only activates if LIVE_TRADING=true in your .env
  - Even then, place_live_order() is intentionally left as a stub that raises
    NotImplementedError, so a single misconfigured .env can never cause a
    real order to fire by accident. You fill this in yourself, deliberately,
    only after reviewing paper results.
"""
import csv
import datetime as dt
import json
import os
import time

import config
from time_utils import now_ist
from angel_data_feed import AngelFeed, is_market_open
from strategy import score_symbol
from notifier import send_telegram


class PaperPortfolio:
    def __init__(self):
        self.cash = config.STARTING_CAPITAL
        self.positions = {}  # symbol -> dict(direction, qty, entry, sl, target)
        self._load()

    def _load(self):
        if os.path.exists(config.POSITIONS_FILE):
            with open(config.POSITIONS_FILE) as f:
                saved = json.load(f)
                self.cash = saved.get("cash", self.cash)
                self.positions = saved.get("positions", {})

    def _save(self):
        with open(config.POSITIONS_FILE, "w") as f:
            json.dump({"cash": self.cash, "positions": self.positions}, f, indent=2)

    def has_position(self, symbol):
        return symbol in self.positions

    def open_position(self, symbol, signal):
        risk_amount = self.cash * (config.RISK_PER_TRADE_PCT / 100)
        per_share_risk = abs(signal["entry"] - signal["stop_loss"])
        if per_share_risk <= 0:
            return
        qty = max(1, int(risk_amount / per_share_risk))

        self.positions[symbol] = {
            "direction": signal["direction"],
            "qty": qty,
            "entry": signal["entry"],
            "stop_loss": signal["stop_loss"],
            "target": signal["target"],
            "entry_time": now_ist().isoformat(),
            "grade": signal["grade"],
            "reasons": signal["reasons"],
        }
        self._save()
        log_trade_event(symbol, "ENTRY", self.positions[symbol])
        print(f"[PAPER ENTRY] {symbol} {signal['direction']} qty={qty} "
              f"entry={signal['entry']:.2f} SL={signal['stop_loss']:.2f} "
              f"target={signal['target']:.2f} grade={signal['grade']}")
        send_telegram(
            f"🟢 EQUITY ENTRY\n{symbol} {signal['direction']} (Grade {signal['grade']})\n"
            f"Qty: {qty}\nEntry: ₹{signal['entry']:.2f}\n"
            f"SL: ₹{signal['stop_loss']:.2f}  Target: ₹{signal['target']:.2f}"
        )

    def check_exit(self, symbol, ltp):
        pos = self.positions.get(symbol)
        if not pos:
            return None
        hit_sl = (pos["direction"] == "LONG" and ltp <= pos["stop_loss"]) or \
                 (pos["direction"] == "SHORT" and ltp >= pos["stop_loss"])
        hit_target = (pos["direction"] == "LONG" and ltp >= pos["target"]) or \
                     (pos["direction"] == "SHORT" and ltp <= pos["target"])

        if hit_sl or hit_target:
            pnl = (ltp - pos["entry"]) * pos["qty"] if pos["direction"] == "LONG" \
                else (pos["entry"] - ltp) * pos["qty"]
            self.cash += pnl
            result = "TARGET" if hit_target else "STOP_LOSS"
            exit_record = {**pos, "exit_price": ltp, "pnl": pnl, "result": result,
                            "exit_time": now_ist().isoformat()}
            log_trade_event(symbol, f"EXIT_{result}", exit_record)
            print(f"[PAPER EXIT] {symbol} {result} pnl={pnl:.2f} cash={self.cash:.2f}")
            emoji = "🟢" if pnl >= 0 else "🔴"
            send_telegram(
                f"{emoji} EQUITY EXIT\n{symbol} - {result}\n"
                f"P&L: ₹{pnl:.2f}\nVirtual Cash: ₹{self.cash:.2f}"
            )
            del self.positions[symbol]
            self._save()
            return exit_record
        return None


def log_trade_event(symbol, event, data):
    file_exists = os.path.exists(config.TRADE_LOG_FILE)
    with open(config.TRADE_LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "symbol", "event", "data"])
        writer.writerow([now_ist().isoformat(), symbol, event, json.dumps(data)])


def place_live_order(feed: AngelFeed, symbol: str, signal: dict):
    """
    INTENTIONALLY NOT IMPLEMENTED.

    This is the only place in the whole bot that would ever touch real money.
    It's left as a stub on purpose so that flipping LIVE_TRADING=true in your
    .env cannot, by itself, cause a real order. You must come back here and
    write the SmartConnect placeOrder(...) call yourself, deliberately, after
    you have:
      1. Reviewed weeks of paper trading results in trades_log.csv
      2. Decided on real position sizing you're comfortable with
      3. Registered as required under SEBI's algo trading rules with your broker
    """
    raise NotImplementedError(
        "Live order placement is disabled. This is deliberate - see the "
        "docstring in place_live_order(). Review paper trading results first."
    )


def run():
    feed = AngelFeed()
    feed.login()
    feed.load_instrument_master()
    portfolio = PaperPortfolio()

    print(f"Bot started. LIVE_TRADING={config.LIVE_TRADING}. "
          f"Watching: {config.WATCHLIST}")

    while True:
        if not is_market_open():
            print(f"[{now_ist().strftime('%H:%M:%S')}] Market closed. Sleeping...")
            time.sleep(300)
            continue

        for symbol in config.WATCHLIST:
            try:
                ltp = feed.get_ltp(symbol)

                if portfolio.has_position(symbol):
                    portfolio.check_exit(symbol, ltp)
                    continue

                df = feed.get_historical_df(symbol)
                signal = score_symbol(df)

                if signal["grade"] in ("A+", "B"):
                    if config.LIVE_TRADING:
                        place_live_order(feed, symbol, signal)  # will raise until you implement it
                    else:
                        portfolio.open_position(symbol, signal)
                else:
                    print(f"[{symbol}] score={signal['score']} grade={signal['grade']} - no trade")

            except Exception as e:
                print(f"[ERROR] {symbol}: {e}")

        time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
