import requests
from datetime import datetime, timedelta
import json
import openai

# 1. Fetch earthquake data (all earthquakes in the past week)
url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson"
discord_webhook = "https://discord.com/api/webhooks/1359499134767206440/pZmxJYfRjb4Qj6vfEdO0Np4UhIrHb2soXVMSKZybDvE5mYjOOh2VNG31VL10Y0i2c0fd"
openai_api_key = "your_openai_api_key"
response = requests.get(url)
data = response.json()

# 2. Get the current time and time 3 days ago
current_time = datetime.utcnow()
three_days_ago = current_time - timedelta(days=3)
three_days_ago_timestamp = int(three_days_ago.timestamp() * 1000)  # Convert to milliseconds


# 3. Function to determine significant earthquakes
def is_significant_quake(quake):
    # Magnitude
    magnitude = quake.get("properties", {}).get("mag", 0)
    # Location
    place = quake.get("properties", {}).get("place", "").lower()
    # Depth (coordinates: [longitude, latitude, depth])
    depth = quake.get("geometry", {}).get("coordinates", [None, None, 999])[2]
    # Alert level: one of green, yellow, orange, or red
    alert = quake.get("properties", {}).get("alert", "green")
    # Number of people who actually felt the earthquake
    felt = quake.get("properties", {}).get("felt", 0)
    # Time of the earthquake
    time = quake.get("properties", {}).get("time", 0)
    time = datetime.utcfromtimestamp(time / 1000).strftime('%Y-%m-%d %H:%M:%S')  # Convert from timestamp

    # Check if the earthquake occurred at sea
    is_sea = "sea" in place or "ocean" in place

    # Filtering conditions (can be adjusted)
    return (
        magnitude >= 0 and             # Large magnitude
        depth <= 70 and                # Shallow earthquake (potentially higher impact)
        ("city" in place or "near" in place or "km" in place) and  # Includes nearby location info
        (alert in ["orange", "red"] or (felt and felt > 10)) and  # High alert level or felt by many people
        (time >= three_days_ago.strftime('%Y-%m-%d %H:%M:%S'))    # Filter by time (within the last 3 days)
    ), time, is_sea

# 4. Create a list of significant earthquakes
earthquake_list = []
for quake in data["features"]:
    is_significant, time, is_sea = is_significant_quake(quake)
    if is_significant:
        earthquake_info = {
            "location": quake['properties']['place'],
            "magnitude": quake['properties']['mag'],
            "depth": quake['geometry']['coordinates'][2],
            "time": time,
            "alert_level": quake['properties'].get('alert', 'None'),
            "felt": quake['properties'].get('felt', 0),
            "url": quake['properties']['url'],
            "region": '🌊 Ocean' if is_sea else '🌍 Ground'
        }
        earthquake_list.append(earthquake_info)

# 5. Process each earthquake in the list and ask GPT-3.5 for an explanation
for count, quake_info in enumerate(earthquake_list, start=1):
    earthquake_description = (
        f"===============================================\n"
        f"**Earthquake #{count}** 🌍\n\n"
        f"**Location**: {quake_info['location']}\n"
        f"**Magnitude**: {quake_info['magnitude']}\n"
        f"**Depth**: {quake_info['depth']} km\n"
        f"**Occurred at**: {quake_info['time']}\n"
        f"**Region**: {quake_info['region']}\n"
        f"**Alert Level**: {quake_info['alert_level']}\n"
        f"**Number of People Who Felt**: {quake_info['felt']} people\n\n"
        f"**Interactive Map**: [Click here]({quake_info['url']})\n"
        f"**More Info**: [Click here]({quake_info['url']})"
    )

def get_earthquake_explanation(data):
    try:
        client = openai()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an earthquake expert with the ability to explain earthquake events in an easy-to-understand way for the general public. "
                        "Using the provided earthquake data, you should explain the event in detail, helping people understand the significance, "
                        "the magnitude of the event, and whether it was a dangerous earthquake or a minor tremor. "
                        "You need to assess the potential impact of the earthquake, including the possibility of damage, risk to life, and any secondary hazards like aftershocks or tsunamis. "
                        "If it was a major earthquake, explain its power (magnitude) and the expected effects. "
                        "If it was a minor earthquake, explain why it is less likely to cause harm and the typical behavior of such events.\n\n"
                        
                        "### Earthquake Explanation Guidelines:\n"
                        "- Explain the earthquake's magnitude (e.g., 'This was a magnitude 7.5 earthquake, which is classified as major').\n"
                        "- Describe the depth of the earthquake and its relationship to the potential for damage (e.g., shallow vs. deep earthquakes).\n"
                        "- Provide an understanding of the location and its vulnerability (e.g., near a densely populated area or a fault line). \n"
                        "- If the earthquake is significant, describe the potential for secondary effects, such as aftershocks or tsunamis.\n"
                        "- Highlight the differences between a minor tremor and a major earthquake in terms of public safety and infrastructure risk.\n"
                        "- Include any relevant historical context for the area (e.g., 'This region is prone to earthquakes of this magnitude').\n\n"
                        
                        "### Response Format:\n"
                        "Provide the output as a detailed explanation, focusing only on the earthquake's significance and potential risk:\n"
                        "'Explanation of the earthquake in simple, detailed terms, addressing the magnitude, depth, location, and danger level, "
                        "and explaining the expected impact or safety of the event.'\n\n"
                    )
                },
                {
                    "role": "user",
                    "content": json.dumps(data, indent=4)
                }
            ]
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"Error generating earthquake explanation: {e}")
        return "AI processing error, unable to provide explanation."


# try to get the explanation from OpenAI
explanation = get_earthquake_explanation(earthquake_list[0])

print(explanation)