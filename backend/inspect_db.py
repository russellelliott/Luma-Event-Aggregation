import lancedb
import os
import pandas as pd

home_dir = os.path.expanduser("~")
db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")

if os.path.exists(db_path):
    db = lancedb.connect(db_path)
    if "events" in db.table_names():
        table = db.open_table("events")
        df = table.to_pandas()
        
        print(f"Total rows: {len(df)}")
        print(f"Unique api_id count: {df['api_id'].nunique()}")
        
        # Check if event.api_id is accessible and unique
        if 'event' in df.columns:
            # event is a struct, so in pandas it might be a dict or struct
            # We need to extract api_id from it if possible
            try:
                event_api_ids = df['event'].apply(lambda x: x.get('api_id') if isinstance(x, dict) else None)
                print(f"Unique event.api_id count: {event_api_ids.nunique()}")
            except Exception as e:
                print(f"Could not extract event.api_id: {e}")

        # Check if bookmarked column exists
        if 'bookmarked' in df.columns:
            print("bookmarked column already exists")
        else:
            print("bookmarked column does not exist")
            
        print("\nSchema:")
        print(table.schema)
            
    else:
        print("Table 'events' not found.")
else:
    print("Database not found.")
