import lancedb
import os
import pandas as pd

home_dir = os.path.expanduser("~")
db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
db = lancedb.connect(db_path)

if "city_summary" in db.table_names():
    table = db.open_table("city_summary")
    df = table.to_pandas()
    print("City Summary Keys:")
    for city in df['city'].unique():
        print(f"'{city}'")
else:
    print("city_summary table not found")
