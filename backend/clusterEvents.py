import os
import lancedb

from topic_clustering import cluster_events_with_bertopic


def load_events_from_lancedb(db_path=None):
    if db_path is None:
        home_dir = os.path.expanduser("~")
        db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"LanceDB database not found at {db_path}")

    db = lancedb.connect(db_path)
    if "events" not in db.table_names():
        raise FileNotFoundError("'events' table not found in LanceDB")

    table = db.open_table("events")
    events = table.to_pandas().to_dict("records")
    print(f"📊 Loaded {len(events)} events from LanceDB")
    return db, events


def save_events_to_lancedb(db, events):
    db.create_table("events", data=events, mode="overwrite")
    print(f"💾 Updated 'events' table in LanceDB with {len(events)} records")


def main():
    db, events = load_events_from_lancedb()
    clustered_events, cluster_summary = cluster_events_with_bertopic(events)

    save_events_to_lancedb(db, clustered_events)
    print(f"✅ Clustered events into {len(cluster_summary)} clusters")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        exit(1)
