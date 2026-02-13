import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from filterEvents import load_events
    print("Function imported successfully")
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

try:
    events = load_events()
    print(f"Loaded {len(events)} events")
    
    if events:
        first = events[0]
        print("First event keys:", first.keys())
        if 'cosine_distance' in first:
            print(f"Cosine distance present: {first['cosine_distance']}")
        else:
            print("Cosine distance NOT present")
            
        # Check if vectors are loaded
        if 'vector' in first:
             vector = first['vector']
             if vector is not None:
                print("Vector data loaded (length):", len(vector))
             else:
                print("Vector is None")
except Exception as e:
    print(f"Execution failed: {e}")
