#!/usr/bin/env python3
"""Aggregate, sort, and summarize Luma events from fetched JSON files.

Produces:
- fetchedEvents/combined_events.json  (all events from fetchedEvents/*.json sorted by start_at)
- fetchedEvents/city_summary.json     (counts per city and optional distance/time from user's location)

Usage:
  - Ensure you have Python 3.8+ and install requirements from requirements.txt
  - Set GOOGLE_MAPS_API_KEY in your environment if you want distance/time lookups.
    Example (zsh):
      export GOOGLE_MAPS_API_KEY="YOUR_KEY_HERE"

  - Run:
      python3 aggregate_events.py

The script will not attempt Google Maps calls unless GOOGLE_MAPS_API_KEY is present.
"""

import os
import json
from pathlib import Path
from datetime import datetime
from collections import Counter
import requests
import googlemaps


EVENTS_DIR = Path(__file__).resolve().parent / "fetchedEvents"
# write outputs to a separate folder (aggregatedEvents) as requested
OUTPUT_DIR = Path(__file__).resolve().parent / "aggregatedEvents"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
COMBINED_OUT = OUTPUT_DIR / "combined_events.json"
CITY_SUMMARY_OUT = OUTPUT_DIR / "city_summary.json"


def load_events(events_dir: Path):
    events = []
    for p in sorted(events_dir.glob("*.json")):
        # skip output files if present
        if p.name in {COMBINED_OUT.name, CITY_SUMMARY_OUT.name}:
            continue
        try:
            with p.open("r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    events.extend(data)
                else:
                    print(f"Warning: {p} did not contain a top-level list; skipping")
        except Exception as e:
            print(f"Failed to read {p}: {e}")
    print(f"Loaded {len(events)} total events from {events_dir}")
    return events


def get_start_at(item):
    # Events in fetched files have 'start_at' at top-level and/or under 'event'
    s = item.get("start_at") or item.get("event", {}).get("start_at")
    if not s:
        return None
    try:
        # handle ISO with 'Z'
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")
        except Exception:
            return None


def extract_city(item):
    ev = item.get("event", {})
    geo = ev.get("geo_address_info", {}) if isinstance(ev.get("geo_address_info", {}), dict) else {}

    # Prefer explicit city field
    city = geo.get("city")
    if city:
        return city

    # Fallback to city_state like "San Francisco, California"
    city_state = geo.get("city_state")
    if city_state and "," in city_state:
        return city_state.split(",")[0].strip()

    # Fallback to calendar geo_city
    cal_city = item.get("calendar", {}).get("geo_city")
    if cal_city:
        return cal_city

    # last resort: try to extract from full_address
    full = geo.get("full_address")
    if full and "," in full:
        return full.split(",")[0].strip()

    return "Unknown"


def combine_and_sort(events):
    # attach sortable start datetime and sort
    annotated = []
    for it in events:
        start_dt = get_start_at(it)
        annotated.append((start_dt, it))

    # sort, putting None (no start) at the end
    annotated.sort(key=lambda x: (x[0] is None, x[0]))
    sorted_events = [it for _, it in annotated]
    return sorted_events


def get_user_location():
    try:
        ipinfo = requests.get("https://ipinfo.io").json()
        loc = ipinfo.get("loc")
        if loc:
            print("Detected your coordinates from IP:", loc)
            return loc
    except Exception as e:
        print("Could not determine location from IP (ipinfo):", e)
    return None


def query_google_for_cities(cities, your_location, api_key):
    # Use googlemaps client to get distance matrix results. This function assumes
    # the `googlemaps` package is importable (per your instruction not to change the import).
    client = googlemaps.Client(key=api_key)
    from datetime import datetime as _dt
    results = {}
    for city in cities:
        try:
            res = client.distance_matrix(origins=[your_location], destinations=[city], mode="driving", departure_time=_dt.now())
            elem = res.get("rows", [])[0].get("elements", [])[0]
            status = elem.get("status")
            if status == "OK":
                distance_text = elem["distance"]["text"]
                duration_text = elem["duration"]["text"]
                distance_value = elem["distance"]["value"]  # meters
                duration_value = elem["duration"]["value"]  # seconds
                # convert meters to miles
                distance_miles = None
                try:
                    distance_miles = round(distance_value / 1609.344, 2) if distance_value is not None else None
                except Exception:
                    distance_miles = None
                # also provide duration in minutes
                duration_minutes = None
                try:
                    duration_minutes = round(duration_value / 60, 1) if duration_value is not None else None
                except Exception:
                    duration_minutes = None
            else:
                distance_text = duration_text = None
                distance_value = distance_miles = duration_value = duration_minutes = None

            results[city] = {
                "status": status,
                "distance_text": distance_text,
                "distance_meters": distance_value,
                "distance_miles": distance_miles,
                "duration_text": duration_text,
                "duration_seconds": duration_value,
                "duration_minutes": duration_minutes,
            }
        except Exception as e:
            print(f"Google API error for city '{city}':", e)
            results[city] = {"status": "ERROR", "error": str(e)}

    return results


def main():
    events = load_events(EVENTS_DIR)
    sorted_events = combine_and_sort(events)

    # write combined sorted events
    try:
        with COMBINED_OUT.open("w") as f:
            json.dump(sorted_events, f, default=str, indent=2)
        print(f"Wrote combined sorted events to {COMBINED_OUT} ({len(sorted_events)} events)")
    except Exception as e:
        print("Failed to write combined events:", e)

    # extract cities and counts
    cities = [extract_city(it) for it in sorted_events]
    counts = Counter(cities)

    summary = []
    for city, cnt in counts.most_common():
        summary.append({"city": city, "count": cnt})

    # Optionally get distances/times using Google Maps if API key present
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    user_loc = None
    google_results = {}
    if api_key:
        user_loc = get_user_location()
        if not user_loc:
            print("Warning: could not detect user location from IP; skipping Google queries")
        else:
            city_names = [s["city"] for s in summary if s["city"] != "Unknown"]
            google_results = query_google_for_cities(city_names, user_loc, api_key)

    # attach google results to summary
    for item in summary:
        city = item["city"]
        if city in google_results:
            item.update({"google": google_results[city]})

    try:
        with CITY_SUMMARY_OUT.open("w") as f:
            json.dump({"generated_at": datetime.utcnow().isoformat() + "Z", "summary": summary}, f, indent=2)
        print(f"Wrote city summary to {CITY_SUMMARY_OUT} ({len(summary)} cities)")
    except Exception as e:
        print("Failed to write city summary:", e)


if __name__ == "__main__":
    main()
