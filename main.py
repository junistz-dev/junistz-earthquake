import requests
from datetime import datetime
import json
import openai
import os
from dotenv import load_dotenv

load_dotenv()
# ========== 날짜/시간 설정 ==========
# ✅ 디버깅용 하드코딩 (날짜, 시간)
# today_date = "2025-04-09"
# current_time_text = "00:00 UTC"
# today_start = datetime(2025, 4, 9, 0, 0, 0)
# today_end = datetime(2025, 4, 9, 23, 59, 59)

# 🟡 실시간 사용 시 아래 코드 사용 (현재는 주석처리)
current_time = datetime.utcnow()
today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
today_end = current_time
today_date = current_time.strftime('%Y-%m-%d')
current_time_text = current_time.strftime('%H:%M UTC')

# ========== 설정 ==========
url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson"
discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
openai_api_key = os.getenv("OPENAI_API_KEY")

# ========== 지진 데이터 불러오기 ==========
response = requests.get(url)
data = response.json()

# ========== 중요 지진 판별 함수 ==========
def is_significant_quake(quake):
    magnitude = quake.get("properties", {}).get("mag", 0)
    place = quake.get("properties", {}).get("place", "").lower()
    depth = quake.get("geometry", {}).get("coordinates", [None, None, 999])[2]
    alert = quake.get("properties", {}).get("alert", "green")
    felt = quake.get("properties", {}).get("felt", 0)
    time = quake.get("properties", {}).get("time", 0)
    time = datetime.utcfromtimestamp(time / 1000)

    is_sea = "sea" in place or "ocean" in place

    return (
        # 강도를 1 이상으로 설정하여 더 작은 지진도 포함
        magnitude >= 3 and
        # 깊이를 1000km 이하로 설정하여 더 깊은 지진도 포함
        depth <= 10 and
        # "city", "near", "km" 외에도 "sea"나 "ocean"도 포함하여 더 많은 지진을 포착
        ("city" in place or "near" in place or "km" in place or "sea" in place or "ocean" in place) and
        # 경고 수준을 "green"도 포함하여 더 많은 지진을 포착
        (alert in ["orange", "red", "green"] or (felt and felt > 0)) and
        # 오늘 날짜 범위 내에서 발생한 지진
        (today_start <= time <= today_end)
    ), time, is_sea

# ========== 중요 지진 필터링 ==========
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

def get_earthquake_explanation(data):
    try:
        openai.api_key = openai_api_key  # OpenAI API 키 설정

        # messages 형식으로 변경
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an earthquake expert with the ability to explain earthquake events in an easy-to-understand way for the general public. "
                    "You explain magnitude, depth, region, alert level, and any possible impact such as damage, aftershocks, or tsunamis."
                )
            },
            {
                "role": "user",
                "content": (
                    "### Earthquake Explanation Guidelines:\n"
                    "- Explain the earthquake's magnitude (e.g., 'This was a magnitude 7.5 earthquake, which is classified as major').\n"
                    "- Describe the depth and its relationship to potential damage.\n"
                    "- Mention the location and its vulnerability.\n"
                    "- Include risks of aftershocks or tsunamis if applicable.\n"
                    "- Distinguish between minor and major earthquakes in terms of safety/infrastructure risk.\n"
                    "- Optionally provide historical context.\n\n"

                    "### Earthquake Data:\n"
                    f"Location: {data['location']}\n"
                    f"Magnitude: {data['magnitude']}\n"
                    f"Depth: {data['depth']} km\n"
                    f"Time: {data['time']}\n"
                    f"Alert Level: {data['alert_level']}\n"
                    f"People Who Felt: {data['felt']}\n"
                    f"Region: {data['region']}\n\n"

                    "Please provide a clear, informative explanation in simple terms."
                )
            }
        ]

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=500
        )

        return response['choices'][0]['message']['content'].strip()

    except Exception as e:
        print(f"Error generating earthquake explanation: {e}")
        return "AI processing error, unable to provide explanation."
# ========== Discord 메시지 전송 함수 ==========
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

# ========== 결과 전송 ==========
if len(earthquake_list) == 0:
    discord_payload = {
        "content": f"🌍 **Today's Earthquake Report** 🌍\n\n"
                   f"**Date**: {today_date} (Updated at {current_time_text})\n\n"
                   f"✅ No earthquakes have been reported around the world today!  Enjoy a peaceful day! ☀️🌿"
    }
    response = requests.post(discord_webhook, json=discord_payload)
    if response.status_code == 204:
        print("No earthquake report sent successfully.")
    else:
        print(f"Failed to send no-earthquake report: {response.status_code}, {response.text}")
else:
    earthquake_report_description = (
        f"**Total Earthquakes Today**: {len(earthquake_list)}\n"
        f"**Total Significant Earthquakes**: {len(earthquake_list)}\n\n"
        "Please find the details of significant earthquakes below:\n"
    )

    discord_payload = {
        "content": f"🌍 **Today's Earthquake Report** 🌍\n\n"
                   f"**Date**: {today_date} (Updated at {current_time_text})\n"
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

    for count, quake_info in enumerate(earthquake_list, start=1):
        earthquake_description = (
            f"**Earthquake #{count} on {today_date}** 🌍\n\n"
            f"**Location**: {quake_info['location']}\n"
            f"**Magnitude**: {quake_info['magnitude']}\n"
            f"**Depth**: {quake_info['depth']} km\n"
            f"**Occurred at**: {quake_info['time']}\n"
            f"**Region**: {quake_info['region']}\n"
            f"**Alert Level**: {quake_info['alert_level']}\n"
            f"**Number of People Who Felt**: {quake_info['felt']} people\n\n"
            f"**Interactive Map**: [Click here]({quake_info['url']+'/map'})\n" 
            f"**More Info**: [Click here]({quake_info['url']})"
        )

        explanation = get_earthquake_explanation(quake_info)
        send_to_discord(earthquake_description, explanation)

 