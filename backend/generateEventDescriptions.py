import json
import os

import lancedb
import pyarrow as pa

from eventDescription import get_luma_event_info


def get_db_path(db_path=None):
    if db_path is not None:
        return db_path
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")


def events_schema():
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("name", pa.string()),
            pa.field("url", pa.string()),
            pa.field("start_at", pa.string()),
            pa.field("end_at", pa.string()),
            pa.field("description", pa.string()),
            pa.field("timezone", pa.string()),
            pa.field("pricing", pa.string()),
            pa.field("city", pa.string()),
            pa.field(
                "coordinates",
                pa.struct(
                    [
                        pa.field("latitude", pa.float64()),
                        pa.field("longitude", pa.float64()),
                    ]
                ),
            ),
            pa.field("bookmarked", pa.bool_()),
            pa.field("vector", pa.list_(pa.float32())),
            pa.field("topic_id", pa.int64()),
            pa.field("topic_label", pa.string()),
            pa.field("topic_color", pa.string()),
            pa.field("cosine_distance", pa.float64()),
        ]
    )


def ensure_events_table_exists(db_path=None):
    resolved_db_path = get_db_path(db_path)
    if not os.path.exists(resolved_db_path):
        raise FileNotFoundError(f"LanceDB database not found at {resolved_db_path}")
    db = lancedb.connect(resolved_db_path)
    if "events" not in db.list_tables():
        print("'events' table is missing; it will be created when data is written.")


def normalize_pricing_for_storage(pricing):
    if pricing is None:
        return None
    if isinstance(pricing, str):
        return pricing
    return json.dumps(pricing, default=str)


def normalize_event_for_storage(event_entry):
    coordinates = event_entry.get("coordinates") if isinstance(event_entry.get("coordinates"), dict) else {}
    vector = event_entry.get("vector")
    if vector is not None and hasattr(vector, "tolist"):
        vector = vector.tolist()

    return {
        "id": event_entry.get("id"),
        "name": event_entry.get("name"),
        "url": event_entry.get("url"),
        "start_at": event_entry.get("start_at"),
        "end_at": event_entry.get("end_at"),
        "description": event_entry.get("description"),
        "timezone": event_entry.get("timezone"),
        "pricing": normalize_pricing_for_storage(event_entry.get("pricing")),
        "city": event_entry.get("city"),
        "coordinates": {
            "latitude": coordinates.get("latitude"),
            "longitude": coordinates.get("longitude"),
        },
        "bookmarked": bool(event_entry.get("bookmarked", False)),
        "vector": vector,
        "topic_id": event_entry.get("topic_id"),
        "topic_label": event_entry.get("topic_label"),
        "topic_color": event_entry.get("topic_color"),
        "cosine_distance": event_entry.get("cosine_distance"),
    }


def load_events_from_lancedb(db_path=None):
    db_path = get_db_path(db_path)
    ensure_events_table_exists(db_path)

    db = lancedb.connect(db_path)
    table = db.open_table("events")
    events = table.to_pandas().to_dict("records")
    print(f"📊 Loaded {len(events)} events from LanceDB")
    return events


def save_events_to_lancedb(events, db_path=None):
    db_path = get_db_path(db_path)

    db = lancedb.connect(db_path)
    normalized_events = [normalize_event_for_storage(event) for event in events]
    if not normalized_events:
        return

    db.create_table("events", data=pa.Table.from_pylist(normalized_events, schema=events_schema()), mode="overwrite")


def generate_descriptions_for_all_events(events, delay=1.0, db_path=None):
    print(f"Processing {len(events)} events sequentially with {delay}s delay between requests...\n")

    for i, event_entry in enumerate(events):
        event_url = event_entry.get("url")
        event_name = event_entry.get("name", "Unknown Event")

        if not event_url:
            print(f"[{i+1}/{len(events)}] Skipping: {event_name} (no URL found)")
            event_entry["fetch_error"] = "No URL found"
            continue

        if event_entry.get("description"):
            print(f"[{i+1}/{len(events)}] Skipping: {event_name} (already has description)")
            continue

        try:
            print(f"[{i+1}/{len(events)}] Processing: {event_name}")
            print(f"  URL: {event_url}")

            event_info = get_luma_event_info(str(event_url).strip(), delay=delay)
            if "error" in event_info:
                print(f"  ⚠️  Error: {event_info['error']}")
                event_entry["fetch_error"] = event_info["error"]
                continue

            if "description" in event_info:
                event_entry["description"] = event_info["description"]
            if "pricing" in event_info:
                event_entry["pricing"] = event_info["pricing"]

            save_events_to_lancedb(events, db_path=db_path)
            print("  ✓ Description and pricing added and persisted")
        except Exception as exc:
            event_entry["fetch_error"] = str(exc)
            print(f"  ⚠️  Failed to process {event_name}: {exc}")

    return events


if __name__ == '__main__':
    try:
        events = load_events_from_lancedb()
        events_with_descriptions = generate_descriptions_for_all_events(events, delay=1.0)
        print(f"\n🎉 Successfully processed {len(events_with_descriptions)} events!")
    
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Run 'python fetchEvents.py' first to populate the database.")
        exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        exit(1)
