"""
Standalone backtester - does NOT need AngelOne API access at all.
Uses free Yahoo Finance data (yfinance) so you can test the strategy's
historical win rate BEFORE ever connecting a broker.

Run: python backtest.py
"""
import pandas as pd
import yfinance as yf

from strategy import score_symbol
import config

# yfinance NSE symbols need a ".NS" suffix, e.g. RELIANCE.NS
BACKTEST_SYMBOLS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "SBIN.NS"]
PERIOD = "2y"
INTERVAL = "1d"   # daily candles for a clean, fast backtest


def run_backtest():
    all_trades = []

    for symbol in BACKTEST_SYMBOLS:
        print(f"\n--- Backtesting {symbol} ---")
        df = yf.download(symbol, period=PERIOD, interval=INTERVAL, progress=False)
        if df.empty:
            print("No data, skipping.")
            continue
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={"date": "timestamp"})

        position = None
        for i in range(55, len(df)):
            window = df.iloc[:i + 1]
            last_close = window.iloc[-1]["close"]

            if position:
                hit_sl = (position["direction"] == "LONG" and last_close <= position["stop_loss"]) or \
                         (position["direction"] == "SHORT" and last_close >= position["stop_loss"])
                hit_target = (position["direction"] == "LONG" and last_close >= position["target"]) or \
                             (position["direction"] == "SHORT" and last_close <= position["target"])
                if hit_sl or hit_target:
                    pnl_pct = ((last_close - position["entry"]) / position["entry"] * 100
                               if position["direction"] == "LONG"
                               else (position["entry"] - last_close) / position["entry"] * 100)
                    result = "TARGET" if hit_target else "STOP_LOSS"
                    all_trades.append({
                        "symbol": symbol, "direction": position["direction"],
                        "entry": position["entry"], "exit": last_close,
                        "pnl_pct": pnl_pct, "result": result, "grade": position["grade"],
                    })
                    position = None
                continue

            signal = score_symbol(window)
            if signal["grade"] in ("A+", "B"):
                position = signal

    trades_df = pd.DataFrame(all_trades)
    if trades_df.empty:
        print("\nNo trades were generated - try lowering MIN_SCORE_FOR_ENTRY in config.py")
        return

    print("\n" + "=" * 50)
    print("BACKTEST SUMMARY")
    print("=" * 50)
    total = len(trades_df)
    wins = (trades_df["result"] == "TARGET").sum()
    win_rate = wins / total * 100
    avg_pnl = trades_df["pnl_pct"].mean()
    print(f"Total trades:  {total}")
    print(f"Win rate:      {win_rate:.1f}%  ({wins} wins / {total - wins} losses)")
    print(f"Avg P&L/trade: {avg_pnl:.2f}%")
    print(f"By grade:\n{trades_df.groupby('grade')['pnl_pct'].agg(['count', 'mean'])}")
    trades_df.to_csv("backtest_results.csv", index=False)
    print("\nFull results saved to backtest_results.csv")


if __name__ == "__main__":
    run_backtest()
