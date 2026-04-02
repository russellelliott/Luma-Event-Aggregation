import math
import os
from datetime import datetime
from typing import List, Optional

import lancedb
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from eventDescription import get_luma_event_info
from eventSearch import search_events
from filterEvents import apply_filters, convert_to_serializable, load_events
from normalize_event import normalize_luma_event

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Loading data...")
try:
    ALL_EVENTS = load_events()
    home_dir = os.path.expanduser("~")
    db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
    db = lancedb.connect(db_path)
    CITY_SUMMARY_DF = None
    if "city_summary" in db.list_tables():
        CITY_SUMMARY_DF = db.open_table("city_summary").to_pandas()
    print("Data loaded successfully.")
except Exception as exc:
    print(f"Error loading data: {exc}")
    ALL_EVENTS = []
    CITY_SUMMARY_DF = None


def clean_nans(data):
    if isinstance(data, list):
        return [clean_nans(item) for item in data]
    if isinstance(data, dict):
        return {k: clean_nans(v) for k, v in data.items()}
    if isinstance(data, float):
        if math.isnan(data):
            return None
    if isinstance(data, str):
        if data.lower() in ('nan', 'none', ''):
            return None
    return data


def get_cosine_distance_sort_value(event):
    value = event.get("cosine_distance") if isinstance(event, dict) else None
    if value is None:
        return float("inf")
    try:
        numeric_value = float(value)
        if math.isnan(numeric_value):
            return float("inf")
        return numeric_value
    except (TypeError, ValueError):
        return float("inf")


