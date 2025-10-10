# Luma Event Aggregator
Fetches events from several Luma calendar. Will enable user to filter them based on preference via AI (perhaps Perplexity)

Start and End times (start_at, end_at) appear to be in standard UTC timestamp. For filtering by dates and times, go by the user's time zone.

1. fetch events using `fetchEvents.py`, events go into fetchedEvents/[slug].json

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

Fetching events from these calendars:

* https://luma.com/tech
* https://luma.com/ai
* https://luma.com/sf-developer-events (endpoint doesn't work)
* https://luma.com/genai-sf (endpoint doesn't work)
* https://luma.com/sf



https://github.com/copilot/c/7d08c886-2a01-470b-b89e-348a9169d863

Distance from your location to city
https://chatgpt.com/c/68e95cbc-9aa0-8328-8b6a-db7e227872d9

## Aggregating and summarizing events

A new helper script `aggregate_events.py` will combine all JSON files in `fetchedEvents/`, sort events by `start_at`, extract city names and write two outputs:

- `fetchedEvents/combined_events.json` — combined list of all events sorted by start time
- `fetchedEvents/city_summary.json` — counts per city and (optionally) Google Maps distance/time data

Quick start (zsh):

```bash
python3 -m pip install -r requirements.txt
# optionally set your Google Maps API key to enable distance/time lookups
export GOOGLE_MAPS_API_KEY="YOUR_KEY_HERE"
python3 aggregate_events.py
```

If `GOOGLE_MAPS_API_KEY` is not set, the script will still produce the combined and city count outputs but skip remote distance queries.



figuring out filters
https://www.perplexity.ai/search/for-this-repo-how-would-you-su-dPljCyGCRS6GJ9larrrKcw

firebase upload files to web (should i make this as a public app? i feel there would be lots of redundant data if we use this hardcoded stuff)
https://firebase.google.com/docs/storage/web/upload-files