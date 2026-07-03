import os
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, redirect
import requests

app = Flask(__name__)

# --------------------------------------------------------------------------
# Configuration & Constants
# --------------------------------------------------------------------------
# Replace with your actual OpenWeatherMap API key
OWM_API_KEY = os.environ.get("OWM_API_KEY", "b3413139f3a356b15d3853f7f8420dd8")

IP_GEOLOCATION_URL = "http://ip-api.com/json/"
OWM_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
OWM_AIR_QUALITY_URL = "https://api.openweathermap.org/data/2.5/air_pollution"

# --------------------------------------------------------------------------
# Helper Functions
# --------------------------------------------------------------------------
def get_aqi_status(aqi_score):
    levels = {
        1: ("Good", "text-green-400"),
        2: ("Fair", "text-yellow-400"),
        3: ("Moderate", "text-orange-400"),
        4: ("Poor", "text-red-400"),
        5: ("Very Poor", "text-purple-400")
    }
    return levels.get(aqi_score, ("Unknown", "text-gray-400"))

def format_timestamp(ts, fmt="%I:%M %p"):
    return datetime.fromtimestamp(ts).strftime(fmt).lstrip("0")

def weather_desc_to_emoji(cond_id):
    if not cond_id: return "❓"
    if cond_id == 800: return "☀️"
    if cond_id == 801: return "🌤️"
    if cond_id in [802, 803]: return "⛅"
    if cond_id == 804: return "☁️"
    if cond_id >= 200 and cond_id < 300: return "⛈️"
    if cond_id >= 300 and cond_id < 400: return "🌦️"
    if cond_id >= 500 and cond_id < 600: return "🌧️"
    if cond_id >= 600 and cond_id < 700: return "❄️"
    if cond_id >= 700 and cond_id < 800: return "🌫️"
    return "✨"

# --------------------------------------------------------------------------
# Web Routes
# --------------------------------------------------------------------------
@app.route("/")
def index():
    location_name = "Bhopal, Madhya Pradesh, India"
    lat, lon = 23.2599, 77.4126
    try:
        ip_res = requests.get(IP_GEOLOCATION_URL, timeout=5).json()
        if ip_res.get("status") == "success":
            location_name = f"{ip_res.get('city')}, {ip_res.get('regionName')}, {ip_res.get('country')}"
            lat, lon = ip_res.get("lat"), ip_res.get("lon")
    except Exception:
        pass

    weather_data = fetch_all_weather(lat, lon, location_name)
    return render_template_string(HTML_TEMPLATE, **weather_data)

@app.route("/search")
def search():
    city = request.args.get("city", "").strip()
    if not city:
        return redirect("/")
    try:
        params = {"q": city, "appid": OWM_API_KEY, "units": "metric"}
        res = requests.get(OWM_FORECAST_URL, params=params, timeout=5)
        if res.status_code != 200:
            return render_template_string(HTML_TEMPLATE, error=f"City '{city}' not found or API key invalid.")
        
        data = res.json()
        lat = data["city"]["coord"]["lat"]
        lon = data["city"]["coord"]["lon"]
        location_name = f"{data['city']['name']}, {data['city']['country']}"
        
        weather_data = fetch_all_weather(lat, lon, location_name)
        return render_template_string(HTML_TEMPLATE, **weather_data)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"An error occurred: {str(e)}")

