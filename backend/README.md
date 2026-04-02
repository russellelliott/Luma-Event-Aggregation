# Luma Event Aggregation Backend

This backend ingests Bay Area Luma events into LanceDB, enriches missing metadata, clusters events into topic buckets with BERTopic, and serves filtered/searchable results through FastAPI.

## What Is In This Folder

- `fetchEvents.py`: Pulls events from multiple Luma sources, deduplicates by URL, filters to California, and writes LanceDB tables.
- `generateEventDescriptions.py`: Fills missing event description/city/coordinates (and pricing when available).
- `cluster_topics.py`: Runs BERTopic topic clustering and writes `topic_id` / `topic_label` / `topic_color` back to the `events` table.
- `main.py`: FastAPI server used by the frontend.
- `filterEvents.py`: Shared filtering logic used by the API and CLI testing.
- `run_pipeline.sh`: Recommended one-command pipeline.

## Recommended Run Flow

From this `backend` directory:

```bash
python3 -m pip install -r requirements.txt
export GOOGLE_MAPS_API_KEY="your_api_key_here"
chmod +x run_pipeline.sh
./run_pipeline.sh
```

The pipeline currently runs:

1. `backup_db.py`
2. `fetchEvents.py`
3. `generateEventDescriptions.py`
4. `cluster_topics.py`

Then start the API:

```bash
uvicorn main:app --reload
```

## BERTopic Clustering: How It Is Used Here

`cluster_topics.py` performs unsupervised topic grouping over event text and persists cluster metadata used directly by the UI and `/topics` endpoint.

### Inputs to BERTopic

- Each document is built as: `name + "\n\n" + description`.
- If description is missing, the event name still participates.

### Text preprocessing before clustering

- Tokenization is regex-based (`[A-Za-z][A-Za-z0-9']*`).
- A large custom stopword list is removed (time words, venue words, generic social words, geography noise, etc.).
- Dynamic stopwords are also removed: any token appearing in more than 0.1% of total corpus tokens.

### BERTopic model configuration

- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`.
- Device: Apple `mps` when available, else CPU.
- BERTopic is run recursively, not just once:
  - The corpus is clustered.
  - Any cluster still larger than 10% of all documents is re-clustered.
  - Recursion stops when clusters are small enough or no meaningful split is possible.
- Effective `min_topic_size` is adapted per subset to avoid degenerate small-group behavior.

### Outliers and labels

- BERTopic outliers (`-1`) are remapped to the most common non-outlier topic so every event receives a concrete topic id.
- Final labels are generated from top token frequencies in each cluster (up to 3 terms, joined by ` / `).
- Each cluster gets a random dark-ish hex color for frontend chips/cards.

### What gets written back

The `events` table is overwritten with the same base columns plus:

- `topic_id` (int)
- `topic_label` (string)
- `topic_color` (hex string)

Before this overwrite, clustering creates a safety backup table named:

- `events_backup_before_clustering_<unix_timestamp>`

## LanceDB Storage

Database path:

- `~/.luma-event-aggregation/data/events.db`

Primary tables:

- `events`
- `city_summary`

Backup tables are created over time and kept in the same DB.

### `events` table schema

Current normalized schema used by `fetchEvents.py`, `generateEventDescriptions.py`, `cluster_topics.py`, and API load paths:

- `id`: string (UUID or source id)
- `name`: string
- `url`: string (normalized to full Luma URL when available)
- `start_at`: string (ISO timestamp, typically UTC)
- `end_at`: string (ISO timestamp, typically UTC)
- `description`: string or null
- `timezone`: string (`America/Los_Angeles` default during normalization)
- `pricing`: string or null (non-string values are JSON-serialized in description generation step)
- `city`: string or null
- `coordinates`: struct
  - `latitude`: float64 or null
  - `longitude`: float64 or null
- `bookmarked`: bool
- `topic_id`: int64 or null
- `topic_label`: string or null
- `topic_color`: string or null
- `cosine_distance`: float64 or null

Notes:

- `bookmarked` is preserved for existing rows when fetching new data.
- New events default to `bookmarked = False` and null topic fields until clustering runs.
- `cosine_distance` is an ephemeral ranking value set during text search and reset during filtering.

### `city_summary` table schema

Generated in `fetchEvents.py` from Google Maps Distance Matrix results, keyed by city:

- `city`: string
- `event_count`: int
- `status`: string (usually `OK` when retained)
- `distance_text`: string (example: `15.2 mi`)
- `distance_meters`: number
- `distance_miles`: number
- `duration_text`: string (example: `23 mins`)
- `duration_seconds`: number
- `duration_minutes`: number

Only California cities with successful distance lookups are kept in this table.

## API Surface (used by frontend)

- `GET /events/all`: full list endpoint with query search and topic filtering.
- `GET /events`: filtered events by location/date/weekday/topic/bookmarked/include_past.
- `GET /topics`: aggregated topic labels/colors/counts from `events`.
- `GET /cities`: city summary rows.
- `POST /add-event`: scrape and insert one event URL.
- `POST /events/{event_id}/bookmark`: toggle bookmark.
- `GET /bookmarks`: bookmarked events only.

## Calendar Sources

Two Luma API patterns are used in `fetchEvents.py`:

- Discover slug endpoint: `discover/get-paginated-events`
- Calendar endpoint: `calendar/get-items`

Current source lists are hard-coded in `fetchEvents.py` (`slugs` and `calendar_configs`).

## Legacy Script Note

`classifyEvents.py` (Ollama event_type/audience labeling) still exists, but it is not part of `run_pipeline.sh` now. The current frontend topic experience is driven by BERTopic fields (`topic_id`, `topic_label`, `topic_color`).