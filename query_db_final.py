import sqlite3
import pandas as pd
conn = sqlite3.connect("artifacts/sa_intraday.sqlite")
run_id = pd.read_sql("SELECT run_id FROM strategy_summary ORDER BY run_id DESC LIMIT 1", conn).iloc[0]["run_id"]
print(f"Latest run_id: {run_id}")
for t in ["strategy_signals", "equity_curve"]:
    df = pd.read_sql(f"SELECT COUNT(DISTINCT trade_day) as count, MIN(trade_day) as min, MAX(trade_day) as max FROM {t} WHERE run_id = '{run_id}'", conn)
    print(f"\nTable: {t}\n{df.to_string(index=False)}")
print(f"\nRow counts for run_id {run_id}:")
for t in ["strategy_signals", "equity_curve", "fills", "trades", "tca_summary", "tca_by_hour"]:
    c = pd.read_sql(f"SELECT COUNT(*) as c FROM {t} WHERE run_id = '{run_id}'", conn).iloc[0]["c"]
    print(f"{t}: {c}")
conn.close()
