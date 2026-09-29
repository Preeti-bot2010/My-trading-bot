"""
Central configuration for the bot.
Loads secrets from a local .env file (never hardcode credentials in code).
"""
import os
from dotenv import load_dotenv

load_dotenv()

ANGEL_API_KEY = os.getenv("ANGEL_API_KEY", "").strip()
ANGEL_CLIENT_CODE = os.getenv("ANGEL_CLIENT_CODE", "").strip()
ANGEL_PIN = os.getenv("ANGEL_PIN", "").strip()
ANGEL_TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET", "").strip().replace(" ", "")

# ---- Telegram alerts (optional - leave blank to disable) ----
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Safety switch: stays False (paper trading) unless you explicitly set
# LIVE_TRADING=true in your .env AND you understand the risk.
LIVE_TRADING = os.getenv("LIVE_TRADING", "false").strip().lower() == "true"

# ---- Strategy / risk settings ----
WATCHLIST = ["RELIANCE-EQ", "TCS-EQ", "HDFCBANK-EQ", "INFY-EQ", "SBIN-EQ"]

CANDLE_INTERVAL = "FIFTEEN_MINUTE"   # Angel interval codes: ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, ONE_DAY, etc.
LOOKBACK_DAYS = 15                   # how many days of candles to pull for indicator calculation

RISK_PER_TRADE_PCT = 1.0             # % of virtual capital risked per trade
STARTING_CAPITAL = 100000.0          # virtual paper-trading capital (INR)

MIN_SCORE_FOR_ENTRY = 5              # out of 9 -> see strategy.py scoring table
RISK_REWARD_RATIO = 2.0              # target distance = SL distance * this

POLL_INTERVAL_SECONDS = 60           # how often the bot checks the market during trading hours

TRADE_LOG_FILE = "trades_log.csv"
POSITIONS_FILE = "open_positions.json"

# =====================================================================
# OPTIONS TRADING CONFIG (used by run_once.py, which is now options-first)
# =====================================================================

# Which index to trade options on. NIFTY has the deepest liquidity and,
# as of 2026, is the only NSE index with WEEKLY expiry (every Tuesday).
# Bank Nifty currently has MONTHLY expiry only (weekly discontinued Nov 2024).
UNDERLYING = "NIFTY"

# The index's own trading symbol/token lookup name in Angel's instrument
# master and the exchange segment options trade on.
INDEX_SPOT_SYMBOL = "Nifty 50"     # for fetching spot LTP/candles (exch_seg NSE)
OPTIONS_EXCH_SEG = "NFO"           # options trade on the F&O segment

STRIKE_INTERVAL = 50               # Nifty strikes are in multiples of 50
LOT_SIZE = 65                      # Nifty lot size, effective Jan 2026 - VERIFY
                                    # against your broker before going live;
                                    # NSE revises this periodically.

# ---- Rule: roll to next expiry if too close (your requirement) ----
MIN_DAYS_TO_EXPIRY = 4              # if current weekly expiry is <=4 days away,
                                     # use NEXT week's expiry instead (avoids
                                     # extreme theta decay / gamma risk near expiry)

# ---- Rule: intraday only, no carry forward (your requirement) ----
SQUARE_OFF_TIME = "15:20"           # force-close any open option position by
                                     # this time, no matter what SL/target says
NO_NEW_ENTRY_AFTER = "14:45"        # don't open new positions this late in the day
NO_NEW_ENTRY_BEFORE = "09:30"       # skip the first 15 min - opening volatility
                                     # gives unreliable signals

# ---- Option-specific risk management ----
# SL/target are on the OPTION PREMIUM (%), not on the underlying index price -
# premiums move much faster and non-linearly, so underlying-based SL doesn't work.
OPTION_SL_PCT = 30.0                 # exit if premium drops 30% from entry
OPTION_TARGET_PCT = 60.0             # exit if premium rises 60% from entry
MAX_CONCURRENT_OPTION_POSITIONS = 1  # only one option trade open at a time -
                                      # keeps risk contained while this is unproven

OPTIONS_TRADE_LOG_FILE = "options_trades_log.csv"
OPTIONS_POSITIONS_FILE = "options_open_positions.json"
