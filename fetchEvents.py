#!/usr/bin/env python3
"""Fetch and aggregate Luma events from multiple slugs into a single combined JSON file.

This script:
1. Fetches events from multiple Luma slugs in parallel 
2. Combines all events into a single JSON file
3. Optionally generates city summaries with Google Maps integration

Usage:
  python3 fetchEvents.py

The script will create:
- aggregatedEvents/combined_events.json (all events sorted by start_at)
- aggregatedEvents/city_summary.json (city counts and distances, if Google Maps API is available)
"""

import asyncio
import aiohttp
import json
import os
from pathlib import Path
from datetime import datetime
from collections import Counter
import requests
import googlemaps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

async def fetch_all_luma_events_bounding_box(session, east, north, south, west, slug,
                                               base_url="https://api2.luma.com/discover/get-paginated-events",
                                               pagination_limit=100):
    """
    Fetch all events for a given slug and bounding box using async requests.
    """
    all_events = []
    has_more = True
    current_cursor = None

    print(f"[{slug}] Starting to fetch events within bounding box:")
    print(f"[{slug}]   North: {north}, South: {south}, East: {east}, West: {west}")

    while has_more:
        params = {
            "east": east,
            "north": north,
            "south": south,
            "west": west,
            "pagination_limit": pagination_limit,
            "slug": slug
        }
        if current_cursor:
            params["pagination_cursor"] = current_cursor

        try:
            async with session.get(base_url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

                # Add events from the current page to our list
                current_page_entries = data.get("entries", [])
                all_events.extend(current_page_entries)

                # Update pagination info
                has_more = data.get("has_more", False)
                current_cursor = data.get("next_cursor")

                print(f"[{slug}] Fetched {len(current_page_entries)} events. Total: {len(all_events)}. Has more: {has_more}")
                if current_cursor:
                    print(f"[{slug}]   Next cursor: {current_cursor}")

                if has_more:
                    # Small delay to be polite to the API
                    await asyncio.sleep(0.2)

        except aiohttp.ClientError as e:
            print(f"[{slug}] HTTP error occurred: {e}")
            break
        except json.JSONDecodeError as e:
            print(f"[{slug}] Error decoding JSON response: {e}")
            break
        except Exception as e:
            print(f"[{slug}] An unexpected error occurred: {e}")
            break

    print(f"[{slug}] Finished fetching. Total events collected: {len(all_events)}")
    return slug, all_events


def get_start_at(item):
    """Extract start_at datetime from event item."""
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

    return "Unknown"


def get_distance_and_time_from_user_location(origin, destination, gmaps_client):
    """Get distance and estimated driving time between two locations."""
    try:
        # Use Google Maps Distance Matrix API
        result = gmaps_client.distance_matrix(
            origins=[origin],
            destinations=[destination],
            mode="driving",
            units="imperial"
        )
        
        if result["status"] == "OK":
            element = result["rows"][0]["elements"][0]
            if element["status"] == "OK":
                distance = element["distance"]["text"]
                duration = element["duration"]["text"]
                return distance, duration
    except Exception as e:
        print(f"Error getting distance/time for {destination}: {e}")
    
    return None, None


def generate_city_summary(events, user_location=None):
    """Generate summary of events by city with optional distance/time info."""
    print("Generating city summary...")
    
    # Count events by city
    city_counter = Counter()
    for event in events:
        city = extract_city(event)
        city_counter[city] += 1
    
    summary = {}
    
    # Set up Google Maps client if API key is available
    gmaps_client = None
    google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if google_maps_api_key:
        try:
            gmaps_client = googlemaps.Client(key=google_maps_api_key)
            print("Google Maps API key found - will include distance/time info")
        except Exception as e:
            print(f"Error setting up Google Maps client: {e}")
    else:
        print("No Google Maps API key found - will skip distance/time info")
    
    for city, count in city_counter.most_common():
        city_info = {"event_count": count}
        
        # Add distance/time info if user location and Google Maps are available
        if user_location and gmaps_client and city != "Unknown":
            distance, duration = get_distance_and_time_from_user_location(
                user_location, city, gmaps_client
            )
            if distance and duration:
                city_info["distance_from_user"] = distance
                city_info["drive_time_from_user"] = duration
        
        summary[city] = city_info
    
    return summary


async def fetch_and_aggregate_events(slugs, east, north, south, west, 
                                   output_dir="aggregatedEvents", 
                                   user_location=None):
    """
    Fetch events for multiple slugs concurrently and combine into single JSON file.
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Create a single aiohttp session for all requests
    async with aiohttp.ClientSession() as session:
        # Create tasks for all slugs
        tasks = [
            fetch_all_luma_events_bounding_box(session, east, north, south, west, slug)
            for slug in slugs
        ]

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks)

        # Combine all events from all slugs
        all_events = []
        for slug, events in results:
            print(f"\n[{slug}] Collected {len(events)} events")
            all_events.extend(events)

        print(f"\n✓ Total events collected from all slugs: {len(all_events)}")

        # Sort events by start_at
        def sort_key(item):
            dt = get_start_at(item)
            return dt if dt else datetime.min.replace(tzinfo=dt.tzinfo if dt else None)

        sorted_events = sorted(all_events, key=sort_key)
        print(f"✓ Events sorted by start time")

        # Save combined events
        combined_output = os.path.join(output_dir, "combined_events.json")
        with open(combined_output, "w") as f:
            json.dump(sorted_events, f, indent=2)
        print(f"✓ Saved {len(sorted_events)} combined events to {combined_output}")

        # Generate city summary
        city_summary = generate_city_summary(sorted_events, user_location)
        summary_output = os.path.join(output_dir, "city_summary.json")
        with open(summary_output, "w") as f:
            json.dump(city_summary, f, indent=2)
        print(f"✓ Saved city summary to {summary_output}")

    print(f"\n✓ All processing completed successfully!")
    return len(sorted_events)


async def main():
    """Main function to fetch and aggregate events."""
    # Bounding box coordinates (San Francisco Bay Area)
    east_coord = -121.57055455494474
    north_coord = 37.96737772066783
    south_coord = 36.71845574708184
    west_coord = -122.7412517581312

    # Slugs to fetch
    slugs = [
        "tech",
        "ai",
        # "sf-developer-events", #endpoint doesn't work
        # "genai-sf", #endpoint doesn't work
        "sf"
    ]

    # Optional: user location for distance calculations
    # Set this to your location if you want distance/time info in city summary
    user_location = None  # e.g., "San Francisco, CA" or "1234 Main St, City, State"

    print("=== Starting concurrent fetch and aggregation for multiple slugs ===\n")
    total_events = await fetch_and_aggregate_events(
        slugs, east_coord, north_coord, south_coord, west_coord,
        user_location=user_location
    )
    
    print(f"\n🎉 Successfully processed {total_events} total events!")
    print("📁 Output files:")
    print("   - aggregatedEvents/combined_events.json")
    print("   - aggregatedEvents/city_summary.json")
    print("\n💡 Use filterEvents.py to filter the combined events by location, date, or weekday")


if __name__ == "__main__":
    asyncio.run(main())