def fetch_all_weather(lat, lon, location_name):
    try:
        f_params = {"lat": lat, "lon": lon, "appid": OWM_API_KEY, "units": "metric"}
        f_res = requests.get(OWM_FORECAST_URL, params=f_params, timeout=5).json()
        aq_params = {"lat": lat, "lon": lon, "appid": OWM_API_KEY}
        aq_res = requests.get(OWM_AIR_QUALITY_URL, params=aq_params, timeout=5).json()
    except Exception as e:
        return {"error": f"Failed to retrieve weather data: {str(e)}"}

    timeline = f_res.get("list", [])
    if not timeline:
        return {"error": "Weather data timeline is empty."}
        
    current_block = timeline[0]
    main_metrics = current_block.get("main", {})
    wind_metrics = current_block.get("wind", {})
    weather_desc = current_block.get("weather", [{}])[0]
    
    aqi_val = aq_res.get("list", [{}])[0].get("main", {}).get("aqi", 1)
    aqi_label, aqi_color_class = get_aqi_status(aqi_val)

    hourly_trend = []
    for block in timeline[:8]:
        hourly_trend.append({
            "time": format_timestamp(block["dt"], "%I %p"),
            "temp_c": round(block["main"]["temp"]),
            "temp_f": round((block["main"]["temp"] * 9/5) + 32),
            "icon": weather_desc_to_emoji(block["weather"][0].get("id")),
        })

    today_max, today_min = -999, 999
    tomorrow_max, tomorrow_min = -999, 999
    today_desc, tomorrow_desc = "", ""
    today_icon, tomorrow_icon = "☀️", "☀️"
    current_day = datetime.fromtimestamp(timeline[0]["dt"]).date()
    
    for block in timeline:
        block_date = datetime.fromtimestamp(block["dt"]).date()
        temp = block["main"]["temp"]
        desc = block["weather"][0].get("description", "Clear").title()
        icon = weather_desc_to_emoji(block["weather"][0].get("id"))
        
        if block_date == current_day:
            if temp > today_max: today_max = temp
            if temp < today_min: today_min = temp
            today_desc = desc
            today_icon = icon
        elif block_date == current_day.__class__(current_day.year, current_day.month, current_day.day + 1):
            if temp > tomorrow_max: tomorrow_max = temp
            if temp < tomorrow_min: tomorrow_min = temp
            tomorrow_desc = desc
            tomorrow_icon = icon

    return {
        "location": location_name,
        "updated_at": datetime.now().strftime("%I:%M:%S %p"),
        "current_temp_c": round(main_metrics.get("temp")),
        "current_temp_f": round((main_metrics.get("temp") * 9/5) + 32),
        "feels_like_c": round(main_metrics.get("feels_like")),
        "feels_like_f": round((main_metrics.get("feels_like") * 9/5) + 32),
        "condition": weather_desc.get("description", "N/A").title(),
        "emoji": weather_desc_to_emoji(weather_desc.get("id")),
        "humidity": main_metrics.get("humidity"),
        "wind_speed": round(wind_metrics.get("speed") * 3.6, 1),
        "aqi_text": f"{aqi_val} — {aqi_label}",
        "aqi_color": aqi_color_class,
        "sunrise": format_timestamp(f_res["city"]["sunrise"]),
        "sunset": format_timestamp(f_res["city"]["sunset"]),
        "hourly": hourly_trend,
        "today": {"max_c": round(today_max), "min_c": round(today_min), "max_f": round((today_max*9/5)+32), "min_f": round((today_min*9/5)+32), "desc": today_desc, "icon": today_icon},
        "tomorrow": {"max_c": round(tomorrow_max), "min_c": round(tomorrow_min), "max_f": round((tomorrow_max*9/5)+32), "min_f": round((tomorrow_min*9/5)+32), "desc": tomorrow_desc, "icon": tomorrow_icon}
    }

