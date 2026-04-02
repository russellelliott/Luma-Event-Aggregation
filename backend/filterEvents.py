import argparse
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import lancedb
import numpy as np

from normalize_event import normalize_luma_event


def convert_to_serializable(obj):
    if isinstance(obj, np.ndarray):
        return convert_to_serializable(obj.tolist())
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    if isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [convert_to_serializable(item) for item in obj]
    return obj


def _db_path(db_path=None):
    if db_path:
        return db_path
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")


def load_events(db_path=None):
    path = _db_path(db_path)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"LanceDB database not found at {path}\n"
            "Run 'python fetchEvents.py' first to populate the database."
        )

    db = lancedb.connect(path)
    if "events" not in db.table_names():
        raise FileNotFoundError(
            f"'events' table not found in LanceDB at {path}\n"
            "Run 'python fetchEvents.py' first to populate the database."
        )

    table = db.open_table("events")
    raw_events = table.to_pandas().to_dict("records")
    events = [normalize_luma_event(event) for event in raw_events]

    try:
        bookmarked_vectors = [
            e.get("vector")
            for e in events
            if e.get("bookmarked") and isinstance(e.get("vector"), (list, np.ndarray))
        ]
        if bookmarked_vectors:
            bookmark_matrix = np.array(bookmarked_vectors)
            mean_vector = np.mean(bookmark_matrix, axis=0)
            norm_mean = np.linalg.norm(mean_vector)
            if norm_mean > 0:
                mean_vector = mean_vector / norm_mean
                for e in events:
                    vec = e.get("vector")
                    if isinstance(vec, (list, np.ndarray)):
                        vec_np = np.array(vec)
                        norm_vec = np.linalg.norm(vec_np)
                        e["cosine_distance"] = float(1 - np.dot(vec_np / norm_vec, mean_vector)) if norm_vec > 0 else None
                    else:
                        e["cosine_distance"] = None
        else:
            for e in events:
                e["cosine_distance"] = None
    except Exception as exc:
        print(f"Warning: Failed to calculate embeddings distance: {exc}")
        for e in events:
            e.setdefault("cosine_distance", None)

    print(f"Loaded {len(events)} events from LanceDB")
    return events


def get_local_date_and_weekday(utc_iso_str, pacific_tz):
    dt_utc = datetime.fromisoformat(utc_iso_str.replace("Z", "+00:00")).replace(tzinfo=ZoneInfo("UTC"))
    dt_local = dt_utc.astimezone(pacific_tz)
    return dt_local.date(), dt_local.strftime("%A")


def get_city_from_event(event):
    city = event.get("city")
    return city if city else "Unknown city"


def convert_to_local_time(utc_iso_str, timezone_str="America/Los_Angeles"):
    if not utc_iso_str:
        return None
    dt_utc = datetime.fromisoformat(utc_iso_str.replace("Z", "+00:00")).replace(tzinfo=ZoneInfo("UTC"))
    local_tz = ZoneInfo(timezone_str)
    dt_local = dt_utc.astimezone(local_tz)
    return dt_local.strftime("%Y-%m-%d %I:%M %p %Z")


def filter_by_location(events, locations=None):
    if not locations:
        return events
    if isinstance(locations, str):
        locations = [locations]
    locations_lower = {loc.lower() for loc in locations}
    return [e for e in events if (e.get("city") or "").lower() in locations_lower]


def filter_by_dates_or_weekdays(events, dates, weekdays, pacific_tz):
    if not dates and not weekdays:
        return events

    date_set = set(dates) if dates else set()
    weekdays_set = {day.capitalize() for day in weekdays} if weekdays else set()

    filtered = []
    for e in events:
        start_at = e.get("start_at")
        if not start_at:
            continue
        event_date, event_weekday = get_local_date_and_weekday(start_at, pacific_tz)

        match_date = event_date.isoformat() in date_set if dates else False
        match_weekday = event_weekday in weekdays_set if weekdays else False

        if match_date or match_weekday:
            filtered.append(e)

    return filtered


def filter_by_bookmarked(events, bookmarked):
    if not bookmarked:
        return events
    return [e for e in events if e.get("bookmarked", False)]


