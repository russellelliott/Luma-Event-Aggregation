import lancedb
import os
import json

# Full description from previous context
full_description = """Join us for the Sunday Builders Club, a private weekly meetup of tasteful founders, engineers, designers, and inventors who care about building with intention.
The gathering is lightly organized. Conversations form on their own, shaped by the people in the room.
The atmosphere is easy:
Coffee, tea & pasteries    A DJ deck with slow tunes    A few poker tables for anyone who wants to play
We will then break into small circles. You can stay in one or float between them:
Product & Taste Circle:  How we shape products people love. Taste, design, and the choices that define great work.  **•
Management Circle:  Hiring, leading, firing, staying grounded, and handling pressure.    I
Industry Circle:  Open dives into sectors like AI, tools for creators, education, consumer apps, and more.
Mental Health Circle:  A quiet, honest place to talk about motivation, burnout, and the emotional weight of building.
You are welcome to bring your own food or snacks.    To stay connected, join our WhatsApp group. It’s where we share details on future events, coordinate logistics, and keep conversations going.  A member can add you, or use the link below and introduce yourself so we can approve you and keep out spam:  WhatsApp Group: (https://chat.whatsapp.com/IgdXA20i0y78KitDGeZ4u9)
Sunday Builder Club is sponsored by TalentOS and TalentHunt.
TalentOS — a game for your career where talents prove what they can do through real missions, projects, and bounties, not resumes.
👉 https://talentosapp.com
TalentHunt — a hiring platform that helps companies discover and hire real talent based on verified work and skills, not background or credentials.
👉 https://talenthunt.so

This event is hosted at the Frontier Tower:
We are transforming a 16-floor tower in San Francisco into a self-governed vertical village—a hub for frontier technologies and creative arts. Tier-one labs presenting AI, Ethereum, biotech, neuroscience, longevity, robotics, human flourishing, and arts & music. These floors will house innovators and creators pushing the boundaries of human potential in a post-AI-singularity world.
Apply here for founding citizenship: https://frontiertower.io/apply
Why should I become a citizen?
Be part of creating the first self-governed vertical village
Connect with the most creative people in the city
Get access to all floors, free event space & movement floor
Website: https://frontiertower.io/
Need more reading? Visit https://frontiertower.notion.site/"""

def normalize_url(url):
    if not url: return ""
    if url.startswith("https://luma.com/"):
        url = url.replace("https://luma.com/", "https://lu.ma/")
    return url

def fix_description():
    home_dir = os.path.expanduser("~")
    db_path = os.path.join(home_dir, ".luma-event-aggregation", "data", "events.db")
    db = lancedb.connect(db_path)
    table = db.open_table("events")
    
    target_url = "https://lu.ma/sunday-builders-club-salon-for-the-taste-2270"
    
    # Load all events
    df = table.to_pandas()
    events = df.to_dict('records')
    
    # Find the event
    target_event = None
    target_index = -1
    
    for i, event in enumerate(events):
        row_url = event.get('url')
        nested_url = event.get('event', {}).get('url') if isinstance(event.get('event'), dict) else None
        
        if normalize_url(row_url) == target_url or normalize_url(nested_url) == target_url:
            target_event = event
            target_index = i
            break
    
    if target_event:
        print(f"Found event: {target_event.get('event', {}).get('name')}")
    else:
        print("Event not found.")
        return

    # Update description
    event_struct = target_event.get('event', {})
    if not isinstance(event_struct, dict):
        event_struct = {}
        
    event_struct['description'] = full_description
    target_event['event'] = event_struct
    
    # Update in list
    events[target_index] = target_event
    
    # Save back to DB
    print("Updating database with full description...")
    try:
        db.create_table("events", data=events, mode="overwrite")
        print("✅ Event description updated successfully.")
    except Exception as e:
        print(f"❌ Update failed: {e}")

if __name__ == "__main__":
    fix_description()
