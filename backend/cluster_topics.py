import os
from datetime import datetime

import lancedb
import pandas as pd
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
import torch


PALETTE = [
    "#0EA5E9",
    "#22C55E",
    "#F97316",
    "#EAB308",
    "#EF4444",
    "#14B8A6",
    "#3B82F6",
    "#84CC16",
    "#F59E0B",
    "#06B6D4",
]


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


def assign_outliers_to_fallback(topics):
    """Ensure every event has a concrete topic id by remapping BERTopic outliers (-1)."""
    non_outliers = [topic for topic in topics if topic != -1]
    if non_outliers:
        fallback_topic = max(set(non_outliers), key=non_outliers.count)
    else:
        fallback_topic = 0
    return [fallback_topic if topic == -1 else topic for topic in topics]


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
    topics, _ = topic_model.fit_transform(docs)
    topics = assign_outliers_to_fallback(topics)

    unique_topics = sorted({topic for topic in topics if topic != -1})
    topic_color_map = {topic_id: PALETTE[i % len(PALETTE)] for i, topic_id in enumerate(unique_topics)}
    topic_color_map[-1] = "#64748B"

    labels = []
    colors = []
    for topic_id in topics:
        labels.append(build_topic_label(topic_model, topic_id))
        colors.append(topic_color_map.get(topic_id, "#64748B"))

    df["topic_id"] = topics
    df["topic_label"] = labels
    df["topic_color"] = colors

    db.create_table("events", data=df.to_dict("records"), mode="overwrite")

    topic_info = topic_model.get_topic_info()
    print("Updated topic clusters.")
    print(topic_info[["Topic", "Count", "Name"]].head(20).to_string(index=False))


if __name__ == "__main__":
    cluster_event_topics()
