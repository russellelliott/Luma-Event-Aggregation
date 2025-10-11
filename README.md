# Luma Event Aggregator
Fetches events from several Luma calendars and enables filtering by location, date, and weekdays.

Start and End times (start_at, end_at) appear to be in standard UTC timestamp. For filtering by dates and times, go by the user's time zone.

## Quick Start

1. **Fetch and aggregate events** using `fetchEvents.py` - this will fetch events from multiple Luma slugs in parallel and create combined output files:
   ```bash
   python3 -m pip install -r requirements.txt
   # Optionally set your Google Maps API key to enable distance/time lookups in city summary
   export GOOGLE_MAPS_API_KEY="YOUR_KEY_HERE"
   python3 fetchEvents.py
   ```

2. **Filter events** using `filterEvents.py` to find events matching your criteria:
   ```bash
   # Filter by location and date
   python3 filterEvents.py --location "Mountain View" --dates 2025-10-10 2025-10-11
   
   # Filter by weekdays
   python3 filterEvents.py --weekdays Friday Saturday
   
   # Combine filters
   python3 filterEvents.py --location "San Francisco" --weekdays Friday --dates 2025-10-10
   ```

## Output Files

After running `fetchEvents.py`, you'll get:
- `aggregatedEvents/combined_events.json` — All events from all slugs, sorted by start time
- `aggregatedEvents/city_summary.json` — Event counts per city (with optional distance/time data if Google Maps API is configured)

## How It Works

- **fetchEvents.py**: Fetches events from multiple Luma calendar slugs in parallel, combines them into a single sorted list, and generates a city summary
- **filterEvents.py**: Filters the combined events by location, specific dates, and/or weekdays

No intermediate JSON files are created per slug - everything is processed in memory and output as a single combined file.

## Resources

### Writing the Code
https://colab.research.google.com/drive/1T362Lml9rCxyloaV3sV_5ngZu3PrOSHH#scrollTo=K3Y-IS_sbP2h

https://aistudio.google.com/prompts/1Qte8iKmJXVQCLG-iF3ZvWUXp5z4Rz1iY

https://claude.ai/chat/37dc1455-86fe-494c-bd60-2528fb09190d

### Fleshing out the idea
https://chatgpt.com/c/68e7faa9-fa48-8329-932d-55d4b2b41238

### Perplexity API
https://docs.perplexity.ai/getting-started/overview

https://www.perplexity.ai/api-platform

**Fetching events from these calendars:**

* https://luma.com/tech
* https://luma.com/ai  
* https://luma.com/sf-developer-events (endpoint doesn't work)
* https://luma.com/genai-sf (endpoint doesn't work)
* https://luma.com/sf

Additional resources:
- https://github.com/copilot/c/7d08c886-2a01-470b-b89e-348a9169d863
- Distance from location calculations: https://chatgpt.com/c/68e95cbc-9aa0-8328-8b6a-db7e227872d9
- Filtering logic: https://www.perplexity.ai/search/for-this-repo-how-would-you-su-dPljCyGCRS6GJ9larrrKcw
- Firebase integration ideas: https://firebase.google.com/docs/storage/web/upload-files