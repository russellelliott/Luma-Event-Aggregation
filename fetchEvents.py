import asyncio
import aiohttp
import json
import os
from pathlib import Path

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


async def fetch_multiple_slugs(slugs, east, north, south, west, output_dir="fetchedEvents"):
    """
    Fetch events for multiple slugs concurrently.
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

        # Save results to files
        for slug, events in results:
            output_filename = os.path.join(output_dir, f"{slug}.json")
            with open(output_filename, "w") as f:
                json.dump(events, f, indent=2)
            print(f"\n[{slug}] Saved {len(events)} events to {output_filename}")

    print(f"\n✓ All slugs processed successfully!")


async def main():
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

    print("=== Starting concurrent fetch for multiple slugs ===\n")
    await fetch_multiple_slugs(slugs, east_coord, north_coord, south_coord, west_coord)


if __name__ == "__main__":
    asyncio.run(main())