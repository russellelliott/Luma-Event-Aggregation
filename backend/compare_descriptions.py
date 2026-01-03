import lancedb
import os
import pandas as pd

home_dir = os.path.expanduser("~")
db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
db = lancedb.connect(db_path)
table = db.open_table("events")

df = table.to_pandas()

# Find Sunday Builders Club
builders_club_url = "https://lu.ma/sunday-builders-club-salon-for-the-taste-2270"
builders_club = None

# Find Sundays in SF (searching by name or description content)
sundays_sf = None

def normalize_url(url):
    if not url: return ""
    if url.startswith("https://luma.com/"):
        url = url.replace("https://luma.com/", "https://lu.ma/")
    return url

for index, row in df.iterrows():
    row_url = row.get('url')
    nested_url = row.get('event', {}).get('url') if isinstance(row.get('event'), dict) else None
    
    name = row.get('event', {}).get('name', '') if isinstance(row.get('event'), dict) else row.get('name', '')
    desc = row.get('event', {}).get('description', '') if isinstance(row.get('event'), dict) else row.get('description', '')
    
    if normalize_url(row_url) == builders_club_url or normalize_url(nested_url) == builders_club_url:
        builders_club = row
    
    if "Sundays in SF" in name or "Sundays in SF" in str(desc):
        sundays_sf = row

print("--- Sunday Builders Club ---")
if builders_club is not None:
    desc = builders_club.get('event', {}).get('description')
    print(f"Length: {len(desc) if desc else 0}")
    print(f"Preview: {desc[:100] if desc else 'None'}...")
else:
    print("Not found")

print("\n--- Sundays in SF ---")
if sundays_sf is not None:
    desc = sundays_sf.get('event', {}).get('description')
    print(f"Length: {len(desc) if desc else 0}")
    print(f"Preview: {desc[:100] if desc else 'None'}...")
else:
    print("Not found")
