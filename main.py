import requests
from datetime import datetime
import json
import openai
import os
from dotenv import load_dotenv

load_dotenv()
# 1. Fetch earthquake data (all earthquakes in the past week)
url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson"
discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
openai_api_key = os.getenv("OPENAI_API_KEY")

response = requests.get(url)
data = response.json()

# 2. Get the current time (today's start and end)
current_time = datetime.utcnow()
today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)  # Start of today
today_end = current_time  # Current time as the end of today

# 3. Function to determine significant earthquakes for today only
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
    time = datetime.utcfromtimestamp(time / 1000)  # Convert from timestamp

    # Check if the earthquake occurred at sea
    is_sea = "sea" in place or "ocean" in place

    # Filtering conditions (can be adjusted)
    return (
        magnitude >= 0 and             # Large magnitude
        depth <= 70 and                # Shallow earthquake (potentially higher impact)
        ("city" in place or "near" in place or "km" in place) and  # Includes nearby location info
        (alert in ["orange", "red"] or (felt and felt > 10)) and  # High alert level or felt by many people
        (today_start <= time <= today_end)    # Only earthquakes that occurred today
    ), time, is_sea

# 4. Create a list of significant earthquakes for today
earthquake_list = []
for quake in data["features"]:
    is_significant, time, is_sea = is_significant_quake(quake)
    if is_significant:
        earthquake_info = {
            "location": quake['properties']['place'],
            "magnitude": quake['properties']['mag'],
            "depth": quake['geometry']['coordinates'][2],
            "time": time.strftime('%Y-%m-%d %H:%M:%S'),
            "alert_level": quake['properties'].get('alert', 'None'),
            "felt": quake['properties'].get('felt', 0),
            "url": quake['properties']['url'],
            "region": '🌊 Ocean' if is_sea else '🌍 Ground'
        }
        earthquake_list.append(earthquake_info)

# 5. Process each earthquake in the list and ask GPT-3.5 for an explanation
def get_earthquake_explanation(data):
    try:
        openai.api_key = openai_api_key

        # API 호출
        response = openai.ChatCompletion.create(
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
                    "- Provide an understanding of the location and its vulnerability (e.g., near a densely populated area or a fault line).\n"
                    "- If the earthquake is significant, describe the potential for secondary effects, such as aftershocks or tsunamis.\n"
                    "- Highlight the differences between a minor tremor and a major earthquake in terms of public safety and infrastructure risk.\n"
                    "- Include any relevant historical context for the area (e.g., 'This region is prone to earthquakes of this magnitude').\n\n"
                    
                    "### Example Response Format (for consistency):\n"
                    "'This was a magnitude 7.5 earthquake, which is classified as a major earthquake. The earthquake occurred at a depth of 10 km, which is considered shallow and increases the potential for significant damage. The event took place near a heavily populated area, and based on its location, the impact could be severe, with potential aftershocks or even a tsunami. We expect significant infrastructure damage and loss of life, and we recommend immediate safety precautions for anyone in the affected region.'\n\n"
                    
                    "### Response Format:\n"
                    "Provide the output as a detailed explanation, focusing only on the earthquake's significance and potential risk:\n"
                    "'Explanation of the earthquake in simple, detailed terms, addressing the magnitude, depth, location, and danger level, "
                    "and explaining the expected impact or safety of the event.'\n\n"
                )
            },
                {
                    "role": "user",
                    "content": json.dumps({
                        "Location": data["location"],
                        "Magnitude": data["magnitude"],
                        "Depth": data["depth"],
                        "Time": data["time"],
                        "Alert Level": data["alert_level"],
                        "People Who Felt": data["felt"],
                        "Region": data["region"]
                    }, indent=4)
                }
            ]
        )

        # 응답 반환
        return response.choices[0].message['content'].strip()

    except Exception as e:
        print(f"Error generating earthquake explanation: {e}")
        return "AI processing error, unable to provide explanation."

# send to discord about the earthquake
# example: "2025-01-01 Today's earthquake report"
earthquake_report_date = datetime.utcnow().strftime('%Y-%m-%d')
earthquake_report_title = f"Today's Earthquake Report - {earthquake_report_date}"
earthquake_report_description = (
    f"**Total Earthquakes Today**: {len(earthquake_list)}\n"
    f"**Total Significant Earthquakes**: {len(earthquake_list)}\n\n"
    "Please find the details of significant earthquakes below:\n"
)

today_date = datetime.utcnow().strftime('%Y-%m-%d')
# Send the earthquake report to Discord]
discord_payload = {
    "content": f"🌍 **Today's Earthquake Report** 🌍\n\n"
                f"**Date**: {today_date} (Updated at {current_time})\n"
                f"**Total Significant Earthquakes Today**: {len(earthquake_list)}\n\n"
                f"🔴 **Highlights** 🔴\n\n"
                f"{earthquake_report_description}",
    "embeds": []
}
response = requests.post(discord_webhook, json=discord_payload)
if response.status_code == 204:
    print("Report sent successfully.")
else:
    print(f"Failed to send report: {response.status_code}, {response.text}")

# 6. Send the earthquake information to Discord
def send_to_discord(earthquake_description, explanation):
    discord_payload = {
        "content": earthquake_description,
        "embeds": [
            {
                "title": "Earthquake Explanation",
                "description": explanation,
                "color": 0xFF5733
            }
        ]
    }

    response = requests.post(discord_webhook, json=discord_payload)
    if response.status_code == 204:
        print("Message sent successfully.")
    else:
        print(f"Failed to send message: {response.status_code}, {response.text}")

# 7. Process each earthquake and send to Discord
for count, quake_info in enumerate(earthquake_list, start=1):
    earthquake_description = (
        f"===============================================\n"
        f"**Earthquake #{count} on {today_date}** 🌍\n\n"
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

    # Get the earthquake explanation from OpenAI
    explanation = get_earthquake_explanation(quake_info)

    # Send the earthquake information to Discord
    send_to_discord(earthquake_description, explanation)