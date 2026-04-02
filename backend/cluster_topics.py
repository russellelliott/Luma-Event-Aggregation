import os
import random
import re
from datetime import datetime
from collections import Counter

import lancedb
import pandas as pd
import pyarrow as pa
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
import torch


def get_db_path():
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")


def build_topic_label(topic_model, topic_id):
    if topic_id == -1:
        return "Other"
    words = topic_model.get_topic(topic_id) or []
    top_terms = [word for word, _ in words[:3]]
    if not top_terms:
        return f"Topic {topic_id}"
    return " / ".join(top_terms)


def random_hex_color():
    return f"#{random.randint(0, 255):02X}{random.randint(0, 255):02X}{random.randint(0, 255):02X}"


def assign_outliers_to_fallback(topics):
    """Ensure every event has a concrete topic id by remapping BERTopic outliers (-1)."""
    non_outliers = [topic for topic in topics if topic != -1]
    if non_outliers:
        fallback_topic = max(set(non_outliers), key=non_outliers.count)
    else:
        fallback_topic = 0
    return [fallback_topic if topic == -1 else topic for topic in topics]


def tokenize_text(text):
    return re.findall(r"[A-Za-z][A-Za-z0-9']*", (text or "").lower())


def remove_high_frequency_stopwords(docs, frequency_threshold=0.001):
    """
    Remove words that appear in more than `frequency_threshold` of all corpus tokens.
    frequency_threshold=0.001 corresponds to 0.1%.
    """
    tokenized_docs = [tokenize_text(doc) for doc in docs]
    all_tokens = [token for doc_tokens in tokenized_docs for token in doc_tokens]

    if not all_tokens:
        return docs, set()

    token_counts = Counter(all_tokens)
    total_tokens = len(all_tokens)
    dynamic_stopwords = {
        token
        for token, count in token_counts.items()
        if (count / total_tokens) > frequency_threshold
    }

    filtered_docs = [
        " ".join(token for token in doc_tokens if token not in dynamic_stopwords)
        for doc_tokens in tokenized_docs
    ]
    return filtered_docs, dynamic_stopwords


