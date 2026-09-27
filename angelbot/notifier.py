"""
Sends trade alerts to Telegram. If TELEGRAM_TOKEN / TELEGRAM_CHAT_ID aren't
set in .env, this silently does nothing - the bot still works fine without
Telegram configured, notifications are just skipped.
"""
import requests

import config


def send_telegram(message: str):
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        return  # not configured - skip quietly

    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(
            url,
            data={"chat_id": config.TELEGRAM_CHAT_ID, "text": message},
            timeout=10,
        )
    except Exception as e:
        # Never let a Telegram failure break the trading bot itself
        print(f"[telegram] notification failed: {e}")
