import lancedb
import os

home_dir = os.path.expanduser("~")
db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")

if os.path.exists(db_path):
    db = lancedb.connect(db_path)
    if "events" in db.table_names():
        table = db.open_table("events")
        df = table.to_pandas()

        if df.empty:
            print("Table 'events' is empty.")
        else:
            print(df.iloc[0].to_dict())
            
    else:
        print("Table 'events' not found.")
else:
    print("Database not found.")
