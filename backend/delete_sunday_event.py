import lancedb
import os

home_dir = os.path.expanduser("~")
db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
db = lancedb.connect(db_path)
table = db.open_table("events")

url_to_remove = "https://lu.ma/sunday-builders-club-salon-for-the-taste-2270"

# Filter out the event
df = table.to_pandas()
initial_count = len(df)

def normalize_url(url):
    if not url: return ""
    if url.startswith("https://luma.com/"):
        url = url.replace("https://luma.com/", "https://lu.ma/")
    return url

# Filter rows where NEITHER the top-level URL nor the nested event URL matches
df = df[~df.apply(lambda row: 
    normalize_url(row.get('url')) == url_to_remove or 
    normalize_url(row.get('event', {}).get('url') if isinstance(row.get('event'), dict) else None) == url_to_remove, 
    axis=1
)]

final_count = len(df)

if initial_count != final_count:
    print(f"Removing {initial_count - final_count} event(s)...")
    # Overwrite the table
    db.create_table("events", data=df, mode="overwrite")
    print("✅ Event removed.")
else:
    print("Event not found.")
