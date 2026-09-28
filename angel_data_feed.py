"""
Thin wrapper around AngelOne's SmartAPI for:
  1. Logging in (API key + client code + PIN + TOTP)
  2. Downloading the instrument master (to map symbol -> token)
  3. Pulling historical candles (for indicators)
  4. Pulling live LTP (last traded price)

This file does NOT place any orders. Order placement lives in a separate,
explicitly-gated function in paper_trader.py.
"""
import datetime as dt
import json
import time

import pandas as pd
import pyotp
import requests
from SmartApi import SmartConnect

import config
from time_utils import now_ist

INSTRUMENT_MASTER_URL = (
    "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
)


class AngelFeed:
    def __init__(self):
        self.smart = SmartConnect(api_key=config.ANGEL_API_KEY)
        self.session = None
        self._token_map = None  # symbol -> {token, exch_seg}

    # ---------- LOGIN ----------
    def login(self):
        totp = pyotp.TOTP(config.ANGEL_TOTP_SECRET).now()
        data = self.smart.generateSession(
            config.ANGEL_CLIENT_CODE, config.ANGEL_PIN, totp
        )
        if not data.get("status"):
            raise RuntimeError(f"AngelOne login failed: {data}")
        self.session = data
        print(f"[login] Connected as {config.ANGEL_CLIENT_CODE}")
        return data

    # ---------- INSTRUMENT LOOKUP ----------
    def load_instrument_master(self, cache_path="instruments_cache.json"):
        """
        Angel doesn't take plain symbol names for historical/LTP calls - it wants
        an exchange token. This downloads their full instrument list once and
        caches it locally so we don't refetch every run.
        """
        try:
            with open(cache_path, "r") as f:
                raw = json.load(f)
            print("[instruments] Loaded from local cache")
        except FileNotFoundError:
            print("[instruments] Downloading instrument master (one-time, ~5-10MB)...")
            resp = requests.get(INSTRUMENT_MASTER_URL, timeout=60)
            resp.raise_for_status()
            raw = resp.json()
            with open(cache_path, "w") as f:
                json.dump(raw, f)

        token_map = {}
        for row in raw:
            # NSE equities look like symbol "RELIANCE-EQ" with exch_seg "NSE"
            if row.get("exch_seg") == "NSE" and row.get("symbol", "").endswith("-EQ"):
                token_map[row["symbol"]] = {
                    "token": row["token"],
                    "exch_seg": row["exch_seg"],
                }
        self._token_map = token_map
        return token_map

    def get_token(self, symbol: str):
        if self._token_map is None:
            self.load_instrument_master()
        info = self._token_map.get(symbol)
        if not info:
            raise ValueError(f"Symbol '{symbol}' not found in instrument master")
        return info

    # ---------- HISTORICAL CANDLES ----------
    def get_historical_df(self, symbol: str) -> pd.DataFrame:
        info = self.get_token(symbol)
        to_date = now_ist()
        from_date = to_date - dt.timedelta(days=config.LOOKBACK_DAYS)

        params = {
            "exchange": info["exch_seg"],
            "symboltoken": info["token"],
            "interval": config.CANDLE_INTERVAL,
            "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
            "todate": to_date.strftime("%Y-%m-%d %H:%M"),
        }
        resp = self.smart.getCandleData(params)
        if not resp.get("status") or not resp.get("data"):
            raise RuntimeError(f"Historical data fetch failed for {symbol}: {resp}")

        df = pd.DataFrame(
            resp["data"], columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df

    # ---------- LIVE LTP ----------
    def get_ltp(self, symbol: str) -> float:
        info = self.get_token(symbol)
        resp = self.smart.ltpData(info["exch_seg"], symbol, info["token"])
        if not resp.get("status"):
            raise RuntimeError(f"LTP fetch failed for {symbol}: {resp}")
        return float(resp["data"]["ltp"])

    # ---------- GENERIC LTP BY EXPLICIT TOKEN (used for options & index) ----------
    def get_ltp_by_token(self, exch_seg: str, symbol: str, token: str) -> float:
        resp = self.smart.ltpData(exch_seg, symbol, token)
        if not resp.get("status"):
            raise RuntimeError(f"LTP fetch failed for {symbol} ({token}): {resp}")
        return float(resp["data"]["ltp"])

    # ---------- INDEX SPOT DATA (for the underlying signal) ----------
    def _find_index_row(self, index_name: str):
        """
        Index rows in Angel's instrument master usually sit under exch_seg
        'NSE' with instrumenttype like 'AMXIDX' and a symbol such as
        'Nifty 50'. Schema fields can shift over time - if this raises,
        open instruments_cache.json and search for your index name to
        confirm the exact 'symbol' string and adjust config.INDEX_SPOT_SYMBOL.
        """
        with open("instruments_cache.json") as f:
            raw = json.load(f)
        for row in raw:
            if row.get("symbol") == index_name and row.get("exch_seg") == "NSE":
                return row
        raise ValueError(
            f"Index '{index_name}' not found in instrument master - check "
            f"instruments_cache.json for the exact symbol name used."
        )

    def get_index_ltp(self, index_name: str) -> float:
        row = self._find_index_row(index_name)
        return self.get_ltp_by_token("NSE", row["symbol"], row["token"])

    def get_index_historical_df(self, index_name: str) -> pd.DataFrame:
        row = self._find_index_row(index_name)
        to_date = now_ist()
        from_date = to_date - dt.timedelta(days=config.LOOKBACK_DAYS)
        params = {
            "exchange": "NSE",
            "symboltoken": row["token"],
            "interval": config.CANDLE_INTERVAL,
            "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
            "todate": to_date.strftime("%Y-%m-%d %H:%M"),
        }
        resp = self.smart.getCandleData(params)
        if not resp.get("status") or not resp.get("data"):
            raise RuntimeError(f"Index historical data fetch failed: {resp}")
        df = pd.DataFrame(
            resp["data"], columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df

    # ---------- OPTION CHAIN ----------
    def list_option_expiries(self, underlying: str) -> list:
        """Returns sorted list of available expiry dates (date objects) for the underlying."""
        with open("instruments_cache.json") as f:
            raw = json.load(f)
        expiries = set()
        for row in raw:
            if (row.get("exch_seg") == config.OPTIONS_EXCH_SEG
                    and row.get("name") == underlying
                    and row.get("instrumenttype") == "OPTIDX"):
                try:
                    expiries.add(dt.datetime.strptime(row["expiry"], "%d%b%Y").date())
                except (ValueError, KeyError):
                    continue
        return sorted(expiries)

    def pick_expiry(self, underlying: str, min_days_to_expiry: int) -> dt.date:
        """
        Implements your rule: if the nearest expiry is <= min_days_to_expiry
        away, skip it and use the NEXT one instead.
        """
        today = dt.date.today()
        expiries = [e for e in self.list_option_expiries(underlying) if e >= today]
        if not expiries:
            raise RuntimeError(f"No upcoming expiries found for {underlying}")

        nearest = expiries[0]
        days_left = (nearest - today).days
        if days_left <= min_days_to_expiry and len(expiries) > 1:
            return expiries[1]
        return nearest

    def get_option_contract(self, underlying: str, expiry: dt.date, strike: float, option_type: str):
        """option_type: 'CE' or 'PE'. Returns {symbol, token, lotsize}."""
        expiry_str = expiry.strftime("%d%b%Y").upper()
        with open("instruments_cache.json") as f:
            raw = json.load(f)
        for row in raw:
            if (row.get("exch_seg") == config.OPTIONS_EXCH_SEG
                    and row.get("name") == underlying
                    and row.get("instrumenttype") == "OPTIDX"
                    and row.get("expiry", "").upper() == expiry_str):
                row_strike = float(row.get("strike", 0)) / 100  # Angel stores strike in paisa
                row_type = "CE" if row.get("symbol", "").endswith("CE") else (
                    "PE" if row.get("symbol", "").endswith("PE") else None)
                if abs(row_strike - strike) < 0.01 and row_type == option_type:
                    return {
                        "symbol": row["symbol"],
                        "token": row["token"],
                        "lotsize": int(row.get("lotsize", config.LOT_SIZE)),
                    }
        raise ValueError(
            f"No contract found for {underlying} {expiry_str} {strike}{option_type} - "
            f"strike may not exist at this interval, check instruments_cache.json"
        )

    @staticmethod
    def nearest_strike(spot_price: float, interval: int) -> float:
        return round(spot_price / interval) * interval


def is_market_open(now: dt.datetime = None) -> bool:
    """NSE cash market hours: 9:15 - 15:30 IST, Mon-Fri. Holidays not checked here."""
    now = now or now_ist()
    if now.weekday() >= 5:
        return False
    start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return start <= now <= end
