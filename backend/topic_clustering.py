from collections import Counter
from typing import List, Tuple
import colorsys

from bertopic import BERTopic


def hsl_to_hex(h: float, s: float, l: float) -> str:
    """Convert HSL color values in [0,1] to a hex color string."""
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def fallback_color_for_topic(topic_id: int) -> str:
    """Generate a deterministic color from topic id when precomputed palette misses."""
    normalized = ((abs(int(topic_id)) * 37) % 360) / 360.0
    hue = (0.05 + normalized * 0.85) % 1.0
    return hsl_to_hex(hue, 0.65, 0.52)


def generate_cluster_colors(topic_counts: dict) -> dict:
    """Generate deterministic, size-aware colors for topic clusters."""
    ordered_topics = sorted(topic_counts.items(), key=lambda item: item[1], reverse=True)

    total = sum(count for _, count in ordered_topics) or 1
    cumulative = 0
    colors = {}

    for topic_id, count in ordered_topics:
        ratio_midpoint = (cumulative + (count / 2)) / total
        hue = (0.05 + (ratio_midpoint * 0.85)) % 1.0
        colors[topic_id] = hsl_to_hex(hue, 0.65, 0.52)
        cumulative += count

    return colors


def resolve_cluster_color(topic_id: int, topic_colors: dict) -> str:
    """Resolve cluster color without hardcoded literals."""
    return topic_colors.get(topic_id) or fallback_color_for_topic(topic_id)


def extract_event_text(event_record: dict) -> str:
    """Build a clustering text string from an event record."""
    event = event_record.get("event", event_record) if isinstance(event_record, dict) else {}
    name = event.get("name") or event_record.get("name") or ""
    description = event.get("description") or event_record.get("description") or ""
    return f"{name}. {description}".strip()


def cluster_events_with_bertopic(events: List[dict]) -> Tuple[List[dict], List[dict]]:
    """Assign BERTopic clusters to events and return cluster summaries."""
    if not events:
        return events, []

    docs = []
    embeddings = []
    doc_to_event_index = []

    for idx, event in enumerate(events):
        text = extract_event_text(event)
        if not text:
            continue

        docs.append(text)
        doc_to_event_index.append(idx)

        vector = event.get("vector") if isinstance(event.get("vector"), (list, tuple)) else None
        embeddings.append(vector)

    if len(docs) == 0:
        return events, []

    try:
        valid_embeddings = all(v is not None for v in embeddings)
        model = BERTopic(
            nr_topics="auto",
            min_topic_size=max(3, min(12, len(docs) // 10 or 3)),
            calculate_probabilities=False,
            verbose=False,
        )

        if valid_embeddings:
            topics, _ = model.fit_transform(docs, embeddings=embeddings)
        else:
            topics, _ = model.fit_transform(docs)

        topics = [int(t) for t in topics]

        # Reassign BERTopic outliers (-1) so every event receives a concrete cluster.
        non_outlier_topics = [t for t in topics if t != -1]
        if non_outlier_topics:
            dominant_topic = max(set(non_outlier_topics), key=non_outlier_topics.count)
            topics = [dominant_topic if t == -1 else t for t in topics]
        else:
            topics = [0 for _ in topics]

        topic_counts = dict(Counter(topics))
        topic_keywords = {}
        topic_labels = {}

        for topic_id in topic_counts.keys():
            words = model.get_topic(topic_id) or []
            keywords = [word for word, _ in words[:5]]
            topic_keywords[topic_id] = keywords
            topic_labels[topic_id] = " / ".join(keywords[:3]) if keywords else f"Cluster {topic_id}"

        topic_colors = generate_cluster_colors(topic_counts)

        for doc_idx, topic_id in enumerate(topics):
            event_index = doc_to_event_index[doc_idx]
            events[event_index]["topic_cluster"] = {
                "cluster_id": topic_id,
                "keywords": topic_keywords.get(topic_id, []),
                "label": topic_labels.get(topic_id, f"Cluster {topic_id}"),
                "color": resolve_cluster_color(topic_id, topic_colors),
            }

        # Assign events with missing/empty text to the dominant cluster.
        default_topic = max(topic_counts, key=topic_counts.get) if topic_counts else 0
        for event in events:
            if "topic_cluster" not in event:
                event["topic_cluster"] = {
                    "cluster_id": default_topic,
                    "keywords": topic_keywords.get(default_topic, []),
                    "label": topic_labels.get(default_topic, f"Cluster {default_topic}"),
                    "color": resolve_cluster_color(default_topic, topic_colors),
                }

        sorted_topics = sorted(topic_counts.items(), key=lambda item: item[1], reverse=True)
        cluster_summary = [
            {
                "cluster_id": topic_id,
                "count": count,
                "keywords": topic_keywords.get(topic_id, []),
                "label": topic_labels.get(topic_id, f"Cluster {topic_id}"),
                "color": resolve_cluster_color(topic_id, topic_colors),
            }
            for topic_id, count in sorted_topics
        ]
        return events, cluster_summary

    except Exception as clustering_error:
        print(f"⚠️ BERTopic clustering failed: {clustering_error}")
        return events, []


def summarize_clusters_from_events(events: List[dict]) -> List[dict]:
    """Build cluster summaries from precomputed event.topic_cluster metadata."""
    cluster_groups = {}

    for event in events:
        cluster = event.get("topic_cluster")
        if not isinstance(cluster, dict):
            continue

        cluster_id = cluster.get("cluster_id")
        if cluster_id is None:
            continue

        try:
            cluster_id = int(cluster_id)
        except (TypeError, ValueError):
            continue

        if cluster_id not in cluster_groups:
            cluster_groups[cluster_id] = {
                "cluster_id": cluster_id,
                "count": 0,
                "keywords": cluster.get("keywords") if isinstance(cluster.get("keywords"), list) else [],
                "label": cluster.get("label") or f"Cluster {cluster_id}",
                "color": cluster.get("color") or fallback_color_for_topic(cluster_id),
            }

        cluster_groups[cluster_id]["count"] += 1

        existing_keywords = cluster_groups[cluster_id]["keywords"]
        new_keywords = cluster.get("keywords") if isinstance(cluster.get("keywords"), list) else []
        if not existing_keywords and new_keywords:
            cluster_groups[cluster_id]["keywords"] = new_keywords

    return sorted(cluster_groups.values(), key=lambda item: item["count"], reverse=True)
