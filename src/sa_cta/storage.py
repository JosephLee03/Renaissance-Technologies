from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


class SQLiteStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def write_frame(self, table_name: str, df: pd.DataFrame, if_exists: str = "append") -> None:
        with sqlite3.connect(self.db_path) as conn:
            df.to_sql(table_name, conn, if_exists=if_exists, index=False)

    def read_frame(self, table_name: str) -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
