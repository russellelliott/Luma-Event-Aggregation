#!/usr/bin/env python3
"""Aggregate, sort, and summarize Luma events from fetched JSON files.

Produces:
- fetchedEvents/combined_events.json  (all events from fetchedEvents/*.json sorted by start_at)
- fetchedEvents/city_summary.json     (counts per city and optional distance/time from user's location)

Usage:
  - Ensure you have Python 3.8+ and install requirements from requirements.txt
  - Set GOOGLE_MAPS_API_KEY in your .env file
    Example:
      GOOGLE_MAPS_API_KEY=YOUR_KEY_HERE

  - Run:
      python3 aggregate_events.py

The script will load the .env file automatically and use the API key.
"""

import os
import json
from pathlib import Path
from datetime import datetime
from collections import Counter
import requests
import googlemaps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
    """Extract city name, preferring city_state format for better Google Maps accuracy."""
    ev = item.get("event", {})
    geo = ev.get("geo_address_info", {}) if isinstance(ev.get("geo_address_info", {}), dict) else {}

    # PREFER city_state like "San Francisco, California" for better Google Maps accuracy
    city_state = geo.get("city_state")
    if city_state:
        return city_state

    # Fallback to calendar geo_city with state if available
    cal_city = item.get("calendar", {}).get("geo_city")
    cal_region = item.get("calendar", {}).get("geo_region_abbrev") or item.get("calendar", {}).get("geo_region")
    if cal_city and cal_region:
        return f"{cal_city}, {cal_region}"
    if cal_city:
        return cal_city

    # Fallback to explicit city field (but this lacks state info)
    city = geo.get("city")
    if city:
        # Try to add state if available
        state = geo.get("region") or geo.get("region_abbrev")
        if state:
            return f"{city}, {state}"
        return city

    # last resort: try to extract from full_address
    full = geo.get("full_address")
    if full and "," in full:
        # Try to get "City, State" from full address
        parts = [p.strip() for p in full.split(",")]
        if len(parts) >= 2:
            return f"{parts[0]}, {parts[1]}"
        return parts[0]

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
        print("Detecting your location from IP...")
        ipinfo = requests.get("https://ipinfo.io").json()
        loc = ipinfo.get("loc")
        if loc:
            print(f"✓ Detected your coordinates: {loc}")
            print(f"  City: {ipinfo.get('city', 'Unknown')}, {ipinfo.get('region', 'Unknown')}")
            return loc
    except Exception as e:
        print("Could not determine location from IP (ipinfo):", e)
    return None


def query_google_for_cities(cities, your_location, api_key):
    # Use googlemaps client to get distance matrix results. This function assumes
    # the `googlemaps` package is importable (per your instruction not to change the import).
    print(f"\nQuerying Google Maps for {len(cities)} cities...")
    client = googlemaps.Client(key=api_key)
    from datetime import datetime as _dt
    results = {}
    for i, city in enumerate(cities, 1):
        print(f"  [{i}/{len(cities)}] Querying: {city}", end="")
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
                print(f" ✓ {distance_miles} mi, {duration_minutes} min")
            else:
                distance_text = duration_text = None
                distance_value = distance_miles = duration_value = duration_minutes = None
                print(f" ✗ Status: {status}")

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
            print(f" ✗ Error: {e}")
            results[city] = {"status": "ERROR", "error": str(e)}

    return results


def main():
    print("=" * 70)
    print("Aggregating Luma Events")
    print("=" * 70)
    
    events = load_events(EVENTS_DIR)
    sorted_events = combine_and_sort(events)

    # write combined sorted events
    try:
        with COMBINED_OUT.open("w") as f:
            json.dump(sorted_events, f, default=str, indent=2)
        print(f"\n✓ Wrote combined sorted events to {COMBINED_OUT} ({len(sorted_events)} events)")
    except Exception as e:
        print("Failed to write combined events:", e)

    # extract cities and counts
    cities = [extract_city(it) for it in sorted_events]
    counts = Counter(cities)

    summary = []
    # include distance and travel time fields (filled when Google results are available)
    for city, cnt in counts.most_common():
        summary.append({
            "city": city,
            "count": cnt,
            # top-level fields required by the user: distance in miles and travel time in minutes
            "distance_miles": None,
            "travel_time_minutes": None,
        })

    # Optionally get distances/times using Google Maps if API key present
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    user_loc = None
    google_results = {}
    
    if not api_key:
        print("\n⚠ Warning: GOOGLE_MAPS_API_KEY not found in environment")
        print("  Distance and travel time will not be calculated")
        print("  Make sure your .env file contains: GOOGLE_MAPS_API_KEY=your_key_here")
    else:
        print(f"\n✓ Found Google Maps API key: {api_key[:10]}...")
        user_loc = get_user_location()
        if not user_loc:
            print("Warning: could not detect user location from IP; skipping Google queries")
        else:
            city_names = [s["city"] for s in summary if s["city"] != "Unknown"]
            google_results = query_google_for_cities(city_names, user_loc, api_key)

    # attach google results to summary: populate top-level distance_miles and travel_time_minutes
    for item in summary:
        city = item["city"]
        if city in google_results:
            res = google_results[city]
            # keep the original google object for debugging/diagnostics
            item["google"] = res
            # fill the required top-level fields if available
            if isinstance(res, dict):
                # distance_miles and duration_minutes were computed in query_google_for_cities
                if res.get("distance_miles") is not None:
                    item["distance_miles"] = res.get("distance_miles")
                if res.get("duration_minutes") is not None:
                    # normalize name to travel_time_minutes per user's request
                    item["travel_time_minutes"] = res.get("duration_minutes")

    try:
        with CITY_SUMMARY_OUT.open("w") as f:
            json.dump({"generated_at": datetime.utcnow().isoformat() + "Z", "summary": summary}, f, indent=2)
        print(f"\n✓ Wrote city summary to {CITY_SUMMARY_OUT} ({len(summary)} cities)")
        
        # Print summary of what was calculated
        with_distance = sum(1 for s in summary if s["distance_miles"] is not None)
        print(f"  - {with_distance}/{len(summary)} cities have distance/time data")
        
    except Exception as e:
        print("Failed to write city summary:", e)
    
    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)


if __name__ == "__main__":
    main()