def _to_text_or_none(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return str(value)


def _to_float_or_none(value):
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int_or_none(value):
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_events_arrow_table(df):
    records = []
    for _, row in df.iterrows():
        coordinates = row.get("coordinates") if isinstance(row.get("coordinates"), dict) else {}
        records.append(
            {
                "id": _to_text_or_none(row.get("id")),
                "name": _to_text_or_none(row.get("name")),
                "url": _to_text_or_none(row.get("url")),
                "start_at": _to_text_or_none(row.get("start_at")),
                "end_at": _to_text_or_none(row.get("end_at")),
                "description": _to_text_or_none(row.get("description")),
                "timezone": _to_text_or_none(row.get("timezone")),
                "pricing": _to_text_or_none(row.get("pricing")),
                "city": _to_text_or_none(row.get("city")),
                "coordinates": {
                    "latitude": _to_float_or_none(coordinates.get("latitude")),
                    "longitude": _to_float_or_none(coordinates.get("longitude")),
                },
                "bookmarked": bool(row.get("bookmarked", False)),
                "topic_id": _to_int_or_none(row.get("topic_id")),
                "topic_label": _to_text_or_none(row.get("topic_label")),
                "topic_color": _to_text_or_none(row.get("topic_color")),
                "cosine_distance": _to_float_or_none(row.get("cosine_distance")),
            }
        )

    coordinates_array = pa.array(
        [record["coordinates"] for record in records],
        type=pa.struct(
            [
                pa.field("latitude", pa.float64()),
                pa.field("longitude", pa.float64()),
            ]
        ),
    )

    arrays = [
        pa.array([record["id"] for record in records], type=pa.string()),
        pa.array([record["name"] for record in records], type=pa.string()),
        pa.array([record["url"] for record in records], type=pa.string()),
        pa.array([record["start_at"] for record in records], type=pa.string()),
        pa.array([record["end_at"] for record in records], type=pa.string()),
        pa.array([record["description"] for record in records], type=pa.string()),
        pa.array([record["timezone"] for record in records], type=pa.string()),
        pa.array([record["pricing"] for record in records], type=pa.string()),
        pa.array([record["city"] for record in records], type=pa.string()),
        coordinates_array,
        pa.array([record["bookmarked"] for record in records], type=pa.bool_()),
        pa.array([record["topic_id"] for record in records], type=pa.int64()),
        pa.array([record["topic_label"] for record in records], type=pa.string()),
        pa.array([record["topic_color"] for record in records], type=pa.string()),
        pa.array([record["cosine_distance"] for record in records], type=pa.float64()),
    ]

    field_names = [
        "id",
        "name",
        "url",
        "start_at",
        "end_at",
        "description",
        "timezone",
        "pricing",
        "city",
        "coordinates",
        "bookmarked",
        "topic_id",
        "topic_label",
        "topic_color",
        "cosine_distance",
    ]

    return pa.Table.from_arrays(arrays, names=field_names)


def backup_events_table(db, events_df):
    backup_df = events_df.copy()
    backup_df = backup_df.where(pd.notna(backup_df), None)

    text_columns = [
        "id",
        "name",
        "url",
        "start_at",
        "end_at",
        "description",
        "timezone",
        "pricing",
        "city",
        "topic_label",
        "topic_color",
    ]
    for column in text_columns:
        if column in backup_df.columns:
            backup_df[column] = backup_df[column].apply(
                lambda value: str(value) if value is not None and not isinstance(value, str) else value
            )

    timestamp = int(datetime.now().timestamp())
    backup_name = f"events_backup_before_clustering_{timestamp}"
    db.create_table(backup_name, data=backup_df.to_dict("records"), mode="overwrite")
    print(f"Created backup table: {backup_name}")
    return backup_name


def get_table_names(db):
    """Return table names across LanceDB versions where list_tables/table_names differ."""
    tables = []

    def _extract_names(raw):
        # Common shape: ['events', 'city_summary']
        if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
            return raw

        # Shape: {'tables': [...], 'page_token': ...}
        if isinstance(raw, dict):
            if isinstance(raw.get("tables"), list):
                return [str(x) for x in raw["tables"]]
            return [str(x) for x in raw.keys()]

        # Shape: [('tables', [...]), ('page_token', None)]
        if isinstance(raw, list) and raw and all(isinstance(x, tuple) and len(x) == 2 for x in raw):
            as_dict = dict(raw)
            if isinstance(as_dict.get("tables"), list):
                return [str(x) for x in as_dict["tables"]]

        return None

    if hasattr(db, "list_tables"):
        try:
            raw_tables = db.list_tables()
            extracted = _extract_names(raw_tables)
            tables = extracted if extracted is not None else (raw_tables or [])
        except Exception:
            tables = []

    if (not tables) and hasattr(db, "table_names"):
        try:
            raw_tables = db.table_names()
            extracted = _extract_names(raw_tables)
            tables = extracted if extracted is not None else (raw_tables or [])
        except Exception:
            tables = []

    normalized = []
    for table in tables:
        if isinstance(table, str):
            normalized.append(table)
        elif isinstance(table, dict) and isinstance(table.get("name"), str):
            normalized.append(table["name"])
        else:
            normalized.append(str(table))

    return normalized


def cluster_event_topics(min_topic_size=8):
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    db = lancedb.connect(db_path)
    try:
        table = db.open_table("events")
    except Exception as exc:
        table_names = get_table_names(db)
        print(f"events table not found. Available tables: {table_names}")
        print(f"open_table('events') error: {exc}")
        return
    df = table.to_pandas()

    # Safety gate: backup must succeed before any clustering work proceeds.
    try:
        backup_events_table(db, df)
        print("Backup check succeeded.")
    except Exception as exc:
        print(f"Backup failed, aborting clustering: {exc}")
        return

    if df.empty:
        print("No events to cluster")
        return

    docs = []
    for _, row in df.iterrows():
        name = row.get("name") or ""
        description = row.get("description") or ""
        docs.append(f"{name}\n\n{description}".strip())

    clustering_docs, dynamic_stopwords = remove_high_frequency_stopwords(docs, frequency_threshold=0.001)
    print(
        f"Removed {len(dynamic_stopwords)} high-frequency stopwords (>0.1% corpus frequency) for clustering input."
    )

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    embedding_model = SentenceTransformer(
        "all-MiniLM-L6-v2",
        device=device,
    )

    topic_model = BERTopic(
        embedding_model=embedding_model,
        min_topic_size=min_topic_size,
        calculate_probabilities=False,
        verbose=True,
    )
    topics, _ = topic_model.fit_transform(clustering_docs)
    topics = assign_outliers_to_fallback(topics)

    unique_topics = sorted({topic for topic in topics if topic != -1})
    topic_color_map = {topic_id: random_hex_color() for topic_id in unique_topics}
    topic_color_map[-1] = random_hex_color()

    labels = []
    colors = []
    for topic_id in topics:
        labels.append(build_topic_label(topic_model, topic_id))
        colors.append(topic_color_map.get(topic_id, "#64748B"))

    df["topic_id"] = topics
    df["topic_label"] = labels
    df["topic_color"] = colors

    events_table = build_events_arrow_table(df)
    db.create_table("events", data=events_table, mode="overwrite")

    topic_info = topic_model.get_topic_info()
    print("Updated topic clusters.")
    print(topic_info[["Topic", "Count", "Name"]].head(20).to_string(index=False))


if __name__ == "__main__":
    cluster_event_topics()