# --------------------------------------------------------------------------
# UI Template Layout (Tailwind Web Presentation)
# --------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real-Time Weather</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <style>
        body { background-color: #0f1729; color: #f5f7fa; font-family: 'Segoe UI', sans-serif; }
        .card { background-color: #1b2740; }
    </style>
</head>
<body class="min-h-screen flex flex-col items-center py-8 px-4">
    <div class="w-full max-w-3xl">
        <form action="/search" method="get" class="flex gap-2 mb-2">
            <input type="text" name="city" placeholder="Search for a city..." required
                   class="flex-1 px-4 py-3 rounded-lg bg-[#1b2740] border border-gray-700 focus:outline-none focus:border-[#4da6ff] text-white">
            <button type="submit" class="px-6 py-3 rounded-lg bg-[#4da6ff] text-slate-900 font-semibold hover:bg-sky-400 transition cursor-pointer">
                Search
            </button>
            <a href="/" class="px-4 py-3 rounded-lg border border-gray-700 flex items-center hover:bg-[#1b2740] transition text-sm">
                📍 My Location
            </a>
        </form>

        {% if error %}
            <div class="p-4 mb-4 rounded-lg bg-red-900/40 border border-red-700 text-red-200 text-sm">
                {{ error }}
            </div>
        {% endif %}

        {% if location %}
            <div class="text-[#9aa7c2] text-sm mb-4 px-1">📍 {{ location }}</div>
            <div class="card p-6 rounded-xl shadow-lg mb-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                <div>
                    <div class="text-5xl font-bold flex items-center gap-3">
                        <span>{{ emoji }}</span>
                        <span>{{ current_temp_c }}°C</span>
                        <span class="text-xl text-gray-400 font-normal">/ {{ current_temp_f }}°F</span>
                    </div>
                    <div class="text-[#9aa7c2] text-lg mt-1 font-medium">{{ condition }}</div>
                </div>
                <div class="w-full md:w-auto flex flex-col gap-2 border-t md:border-t-0 border-gray-700 pt-4 md:pt-0">
                    <div class="flex justify-between md:gap-12 text-sm"><span class="text-[#9aa7c2]">Feels like</span> <span class="font-semibold">{{ feels_like_c }}°C ({{ feels_like_f }}°F)</span></div>
                    <div class="flex justify-between md:gap-12 text-sm"><span class="text-[#9aa7c2]">Humidity</span> <span class="font-semibold">{{ humidity }}%</span></div>
                    <div class="flex justify-between md:gap-12 text-sm"><span class="text-[#9aa7c2]">Wind</span> <span class="font-semibold">{{ wind_speed }} km/h</span></div>
                    <div class="flex justify-between md:gap-12 text-sm"><span class="text-[#9aa7c2]">Air Quality (AQI)</span> <span class="font-bold {{ aqi_color }}">{{ aqi_text }}</span></div>
                </div>
            </div>

            <div class="grid grid-cols-2 gap-4 mb-6">
                <div class="card p-4 rounded-xl shadow flex flex-col">
                    <span class="text-[#9aa7c2] text-xs uppercase tracking-wider mb-1">🌅 Sunrise</span>
                    <span class="text-xl font-bold">{{ sunrise }}</span>
                </div>
                <div class="card p-4 rounded-xl shadow flex flex-col">
                    <span class="text-[#9aa7c2] text-xs uppercase tracking-wider mb-1">🌇 Sunset</span>
                    <span class="text-xl font-bold">{{ sunset }}</span>
                </div>
            </div>

            <div class="text-[#9aa7c2] text-sm mb-2 px-1 font-medium">Hourly Trend (3h Intervals)</div>
            <div class="grid grid-cols-4 sm:grid-cols-8 gap-2 mb-6">
                {% for hour in hourly %}
                <div class="card p-3 rounded-lg flex flex-col items-center text-center shadow">
                    <span class="text-[#9aa7c2] text-xs mb-1">{{ hour.time }}</span>
                    <span class="text-2xl my-1">{{ hour.icon }}</span>
                    <span class="text-sm font-bold">{{ hour.temp_c }}°C</span>
                </div>
                {% endfor %}
            </div>

            <div class="grid md:grid-cols-2 gap-4 mb-8">
                <div class="card p-5 rounded-xl shadow">
                    <div class="text-[#9aa7c2] text-sm font-bold mb-2">Today</div>
                    <div class="text-lg font-semibold flex items-center gap-2 mb-1">
                        <span>{{ today.icon }}</span> <span>{{ today.desc }}</span>
                    </div>
                    <div class="text-sm">
                        High <span class="font-semibold text-white">{{ today.max_c }}°C</span> &middot; Low <span class="font-semibold text-gray-300">{{ today.min_c }}°C</span>
                    </div>
                </div>
                <div class="card p-5 rounded-xl shadow">
                    <div class="text-[#9aa7c2] text-sm font-bold mb-2">Tomorrow</div>
                    <div class="text-lg font-semibold flex items-center gap-2 mb-1">
                        <span>{{ tomorrow.icon }}</span> <span>{{ tomorrow.desc }}</span>
                    </div>
                    <div class="text-sm">
                        High <span class="font-semibold text-white">{{ tomorrow.max_c }}°C</span> &middot; Low <span class="font-semibold text-gray-300">{{ tomorrow.min_c }}°C</span>
                    </div>
                </div>
            </div>

            <div class="flex justify-between items-center text-xs text-[#9aa7c2] px-1 border-t border-gray-800 pt-4">
                <span>Last updated: {{ updated_at }}</span>
                <a href="/" class="hover:text-white transition">🔄 Refresh</a>
            </div>
        {% endif %}
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, port=5000)