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

def filter_by_location(events, location=None):
    if not location:
        return events
    location_lower = location.lower()
    return [
        e for e in events
        if e['event'].get('geo_address_info', {}).get('city', '').lower() == location_lower
    ]

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
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    events = load_events(args.file)
    
    filtered_events = apply_filters(
        events,
        location=args.location,
        dates=args.dates,
        weekdays=args.weekdays
    )
    
    print(f"Filtered {len(filtered_events)} events matching criteria.")
    
    # Optional: print event names with start dates
    for e in filtered_events:
        name = e['event'].get('name', 'Unnamed Event')
        start = e['event'].get('start_at', 'No start date')
        city = e['event'].get('geo_address_info', {}).get('city', 'Unknown city')
        print(f"- {name} | Start: {start} UTC | City: {city}")
