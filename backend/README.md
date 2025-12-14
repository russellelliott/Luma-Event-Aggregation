# Luma Event Aggregator (Backend)
Fetches events from several Luma calendars and enables filtering by location, date, and weekdays.

Start and End times (start_at, end_at) appear to be in standard UTC timestamp. For filtering by dates and times, go by the user's time zone.

## Requirements

- **Google Maps API Key**: Required for generating city summaries with distance/time data
- **Internet Connection**: For automatic IP-based location detection

## Quick Start

1. **Set up Google Maps API key**:
   ```bash
   export GOOGLE_MAPS_API_KEY="your_api_key_here"
   ```

2. **Fetch and aggregate events** (location will be detected automatically):
   ```bash
   cd backend
   python3 -m pip install -r requirements.txt
   python3 fetchEvents.py
   ```

3. **Generate event descriptions** (scrapes detailed info):
   ```bash
   # From backend directory
   # Fetches full descriptions and pricing for events
   python3 generateEventDescriptions.py
   ```
5. **Classify events** (requires Ollama running locally):
   ```bash
   # From backend directory
   # Classifies events by type and audience using local LLM
   python3 classifyEvents.py
   ```

6. **Filter events** using `filterEvents.py`:
   ```bash
   # From backend directory
   # Filter by location(s) and date
   python3 filterEvents.py --location "Mountain View" "San Francisco" --dates 2025-10-10 2025-10-11
   ```

7. **Run the API Server**:
   ```bash
   # Start the FastAPI server
   uvicorn main:app --reload
   ```
   The API will be available at `http://localhost:8000`.

   # Filter by weekdays
   ```
   python3 filterEvents.py --weekdays Friday Saturday
   ```
   
   # Filter by event type and audience (requires running classifyEvents.py first)
   ```
   python3 filterEvents.py --event-type hackathon workshop --audience job_seekers
   ```

   # Combine filters
   ```
   python3 filterEvents.py --location "San Francisco" --weekdays Friday --event-type networking
   ```

6. **Run the API Server**:
   ```bash
   # From backend directory
   python3 main.py
   # OR
   uvicorn main:app --reload
   ```
   
   The API will be available at `http://localhost:8000`.
   - **List Cities**: `GET /cities`
   - **Filter Events**: `GET /events` (supports query params: `location`, `dates`, `weekdays`, `event-type`, `audience`)

## Automated Pipeline

To run the entire data collection and processing pipeline (fetch, generate descriptions, and classify) in one go:

```bash
cd backend
chmod +x run_pipeline.sh
./run_pipeline.sh
```

### Available Classification Options

**Event Types:**
- `career_fair`
- `hackathon`
- `workshop`
- `networking`
- `conference`
- `demo_day`
- `panel_discussion`
- `social`

**Audience Categories:**
- `job_seekers`
- `founder_investor`
- `general`

## Output Files

After running `fetchEvents.py`, data is saved to LanceDB (`~/.luma-event-aggregation/data/events.db`):
- Table `events` — All events from all slugs, sorted by start time
- Table `city_summary` — Event counts per city **with comprehensive distance/time data**

### City Summary Data Structure
Each city in the summary includes:
- `event_count`: Number of events in that city
- `status`: Google Maps API status ("OK", "ERROR", etc.)
- `distance_text`: Human-readable distance (e.g., "15.2 miles")
- `distance_meters`: Distance in meters (numeric)
- `distance_miles`: Distance in miles (numeric)
- `duration_text`: Human-readable duration (e.g., "23 minutes")
- `duration_seconds`: Duration in seconds (numeric)  
- `duration_minutes`: Duration in minutes (numeric)

## How It Works

- **Automatic Location Detection**: Uses ipinfo.io to detect your location from IP address
- **fetchEvents.py**: Fetches events from multiple Luma calendar slugs in parallel, combines them into a single sorted list, and generates a comprehensive city summary with **mandatory** Google Maps distance/time data
- **listCities.py**: Lists all cities found in the events, sorted by travel time from your location.
- **classifyEvents.py**: Uses a local Ollama LLM to analyze event descriptions and assign an `event_type` (e.g., hackathon, workshop, networking) and `audience` (e.g., job_seekers, founder_investor). Supports parallel processing for speed.
- **filterEvents.py**: Filters the combined events by location, specific dates, weekdays, event type, and/or audience.

No intermediate JSON files are created per slug - everything is processed in memory and output as a single combined file.

## Resources

### Writing the Code
https://colab.research.google.com/drive/1T362Lml9rCxyloaV3sV_5ngZu3PrOSHH#scrollTo=K3Y-IS_sbP2h

https://aistudio.google.com/prompts/1Qte8iKmJXVQCLG-iF3ZvWUXp5z4Rz1iY

https://claude.ai/chat/37dc1455-86fe-494c-bd60-2528fb09190d

### Fleshing out the idea
https://chatgpt.com/c/68e7faa9-fa48-8329-932d-55d4b2b41238

https://www.perplexity.ai/search/i-have-this-repo-which-gets-a-UPZPZKtHQTWfFyDOkozp5w

### Perplexity API
https://docs.perplexity.ai/getting-started/overview

https://www.perplexity.ai/api-platform

**Fetching events from these calendars:**

**Slug-based calendars** (using discover API):
* https://luma.com/tech
* https://luma.com/ai
* https://luma.com/sf

**Calendar API calendars** (using calendar/get-items API):
* https://luma.com/foundersocialclub
* https://luma.com/genai-sf
* https://luma.com/sf-developer-events
* https://luma.com/svgenai
* https://luma.com/genai-collective

### How to Add More Calendars

To find the API endpoint for a new Luma calendar:

1. **Go to the calendar's map page** (e.g., `https://luma.com/[calendar-name]/map`)
2. **Open browser DevTools** (F12 or Right Click → Inspect)
3. **Go to the Network tab**
4. **Refresh the page** and look for API calls with `200` status
5. **Find the request** named `get-items` or `get-paginated-events`
6. **Click on it** to view the request details

You'll see one of two types:
- **Slug-based**: `https://api2.luma.com/discover/get-paginated-events?slug=...`
  - Add the slug to the `slugs` list in `fetchEvents.py`
- **Calendar API**: `https://api2.luma.com/calendar/get-items?calendar_api_id=cal-...`
  - Add the calendar_api_id and name to the `calendar_configs` list in `fetchEvents.py`

Example:
```python
# In fetchEvents.py main() function:

slugs = [
    "tech",
    "ai",
    "your-new-slug"  # Add here
]

calendar_configs = [
    {
        "calendar_api_id": "cal-YourNewId",
        "name": "your-calendar-name"  # Add here
    }
]
```

Additional resources:
- https://github.com/copilot/c/7d08c886-2a01-470b-b89e-348a9169d863
- Distance from location calculations: https://chatgpt.com/c/68e95cbc-9aa0-8328-8b6a-db7e227872d9
- Filtering logic: https://www.perplexity.ai/search/for-this-repo-how-would-you-su-dPljCyGCRS6GJ9larrrKcw
- Firebase integration ideas: https://firebase.google.com/docs/storage/web/upload-files