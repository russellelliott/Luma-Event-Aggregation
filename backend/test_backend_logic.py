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

        # Basic Stats on Cosine Distance
        import numpy as np
        
        distances = [e.get('cosine_distance') for e in events if e.get('cosine_distance') is not None]
        
        if distances:
            print("\n----- Cosine Distance Statistics -----")
            print(f"Count: {len(distances)}")
            print(f"Min: {min(distances):.4f}")
            print(f"Mean: {sum(distances)/len(distances):.4f}")
            print(f"Max: {max(distances):.4f}")
            if len(distances) > 1:
                print(f"Std Dev: {np.std(distances):.4f}")
            print("--------------------------------------\n")
        else:
            print("\nNo cosine distances found (are any events bookmarked?)")
except Exception as e:
    print(f"Execution failed: {e}")
