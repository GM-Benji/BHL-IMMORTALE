import uvicorn
import random
import math
import os
import time
from collections import deque
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Optional, List

app = FastAPI()

if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

class SensorData(BaseModel):
    sensor_name: str
    api_key: str
    # Added coordinates so simulator can control geography
    lat: Optional[float] = None
    lng: Optional[float] = None

    carbon_dioxide: float
    temperature: float
    humidity: float
    soil_humidity: float
    voc_index: float = 0.0
    nox_index: float = 0.0
    pm1_0: float
    pm2_5: float
    pm10: float
    universal_aqi: Optional[int] = None
    timestamp: Optional[float] = None # Added timestamp for history

sensor_locations: Dict[str, Dict[str, float]] = {}
latest_readings: Dict[str, SensorData] = {}
# History storage: Map sensor_name -> Deque of last 30 readings
sensor_history: Dict[str, deque] = {}

# --- FALLBACK LOCATIONS (If sensor doesn't report its own) ---
GREEN_ZONES = [
    {"name": "Pole Mokotowskie (Main Lawn)", "lat": 52.2185, "lng": 21.0060, "radius": 0.0025},
    {"name": "Ogrod Saski", "lat": 52.2410, "lng": 21.0030, "radius": 0.0015},
    {"name": "Park Skaryszewski", "lat": 52.2425, "lng": 21.0540, "radius": 0.0020},
]

def generate_warsaw_location():
    """Generates a random coordinate strictly inside a green zone."""
    zone = random.choice(GREEN_ZONES)
    r = zone["radius"] * math.sqrt(random.random())
    theta = random.random() * 2 * math.pi
    return {
        "lat": zone["lat"] + r * math.cos(theta),
        "lng": zone["lng"] + r * math.sin(theta) * 1.6
    }

# --- AQI ALGORITHM ---
def map_value(x, in_min, in_max, out_min, out_max):
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

def calc_pm25_idx(pm):
    if pm <= 10.0:  return map_value(pm, 0, 10, 0, 50)
    if pm <= 25.0:  return map_value(pm, 10.1, 25, 51, 100)
    if pm <= 50.0:  return map_value(pm, 25.1, 50, 101, 150)
    if pm <= 75.0:  return map_value(pm, 50.1, 75, 151, 200)
    if pm <= 150.0: return map_value(pm, 75.1, 150, 201, 300)
    if pm > 150:    return 500
    return 0

def calc_pm10_idx(pm):
    if pm <= 20.0:  return map_value(pm, 0, 20, 0, 50)
    if pm <= 50.0:  return map_value(pm, 20.1, 50, 51, 100)
    if pm <= 80.0:  return map_value(pm, 50.1, 80, 101, 150)
    if pm <= 110.0: return map_value(pm, 80.1, 110, 151, 200)
    if pm <= 200.0: return map_value(pm, 110.1, 200, 201, 300)
    if pm > 200:    return 500
    return 0

def calculate_aqi(data: SensorData) -> int:
    i_pm25 = calc_pm25_idx(data.pm2_5)
    i_pm10 = calc_pm10_idx(data.pm10)
    i_voc = int(data.voc_index)
    i_nox = int(data.nox_index)
    return max(i_pm25, i_pm10, i_voc, i_nox)

# --- API ENDPOINTS ---

@app.post("/api/report")
async def report_pollution(data: SensorData):
    if data.api_key != "SECRET_KEY_123":
        raise HTTPException(status_code=403, detail="Invalid API Key")

    # 1. Location Handling
    if data.lat is not None and data.lng is not None:
        sensor_locations[data.sensor_name] = {"lat": data.lat, "lng": data.lng}
    elif data.sensor_name not in sensor_locations:
        sensor_locations[data.sensor_name] = generate_warsaw_location()
        print(f"New sensor (auto-located): {data.sensor_name}")

    # 2. Add Timestamp & Calculate AQI
    data.timestamp = time.time()
    data.universal_aqi = calculate_aqi(data)

    # 3. Store in Latest & History
    latest_readings[data.sensor_name] = data

    data.soil_humidity = (0 if data.soil_humidity > 2000 else 100 - data.soil_humidity / 2000 * 100)

    if data.sensor_name not in sensor_history:
        sensor_history[data.sensor_name] = deque(maxlen=30)
    sensor_history[data.sensor_name].append(data)

    return {"status": "success", "aqi": data.universal_aqi}

@app.get("/api/pollution-data")
async def get_pollution_map():
    response_data = []

    for name, location in sensor_locations.items():
        reading = latest_readings.get(name)
        if reading:
            response_data.append({
                "name": name,
                "lat": location["lat"],
                "lng": location["lng"],
                "aqi": reading.universal_aqi,
                "details": reading.dict()
            })

    return response_data

@app.get("/api/history/{sensor_name}")
async def get_sensor_history(sensor_name: str):
    """Returns the last 30 readings for a specific sensor."""
    if sensor_name not in sensor_history:
        return []
    return list(sensor_history[sensor_name])

@app.get("/")
async def read_root():
    return FileResponse("static/map.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