def filter_by_topics(events, topics):
    if not topics:
        return events
    normalized_topics = {topic.lower() for topic in topics}
    return [
        e
        for e in events
        if isinstance(e.get("topic_label"), str) and e.get("topic_label").lower() in normalized_topics
    ]


def filter_by_future(events, include_past, pacific_tz):
    if include_past:
        return events

    current_date = datetime.now(pacific_tz).date()
    filtered = []
    for e in events:
        start_at = e.get("start_at")
        if not start_at:
            continue
        event_date, _ = get_local_date_and_weekday(start_at, pacific_tz)
        if event_date >= current_date:
            filtered.append(e)
    return filtered


def update_cosine_distances(events):
    try:
        bookmarked_vectors = [
            e.get("vector")
            for e in events
            if e.get("bookmarked") is True and isinstance(e.get("vector"), (list, np.ndarray))
        ]
        if not bookmarked_vectors:
            for e in events:
                e["cosine_distance"] = None
            return

        bookmark_matrix = np.array(bookmarked_vectors)
        mean_vector = np.mean(bookmark_matrix, axis=0)
        norm_mean = np.linalg.norm(mean_vector)
        if norm_mean == 0:
            for e in events:
                e["cosine_distance"] = None
            return

        mean_vector_normalized = mean_vector / norm_mean
        for e in events:
            vec = e.get("vector")
            if isinstance(vec, (list, np.ndarray)):
                vec_np = np.array(vec)
                norm_vec = np.linalg.norm(vec_np)
                e["cosine_distance"] = float(1 - np.dot(vec_np / norm_vec, mean_vector_normalized)) if norm_vec > 0 else None
            else:
                e["cosine_distance"] = None
    except Exception as exc:
        print(f"Error updating cosine distances: {exc}")


def apply_filters(
    events,
    location=None,
    dates=None,
    weekdays=None,
    topics=None,
    bookmarked=False,
    include_past=False,
    recalculate_distances=True,
):
    if recalculate_distances:
        update_cosine_distances(events)

    pacific_tz = ZoneInfo("America/Los_Angeles")
    events = filter_by_future(events, include_past, pacific_tz)
    events = filter_by_location(events, location)
    if dates or weekdays:
        events = filter_by_dates_or_weekdays(events, dates, weekdays, pacific_tz)
    events = filter_by_topics(events, topics)
    events = filter_by_bookmarked(events, bookmarked)
    return events


def parse_args():
    parser = argparse.ArgumentParser(description="Filter events from LanceDB database")
    parser.add_argument("--db", type=str, default=None, help="Path to LanceDB database")
    parser.add_argument("--location", type=str, nargs="*", help="City name(s) to filter by")
    parser.add_argument("--dates", type=str, nargs="*", help="Specific date(s) (YYYY-MM-DD)")
    parser.add_argument("--weekdays", type=str, nargs="*", help="Weekday(s), e.g. Monday Tuesday")
    parser.add_argument("--topic", type=str, nargs="*", help="Topic label(s) to filter by")
    parser.add_argument("--today", action="store_true", help="Filter events happening today")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        events = load_events(db_path=args.db)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)

    if args.today:
        today = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
        args.dates = [today] if not args.dates else args.dates + [today]

    filtered_events = apply_filters(
        events,
        location=args.location,
        dates=args.dates,
        weekdays=args.weekdays,
        topics=args.topic,
    )

    output = []
    for event in filtered_events:
        event_url = event.get("url") or ""
        if event_url and not event_url.startswith("http"):
            event_url = f"https://luma.com/{event_url}"
        output.append(
            {
                "name": event.get("name") or "Unnamed Event",
                "city": get_city_from_event(event),
                "start": convert_to_local_time(event.get("start_at"), event.get("timezone") or "America/Los_Angeles"),
                "end": convert_to_local_time(event.get("end_at"), event.get("timezone") or "America/Los_Angeles"),
                "description": event.get("description"),
                "pricing": event.get("pricing"),
                "topic": event.get("topic_label"),
                "url": event_url,
            }
        )

    print(convert_to_serializable(output))

