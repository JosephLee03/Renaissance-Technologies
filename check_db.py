import yaml
import os
import sqlite3
import re

def get_days_from_dirs(path):
    if not os.path.exists(path):
        return set()
    return {d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)) and re.match(r"^\d{8}", d)}

try:
    with open("config/default.yaml", "r") as f:
        config = yaml.safe_load(f)

    data_root = config["data"]["root"]
    min1_path = os.path.join(data_root, config["data"]["min1_subdir"])
    tick_path = os.path.join(data_root, config["data"]["tick_subdir"])
    db_path = config["database"]["path"]

    min1_days = get_days_from_dirs(min1_path)
    tick_days = get_days_from_dirs(tick_path)
    common_days = sorted(list(min1_days & tick_days))

    print(f"Data Root: {data_root}")
    print(f"Common Days Count: {len(common_days)}")

    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        for table in ["strategy_signals", "equity_curve"]:
            try:
                cursor.execute(f"SELECT COUNT(*), COUNT(DISTINCT trade_day), MIN(trade_day), MAX(trade_day) FROM {table}")
                row_count, distinct_days, min_day, max_day = cursor.fetchone()
                print(f"\nTable: {table}")
                print(f"  Rows: {row_count}")
                print(f"  Distinct Days: {distinct_days}")
                print(f"  Range: {min_day} to {max_day}")
                
                cursor.execute(f"SELECT DISTINCT trade_day FROM {table}")
                db_days = {str(row[0]) for row in cursor.fetchall()}
                missing_days = sorted([d for d in common_days if d not in db_days])
                print(f"  Missing Days: {len(missing_days)}")
                if missing_days:
                    print(f"  First 10 missing: {missing_days[:10]}")
            except Exception as e:
                print(f"Error reading table {table}: {e}")
        
        conn.close()
    else:
        print(f"\nDatabase not found at {db_path}")
except Exception as e:
    print(f"Error: {e}")