def get_start_time_sort_value(event):
    start_at = event.get("start_at") if isinstance(event, dict) else None
    if start_at is None:
        return float("inf")

    if isinstance(start_at, (int, float)):
        try:
            numeric_value = float(start_at)
            if math.isnan(numeric_value):
                return float("inf")
            return numeric_value
        except (TypeError, ValueError):
            return float("inf")

    if isinstance(start_at, str):
        normalized = start_at.strip()
        if not normalized:
            return float("inf")
        try:
            return datetime.fromisoformat(normalized.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return float("inf")

    return float("inf")


def enrich_events_with_distance(events):
    if CITY_SUMMARY_DF is None:
        return events

    city_lookup = {}
    for _, row in CITY_SUMMARY_DF.iterrows():
        city_lookup[row["city"]] = {
            "distance_miles": row.get("distance_miles"),
            "duration_minutes": row.get("duration_minutes"),
            "distance_text": row.get("distance_text"),
            "duration_text": row.get("duration_text"),
        }

    enriched_events = []
    for event in events:
        event_copy = event.copy()
        city_key = event_copy.get("city") or "Unknown"
        dist_info = city_lookup.get(city_key)

        if not dist_info and "," in city_key:
            simple_city = city_key.split(",")[0].strip()
            dist_info = city_lookup.get(simple_city)

        if not dist_info and "," not in city_key:
            california_key = f"{city_key}, California"
            dist_info = city_lookup.get(california_key)

        if dist_info:
            event_copy["distance_info"] = dist_info

        enriched_events.append(event_copy)

    return enriched_events


def build_topic_summary(events):
    summary = {}
    for event in events:
        label = event.get("topic_label")
        if not label:
            continue
        if label not in summary:
            summary[label] = {
                "label": label,
                "color": event.get("topic_color") or "#64748B",
                "count": 0,
            }
        summary[label]["count"] += 1
    return sorted(summary.values(), key=lambda x: (-x["count"], x["label"]))


@app.get("/events/all")
def get_all_events(
    topic: Optional[List[str]] = Query(None),
    bookmarked: bool = Query(False),
    include_past: bool = Query(False),
    query: Optional[str] = Query(None),
):
    try:
        events_to_filter = ALL_EVENTS
        if query and query.strip():
            events_copy = [e.copy() for e in ALL_EVENTS]
            events_to_filter = search_events(query, events_copy)
            should_recalc = False
        else:
            should_recalc = True

        filtered_events = apply_filters(
            events_to_filter,
            location=None,
            dates=None,
            weekdays=None,
            topics=topic,
            bookmarked=bookmarked,
            include_past=include_past,
            recalculate_distances=should_recalc,
        )

        response_events = []
        for event in filtered_events:
            event_copy = event.copy()
            url = event_copy.get("url")
            if url and not url.startswith("http"):
                event_copy["url"] = f"https://luma.com/{url}"
            response_events.append(event_copy)

        response_events = enrich_events_with_distance(response_events)
        if query and query.strip():
            response_events.sort(key=get_cosine_distance_sort_value)
        else:
            response_events.sort(key=get_start_time_sort_value)

        return clean_nans(convert_to_serializable(response_events))
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/events")
def get_events(
    location: Optional[List[str]] = Query(None),
    dates: Optional[List[str]] = Query(None),
    weekdays: Optional[List[str]] = Query(None),
    topic: Optional[List[str]] = Query(None),
    bookmarked: bool = Query(False),
    include_past: bool = Query(False),
):
    try:
        filtered_events = apply_filters(
            ALL_EVENTS,
            location=location,
            dates=dates,
            weekdays=weekdays,
            topics=topic,
            bookmarked=bookmarked,
            include_past=include_past,
        )

        response_events = enrich_events_with_distance(filtered_events)
        response_events.sort(key=get_start_time_sort_value)
        return clean_nans(convert_to_serializable(response_events))
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/topics")
def get_topics():
    try:
        return clean_nans(convert_to_serializable(build_topic_summary(ALL_EVENTS)))
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/cities")
def get_cities():
    try:
        if CITY_SUMMARY_DF is None:
            return []
        result = CITY_SUMMARY_DF.to_dict(orient="records")
        return clean_nans(convert_to_serializable(result))
    except Exception as exc:
        return {"error": str(exc)}


class EventUrl(BaseModel):
    url: str


@app.post("/add-event")
def add_event(event_url: EventUrl):
    global ALL_EVENTS
    try:
        info = get_luma_event_info(event_url.url)
        if "error" in info:
            return {"error": info["error"]}

        normalized = normalize_luma_event(
            {
                "name": info.get("name"),
                "url": info.get("url"),
                "start_at": info.get("start_date"),
                "end_at": info.get("end_date"),
                "description": info.get("description"),
                "pricing": info.get("pricing"),
                "location": {
                    "latitude": info.get("latitude"),
                    "longitude": info.get("longitude"),
                },
                "geo_address_info": {
                    "city": info.get("address", {}).get("addressLocality") if isinstance(info.get("address"), dict) else None,
                    "region": info.get("address", {}).get("addressRegion") if isinstance(info.get("address"), dict) else None,
                },
            }
        )
        normalized["bookmarked"] = True

        def normalize_url(url):
            if not url:
                return None
            cleaned = url.strip().rstrip("/")
            if cleaned.startswith("http://"):
                cleaned = "https://" + cleaned[len("http://"):]
            cleaned = cleaned.replace("https://luma.com/", "https://lu.ma/")
            return cleaned

        new_url = normalize_url(normalized.get("url"))
        existing_record_id = None
        for existing_event in ALL_EVENTS:
            existing_url = normalize_url(existing_event.get("url"))
            if existing_url and new_url and existing_url == new_url:
                existing_record_id = existing_event.get("id")
                break

        if existing_record_id:
            normalized["id"] = existing_record_id

        home_dir = os.path.expanduser("~")
        db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
        db = lancedb.connect(db_path)
        table = db.open_table("events")

        if existing_record_id:
            table.delete(f"id = '{existing_record_id}'")
        table.add([normalized])

        ALL_EVENTS = load_events()
        return {"message": "Event added successfully", "event": normalized}
    except Exception as exc:
        return {"error": str(exc)}


@app.post("/events/{event_id}/bookmark")
def bookmark_event(event_id: str, bookmarked: bool):
    try:
        home_dir = os.path.expanduser("~")
        db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
        db = lancedb.connect(db_path)
        table = db.open_table("events")
        table.update(where=f"id = '{event_id}'", values={"bookmarked": bookmarked})

        global ALL_EVENTS
        for event in ALL_EVENTS:
            if event.get("id") == event_id:
                event["bookmarked"] = bookmarked
                break

        return {"status": "success", "id": event_id, "bookmarked": bookmarked}
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/bookmarks")
def get_bookmarks():
    try:
        bookmarked_events = [e for e in ALL_EVENTS if e.get("bookmarked", False)]
        bookmarked_events.sort(key=get_start_time_sort_value)
        results = enrich_events_with_distance(bookmarked_events)
        return clean_nans(convert_to_serializable(results))
    except Exception as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
