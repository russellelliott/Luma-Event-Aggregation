import json
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import lancedb
import os

def load_events(db_path=None):
    """Load events from LanceDB database.
    
    Args:
        db_path: Path to LanceDB database directory (defaults to ~/.luma-event-aggregation/data)
        
    Returns:
        List of events
        
    Raises:
        FileNotFoundError: If database or events table not found
    """
    # Set default database path if not provided
    if db_path is None:
        home_dir = os.path.expanduser("~")
        db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
    
    # Load from LanceDB
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"LanceDB database not found at {db_path}\n"
            f"Run 'python fetchEvents.py' first to populate the database."
        )
    
    try:
        db = lancedb.connect(db_path)
        if "events" not in db.table_names():
            raise FileNotFoundError(
                f"'events' table not found in LanceDB at {db_path}\n"
                f"Run 'python fetchEvents.py' first to populate the database."
            )
        
        table = db.open_table("events")
        events = table.to_pandas().to_dict('records')
        print(f"📊 Loaded {len(events)} events from LanceDB")
        return events
    except Exception as e:
        raise FileNotFoundError(
            f"Error loading events from LanceDB at {db_path}: {e}\n"
            f"Run 'python fetchEvents.py' first to populate the database."
        )

def get_local_date_and_weekday(utc_iso_str, pacific_tz):
    dt_utc = datetime.fromisoformat(utc_iso_str.replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
    dt_local = dt_utc.astimezone(pacific_tz)
    return dt_local.date(), dt_local.strftime("%A")

def get_city_from_event(event):
    """Extract city from event's geo_address_info."""
    # Handle case where event might be the raw event dict (from API)
    # or might have nested 'event' key (from JSON structure)
    if isinstance(event, dict) and 'event' in event:
        event = event['event']
    
    geo_info = event.get('geo_address_info', {})
    if isinstance(geo_info, dict):
        city = geo_info.get('city') or geo_info.get('city_state', 'Unknown city')
    else:
        city = 'Unknown city'
    
    return city if city else 'Unknown city'

def convert_to_local_time(utc_iso_str, timezone_str="America/Los_Angeles"):
    """Convert UTC timestamp to local timezone."""
    if not utc_iso_str:
        return None
    dt_utc = datetime.fromisoformat(utc_iso_str.replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
    local_tz = ZoneInfo(timezone_str)
    dt_local = dt_utc.astimezone(local_tz)
    return dt_local.strftime("%Y-%m-%d %I:%M %p %Z")

def filter_by_location(events, location=None):
    if not location:
        return events
    location_lower = location.lower()
    filtered = []
    for e in events:
        # Handle both nested and flat event structures
        event_data = e.get('event', e) if isinstance(e, dict) else e
        city = get_city_from_event(event_data)
        if city and city.lower() == location_lower:
            filtered.append(e)
    return filtered

def filter_by_dates(events, dates, pacific_tz):
    if not dates:
        return events
    date_set = set(dates)
    filtered = []
    for e in events:
        # Handle both nested and flat event structures
        event_data = e.get('event', e) if isinstance(e, dict) else e
        start_at = event_data.get('start_at')
        if not start_at:
            continue
        event_date, _ = get_local_date_and_weekday(start_at, pacific_tz)
        if event_date.isoformat() in date_set:
            filtered.append(e)
    return filtered

def filter_by_weekdays(events, weekdays, pacific_tz):
    if not weekdays:
        return events
    weekdays_set = set(day.capitalize() for day in weekdays)
    filtered = []
    for e in events:
        # Handle both nested and flat event structures
        event_data = e.get('event', e) if isinstance(e, dict) else e
        start_at = event_data.get('start_at')
        if not start_at:
            continue
        _, event_weekday = get_local_date_and_weekday(start_at, pacific_tz)
        if event_weekday in weekdays_set:
            filtered.append(e)
    return filtered

def apply_filters(events, location=None, dates=None, weekdays=None):
    pacific_tz = ZoneInfo("America/Los_Angeles")
    events = filter_by_location(events, location)
    events = filter_by_dates(events, dates, pacific_tz)
    events = filter_by_weekdays(events, weekdays, pacific_tz)
    return events

def parse_args():
    parser = argparse.ArgumentParser(description='Filter events from LanceDB database')
    parser.add_argument('--db', type=str, default=None, help='Path to LanceDB database (defaults to ~/.luma-event-aggregation/data/events.db)')
    parser.add_argument('--location', type=str, help='City name to filter by (case-insensitive)')
    parser.add_argument('--dates', type=str, nargs='*', help='Specific date(s) to filter by (YYYY-MM-DD)')
    parser.add_argument('--weekdays', type=str, nargs='*', help='Weekday(s) to filter by (e.g., Monday Tuesday)')
    parser.add_argument('--today', action='store_true', help='Filter events happening today')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    try:
        events = load_events(db_path=args.db)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        exit(1)
    
    # Handle --today flag
    if args.today:
        from datetime import date
        today = date.today().isoformat()
        args.dates = [today] if not args.dates else args.dates + [today]
    
    filtered_events = apply_filters(
        events,
        location=args.location,
        dates=args.dates,
        weekdays=args.weekdays
    )
    
    # Convert to JSON output format with local times
    output = []
    for e in filtered_events:
        # Handle both nested and flat event structures from LanceDB
        event_data = e.get('event', e) if isinstance(e, dict) else e
        timezone = event_data.get('timezone', 'America/Los_Angeles')
        
        output.append({
            'name': event_data.get('name', 'Unnamed Event'),
            'city': get_city_from_event(event_data),
            'start': convert_to_local_time(event_data.get('start_at'), timezone),
            'end': convert_to_local_time(event_data.get('end_at'), timezone),
            'url': f"https://luma.com/{event_data.get('url', '')}"
        })
    
    # Print summary and JSON output
    print(f"Filtered {len(output)} events matching criteria.\n")
    print(json.dumps(output, indent=2))

