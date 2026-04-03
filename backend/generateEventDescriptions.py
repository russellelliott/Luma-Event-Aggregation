import json
import os
import traceback
import math

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
            pa.field("topic_id", pa.int64()),
            pa.field("topic_label", pa.string()),
            pa.field("topic_color", pa.string()),
            pa.field("cosine_distance", pa.float64()),
            pa.field("needs_description_fetch", pa.bool_()),
        ]
    )


def ensure_events_table_exists(db_path=None):
    resolved_db_path = get_db_path(db_path)
    if not os.path.exists(resolved_db_path):
        raise FileNotFoundError(f"LanceDB database not found at {resolved_db_path}")
    db = lancedb.connect(resolved_db_path)
    if "events" not in db.table_names():
        print("'events' table is missing; it will be created when data is written.")


def normalize_pricing_for_storage(pricing):
    if pricing is None:
        return None
    if isinstance(pricing, str):
        return pricing
    return json.dumps(pricing, default=str)


def _to_text_or_none(value):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return str(value)


def _is_nan_value(value):
    try:
        return math.isnan(value)
    except (TypeError, ValueError):
        return False


def _to_int_or_none(value):
    if value is None or _is_nan_value(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_city_from_event_info(event_info):
    address = event_info.get("address") if isinstance(event_info.get("address"), dict) else {}
    city = address.get("addressLocality") or address.get("locality") or address.get("city")
    region = address.get("addressRegion") or address.get("region") or address.get("state")

    if city and region:
        return f"{city}, {region}"
    if city:
        return city

    location_name = event_info.get("location_name")
    if isinstance(location_name, str):
        cleaned = location_name.strip()
        if cleaned and cleaned not in {"Register to See Address", "Online"}:
            return cleaned

    return None


def normalize_event_for_storage(event_entry):
    coordinates = event_entry.get("coordinates") if isinstance(event_entry.get("coordinates"), dict) else {}
    latitude = coordinates.get("latitude")
    longitude = coordinates.get("longitude")

    return {
        "id": _to_text_or_none(event_entry.get("id")),
        "name": _to_text_or_none(event_entry.get("name")),
        "url": _to_text_or_none(event_entry.get("url")),
        "start_at": _to_text_or_none(event_entry.get("start_at")),
        "end_at": _to_text_or_none(event_entry.get("end_at")),
        "description": _to_text_or_none(event_entry.get("description")),
        "timezone": _to_text_or_none(event_entry.get("timezone")),
        "pricing": normalize_pricing_for_storage(event_entry.get("pricing")),
        "city": _to_text_or_none(event_entry.get("city")),
        "coordinates": {
            "latitude": None if _is_nan_value(latitude) else latitude,
            "longitude": None if _is_nan_value(longitude) else longitude,
        },
        "bookmarked": bool(event_entry.get("bookmarked", False)),
        "topic_id": _to_int_or_none(event_entry.get("topic_id")),
        "topic_label": _to_text_or_none(event_entry.get("topic_label")),
        "topic_color": _to_text_or_none(event_entry.get("topic_color")),
        "cosine_distance": None if _is_nan_value(event_entry.get("cosine_distance")) else event_entry.get("cosine_distance"),
        "needs_description_fetch": bool(event_entry.get("needs_description_fetch", False)),
    }


def build_events_table(events):
    normalized_events = [normalize_event_for_storage(event) for event in events]
    if not normalized_events:
        return None

    coordinates_array = pa.array(
        [
            {
                "latitude": record["coordinates"]["latitude"],
                "longitude": record["coordinates"]["longitude"],
            }
            for record in normalized_events
        ],
        type=pa.struct(
            [
                pa.field("latitude", pa.float64()),
                pa.field("longitude", pa.float64()),
            ]
        ),
    )

    arrays = [
        pa.array([record["id"] for record in normalized_events], type=pa.string()),
        pa.array([record["name"] for record in normalized_events], type=pa.string()),
        pa.array([record["url"] for record in normalized_events], type=pa.string()),
        pa.array([record["start_at"] for record in normalized_events], type=pa.string()),
        pa.array([record["end_at"] for record in normalized_events], type=pa.string()),
        pa.array([record["description"] for record in normalized_events], type=pa.string()),
        pa.array([record["timezone"] for record in normalized_events], type=pa.string()),
        pa.array([record["pricing"] for record in normalized_events], type=pa.string()),
        pa.array([record["city"] for record in normalized_events], type=pa.string()),
        coordinates_array,
        pa.array([record["bookmarked"] for record in normalized_events], type=pa.bool_()),
        pa.array([record["topic_id"] for record in normalized_events], type=pa.int64()),
        pa.array([record["topic_label"] for record in normalized_events], type=pa.string()),
        pa.array([record["topic_color"] for record in normalized_events], type=pa.string()),
        pa.array([record["cosine_distance"] for record in normalized_events], type=pa.float64()),
        pa.array([record["needs_description_fetch"] for record in normalized_events], type=pa.bool_()),
    ]

    field_names = [
        "id",
        "name",
        "url",
        "start_at",
        "end_at",
        "description",
        "timezone",
        "pricing",
        "city",
        "coordinates",
        "bookmarked",
        "topic_id",
        "topic_label",
        "topic_color",
        "cosine_distance",
        "needs_description_fetch",
    ]

    return pa.Table.from_arrays(arrays, names=field_names)


def load_events_from_lancedb(db_path=None):
    db_path = get_db_path(db_path)
    ensure_events_table_exists(db_path)

    db = lancedb.connect(db_path)
    table = db.open_table("events")
    events = table.to_pandas().to_dict("records")
    print(f"📊 Loaded {len(events)} events from LanceDB")
    return events


def select_new_events(events):
    new_events = [event for event in events if event.get("needs_description_fetch")]
    print(f"📌 Events marked for description fetch: {len(new_events)}")
    return new_events


def save_events_to_lancedb(events, db_path=None):
    db_path = get_db_path(db_path)

    db = lancedb.connect(db_path)
    events_table = build_events_table(events)
    if events_table is None:
        return

    db.create_table("events", data=events_table, mode="overwrite")


def generate_descriptions_for_all_events(all_events, events_to_process=None, delay=1.0, db_path=None):
    if events_to_process is None:
        events_to_process = all_events

    print(f"Processing {len(events_to_process)} events sequentially with {delay}s delay between requests...\n")

    processed_count = 0
    skipped_count = 0
    already_complete_count = 0
    missing_url_count = 0
    error_count = 0

    for i, event_entry in enumerate(events_to_process):
        event_url = event_entry.get("url")
        event_name = event_entry.get("name", "Unknown Event")

        if not event_url:
            # print(f"[{i+1}/{len(events_to_process)}] Skipping: {event_name} (no URL found)")
            event_entry["fetch_error"] = "No URL found"
            skipped_count += 1
            missing_url_count += 1
            continue

        try:
            has_description = bool(event_entry.get("description"))
            has_city = bool(event_entry.get("city"))
            has_coordinates = (
                event_entry.get("coordinates", {}).get("latitude") is not None
                and event_entry.get("coordinates", {}).get("longitude") is not None
            )
            if has_description and has_city and has_coordinates:
                already_complete_count += 1

            print(f"[{i+1}/{len(events_to_process)}] Processing: {event_name}")
            if not has_description:
                print(f"  - Missing: description")
            if not has_city:
                print(f"  - Missing: city")
            if not has_coordinates:
                print(f"  - Missing: coordinates")

            event_info = get_luma_event_info(str(event_url).strip(), delay=delay)
            if "error" in event_info:
                print(f"  ⚠️  Error fetching: {event_info['error']}")
                event_entry["fetch_error"] = event_info["error"]
                error_count += 1
                continue

            response_description = event_info.get("description")
            response_city = _extract_city_from_event_info(event_info)
            response_lat = event_info.get("latitude")
            response_lng = event_info.get("longitude")
            print("  Response data check:")
            print(f"    - description_present: {bool(response_description)}")
            print(f"    - description_length: {len(response_description) if isinstance(response_description, str) else 0}")
            print(f"    - city_extracted: {response_city}")
            print(f"    - latitude: {response_lat}")
            print(f"    - longitude: {response_lng}")

            updated_count = 0

            if "description" in event_info and event_info["description"]:
                event_entry["description"] = event_info["description"]
                updated_count += 1
                print(f"  ✓ Description written ({len(event_info['description'])} chars)")
            else:
                print("  ⚠️  Description missing in response")

            if "latitude" in event_info and "longitude" in event_info:
                lat = event_info.get("latitude")
                lng = event_info.get("longitude")
                if lat is not None and lng is not None:
                    event_entry["coordinates"] = {"latitude": lat, "longitude": lng}
                    updated_count += 1
                    print(f"  ✓ Coordinates written ({lat}, {lng})")
                else:
                    print("  ⚠️  Coordinates missing in response")
            else:
                print("  ⚠️  Coordinates keys missing in response")

            extracted_city = _extract_city_from_event_info(event_info)
            if extracted_city:
                event_entry["city"] = extracted_city
                updated_count += 1
                print(f"  ✓ City written ({extracted_city})")
            else:
                print("  ⚠️  No city extracted from response")

            if "pricing" in event_info and event_info["pricing"]:
                event_entry["pricing"] = event_info["pricing"]
                updated_count += 1
                print(f"  ✓ Pricing added")

            event_entry["needs_description_fetch"] = False

            if updated_count > 0:
                save_events_to_lancedb(all_events, db_path=db_path)
                print("  💾 Event updates written to LanceDB")
                processed_count += 1
            else:
                print(f"  ⚠️  No new data was available")
                error_count += 1
        except Exception as exc:
            event_entry["fetch_error"] = str(exc)
            print(f"  ⚠️  Failed to process {event_name}: {exc}")
            error_count += 1

    print(f"\n📊 Summary: {processed_count} processed, {skipped_count} skipped, {error_count} errors")
    print(f"  - Already complete before fetch: {already_complete_count}")
    print(f"  - Missing URL: {missing_url_count}")
    print(f"💾 Performing final safety save for all {len(all_events)} events...")
    save_events_to_lancedb(all_events, db_path=db_path)
    print("✓ Final save completed")

    return all_events


if __name__ == '__main__':
    try:
        events = load_events_from_lancedb()
        events_to_process = select_new_events(events)
        events_with_descriptions = generate_descriptions_for_all_events(events, events_to_process, delay=1.0)
        print(f"\n🎉 Successfully processed {len(events_with_descriptions)} events!")
    
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Run 'python fetchEvents.py' first to populate the database.")
        exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        exit(1)
