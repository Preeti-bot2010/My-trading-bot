"""
Paper trading portfolio for OPTIONS (not equity).
Key differences from the equity version:
  - P&L is tracked on the option PREMIUM, multiplied by lot size
  - SL/target are % moves on the premium, not the underlying's price
  - Positions are FORCE-CLOSED at config.SQUARE_OFF_TIME every day,
    regardless of SL/target - no carry forward, per your requirement
"""
import csv
import datetime as dt
import json
import os

import config
from notifier import send_telegram
from time_utils import now_ist


class PaperOptionsPortfolio:
    def __init__(self):
        self.cash = config.STARTING_CAPITAL
        self.positions = {}  # key: option symbol -> details
        self._load()

    def _load(self):
        if os.path.exists(config.OPTIONS_POSITIONS_FILE):
            with open(config.OPTIONS_POSITIONS_FILE) as f:
                saved = json.load(f)
                self.cash = saved.get("cash", self.cash)
                self.positions = saved.get("positions", {})

    def _save(self):
        with open(config.OPTIONS_POSITIONS_FILE, "w") as f:
            json.dump({"cash": self.cash, "positions": self.positions}, f, indent=2)

    def has_open_position(self) -> bool:
        return len(self.positions) >= config.MAX_CONCURRENT_OPTION_POSITIONS

    def open_position(self, contract: dict, signal: dict, expiry: dt.date, strike: float, option_type: str, entry_premium: float):
        sl_price = entry_premium * (1 - config.OPTION_SL_PCT / 100)
        target_price = entry_premium * (1 + config.OPTION_TARGET_PCT / 100)

        self.positions[contract["symbol"]] = {
            "underlying_direction": signal["direction"],
            "option_type": option_type,
            "strike": strike,
            "expiry": expiry.isoformat(),
            "token": contract["token"],
            "lotsize": contract["lotsize"],
            "entry_premium": entry_premium,
            "stop_loss": round(sl_price, 2),
            "target": round(target_price, 2),
            "entry_time": now_ist().isoformat(),
            "grade": signal["grade"],
            "reasons": signal["reasons"],
        }
        self._save()
        log_option_trade(contract["symbol"], "ENTRY", self.positions[contract["symbol"]])
        print(f"[PAPER OPTION ENTRY] {contract['symbol']} premium={entry_premium:.2f} "
              f"SL={sl_price:.2f} target={target_price:.2f} grade={signal['grade']}")
        send_telegram(
            f"🟢 OPTIONS ENTRY\n{contract['symbol']}\n"
            f"Strike: {strike} {option_type}  Expiry: {expiry.isoformat()}\n"
            f"Premium: ₹{entry_premium:.2f}\n"
            f"SL: ₹{sl_price:.2f}  Target: ₹{target_price:.2f}\n"
            f"Grade: {signal['grade']}"
        )

    def check_exit(self, symbol: str, current_premium: float, force_square_off: bool = False):
        pos = self.positions.get(symbol)
        if not pos:
            return None

        hit_sl = current_premium <= pos["stop_loss"]
        hit_target = current_premium >= pos["target"]

        if hit_sl or hit_target or force_square_off:
            pnl = (current_premium - pos["entry_premium"]) * pos["lotsize"]
            self.cash += pnl
            if force_square_off and not (hit_sl or hit_target):
                result = "SQUARE_OFF_EOD"
            else:
                result = "TARGET" if hit_target else "STOP_LOSS"
            exit_record = {**pos, "exit_premium": current_premium, "pnl": round(pnl, 2),
                            "result": result, "exit_time": now_ist().isoformat()}
            log_option_trade(symbol, f"EXIT_{result}", exit_record)
            print(f"[PAPER OPTION EXIT] {symbol} {result} pnl={pnl:.2f} cash={self.cash:.2f}")
            emoji = "🟢" if pnl >= 0 else "🔴"
            send_telegram(
                f"{emoji} OPTIONS EXIT\n{symbol} - {result}\n"
                f"P&L: ₹{pnl:.2f}\nVirtual Cash: ₹{self.cash:.2f}"
            )
            del self.positions[symbol]
            self._save()
            return exit_record
        return None


def log_option_trade(symbol, event, data):
    file_exists = os.path.exists(config.OPTIONS_TRADE_LOG_FILE)
    with open(config.OPTIONS_TRADE_LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "symbol", "event", "data"])
        writer.writerow([now_ist().isoformat(), symbol, event, json.dumps(data)])


def is_past_square_off_time() -> bool:
    now = now_ist().time()
    cutoff = dt.datetime.strptime(config.SQUARE_OFF_TIME, "%H:%M").time()
    return now >= cutoff


def is_within_entry_window() -> bool:
    now = now_ist().time()
    start = dt.datetime.strptime(config.NO_NEW_ENTRY_BEFORE, "%H:%M").time()
    end = dt.datetime.strptime(config.NO_NEW_ENTRY_AFTER, "%H:%M").time()
    return start <= now <= end
