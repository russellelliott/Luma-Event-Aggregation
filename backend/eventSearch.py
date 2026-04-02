from difflib import SequenceMatcher


def _event_search_text(event):
    parts = [
        event.get("name") or "",
        event.get("description") or "",
        event.get("city") or "",
        event.get("topic_label") or "",
    ]
    return " ".join(part for part in parts if part).strip().lower()

def search_events(query, events):
    """
    Search events by query string using text similarity.

    Args:
        query (str): The search query.
        events (list): List of event dictionaries.

    Returns:
        list: events with updated 'cosine_distance' based on textual similarity.
    """
    if not query:
        return events

    try:
        normalized_query = query.strip().lower()
        for e in events:
            search_text = _event_search_text(e)
            if not search_text:
                e["cosine_distance"] = None
                continue

            ratio = SequenceMatcher(None, normalized_query, search_text).ratio()
            e["cosine_distance"] = float(1 - ratio)

        return events
    except Exception as e:
        print(f"Error during search: {e}")
        return events
