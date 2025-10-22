import json
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse

def load_events(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def get_local_date_and_weekday(utc_iso_str, pacific_tz):
    dt_utc = datetime.fromisoformat(utc_iso_str.replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
    dt_local = dt_utc.astimezone(pacific_tz)
    return dt_local.date(), dt_local.strftime("%A")

def get_city_from_event(event):
    """Extract city from event, checking both city and city_state fields."""
    geo_info = event.get('geo_address_info', {})
    
    # First try to get city directly
    city = geo_info.get('city', '')
    if city:
        return city
    
    # Fallback: extract city from city_state (e.g., "Mountain View, California" -> "Mountain View")
    city_state = geo_info.get('city_state', '')
    if city_state and ',' in city_state:
        return city_state.split(',')[0].strip()
    
    return 'Unknown city'

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
        city = get_city_from_event(e['event'])
        if city.lower() == location_lower:
            filtered.append(e)
    return filtered

def filter_by_dates(events, dates, pacific_tz):
    if not dates:
        return events
    date_set = set(dates)
    filtered = []
    for e in events:
        start_at = e['event'].get('start_at')
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
        start_at = e['event'].get('start_at')
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
    parser = argparse.ArgumentParser(description='Filter events from combined_events.json')
    parser.add_argument('--file', type=str, default='aggregatedEvents/combined_events.json', help='Path to combined events JSON file')
    parser.add_argument('--location', type=str, help='City name to filter by (case-insensitive)')
    parser.add_argument('--dates', type=str, nargs='*', help='Specific date(s) to filter by (YYYY-MM-DD)')
    parser.add_argument('--weekdays', type=str, nargs='*', help='Weekday(s) to filter by (e.g., Monday Tuesday)')
    parser.add_argument('--today', action='store_true', help='Filter events happening today')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    events = load_events(args.file)
    
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
        event_data = e['event']
        timezone = event_data.get('timezone', 'America/Los_Angeles')
        
        output.append({
            'name': event_data.get('name', 'Unnamed Event'),
            'city': get_city_from_event(event_data),
            'start': convert_to_local_time(event_data.get('start_at'), timezone),
            'end': convert_to_local_time(event_data.get('end_at'), timezone)
        })
    
    # Print summary and JSON output
    print(f"Filtered {len(output)} events matching criteria.\n")
    print(json.dumps(output, indent=2))

